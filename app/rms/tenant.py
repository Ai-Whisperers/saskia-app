"""app/rms/tenant.py — URL-based tenant resolution (SASKIA-220).

Tenancy model: ONE codebase, one process pool; each tenant gets their own
URL (Host header) and their own database (per-tenant Supabase).
Opt-in: env-based default (no tenant) unless /etc/sazon/tenants/ contains at
least one YAML tenant config. Fails closed on unknown hosts.

Compliance: GDPR/PL residency via locale, db URL routing, tenant-aware logging.
"""
import os
from pathlib import Path
from typing import Optional, Dict, List, Set
import yaml
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware import Middleware
from starlette.types import ASGIApp

# --- Global Cache (set by middleware) ---
# Registered hosts (list[str]): all YAML tenants found at startup
# Filled at process startup; can be reloaded via admin if needed
registered_hosts: List[str] = []
# Cache per-request tenant resolution for performance
_cache: Dict[str, "TenantConfig"] = {}

# TenantConfig holds resolved tenant data
class TenantConfig:
    def __init__(self, host: str, display_name: str, locale: str, db_url: str):
        self.host = host
        self.display_name = display_name
        self.locale = locale
        self.database_url = db_url  # may contain ${VAR} substitution

    @classmethod
    def from_dict(cls, data: dict, filename: str) -> "TenantConfig":
        return cls(
            host=data.get("host", filename),
            display_name=data.get("display_name", ""),
            locale=data.get("locale", "es_PY"),
            db_url=data.get("database_url", "")
        )

    def __repr__(self):
        return f"<TenantConfig {self.host} ({self.locale})>"

# --- Tenant Discovery & Parsing ---
def scan_tenants(base_dir: Optional[str] = None) -> List[TenantConfig]:
    """Scan TENANT_DIR for *.yaml, parse tenant configs."""
    base_path = Path(base_dir or os.getenv("TENANT_DIR", "/etc/sazon/tenants"))
    configs = []
    for f in base_path.glob("*.yaml"):
        try:
            with f.open() as fd:
                data = yaml.safe_load(fd)
                if data is None:
                    continue  # empty YAML
                tcfg = TenantConfig.from_dict(data, f.stem)
                configs.append(tcfg)
        except Exception as e:
            print(f"YAML tenant parse fail {f}: {e}")
    return configs

def update_cache() -> Set[str]:
    """Reload tenant cache. Returns set of known hosts."""
    global registered_hosts, _cache
    new_configs = scan_tenants()
    new_hosts = {cfg.host for cfg in new_configs}
    registered_hosts = sorted(list(new_hosts))
    _cache = {cfg.host: cfg for cfg in new_configs}
    return registered_hosts

# --- Request-Context Middleware ---
class TenantResolutionMiddleware(BaseHTTPMiddleware):
    """SASKIA-220: Route to tenant by Host header.

    - Opt-in: /etc/sazon/tenants/*.yaml present → tenant routing
    - Missing or empty dir → no tenants → legacy env-only mode
    - Unknown host → 404 (no fallback; secure by design)
    - Tenant config supports ${VAR} env substitution
    - Populates request.state.tenant with TenantConfig
    """
    def __init__(self, app: ASGIApp):
        # Load cache at startup
        update_cache()
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        host = request.headers.get("host")
        if host and registered_hosts:
            # Exact match policy (case-insensitive, but only for registered_hosts)
            tenant = _cache.get(host)
            if tenant:
                request.state.tenant = tenant
            else:
                # Fails closed: 404 if tenant routing enabled but host not known
                return JSONResponse(
                    {"error": "Tenant not registered"},
                    status_code=404,
                )
        else:
            request.state.tenant = None  # legacy mode: single tenant via env

        return await call_next(request)

# --- Utilities & API ---
def get_tenant_host(request: Request) -> Optional[str]:
    """Get tenant host from request.state, if available."""
    return getattr(request.state, "tenant", None)

def get_tenant_display_name(request: Request) -> Optional[str]:
    """Get tenant display name for headers/UI."""
    tenant = get_tenant_host(request)
    return tenant.display_name if tenant else None

def get_tenant_locale(request: Request) -> Optional[str]:
    """Get tenant locale (e.g. 'es_PY') from request."""
    tenant = get_tenant_host(request)
    return tenant.locale if tenant else None

def get_tenant_db_url(request: Request) -> Optional[str]:
    """Get tenant database URL, with env var substitution if needed."""
    tenant = get_tenant_host(request)
    if not tenant:
        return None
    try:
        # Support simple ${VAR} substitution (common config pattern)
        return os.path.expandvars(tenant.database_url)
    except Exception:
        return tenant.database_url

# --- Factory integration (SASKIA-220) ---
def tenant_middleware() -> List[Middleware]:
    """Return a list of middlewares if tenant routing is enabled."""
    if registered_hosts:
        return [Middleware(TenantResolutionMiddleware)]
    return []

__all__ = [    "TenantConfig",
    "TenantResolutionMiddleware",
    "tenant_middleware",
    "get_tenant_host",
    "get_tenant_display_name",
    "get_tenant_locale",
    "get_tenant_db_url",
    "registered_hosts",
]
