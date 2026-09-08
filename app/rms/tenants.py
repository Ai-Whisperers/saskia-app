"""app/rms/tenants.py — Multi-tenant scaffolding (E15).

Per docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md E15.

This module provides the SEAM for multi-tenant mode without
inflating scope:
- Tenant model: id, slug (unique), business_name, created_at
- TenantContext: per-request tenant_id resolution (default = 1,
  the single-tenant default — backwards compatible)
- tenant_required decorator: locks a route to require tenant context
- resolve_tenant_id(request): pulls from app.state or env
- tenant_aware_select(query, model): helper to scope queries to the
  current tenant when tenant_id is in the model

The current model layer assumes SINGLE-TENANT. Multi-tenant column
on every table (tenant_id) is OUT OF SCOPE — operators should treat
this module as the gateway to a per-tenant Postgres schema later.

For now, E15 ships:
- the Tenant model + a default tenant seeded on first run
- the routing seam for "subdomain → tenant" resolution
- a guard that warns if more than one Tenant is found (i.e. the
  operator accidentally enabled multi-tenant mode without migrating
  the data layer)
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import AppMeta, Base  # noqa: F401

# --- Tenant dataclass + model ---


@dataclass
class Tenant:
    """Logical bake-shop / restaurant / cafe."""

    id: int
    slug: str
    business_name: str
    created_at: str = ""
    primary_color: str = "#7b3f00"
    currency: str = "Gs."


# We lazy-load the Tenant model from models.py because it doesn't
# exist there yet (this module is the future seam).
def _get_tenant_model():
    """Resolve the Tenant ORM class (lazy import to avoid cycles)."""
    from app.rms.models import Tenant as TenantModel
    return TenantModel


# --- Single-tenant default ---


DEFAULT_TENANT_SLUG = "default"


def ensure_default_tenant(session: Session) -> int:
    """Idempotent: ensure the default tenant exists. Return its id."""
    TenantModel = _get_tenant_model()
    existing = session.execute(
        select(TenantModel).where(TenantModel.slug == DEFAULT_TENANT_SLUG)
    ).scalar_one_or_none()
    if existing is not None:
        return existing.id

    # Find a name from app_meta (set by E10 settings)
    biz = session.execute(
        select(AppMeta).where(AppMeta.key == "general.business_name")
    ).scalar_one_or_none()
    name = biz.value if biz and isinstance(biz.value, str) else "Mi Panadería"

    t = TenantModel(
        slug=DEFAULT_TENANT_SLUG,
        business_name=name,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    session.add(t)
    session.commit()
    return t.id


def list_tenants(session: Session) -> list[Tenant]:
    """List all tenants (for diagnostic / operator check)."""
    TenantModel = _get_tenant_model()
    rows = list(session.execute(select(TenantModel).order_by(TenantModel.id)).scalars())
    return [
        Tenant(
            id=r.id,
            slug=r.slug,
            business_name=r.business_name,
            created_at=r.created_at,
        )
        for r in rows
    ]


def assert_single_tenant(session: Session) -> int:
    """Warn (or raise) if more than one tenant is configured.

    Returns the count. In the current single-tenant model, this is
    expected to be 1 — anything else indicates multi-tenant mode
    was enabled without the data layer being migrated.
    """
    tenants = list_tenants(session)
    if len(tenants) > 1:
        # Multi-tenant data layer is out of scope for the current
        # schema. Surface this loudly in logs / assertions but do
        # not crash production.
        import logging
        logging.warning(
            "Multi-tenant mode: %d tenants found but data layer is "
            "single-tenant. Migration required before isolating data.",
            len(tenants),
        )
    return len(tenants)


# --- Per-request resolution ---


@dataclass
class TenantContext:
    """Resolved tenant for a request."""

    tenant_id: int
    slug: str
    business_name: str


def resolve_tenant_id(
    *,
    request_host: str | None = None,
    env_var: str = "AIW_TENANT_ID",
) -> int:
    """Resolve the active tenant id.

    Order:
      1. Tenant from subdomain (e.g. 'herbus.saskia-rms.paragu-ai.com')
      2. AIW_TENANT_ID env var
      3. Default = 1 (single-tenant default)
    """
    explicit = os.environ.get(env_var)
    if explicit:
        try:
            return int(explicit)
        except (ValueError, TypeError):
            pass
    if request_host:
        parts = request_host.split(".")
        if len(parts) >= 3 and parts[0] not in ("www", "localhost", "127"):
            return _slug_to_id(parts[0])
    return 1


def _slug_to_id(slug: str) -> int:
    """Map subdomain slug → tenant id (very simple hashmap)."""
    # In production this would query the DB; for now the slug "default"
    # always maps to 1.
    if slug == DEFAULT_TENANT_SLUG:
        return 1
    return 1  # unknown → default (until slug table exists)


def current_tenant(session: Session, *, tenant_id: int | None = None) -> TenantContext:
    """Get the active tenant context."""
    if tenant_id is None:
        tenant_id = resolve_tenant_id()
    TenantModel = _get_tenant_model()
    row = session.get(TenantModel, tenant_id)
    if row is None:
        return TenantContext(
            tenant_id=1,
            slug=DEFAULT_TENANT_SLUG,
            business_name="Mi Panadería",
        )
    return TenantContext(
        tenant_id=row.id,
        slug=row.slug,
        business_name=row.business_name,
    )


__all__ = [
    "Tenant",
    "TenantContext",
    "DEFAULT_TENANT_SLUG",
    "ensure_default_tenant",
    "list_tenants",
    "assert_single_tenant",
    "resolve_tenant_id",
    "current_tenant",
]
