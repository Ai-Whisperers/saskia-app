"""Tests for app/rms/tenant.py — URL-based tenant resolution (SASKIA-220).

Covers the plan's Day-4 acceptance list:
- unknown host fails closed
- missing tenant file
- malformed YAML
- ${ENV_VAR} substitution
- fallback to single-tenant mode
- opt-in activation

Verifies middleware propagation and state.tenant attachment.
"""
import pytest
import os
import tempfile
import pathlib
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# tenant module
import app.rms.tenant as tenant_mod
from app.rms.tenant import TenantConfig, TenantResolutionMiddleware

# --- Test Utilities ---
def _mk_app(tenant_routing=True):
    """Factory to create a minimal test app with/without tenant middleware."""
    app = FastAPI()

    if tenant_routing:
        app.add_middleware(TenantResolutionMiddleware)

    @app.get("/whoami")
    def whoami(request: Request):  # pragma: no cover - trivial
        t = getattr(request.state, "tenant", None)
        return {"tenant": t.host if t else None}

    @app.get("/healthz")
    def healthz():  # pragma: no cover
        return {"status": "ok"}

    return app

@pytest.fixture(autouse=True)
def tenant_env():
    """Temporarily use a test tenants/ directory for tests."""
    with tempfile.TemporaryDirectory() as td:
        tdir = pathlib.Path(td) / "tenants"
        tdir.mkdir()
        os.environ["TENANT_DIR"] = str(tdir)

        # Start empty
        tenant_mod._cache.clear()
        yield tdir

# --- Core Discovery Tests ---
def test_no_tenants_directory():
    """No tenant dir registered, no hosts found."""
    tenant_mod._cache.clear()
    hosts = tenant_mod.scan_tenants(base_dir="/nonexistent")
    assert hosts == []

def test_scan_tenants_empty_yaml(tenant_env):
    """Empty YAML file safely skipped."""
    (tenant_env / "test.yaml").write_text("")
    tenant_mod._cache.clear()
    hosts = tenant_mod.update_cache()
    assert hosts == []

def test_scan_tenants_valid(tenant_env):
    """One valid tenant."""
    cfg = """
host: test.sazon.app
display_name: Test Bakery
locale: es_PY
database_url: sqlite:///test.db
"""
    (tenant_env / "test.yaml").write_text(cfg)
    tenant_mod._cache.clear()
    hosts = tenant_mod.update_cache()
    assert hosts == ["test.sazon.app"]
    assert "test.sazon.app" in tenant_mod._cache
    tcfg = tenant_mod._cache["test.sazon.app"]
    assert tcfg.host == "test.sazon.app"
    assert tcfg.display_name == "Test Bakery"
    assert tcfg.locale == "es_PY"

def test_scan_tenants_malformed(tenant_env):
    """Malformed YAML skipped safely."""
    (tenant_env / "bad.yaml").write_text("host: [bad_yaml}")
    tenant_mod._cache.clear()
    # Error logged but doesn't crash
    hosts = tenant_mod.update_cache()
    assert hosts == []

# --- Middleware Integration Tests ---
def test_no_tenants_fallback(tenant_env):
    """No tenants found → normal fallback (single-tenant mode)."""
    (tenant_env / "empty.yaml").write_text("# empty")  # triggers scan but no host
    tenant_mod._cache.clear()
    tenant_mod.update_cache()

    app = _mk_app()
    client = TestClient(app)

    # Host header ignored, tenant state is None
    r = client.get("/whoami", headers={"host": "unknown.com"})
    assert r.status_code == 200
    assert r.json() == {"tenant": None}

def test_middleware_annotates_tenant(tenant_env):
    """Known host gets attached to request.state.tenant."""
    os.environ["TEST_DB_URL"] = "sqlite:///test.db"
    cfg = """
host: test.sazon.app
display_name: Test Bakery
locale: es_PY
database_url: ${TEST_DB_URL}
"""
    (tenant_env / "test.yaml").write_text(cfg)
    tenant_mod._cache.clear()
    tenant_mod.update_cache()

    app = _mk_app()
    client = TestClient(app)

    # Known host: tenant resolved and attached
    r = client.get("/whoami", headers={"host": "test.sazon.app"})
    assert r.status_code == 200
    assert r.json() == {"tenant": "test.sazon.app"}

    # Unknown host: 404 (fail-closed)
    r = client.get("/whoami", headers={"host": "unknown.example"})
    assert r.status_code == 404
    assert r.json() == {"error": "Tenant not registered"}

def test_middleware_unknown_host_error(tenant_env):
    """No tenant config → fails closed (404) for unknown hosts."""
    # Empty tenant dir → no registered hosts
    (tenant_env / "empty.yaml").write_text("")
    tenant_mod._cache.clear()
    tenant_mod.update_cache()

    app = _mk_app()
    client = TestClient(app)

    # Unknown host: 404 even if no tenant route
    r = client.get("/whoami", headers={"host": "unknown.example"})
    assert r.status_code == 404
    assert r.json() == {"error": "Tenant not registered"}

