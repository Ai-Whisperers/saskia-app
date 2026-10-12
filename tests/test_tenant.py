"""Tests for app/rms/tenant.py — URL-based tenant resolution (SASKIA-220).

Covers the plan's Day-4 acceptance list:
- unknown host fails closed
- missing tenant file
- malformed YAML
- ${ENV_VAR} resolution (set + unset)
- engine caching (one engine per tenant)
- tenant routing disabled by default (back-compat)
- middleware behavior (annotates / 404s / no-op when disabled)
- no leakage between tenants (each host resolves its own config)
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import Request

from app.rms.tenant import (
    TenantLoadError,
    TenantResolutionMiddleware,
    UnknownTenantError,
    get_engine,
    registered_hosts,
    reset_caches,
    resolve_tenant,
    tenant_dir,
    tenant_routing_enabled,
)


@pytest.fixture(autouse=True)
def _clean_caches():
    reset_caches()
    yield
    reset_caches()


@pytest.fixture()
def tenant_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A tenant dir with one valid tenant + its DB URL in the env."""
    tdir = tmp_path / "tenants"
    tdir.mkdir()
    (tdir / "la-vaquita.sazon.app.yaml").write_text(
        "host: la-vaquita.sazon.app\n"
        "display_name: La Vaquita Holandesa\n"
        "locale: es_PY\n"
        "database_url: ${VAQUITA_DB_URL}\n"
        "branding:\n  primary_color: '#8B4513'\n"
    )
    monkeypatch.setenv("TENANT_DIR", str(tdir))
    monkeypatch.setenv("VAQUITA_DB_URL", "sqlite://")
    return tdir


# --- resolution ---


def test_resolve_known_host(tenant_env):
    t = resolve_tenant("la-vaquita.sazon.app")
    assert t.host == "la-vaquita.sazon.app"
    assert t.display_name == "La Vaquita Holandesa"
    assert t.database_url == "sqlite://"
    assert t.branding["primary_color"] == "#8B4513"


def test_resolve_normalizes_host_port_and_case(tenant_env):
    t = resolve_tenant("LA-VAQUITA.SAZON.APP:8443")
    assert t.host == "la-vaquita.sazon.app"


def test_unknown_host_fails_closed(tenant_env):
    with pytest.raises(UnknownTenantError):
        resolve_tenant("evil.example.com")


def test_empty_host_fails_closed(tenant_env):
    with pytest.raises(UnknownTenantError):
        resolve_tenant("")


def test_missing_tenant_file(tenant_env):
    # A host whose yaml does not exist -> unknown, not a load error.
    with pytest.raises(UnknownTenantError):
        resolve_tenant("nope.sazon.app")


def test_malformed_yaml(tenant_env, monkeypatch):
    (tenant_dir() / "broken.sazon.app.yaml").write_text("host: [unclosed")
    with pytest.raises(TenantLoadError):
        resolve_tenant("broken.sazon.app")


def test_missing_host_key(tenant_env):
    (tenant_dir() / "nohost.sazon.app.yaml").write_text("display_name: X")
    with pytest.raises(TenantLoadError):
        resolve_tenant("nohost.sazon.app")


def test_missing_database_url_key(tenant_env):
    (tenant_dir() / "nourl.sazon.app.yaml").write_text("host: nourl.sazon.app")
    with pytest.raises(TenantLoadError):
        resolve_tenant("nourl.sazon.app")


# --- ${ENV_VAR} resolution ---


def test_env_var_url_resolved(tenant_env):
    assert resolve_tenant("la-vaquita.sazon.app").database_url == "sqlite://"


def test_unset_env_var_fails_closed(tenant_env, monkeypatch):
    monkeypatch.delenv("VAQUITA_DB_URL", raising=False)
    with pytest.raises(TenantLoadError):
        resolve_tenant("la-vaquita.sazon.app")


def test_literal_url_passthrough(tmp_path, monkeypatch):
    tdir = tmp_path / "t2"
    tdir.mkdir()
    (tdir / "lit.example.yaml").write_text(
        "host: lit.example\ndatabase_url: sqlite:///tmp/lit.sqlite\n"
    )
    monkeypatch.setenv("TENANT_DIR", str(tdir))
    assert resolve_tenant("lit.example").database_url == "sqlite:///tmp/lit.sqlite"


# --- engine cache ---


def test_engine_cached_per_tenant(tenant_env):
    t = resolve_tenant("la-vaquita.sazon.app")
    e1 = get_engine(t)
    e2 = get_engine(t)
    assert e1 is e2


# --- routing enabled flag ---


def test_routing_disabled_when_no_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("TENANT_DIR", str(tmp_path / "does-not-exist"))
    assert tenant_routing_enabled() is False


def test_routing_disabled_when_dir_empty(tmp_path, monkeypatch):
    tdir = tmp_path / "empty"
    tdir.mkdir()
    monkeypatch.setenv("TENANT_DIR", str(tdir))
    assert tenant_routing_enabled() is False


def test_routing_enabled_with_yaml(tenant_env):
    assert tenant_routing_enabled() is True
    assert registered_hosts() == ["la-vaquita.sazon.app"]


def test_no_leakage_between_tenants(tmp_path, monkeypatch):
    tdir = tmp_path / "t3"
    tdir.mkdir()
    (tdir / "a.example.yaml").write_text("host: a.example\ndatabase_url: sqlite:///tmp/a.sqlite\n")
    (tdir / "b.example.yaml").write_text("host: b.example\ndatabase_url: sqlite:///tmp/b.sqlite\n")
    monkeypatch.setenv("TENANT_DIR", str(tdir))
    assert resolve_tenant("a.example").database_url.endswith("/a.sqlite")
    assert resolve_tenant("b.example").database_url.endswith("/b.sqlite")


# --- middleware ---


def _mk_app():
    from fastapi import FastAPI

    app = FastAPI()
    app.add_middleware(TenantResolutionMiddleware)

    @app.get("/whoami")
    def whoami(request: Request):  # pragma: no cover - trivial
        t = getattr(request.state, "tenant", None)
        return {"tenant": t.host if t else None}

    return app


def test_middleware_annotates_tenant(tenant_env):
    from fastapi.testclient import TestClient

    client = TestClient(_mk_app())
    r = client.get("/whoami", headers={"host": "la-vaquita.sazon.app"})
    assert r.status_code == 200
    assert r.json()["tenant"] == "la-vaquita.sazon.app"


def test_middleware_404_unknown_host(tenant_env):
    from fastapi.testclient import TestClient

    client = TestClient(_mk_app())
    r = client.get("/whoami", headers={"host": "evil.example.com"})
    assert r.status_code == 404


def test_middleware_noop_when_disabled(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("TENANT_DIR", str(tmp_path / "none"))
    client = TestClient(_mk_app())
    r = client.get("/whoami", headers={"host": "anything.example.com"})
    assert r.status_code == 200
    assert r.json()["tenant"] is None
