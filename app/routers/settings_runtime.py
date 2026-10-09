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
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled
from app.rms.categories import (
    get_or_create_category,
    list_categories,
    update_category,
)
from app.rms.clock import now
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
    round_to_gs: int = Field(
        default=1000, gt=0, le=1_000_000, description="Round suggested price up to this step in Gs."
    )


@router.get("/settings/pricing-markup")
def read_pricing_markup(
    request: Request,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Return the current suggested-pricing markup config.

    Public to any logged-in user (cashiers see suggested prices on the POS).
    """
    return get_pricing_markup(session)


@router.post("/settings/pricing-markup")
def write_pricing_markup(
    payload: PricingMarkupIn,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Update the suggested-pricing markup config.

    Permission: any logged-in user today; tighten to admin role when role
    enforcement is added (see app/rms/AGENTS.md rules around role-based
    access control).
    """
    new_cfg = set_pricing_markup(session, payload.multiplier, payload.round_to_gs)
    session.commit()
    return new_cfg


# ─── Shop WhatsApp (menu ordering) ─────────────────────────────────────


class ShopWhatsappIn(BaseModel):
    phone: str = Field(
        min_length=0,
        max_length=32,
        description="Order-taking WhatsApp number, digits with country code (595981123456). Empty string disables ordering.",
    )


@router.get("/settings/shop-whatsapp")
def read_shop_whatsapp(
    request: Request,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Digits-only WhatsApp number used by the public /menu order cart."""
    from app.rms.models import SettingsKV

    row = session.get(SettingsKV, "shop_whatsapp")
    return {"phone": str(row.value_json or "") if row else ""}


@router.post("/settings/shop-whatsapp")
def write_shop_whatsapp(
    payload: ShopWhatsappIn,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Set/clear the menu-order WhatsApp number. Stored digits-only."""
    from datetime import datetime, timezone

    from app.rms.models import SettingsKV

    digits = "".join(c for c in payload.phone if c.isdigit())
    row = session.get(SettingsKV, "shop_whatsapp")
    if row is None:
        row = SettingsKV(
            key="shop_whatsapp", value_json=digits, updated_at=datetime.now(timezone.utc)
        )
        session.add(row)
    else:
        row.value_json = digits
        row.updated_at = datetime.now(timezone.utc)
    session.commit()
    return {"phone": digits, "ordering_enabled": bool(digits)}


@router.get("/settings/pricing-markup/preview")
def preview_pricing(
    cost_gs: int = Query(..., gt=0, description="Cost in integer Gs"),
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
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
) -> object:
    """Return active categories for the given scope."""
    cats = list_categories(session, scope)
    return [
        {
            "id": c.id,
            "name": c.name,
            "scope": c.scope,
            "sort_order": c.sort_order,
            "is_active": c.is_active,
        }
        for c in cats
    ]


@router.post("/categories")
def create_category_endpoint(
    payload: CategoryIn,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Create a new category. Idempotent on (scope, name)."""
    cat = get_or_create_category(session, payload.name, payload.scope, payload.sort_order)
    session.commit()
    return {
        "id": cat.id,
        "name": cat.name,
        "scope": cat.scope,
        "sort_order": cat.sort_order,
        "is_active": cat.is_active,
    }


@router.post("/categories/{category_id}/update")
def update_category_endpoint(
    category_id: int,
    payload: CategoryUpdateIn,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
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
        "id": cat.id,
        "name": cat.name,
        "scope": cat.scope,
        "sort_order": cat.sort_order,
        "is_active": cat.is_active,
    }


# ─── Channels + Payment methods ────────────────────────────────────────


@router.get("/channels")
def list_channels_endpoint(
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Return active channels sorted by sort_order."""
    from app.rms.catalogs import list_channels

    cats = list_channels(session)
    return [
        {
            "id": c.id,
            "code": c.code,
            "label": c.label,
            "sort_order": c.sort_order,
            "is_default": c.is_default,
            "is_active": c.is_active,
            "notes": c.notes,
        }
        for c in cats
    ]


class ChannelIn(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    label: str = Field(min_length=1, max_length=64)
    sort_order: int = Field(default=1000, ge=0)
    is_default: bool = False
    notes: str | None = Field(default=None, max_length=500)


@router.post("/channels")
def create_channel_endpoint(
    payload: ChannelIn,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Create a new channel. Idempotent on code."""
    from app.rms.models import Channel as ChannelModel

    existing = session.execute(
        select(ChannelModel).where(ChannelModel.code == payload.code)
    ).scalar_one_or_none()
    if existing is not None:
        # Update label/sort/etc but don't replace is_active
        existing.label = payload.label
        existing.sort_order = payload.sort_order
        if payload.is_default:
            # Clear other defaults first
            session.execute(
                select(ChannelModel).where(ChannelModel.is_default.is_(True))
            ).scalars().all()
            for c in session.execute(select(ChannelModel)).scalars():
                c.is_default = c.code == payload.code
        existing.notes = payload.notes
        session.commit()
        return {
            "id": existing.id,
            "code": existing.code,
            "label": existing.label,
            "sort_order": existing.sort_order,
            "is_default": existing.is_default,
        }

    if payload.is_default:
        # Clear other defaults first
        for c in session.execute(select(ChannelModel)).scalars():
            c.is_default = False

    ch = ChannelModel(
        code=payload.code,
        label=payload.label,
        sort_order=payload.sort_order,
        is_default=payload.is_default,
        is_active=True,
        notes=payload.notes,
    )
    session.add(ch)
    session.commit()
    return {
        "id": ch.id,
        "code": ch.code,
        "label": ch.label,
        "sort_order": ch.sort_order,
        "is_default": ch.is_default,
    }


@router.get("/payment-methods")
def list_payment_methods_endpoint(
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Return active payment methods sorted by sort_order."""
    from app.rms.catalogs import list_payment_methods

    methods = list_payment_methods(session)
    return [
        {
            "id": m.id,
            "code": m.code,
            "label": m.label,
            "requires_reference": m.requires_reference,
            "fee_pct": m.fee_pct,
            "sort_order": m.sort_order,
            "is_default": m.is_default,
        }
        for m in methods
    ]


class PaymentMethodIn(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    label: str = Field(min_length=1, max_length=64)
    requires_reference: bool = False
    fee_pct: float = Field(default=0.0, ge=0, le=100)
    sort_order: int = Field(default=1000, ge=0)
    is_default: bool = False
    notes: str | None = Field(default=None, max_length=500)


@router.post("/payment-methods")
def create_payment_method_endpoint(
    payload: PaymentMethodIn,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Create a new payment method. Idempotent on code."""
    from app.rms.models import PaymentMethod as PMModel

    existing = session.execute(
        select(PMModel).where(PMModel.code == payload.code)
    ).scalar_one_or_none()
    if existing is not None:
        existing.label = payload.label
        existing.requires_reference = payload.requires_reference
        existing.fee_pct = payload.fee_pct
        existing.sort_order = payload.sort_order
        existing.notes = payload.notes
        if payload.is_default:
            for m in session.execute(select(PMModel)).scalars():
                m.is_default = m.code == payload.code
        session.commit()
        return {"id": existing.id, "code": existing.code, "label": existing.label}

    if payload.is_default:
        for m in session.execute(select(PMModel)).scalars():
            m.is_default = False

    pm = PMModel(
        code=payload.code,
        label=payload.label,
        requires_reference=payload.requires_reference,
        fee_pct=payload.fee_pct,
        sort_order=payload.sort_order,
        is_default=payload.is_default,
        is_active=True,
        notes=payload.notes,
    )
    session.add(pm)
    session.commit()
    return {"id": pm.id, "code": pm.code, "label": pm.label}


# ─── Branding (Phase 5) ────────────────────────────────────────────────


@router.get("/settings/branding")
def read_branding(
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Return the branding config dict.

    Public to any logged-in user (the login page itself reads this to
    render the title — operators can change business name without code
    deploy).
    """
    from app.rms.settings_runtime import get_branding

    return get_branding(session)


class BrandingIn(BaseModel):
    """Partial-update schema for branding settings.

    All fields optional — only non-None fields are written. File uploads
    (logo, favicon, hero) go through /admin/branding/upload which returns
    a filename you then set via the corresponding field here.
    """

    business_name: str | None = Field(default=None, max_length=200)
    tagline: str | None = Field(default=None, max_length=200)
    footer: str | None = Field(default=None, max_length=200)
    business_type: str | None = Field(
        default=None, max_length=32
    )  # restaurant|panaderia|cafeteria|bar|heladeria|food_truck|otro
    accent_color: str | None = Field(default=None, max_length=20)
    logo_filename: str | None = Field(default=None, max_length=200)
    favicon_filename: str | None = Field(default=None, max_length=200)
    hero_filename: str | None = Field(default=None, max_length=200)
    contact_email: str | None = Field(default=None, max_length=200)
    contact_phone: str | None = Field(default=None, max_length=64)
    address: str | None = Field(default=None, max_length=300)


@router.post("/settings/branding")
def write_branding(
    payload: BrandingIn,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Update branding. Only non-None fields are written (partial update)."""
    from app.rms.settings_runtime import set_branding

    fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    new_cfg = set_branding(session, **fields)
    session.commit()
    return new_cfg


# ─── Message templates (Phase 6) ──────────────────────────────────────


@router.get("/templates")
def list_templates_endpoint(
    channel: str | None = Query(default=None, pattern="^(email|whatsapp|sms)$"),
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Return active message templates, optionally filtered by channel."""
    from app.rms.models import MessageTemplate as MT

    q = select(MT).where(MT.is_active.is_(True))
    if channel:
        q = q.where(MT.channel == channel)
    q = q.order_by(MT.channel.asc(), MT.key.asc())
    rows = list(session.execute(q).scalars())
    return [
        {
            "id": t.id,
            "channel": t.channel,
            "key": t.key,
            "subject": t.subject,
            "body": t.body,
            "locale": t.locale,
            "version": t.version,
            "notes": t.notes,
        }
        for t in rows
    ]


@router.get("/templates/{template_key}")
def get_template_endpoint(
    template_key: str,
    channel: str = Query("whatsapp", pattern="^(email|whatsapp|sms)$"),
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Return a single template by channel+key. Renders with provided vars if 'vars' param present."""
    from app.rms.models import MessageTemplate as MT

    row = session.execute(
        select(MT).where(
            MT.channel == channel,
            MT.key == template_key,
            MT.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Template {channel}/{template_key} not found")

    return {
        "id": row.id,
        "channel": row.channel,
        "key": row.key,
        "subject": row.subject,
        "body": row.body,
        "locale": row.locale,
        "version": row.version,
        "notes": row.notes,
    }


class TemplateUpdateIn(BaseModel):
    subject: str | None = Field(default=None, max_length=200)
    body: str | None = Field(default=None, min_length=1, max_length=5000)
    notes: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


@router.post("/templates/{template_id}/update")
def update_template_endpoint(
    template_id: int,
    payload: TemplateUpdateIn,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Update a message template. Only non-None fields are written.

    Bumps the `version` on body change so callers can invalidate caches.
    """

    from app.rms.models import MessageTemplate as MT

    row = session.get(MT, template_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")

    body_changed = False
    if payload.subject is not None:
        row.subject = payload.subject
    if payload.body is not None and payload.body != row.body:
        row.body = payload.body
        body_changed = True
    if payload.notes is not None:
        row.notes = payload.notes
    if payload.is_active is not None:
        row.is_active = payload.is_active
    if body_changed:
        row.version += 1
    row.updated_at = now()
    session.commit()
    return {
        "id": row.id,
        "channel": row.channel,
        "key": row.key,
        "subject": row.subject,
        "body": row.body,
        "locale": row.locale,
        "version": row.version,
        "notes": row.notes,
        "is_active": row.is_active,
    }


def render_template(template_body: str, vars: dict) -> str:
    """Pure helper: substitute {placeholder} tokens in a template body.

    Used by the notification routes (when they're migrated to read from
    this table). Falls back to the original body on any KeyError so a
    missing variable never crashes a send.
    """
    try:
        return template_body.format(**vars)
    except (KeyError, IndexError):
        return template_body


# ─── Margin tiers (Phase 7) ────────────────────────────────────────


@router.get("/margin-tiers")
def list_margin_tiers_endpoint(
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Return all margin tiers (operator-tunable thresholds)."""
    from app.rms.margin_tier import list_margin_tiers

    tiers = list_margin_tiers(session)
    return [
        {
            "id": t.id,
            "code": t.code,
            "label": t.label,
            "min_cost_gs": t.min_cost_gs,
            "max_cost_gs": t.max_cost_gs,
            "sort_order": t.sort_order,
            "is_active": t.is_active,
            "notes": t.notes,
        }
        for t in tiers
    ]


class MarginTierUpdateIn(BaseModel):
    label: str | None = Field(default=None, max_length=64)
    min_cost_gs: int | None = Field(default=None, ge=0)
    max_cost_gs: int | None = Field(default=None, ge=0)
    sort_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


@router.post("/margin-tiers/{tier_id}/update")
def update_margin_tier_endpoint(
    tier_id: int,
    payload: MarginTierUpdateIn,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Update a margin tier. Operators use this to adjust thresholds."""
    from app.rms.models import MarginTier

    tier = session.get(MarginTier, tier_id)
    if tier is None:
        raise HTTPException(status_code=404, detail="Tier not found")
    if payload.label is not None:
        tier.label = payload.label
    if payload.min_cost_gs is not None:
        tier.min_cost_gs = payload.min_cost_gs
    if payload.max_cost_gs is not None:
        tier.max_cost_gs = payload.max_cost_gs
    if payload.sort_order is not None:
        tier.sort_order = payload.sort_order
    if payload.is_active is not None:
        tier.is_active = payload.is_active
    session.commit()
    return {
        "id": tier.id,
        "code": tier.code,
        "label": tier.label,
        "min_cost_gs": tier.min_cost_gs,
        "max_cost_gs": tier.max_cost_gs,
        "sort_order": tier.sort_order,
        "is_active": tier.is_active,
    }


# ─── Stock status config (Phase 7) ────────────────────────────────


@router.get("/stock-status-config")
def list_stock_status_config_endpoint(
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Return all stock status thresholds."""
    from app.rms.stock_status import list_status_configs

    configs = list_status_configs(session)
    return [
        {
            "id": c.id,
            "code": c.code,
            "label": c.label,
            "threshold_ratio": c.threshold_ratio,
            "threshold_days": c.threshold_days,
            "sort_order": c.sort_order,
            "is_active": c.is_active,
            "notes": c.notes,
        }
        for c in configs
    ]


class StockStatusConfigUpdateIn(BaseModel):
    label: str | None = Field(default=None, max_length=64)
    threshold_ratio: float | None = Field(default=None, ge=0)
    threshold_days: int | None = Field(default=None, ge=0)
    sort_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


@router.post("/stock-status-config/{config_id}/update")
def update_stock_status_config_endpoint(
    config_id: int,
    payload: StockStatusConfigUpdateIn,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Update a stock status threshold. Operators tune ratios/days here."""
    from app.rms.models import StockStatusConfig

    cfg = session.get(StockStatusConfig, config_id)
    if cfg is None:
        raise HTTPException(status_code=404, detail="Config not found")
    if payload.label is not None:
        cfg.label = payload.label
    if payload.threshold_ratio is not None:
        cfg.threshold_ratio = payload.threshold_ratio
    if payload.threshold_days is not None:
        cfg.threshold_days = payload.threshold_days
    if payload.sort_order is not None:
        cfg.sort_order = payload.sort_order
    if payload.is_active is not None:
        cfg.is_active = payload.is_active
    session.commit()
    return {
        "id": cfg.id,
        "code": cfg.code,
        "label": cfg.label,
        "threshold_ratio": cfg.threshold_ratio,
        "threshold_days": cfg.threshold_days,
        "sort_order": cfg.sort_order,
        "is_active": cfg.is_active,
    }


# ─── Tax / invoice constants (Phase 7) ────────────────────────────


@router.get("/tax-config")
def get_tax_config_endpoint(
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Return current tax config from ComplianceInfo + constants fallback.

    Centralizes the tax/invoice defaults so all callers see the same
    effective values. Future tax law changes touch only this endpoint.
    """
    from app.rms.constants import (
        DEFAULT_INVOICE_TYPE,
        DEFAULT_IVA_RATE,
        DEFAULT_TAX_REGIME,
        INVOICE_TYPES,
        VALID_IVA_RATES,
        VALID_TAX_REGIMES,
    )
    from app.rms.models import ComplianceInfo

    ci = session.get(ComplianceInfo, 1)
    return {
        "iva_rate": ci.iva_default_rate if ci and ci.iva_default_rate else DEFAULT_IVA_RATE,
        "tax_regime": ci.tax_regime if ci and ci.tax_regime else DEFAULT_TAX_REGIME,
        "valid_iva_rates": sorted(VALID_IVA_RATES),
        "valid_tax_regimes": sorted(VALID_TAX_REGIMES),
        "invoice_types": sorted(INVOICE_TYPES),
        "default_invoice_type": DEFAULT_INVOICE_TYPE,
        "labor_cost_per_hour_gs": ci.labor_cost_per_hour_gs if ci else None,
        "overhead_multiplier_pct": ci.overhead_multiplier_pct if ci else None,
    }


# ─── Storage types (Phase 8) ──────────────────────────────────────


@router.get("/storage-types")
def list_storage_types_endpoint(
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Return HACCP storage codes."""
    from app.rms.storage_types import list_storage_types

    types_ = list_storage_types(session)
    return [
        {
            "id": t.id,
            "code": t.code,
            "label": t.label,
            "requires_temp_min": t.requires_temp_min,
            "requires_temp_max": t.requires_temp_max,
            "requires_humidity_max": t.requires_humidity_max,
            "sort_order": t.sort_order,
            "is_active": t.is_active,
        }
        for t in types_
    ]


class StorageTypeIn(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    label: str = Field(min_length=1, max_length=64)
    requires_temp_min: bool = False
    requires_temp_max: bool = False
    requires_humidity_max: bool = False
    sort_order: int = Field(default=1000, ge=0)


@router.post("/storage-types")
def create_storage_type_endpoint(
    payload: StorageTypeIn,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Create a new HACCP storage code. Idempotent on code."""
    from app.rms.models import StorageType as STModel

    existing = session.execute(
        select(STModel).where(STModel.code == payload.code)
    ).scalar_one_or_none()
    if existing is not None:
        existing.label = payload.label
        existing.requires_temp_min = payload.requires_temp_min
        existing.requires_temp_max = payload.requires_temp_max
        existing.requires_humidity_max = payload.requires_humidity_max
        existing.sort_order = payload.sort_order
        session.commit()
        return {"id": existing.id, "code": existing.code, "label": existing.label}

    st = STModel(
        code=payload.code,
        label=payload.label,
        requires_temp_min=payload.requires_temp_min,
        requires_temp_max=payload.requires_temp_max,
        requires_humidity_max=payload.requires_humidity_max,
        sort_order=payload.sort_order,
        is_active=True,
    )
    session.add(st)
    session.commit()
    return {"id": st.id, "code": st.code, "label": st.label}


# ─── Date range presets (Phase 9) ──────────────────────────────────


@router.get("/date-presets")
def list_date_presets_endpoint(
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Return all date range presets."""
    from app.rms.date_presets import list_presets

    presets = list_presets(session)
    return [
        {
            "id": p.id,
            "code": p.code,
            "label": p.label,
            "days": p.days,
            "is_default": p.is_default,
            "sort_order": p.sort_order,
            "is_active": p.is_active,
        }
        for p in presets
    ]


class DatePresetIn(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    label: str = Field(min_length=1, max_length=64)
    days: int = Field(gt=0, le=3650)
    is_default: bool = False
    sort_order: int = Field(default=1000, ge=0)


@router.post("/date-presets")
def create_date_preset_endpoint(
    payload: DatePresetIn,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Create a new date range preset. Idempotent on code."""
    from app.rms.models import DateRangePreset as DRP

    existing = session.execute(select(DRP).where(DRP.code == payload.code)).scalar_one_or_none()
    if existing is not None:
        existing.label = payload.label
        existing.days = payload.days
        existing.sort_order = payload.sort_order
        if payload.is_default:
            for p in session.execute(select(DRP)).scalars():
                p.is_default = p.code == payload.code
        session.commit()
        return {
            "id": existing.id,
            "code": existing.code,
            "label": existing.label,
            "days": existing.days,
        }

    if payload.is_default:
        for p in session.execute(select(DRP)).scalars():
            p.is_default = False

    drp = DRP(
        code=payload.code,
        label=payload.label,
        days=payload.days,
        is_default=payload.is_default,
        sort_order=payload.sort_order,
        is_active=True,
    )
    session.add(drp)
    session.commit()
    return {"id": drp.id, "code": drp.code, "label": drp.label, "days": drp.days}


# ─── IVA rates (Phase 10) ──────────────────────────────────────────


@router.get("/iva-rates")
def list_iva_rates_endpoint(
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Return valid IVA rates.

    Static today (Paraguayan law), but exposed as an endpoint so future
    tax law changes touch only one place.
    """
    from app.rms.constants import DEFAULT_IVA_RATE, VALID_IVA_RATES

    ci = session.get(__import__("app.rms.models", fromlist=["ComplianceInfo"]).ComplianceInfo, 1)
    return {
        "valid_rates": sorted(VALID_IVA_RATES),
        "default_rate": ci.iva_default_rate if ci and ci.iva_default_rate else DEFAULT_IVA_RATE,
    }


# ─── Channel + Payment method update/delete (Phase B) ──────────────


class ChannelUpdateIn(BaseModel):
    label: str | None = Field(default=None, max_length=64)
    sort_order: int | None = Field(default=None, ge=0)
    is_default: bool | None = None
    notes: str | None = Field(default=None, max_length=500)


@router.post("/channels/{channel_id}/update")
def update_channel_endpoint(
    channel_id: int,
    payload: ChannelUpdateIn,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Update an existing channel."""
    from app.rms.models import Channel as Ch

    ch = session.get(Ch, channel_id)
    if ch is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    if payload.label is not None:
        ch.label = payload.label
    if payload.sort_order is not None:
        ch.sort_order = payload.sort_order
    if payload.notes is not None:
        ch.notes = payload.notes
    if payload.is_default is not None and payload.is_default:
        for c in session.execute(select(Ch)).scalars():
            c.is_default = c.id == channel_id
    session.commit()
    return {"id": ch.id, "code": ch.code, "label": ch.label, "is_active": ch.is_active}


@router.post("/channels/{channel_id}/delete")
def delete_channel_endpoint(
    channel_id: int,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Soft-delete a channel (sets is_active=False)."""
    from app.rms.models import Channel as Ch

    ch = session.get(Ch, channel_id)
    if ch is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    ch.is_active = False
    ch.is_default = False
    session.commit()
    return {"id": ch.id, "code": ch.code, "is_active": ch.is_active}


class PaymentMethodUpdateIn(BaseModel):
    label: str | None = Field(default=None, max_length=64)
    requires_reference: bool | None = None
    fee_pct: float | None = Field(default=None, ge=0, le=100)
    sort_order: int | None = Field(default=None, ge=0)
    is_default: bool | None = None
    notes: str | None = Field(default=None, max_length=500)


@router.post("/payment-methods/{method_id}/update")
def update_payment_method_endpoint(
    method_id: int,
    payload: PaymentMethodUpdateIn,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Update an existing payment method."""
    from app.rms.models import PaymentMethod as PM

    pm = session.get(PM, method_id)
    if pm is None:
        raise HTTPException(status_code=404, detail="Payment method not found")
    if payload.label is not None:
        pm.label = payload.label
    if payload.requires_reference is not None:
        pm.requires_reference = payload.requires_reference
    if payload.fee_pct is not None:
        pm.fee_pct = payload.fee_pct
    if payload.sort_order is not None:
        pm.sort_order = payload.sort_order
    if payload.notes is not None:
        pm.notes = payload.notes
    if payload.is_default is not None and payload.is_default:
        for m in session.execute(select(PM)).scalars():
            m.is_default = m.id == method_id
    session.commit()
    return {"id": pm.id, "code": pm.code, "label": pm.label, "is_active": pm.is_active}


@router.post("/payment-methods/{method_id}/delete")
def delete_payment_method_endpoint(
    method_id: int,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Soft-delete a payment method (sets is_active=False)."""
    from app.rms.models import PaymentMethod as PM

    pm = session.get(PM, method_id)
    if pm is None:
        raise HTTPException(status_code=404, detail="Payment method not found")
    pm.is_active = False
    pm.is_default = False
    session.commit()
    return {"id": pm.id, "code": pm.code, "is_active": pm.is_active}


# ─── Category update + delete ──────────────────────────────────────


@router.post("/categories/{category_id}/delete")
def delete_category_endpoint(
    category_id: int,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Soft-delete a category (sets is_active=False)."""
    from app.rms.models import Category

    cat = session.get(Category, category_id)
    if cat is None:
        raise HTTPException(status_code=404, detail="Category not found")
    cat.is_active = False
    session.commit()
    return {"id": cat.id, "name": cat.name, "scope": cat.scope, "is_active": cat.is_active}


# ─── Storage type + Date preset update + delete ───────────────────


class StorageTypeUpdateIn(BaseModel):
    label: str | None = Field(default=None, max_length=64)
    requires_temp_min: bool | None = None
    requires_temp_max: bool | None = None
    requires_humidity_max: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


@router.post("/storage-types/{type_id}/update")
def update_storage_type_endpoint(
    type_id: int,
    payload: StorageTypeUpdateIn,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Update an existing storage type."""
    from app.rms.models import StorageType as STModel

    st = session.get(STModel, type_id)
    if st is None:
        raise HTTPException(status_code=404, detail="Storage type not found")
    if payload.label is not None:
        st.label = payload.label
    if payload.requires_temp_min is not None:
        st.requires_temp_min = payload.requires_temp_min
    if payload.requires_temp_max is not None:
        st.requires_temp_max = payload.requires_temp_max
    if payload.requires_humidity_max is not None:
        st.requires_humidity_max = payload.requires_humidity_max
    if payload.sort_order is not None:
        st.sort_order = payload.sort_order
    if payload.is_active is not None:
        st.is_active = payload.is_active
    session.commit()
    return {"id": st.id, "code": st.code, "label": st.label, "is_active": st.is_active}


@router.post("/storage-types/{type_id}/delete")
def delete_storage_type_endpoint(
    type_id: int,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Soft-delete a storage type (sets is_active=False)."""
    from app.rms.models import StorageType as STModel

    st = session.get(STModel, type_id)
    if st is None:
        raise HTTPException(status_code=404, detail="Storage type not found")
    st.is_active = False
    session.commit()
    return {"id": st.id, "code": st.code, "is_active": st.is_active}


class DatePresetUpdateIn(BaseModel):
    label: str | None = Field(default=None, max_length=64)
    days: int | None = Field(default=None, gt=0, le=3650)
    is_default: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


@router.post("/date-presets/{preset_id}/update")
def update_date_preset_endpoint(
    preset_id: int,
    payload: DatePresetUpdateIn,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Update an existing date preset."""
    from app.rms.models import DateRangePreset as DRP

    drp = session.get(DRP, preset_id)
    if drp is None:
        raise HTTPException(status_code=404, detail="Date preset not found")
    if payload.label is not None:
        drp.label = payload.label
    if payload.days is not None:
        drp.days = payload.days
    if payload.sort_order is not None:
        drp.sort_order = payload.sort_order
    if payload.is_active is not None:
        drp.is_active = payload.is_active
    if payload.is_default is not None and payload.is_default:
        for p in session.execute(select(DRP)).scalars():
            p.is_default = p.id == preset_id
    session.commit()
    return {
        "id": drp.id,
        "code": drp.code,
        "label": drp.label,
        "days": drp.days,
        "is_active": drp.is_active,
    }


@router.post("/date-presets/{preset_id}/delete")
def delete_date_preset_endpoint(
    preset_id: int,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Soft-delete a date preset (sets is_active=False)."""
    from app.rms.models import DateRangePreset as DRP

    drp = session.get(DRP, preset_id)
    if drp is None:
        raise HTTPException(status_code=404, detail="Date preset not found")
    drp.is_active = False
    drp.is_default = False
    session.commit()
    return {"id": drp.id, "code": drp.code, "is_active": drp.is_active}


# ─── Margin tier + Stock status delete ────────────────────────────


@router.post("/margin-tiers/{tier_id}/delete")
def delete_margin_tier_endpoint(
    tier_id: int,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Soft-delete a margin tier."""
    from app.rms.models import MarginTier

    tier = session.get(MarginTier, tier_id)
    if tier is None:
        raise HTTPException(status_code=404, detail="Margin tier not found")
    tier.is_active = False
    session.commit()
    return {"id": tier.id, "code": tier.code, "is_active": tier.is_active}


@router.post("/stock-status-config/{config_id}/delete")
def delete_stock_status_endpoint(
    config_id: int,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Soft-delete a stock status config."""
    from app.rms.models import StockStatusConfig

    cfg = session.get(StockStatusConfig, config_id)
    if cfg is None:
        raise HTTPException(status_code=404, detail="Stock status config not found")
    cfg.is_active = False
    session.commit()
    return {"id": cfg.id, "code": cfg.code, "is_active": cfg.is_active}


# ─── Message template deactivate ───────────────────────────────────


@router.post("/templates/{template_id}/delete")
def delete_template_endpoint(
    template_id: int,
    session: Session = Depends(get_session),
    _user=Depends(require_login_or_disabled),
) -> object:
    """Soft-delete a message template (sets is_active=False)."""
    from app.rms.models import MessageTemplate as MT

    row = session.get(MT, template_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")
    row.is_active = False
    session.commit()
    return {"id": row.id, "channel": row.channel, "key": row.key, "is_active": row.is_active}


# ─── Branding asset upload ──────────────────────────────────────────────
# POST /api/admin/branding/upload — upload logo/favicon/hero image file
# Returns: {filename, url, size_kb, kind}
# Operator then sets branding.logo_filename (etc.) via /settings/branding POST

import secrets
from pathlib import Path as _P

from fastapi import File, Form, UploadFile
from fastapi import HTTPException as _HTTPException

# Allowed file extensions per asset kind
_BRANDING_EXTS = {
    "logo": {".png", ".jpg", ".jpeg", ".svg", ".webp"},
    "favicon": {".ico", ".png"},
    "hero": {".jpg", ".jpeg", ".png", ".webp"},
}
# Max sizes (in MB)
_BRANDING_MAX_MB = {
    "logo": 2,
    "favicon": 0.5,
    "hero": 5,
}
# Output directory (relative to /app/static/, served by /static/branding/)
_ASSET_DIR = "app/static/branding"


@router.post("/admin/branding/upload")
async def upload_branding_asset(
    kind: str = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user=Depends(require_login_or_disabled),
) -> object:
    """Upload a branding asset (logo, favicon, or hero).

    Allowed: logo (2MB png/jpg/svg/webp), favicon (500KB ico/png),
    hero (5MB jpg/png/webp). Filename is randomized; the operator then
    sets branding.logo_filename (etc.) to the returned `filename` field.

    Requires login (no admin gate yet — anyone with valid session can
    upload). This is intentional for now; if abuse becomes an issue,
    add an admin-role check.
    """
    kind = kind.lower()
    if kind not in _BRANDING_EXTS:
        raise _HTTPException(
            status_code=400,
            detail=f"kind must be one of {list(_BRANDING_EXTS)}",
        )

    # Validate extension
    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _BRANDING_EXTS[kind]:
        raise _HTTPException(
            status_code=400,
            detail=f"File extension {ext!r} not allowed for {kind}. "
            f"Allowed: {sorted(_BRANDING_EXTS[kind])}",
        )

    # Read + size-check
    max_bytes = _BRANDING_MAX_MB[kind] * 1024 * 1024
    content = await file.read()
    if len(content) > max_bytes:
        raise _HTTPException(
            status_code=400,
            detail=f"File too large ({len(content) / 1024 / 1024:.1f}MB). "
            f"Max for {kind}: {_BRANDING_MAX_MB[kind]}MB",
        )

    # Random filename: <kind>-<8 hex>.<ext>
    safe_name = f"{kind}-{secrets.token_hex(8)}{ext}"

    # Write to disk
    base_dir = _P(__file__).resolve().parent.parent.parent  # repo root  # noqa: ASYNC240
    asset_dir = base_dir / _ASSET_DIR
    asset_dir.mkdir(parents=True, exist_ok=True)
    out_path = asset_dir / safe_name
    out_path.write_bytes(content)

    return {
        "kind": kind,
        "filename": safe_name,
        "url": f"/static/branding/{safe_name}",
        "size_kb": round(len(content) / 1024, 1),
    }


@router.get("/admin/branding", response_class=HTMLResponse)
def branding_admin_page(
    request: Request,
    session: Session = Depends(get_session),
    user=Depends(require_login_or_disabled),
) -> object:
    """Operator UI for branding (business identity, assets, accent color).

    Renders app/templates/admin/branding.html with current branding context.
    Lives in settings_runtime router because /settings/branding API is here.
    """
    from app.services.template_render import render

    return render(request, "admin/branding.html", {"active_nav": "settings"})


__all__ = ["router"]
