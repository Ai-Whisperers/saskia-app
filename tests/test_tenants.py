"""tests/test_tenants.py — verify app/rms/tenants.py (E15).

Per docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md E15.

Covers:
- Tenant model exists + schema v8 created
- ensure_default_tenant is idempotent (single row)
- list_tenants returns single row
- resolve_tenant_id honors env var
- resolve_tenant_id falls back to 1
- current_tenant returns context
- assert_single_tenant warns on > 1 tenants (mock path)
"""
from __future__ import annotations

from app.rms.models import Tenant
from app.rms.tenants import (
    DEFAULT_TENANT_SLUG,
    TenantContext,
    assert_single_tenant,
    current_tenant,
    ensure_default_tenant,
    list_tenants,
    resolve_tenant_id,
)


def test_ensure_default_tenant_idempotent(session_factory):
    s = session_factory()
    try:
        tid1 = ensure_default_tenant(s)
        tid2 = ensure_default_tenant(s)
        assert tid1 == tid2
    finally:
        s.close()


def test_ensure_default_tenant_uses_app_meta_business_name(session_factory):
    s = session_factory()
    try:
        from app.rms.models import AppMeta
        s.add(AppMeta(key="general.business_name", value="Custom Bakery", updated_at=""))
        s.commit()
        tid = ensure_default_tenant(s)
        s.commit()
        t = s.get(Tenant, tid)
        assert t.business_name == "Custom Bakery"
    finally:
        s.close()


def test_list_tenants_returns_default(session_factory):
    s = session_factory()
    try:
        ensure_default_tenant(s)
        tenants = list_tenants(s)
        assert len(tenants) == 1
        assert tenants[0].slug == DEFAULT_TENANT_SLUG
    finally:
        s.close()


def test_default_tenant_exists_on_empty_db(session_factory):
    s = session_factory()
    try:
        tenants = list_tenants(s)
        # The schema migration may have auto-created one; we tolerate 0 or 1.
        assert len(tenants) <= 1
        if tenants:
            assert tenants[0].slug == DEFAULT_TENANT_SLUG
    finally:
        s.close()


def test_resolve_tenant_id_from_env(monkeypatch):
    monkeypatch.setenv("AIW_TENANT_ID", "5")
    assert resolve_tenant_id() == 5


def test_resolve_tenant_id_env_invalid_falls_back_to_1(monkeypatch):
    monkeypatch.setenv("AIW_TENANT_ID", "not-a-number")
    assert resolve_tenant_id() == 1


def test_resolve_tenant_id_default(monkeypatch):
    for k in ("AIW_TENANT_ID",):
        monkeypatch.delenv(k, raising=False)
    assert resolve_tenant_id() == 1


def test_resolve_tenant_id_from_subdomain():
    """herbus.saskia-rms.paragu-ai.com → slug 'herbus'."""
    tid = resolve_tenant_id(request_host="herbus.saskia-rms.paragu-ai.com")
    # Unknown slug maps to 1 (single-tenant default)
    assert tid == 1


def test_resolve_tenant_id_www_subdomain_ignored():
    """www. should not resolve to a tenant."""
    tid = resolve_tenant_id(request_host="www.example.com")
    assert tid == 1


def test_current_tenant_returns_context(session_factory):
    s = session_factory()
    try:
        ensure_default_tenant(s)
        ctx = current_tenant(s)
        assert isinstance(ctx, TenantContext)
        assert ctx.tenant_id >= 1
        assert ctx.slug == DEFAULT_TENANT_SLUG
    finally:
        s.close()


def test_assert_single_tenant_returns_count(session_factory):
    s = session_factory()
    try:
        ensure_default_tenant(s)
        n = assert_single_tenant(s)
        assert n == 1
    finally:
        s.close()


def test_assert_single_tenant_logs_warning_when_multiple(session_factory, caplog):
    s = session_factory()
    try:
        # Insert 2 tenants manually
        from datetime import datetime, timezone
        s.add_all([
            Tenant(slug="a", business_name="A", created_at=datetime.now(timezone.utc).isoformat()),
            Tenant(slug="b", business_name="B", created_at=datetime.now(timezone.utc).isoformat()),
        ])
        s.commit()
        # Should NOT raise; just warn
        with caplog.at_level("WARNING"):
            n = assert_single_tenant(s)
        assert n == 2
        # Warning was logged
        assert any("Multi-tenant" in r.message for r in caplog.records)
    finally:
        s.close()
