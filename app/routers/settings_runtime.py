"""app/routers/settings_runtime.py — SettingsKV API endpoints.

Phase 2 of the static-content audit (docs/operations/2026-09-24-static-content-audit.md).

Endpoints:
- GET  /api/settings/pricing-markup           — return markup config (multiplier, round_to_gs)
- POST /api/settings/pricing-markup           — update markup config (admin only)
- GET  /api/settings/pricing-markup/preview   — preview suggested price for a cost
- GET  /api/categories?scope=product          — list categories for a scope
- POST /api/categories                        — create a new category
- POST /api/categories/{id}/update            — update category fields

These are JSON endpoints for the JS-driven forms. The full HTML /settings/pricing
page is a follow-up — for now operators POST to the API directly or use
SQLAlchemy session.execute() to edit SettingsKV.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled
from app.rms.categories import (
    SCOPE_PRODUCT,
    SCOPE_RECIPE_FAMILY,
    get_or_create_category,
    list_categories,
    update_category,
)
from app.rms.dependencies import get_session
from app.rms.settings_runtime import (
    compute_suggested_price,
    get_pricing_markup,
    set_pricing_markup,
)


router = APIRouter(prefix="/api", tags=["settings"])


# ─── Pricing markup ────────────────────────────────────────────────────


class PricingMarkupIn(BaseModel):
    multiplier: float = Field(gt=0, le=100, description="Cost × multiplier = suggested retail")
    round_to_gs: int = Field(default=1000, gt=0, le=1_000_000, description="Round suggested price up to this step in Gs.")


@router.get("/settings/pricing-markup")
def read_pricing_markup(
    request: Request,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
):
    """Return the current suggested-pricing markup config.

    Public to any logged-in user (cashiers see suggested prices on the POS).
    """
    return get_pricing_markup(session)


@router.post("/settings/pricing-markup")
def write_pricing_markup(
    payload: PricingMarkupIn,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
):
    """Update the suggested-pricing markup config.

    Permission: any logged-in user today; tighten to admin role when role
    enforcement is added (see app/rms/AGENTS.md rules around role-based
    access control).
    """
    new_cfg = set_pricing_markup(session, payload.multiplier, payload.round_to_gs)
    session.commit()
    return new_cfg


@router.get("/settings/pricing-markup/preview")
def preview_pricing(
    cost_gs: int = Query(..., gt=0, description="Cost in integer Gs"),
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
):
    """Preview what the suggested price would be for a given cost.

    Used by the JS live-calc on the product form to show "Sugerido: Gs. X".
    """
    cfg = get_pricing_markup(session)
    return {
        "cost_gs": cost_gs,
        "markup": cfg,
        "suggested_price_gs": compute_suggested_price(cost_gs, cfg),
    }


# ─── Categories ────────────────────────────────────────────────────────


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    scope: str = Field(pattern="^(product|recipe_family)$")
    sort_order: int = Field(default=1000, ge=0)


class CategoryUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    sort_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


@router.get("/categories")
def list_categories_endpoint(
    scope: str = Query(..., pattern="^(product|recipe_family)$"),
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
):
    """Return active categories for the given scope."""
    cats = list_categories(session, scope)
    return [
        {"id": c.id, "name": c.name, "scope": c.scope, "sort_order": c.sort_order, "is_active": c.is_active}
        for c in cats
    ]


@router.post("/categories")
def create_category_endpoint(
    payload: CategoryIn,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
):
    """Create a new category. Idempotent on (scope, name)."""
    cat = get_or_create_category(session, payload.name, payload.scope, payload.sort_order)
    session.commit()
    return {
        "id": cat.id, "name": cat.name, "scope": cat.scope,
        "sort_order": cat.sort_order, "is_active": cat.is_active,
    }


@router.post("/categories/{category_id}/update")
def update_category_endpoint(
    category_id: int,
    payload: CategoryUpdateIn,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
):
    """Update fields on an existing category."""
    cat = update_category(
        session,
        category_id,
        name=payload.name,
        sort_order=payload.sort_order,
        is_active=payload.is_active,
    )
    if cat is None:
        raise HTTPException(status_code=404, detail="Category not found")
    session.commit()
    return {
        "id": cat.id, "name": cat.name, "scope": cat.scope,
        "sort_order": cat.sort_order, "is_active": cat.is_active,
    }


__all__ = ["router"]