# --- Substitution Tests ---
def test_env_var_substitution(tenant_env):
    """${VAR} substitution works."""
    os.environ["VAQUITA_DB"] = "postgres://user:pass@localhost/la-vaquita"
    cfg = """
host: vaquita.sazon.app
display_name: La Vaquita
database_url: ${VAQUITA_DB}
"""
    (tenant_env / "vaquita.yaml").write_text(cfg)
    tenant_mod._cache.clear()
    tenant_mod.update_cache()

    # Check substitution
    tcfg = tenant_mod._cache["vaquita.sazon.app"]
    assert tcfg.database_url == "postgres://user:pass@localhost/la-vaquita"

def test_substitution_missing_var(tenant_env):
    """Missing VAR → literal string preserved."""
    cfg = """
host: bakery.sazon.app
display_url: ${MISSING_URL}
"""
    (tenant_env / "bakery.yaml").write_text(cfg)
    tenant_mod._cache.clear()
    tenant_mod.update_cache()

    tcfg = tenant_mod._cache["bakery.sazon.app"]
    assert tcfg.database_url == "${MISSING_URL}"

# --- API Utility Tests ---
def test_get_tenant_host(tenant_env):
    """API: get_tenant_host(request) from state."""
    os.environ["TEST_DB"] = "sqlite:///test.db"
    cfg = """
host: test.sazon.app
database_url: ${TEST_DB}
"""
    (tenant_env / "test.yaml").write_text(cfg)
    tenant_mod._cache.clear()
    tenant_mod.update_cache()

    app = _mk_app()
    client = TestClient(app)

    # Attach to test request
    r = client.get("/whoami", headers={"host": "test.sazon.app"})
    t = tenant_mod.get_tenant_host(r.request)
    assert t is not None
    assert t.host == "test.sazon.app"

def test_get_tenant_display_name(tenant_env):
    """API: get_tenant_display_name(request)."""
    cfg = """
host: bakery.sazon.app
display_name: Mi Panadería
"""
    (tenant_env / "bakery.yaml").write_text(cfg)
    tenant_mod._cache.clear()
    tenant_mod.update_cache()

    app = _mk_app()
    client = TestClient(app)

    r = client.get("/whoami", headers={"host": "bakery.sazon.app"})
    d = tenant_mod.get_tenant_display_name(r.request)
    assert d == "Mi Panadería"

def test_get_tenant_locale(tenant_env):
    """API: get_tenant_locale(request)."""
    cfg = """
host: bakery.sazon.app
locale: es_PY
"""
    (tenant_env / "bakery.yaml").write_text(cfg)
    tenant_mod._cache.clear()
    tenant_mod.update_cache()

    app = _mk_app()
    client = TestClient(app)

    r = client.get("/whoami", headers={"host": "bakery.sazon.app"})
    l = tenant_mod.get_tenant_locale(r.request)
    assert l == "es_PY"

def test_get_tenant_db_url(tenant_env):
    """API: get_tenant_db_url(request) with substitution."""
    os.environ["VAQUITA_URL"] = "sqlite:///la-vaquita.db"
    cfg = """
host: vaquita.sazon.app
database_url: ${VAQUITA_URL}
"""
    (tenant_env / "vaquita.yaml").write_text(cfg)
    tenant_mod._cache.clear()
    tenant_mod.update_cache()

    app = _mk_app()
    client = TestClient(app)

    r = client.get("/whoami", headers={"host": "vaquita.sazon.app"})
    db_url = tenant_mod.get_tenant_db_url(r.request)
    assert db_url == "sqlite:///la-vaquita.db"

# --- Factory Integration ---
def test_tenant_middleware_no_tenants(tenant_env):
    """No tenant YAML → empty middleware list."""
    (tenant_env / "empty.yaml").write_text("")
    tenant_mod._cache.clear()
    tenant_mod.update_cache()
    assert tenant_mod.tenant_middleware() == []

def test_tenant_middleware_with_tenants(tenant_env):
    """With tenants → middleware returned."""
    cfg = """
host: test.sazon.app
database_url: sqlite:///test.db
"""
    (tenant_env / "test.yaml").write_text(cfg)
    tenant_mod._cache.clear()
    tenant_mod.update_cache()
    ms = tenant_mod.tenant_middleware()
    assert len(ms) == 1
    assert ms[0].cls == TenantResolutionMiddleware

# --- Smoke Test ---
def test_middleware_non_conflict(tenant_env):
    """Ensure tenant middleware doesn't interfere with FastAPI defaults."""
    cfg = """
host: test.sazon.app
display_name: Test Bakery
database_url: sqlite:///test.db
"""
    (tenant_env / "test.yaml").write_text(cfg)
    tenant_mod._cache.clear()
    tenant_mod.update_cache()

    app = _mk_app()
    client = TestClient(app)

    # Ensure regular FastAPI routes work with tenant middleware
    r = client.get("/healthz", headers={"host": "test.sazon.app"})
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

    r = client.get("/healthz", headers={"host": "unknown.com"})
    assert r.status_code == 200  # healthz works even with 404 middleware
    assert r.json() == {"status": "ok"}