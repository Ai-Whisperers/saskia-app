"""app/rms/tenant.py — URL-based tenant resolution (SASKIA-220).

Tenancy model: ONE codebase, one process pool; each tenant gets their own
URL (Host header) and their own database (per-tenant Supabase project or
SQLite file). The Host header of an incoming request is the routing key.

Resolution order per request:
1. If tenant routing is DISABLED (no tenant dir on disk, see
   ``tenant_routing_enabled()``), every request is the implicit default
   tenant and the DB comes from the existing env-driven path
   (``app.rms.db_dialect.get_database_url()``). This preserves today's
   single-tenant behavior exactly — local dev, tests, and the current
   saskia-vps deployment are unaffected.
2. If tenant routing is ENABLED, the request's Host header (minus port)
   must match a ``<host>.yaml`` file in the tenant dir. Unknown host →
   404 (fail closed). Never guess, never fall through to another tenant.

Tenant YAML format (see tenants/example.yaml in the repo):
    host: la-vaquita.sazon.app
    display_name: "La Vaquita Holandesa"
    locale: es_PY
    database_url: ${SUPABASE_DB_URL_VAQUITA}   # env var reference, or literal

``database_url`` values that start with ``${`` and end with ``}`` are
resolved from the environment at load time (never stored literally in the
YAML, so tenant files can be backed up without credential scrubbing).
A missing referenced env var is a load error — fail closed, not silently
fall back to the default DB.

Engine caching: one SQLAlchemy Engine per tenant per process, created via
``app.rms.db_dialect.make_engine`` (dialect-aware: SQLite pragmas vs
Postgres pool settings). Engines are never closed at runtime; the cache
key is the tenant host.

This module deliberately does NOT touch sessions or the ``get_session``
dependency — the middleware in ``main.py`` only annotates
``request.state.tenant``; the DB session wiring stays as-is for v1
(single-process, one engine per runtime in practice). The per-request
engine *selection* is exposed via ``get_engine_for_request`` for the
Day-5 Supabase cutover.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from sqlalchemy.engine import Engine

from app.rms.db_dialect import make_engine

# Where tenant YAML files live in production. Override for tests via
# the TENANT_DIR env var.
DEFAULT_TENANT_DIR = Path("/etc/sazon/tenants")

_TENANT_DIR_ENV = "TENANT_DIR"

_lock = threading.Lock()
_tenant_cache: dict[str, "TenantConfig"] = {}
_engine_cache: dict[str, Engine] = {}


@dataclass(frozen=True)
class TenantConfig:
    """One tenant = one host + one database. Loaded from <host>.yaml."""

    host: str
    display_name: str
    locale: str = "es_PY"
    database_url: str = ""  # resolved (literal) URL — never an env ref
    branding: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.host:
            raise ValueError("tenant host must not be empty")
        if not self.database_url:
            raise ValueError(f"tenant {self.host!r} has no database_url")


def tenant_dir() -> Path:
    """Tenant config directory (TENANT_DIR env overrides the default)."""
    return Path(os.environ.get(_TENANT_DIR_ENV) or DEFAULT_TENANT_DIR)


def tenant_routing_enabled() -> bool:
    """True when tenant routing is active.

    Tenant routing is opt-in: it requires the tenant dir to exist AND
    contain at least one *.yaml file. An empty or missing dir means
    single-tenant mode (today's behavior).
    """
    d = tenant_dir()
    return d.is_dir() and any(d.glob("*.yaml"))


def _resolve_url(raw: str, host: str) -> str:
    """Resolve ``${ENV_VAR}`` references in database_url. Fail closed."""
    raw = raw.strip()
    if raw.startswith("${") and raw.endswith("}"):
        env_name = raw[2:-1].strip()
        value = os.environ.get(env_name, "").strip()
        if not value:
            raise TenantLoadError(
                f"tenant {host!r}: database_url references env var {env_name!r} which is not set"
            )
        return value
    return raw


class TenantLoadError(Exception):
    """Tenant YAML missing, malformed, or references an unset env var."""


class UnknownTenantError(Exception):
    """No tenant is registered for the request's Host header."""


def _load_tenant(path: Path) -> TenantConfig:
    try:
        data = yaml.safe_load(path.read_text())
    except OSError as e:
        raise TenantLoadError(f"cannot read tenant file {path}: {e}") from e
    except yaml.YAMLError as e:
        raise TenantLoadError(f"malformed YAML in {path}: {e}") from e
    if not isinstance(data, dict):
        raise TenantLoadError(f"tenant file {path} must be a YAML mapping")
    host = str(data.get("host", "")).strip().lower()
    if not host:
        raise TenantLoadError(f"tenant file {path} is missing 'host'")
    raw_url = str(data.get("database_url", "")).strip()
    if not raw_url:
        raise TenantLoadError(f"tenant file {path} is missing 'database_url'")
    return TenantConfig(
        host=host,
        display_name=str(data.get("display_name", host)),
        locale=str(data.get("locale", "es_PY")),
        database_url=_resolve_url(raw_url, host),
        branding=dict(data.get("branding") or {}),
    )


def resolve_tenant(host: str) -> TenantConfig:
    """Host header → TenantConfig. Raises UnknownTenantError (fail closed).

    The host is normalized (lowercased, port stripped). Cached per process.
    """
    normalized = (host or "").split(":", 1)[0].strip().lower()
    if not normalized:
        raise UnknownTenantError("empty Host header")
    with _lock:
        if normalized in _tenant_cache:
            return _tenant_cache[normalized]
    path = tenant_dir() / f"{normalized}.yaml"
    if not path.is_file():
        raise UnknownTenantError(f"no tenant registered for host {normalized!r}")
    tenant = _load_tenant(path)
    with _lock:
        _tenant_cache[normalized] = tenant
    return tenant


def get_engine(tenant: TenantConfig) -> Engine:
    """Cached SQLAlchemy engine for a tenant (one per tenant per process)."""
    with _lock:
        eng = _engine_cache.get(tenant.host)
        if eng is not None:
            return eng
    eng = make_engine(tenant.database_url)
    with _lock:
        # Another thread may have won the race; keep the first engine.
        return _engine_cache.setdefault(tenant.host, eng)


def registered_hosts() -> list[str]:
    """Sorted list of tenant hosts on disk (for startup logging)."""
    d = tenant_dir()
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.yaml"))


def reset_caches() -> None:
    """Test helper: clear tenant + engine caches."""
    with _lock:
        _tenant_cache.clear()
        _engine_cache.clear()


from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class TenantResolutionMiddleware(BaseHTTPMiddleware):
    """Resolve request Host -> tenant, annotate request.state.tenant.

    Opt-in: when tenant routing is disabled (no tenant dir), this is a
    no-op and the app behaves exactly as before (single-tenant).
    When enabled, an unknown Host fails closed with 404.
    """

    async def dispatch(self, request: Request, call_next):
        if not tenant_routing_enabled():
            return await call_next(request)
        try:
            request.state.tenant = resolve_tenant(request.headers.get("host", ""))
        except UnknownTenantError:
            return JSONResponse({"detail": "unknown tenant host"}, status_code=404)
        except TenantLoadError:
            return JSONResponse({"detail": "tenant configuration error"}, status_code=500)
        return await call_next(request)


__all__ = [
    "DEFAULT_TENANT_DIR",
    "TenantConfig",
    "TenantLoadError",
    "TenantResolutionMiddleware",
    "UnknownTenantError",
    "get_engine",
    "registered_hosts",
    "reset_caches",
    "resolve_tenant",
    "tenant_dir",
    "tenant_routing_enabled",
]
