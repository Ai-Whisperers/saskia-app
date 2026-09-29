"""app/routers/settings.py — settings management + business info.

Business information, theme settings, fiscal configuration, and application settings.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.constants import (
    DEFAULT_IVA_RATE,
    DEFAULT_LABOR_COST_PER_HOUR_GS,
    DEFAULT_OVERHEAD_MULTIPLIER_PCT,
    DEFAULT_TAX_REGIME,
)
from app.rms.dependencies import get_session
from app.rms.models import (
    AppMeta,
    ComplianceInfo,
    DeliveryZone,
    User,
)
from app.services.template_render import render

router = APIRouter(prefix="/settings", dependencies=[Depends(require_login)])


@router.get("", response_class=HTMLResponse)
def settings_page(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Settings page with business info, theme, and fiscal config."""
    from app.auth import current_user_id

    user_id = current_user_id(request)

    # Get business settings
    business_name = session.scalar(select(AppMeta).where(AppMeta.key == "business_name"))
    business_ruc = session.scalar(select(AppMeta).where(AppMeta.key == "business_ruc"))
    business_address = session.scalar(select(AppMeta).where(AppMeta.key == "business_address"))
    business_phone = session.scalar(select(AppMeta).where(AppMeta.key == "business_phone"))

    # Get fiscal settings
    timbrado = session.scalar(select(AppMeta).where(AppMeta.key == "timbrado"))
    punto_expedicion = session.scalar(select(AppMeta).where(AppMeta.key == "punto_expedicion"))
    invoice_sequence = session.scalar(select(AppMeta).where(AppMeta.key == "invoice_sequence"))

    # Get theme setting
    theme = session.scalar(select(AppMeta).where(AppMeta.key == "theme"))

    # Phase 1.A — ComplianceInfo row (id=1) for tax / regulatory IDs
    compliance = session.get(ComplianceInfo, 1) or ComplianceInfo(id=1)

    return render(request, "settings.html", {
        "business_name": business_name.value if business_name else "",
        "business_ruc": business_ruc.value if business_ruc else "",
        "business_address": business_address.value if business_address else "",
        "business_phone": business_phone.value if business_phone else "",
        "timbrado": timbrado.value if timbrado else "",
        "punto_expedicion": punto_expedicion.value if punto_expedicion else "",
        "invoice_sequence": invoice_sequence.value if invoice_sequence else "",
        "theme": theme.value if theme else "system",
        "current_user": _safe_get_user(session, user_id),
        "delivery_zones": session.execute(
            select(DeliveryZone).order_by(DeliveryZone.position)
        ).scalars().all(),
        # Phase 1.A — pass compliance fields to the template
        "compliance": compliance,
    })


def _safe_get_user(session, user_id):
    """Look up the User by id, handling UUID strings (Supabase) gracefully.

    Returns None for non-integer ids (e.g., Supabase UUID) so the template
    doesn't crash with TypeError on attribute access.
    """
    if user_id is None:
        return None
    try:
        return session.get(User, user_id)
    except Exception:  # noqa: BLE001 — defensive fallback — guarded response
        return None


@router.post("/business", response_class=RedirectResponse)
def save_business_settings(
    request: Request,
    business_name: str = Form(""),
    business_ruc: str = Form(""),
    business_address: str = Form(""),
    business_phone: str = Form(""),
    business_email: str = Form(""),
    nombre_fantasia: str = Form(""),
    razon_social: str = Form(""),
    tax_regime: str = Form(DEFAULT_TAX_REGIME),
    iva_default_rate: str = Form(DEFAULT_IVA_RATE),
    timbrado_number: str = Form(""),
    timbrado_expiry: str = Form(""),
    inan_re_number: str = Form(""),
    inan_re_expiry: str = Form(""),
    director_tecnico: str = Form(""),
    director_tecnico_registro: str = Form(""),
    municipal_habilitacion: str = Form(""),
    municipal_habilitacion_expiry: str = Form(""),
    labor_cost_per_hour_gs: str = Form(str(DEFAULT_LABOR_COST_PER_HOUR_GS)),
    overhead_multiplier_pct: str = Form(str(DEFAULT_OVERHEAD_MULTIPLIER_PCT)),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Save business + Phase 1.A compliance info.

    Phase 1.A added INAN R.E., Director Técnico, municipal habilitación,
    timbrado, tax_regime, and IVA defaults. All persisted to the single
    ComplianceInfo row (id=1). Phase 1.D also captures costing config
    (labor_cost_per_hour_gs + overhead_multiplier_pct).
    """
    from app.rms.validation import (
        optional_int,
        optional_text,
        validate_phone,
        validate_ruc,
    )

    name = optional_text(business_name, max_len=200)
    ruc = validate_ruc(business_ruc)
    address = optional_text(business_address, max_len=300)
    phone = validate_phone(business_phone)
    email = optional_text(business_email, max_len=120)
    fantasia = optional_text(nombre_fantasia, max_len=120)
    rz = optional_text(razon_social, max_len=120)
    regime = optional_text(tax_regime, max_len=16) or DEFAULT_TAX_REGIME
    iva_def = optional_text(iva_default_rate, max_len=8) or DEFAULT_IVA_RATE
    timbrado = optional_text(timbrado_number, max_len=20)
    timbrado_exp = optional_text(timbrado_expiry, max_len=10)
    re_number = optional_text(inan_re_number, max_len=30)
    re_expiry = optional_text(inan_re_expiry, max_len=10)
    dt = optional_text(director_tecnico, max_len=120)
    dt_reg = optional_text(director_tecnico_registro, max_len=30)
    hab = optional_text(municipal_habilitacion, max_len=30)
    hab_exp = optional_text(municipal_habilitacion_expiry, max_len=10)
    labor = optional_int(labor_cost_per_hour_gs) or DEFAULT_LABOR_COST_PER_HOUR_GS
    overhead = optional_int(overhead_multiplier_pct) or DEFAULT_OVERHEAD_MULTIPLIER_PCT

    # Persist the legacy AppMeta keys (still used by old templates)
    settings = [
        ("business_name", name or ""),
        ("business_ruc", ruc or ""),
        ("business_address", address or ""),
        ("business_phone", phone or ""),
        ("business_email", email or ""),
    ]
    now_iso = datetime.now(timezone.utc).isoformat()
    for key, value in settings:
        existing = session.scalar(select(AppMeta).where(AppMeta.key == key))
        if existing:
            existing.value = value
            existing.updated_at = now_iso
        else:
            session.add(AppMeta(key=key, value=value, updated_at=now_iso))

    # Persist ComplianceInfo (single row, id=1)
    ci = session.get(ComplianceInfo, 1)
    if ci is None:
        ci = ComplianceInfo(id=1)
        session.add(ci)
    ci.ruc = ruc or None
    ci.razon_social = rz
    ci.nombre_fantasia = fantasia or name
    ci.tax_regime = regime
    ci.iva_default_rate = iva_def
    ci.timbrado_number = timbrado
    ci.timbrado_expiry = timbrado_exp
    ci.inan_re_number = re_number
    ci.inan_re_expiry = re_expiry
    ci.director_tecnico = dt
    ci.director_tecnico_registro = dt_reg
    ci.municipal_habilitacion = hab
    ci.municipal_habilitacion_expiry = hab_exp
    ci.establecimiento_address = address
    ci.establecimiento_phone = phone
    ci.establecimiento_email = email
    ci.labor_cost_per_hour_gs = labor
    ci.overhead_multiplier_pct = overhead

    session.commit()
    return RedirectResponse(url="/settings?flash=Información+guardada", status_code=303)


@router.post("/fiscal", response_class=RedirectResponse)
def save_fiscal_settings(
    request: Request,
    timbrado: str = Form(""),
    punto_expedicion: str = Form(""),
    invoice_sequence: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Save fiscal configuration settings."""
    from app.auth import current_user_id
    from app.rms.audit import record as audit_record

    user_id = current_user_id(request)

    # Upsert fiscal settings
    settings = [
        ("timbrado", timbrado),
        ("punto_expedicion", punto_expedicion),
        ("invoice_sequence", invoice_sequence),
    ]
    now_iso = datetime.now(timezone.utc).isoformat()
    for key, value in settings:
        existing = session.scalar(select(AppMeta).where(AppMeta.key == key))
        if existing:
            old_value = existing.value
            existing.value = value
            existing.updated_at = now_iso

            # Audit change
            audit_record(session, user_id=user_id, action="settings.change",
                        detail={"setting": key, "old_value": old_value, "new_value": value})
        else:
            new = AppMeta(key=key, value=value, updated_at=now_iso)
            session.add(new)
            audit_record(session, user_id=user_id, action="settings.create",
                        detail={"setting": key, "value": value})

    session.commit()
    return RedirectResponse(url="/settings?flash=Configuración+fiscal+guardada", status_code=303)


@router.post("/theme", response_class=RedirectResponse)
def save_theme_settings(
    request: Request,
    theme: str = Form("", pattern="^(light|dark|system)$"),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Save theme preference."""
    from app.auth import current_user_id
    from app.rms.audit import record as audit_record

    user_id = current_user_id(request)

    # Validate theme
    if theme not in ["light", "dark", "system"]:
        raise HTTPException(status_code=400, detail="Tema inválido. Opciones: light, dark, system.")

    # Save theme preference
    existing = session.scalar(select(AppMeta).where(AppMeta.key == "theme"))
    now_iso = datetime.now(timezone.utc).isoformat()
    if existing:
        old_value = existing.value
        existing.value = theme
        existing.updated_at = now_iso
        audit_record(session, user_id=user_id, action="settings.change",
                    detail={"setting": "theme", "old_value": old_value, "new_value": theme})
    else:
        new = AppMeta(key="theme", value=theme, updated_at=now_iso)
        session.add(new)
        audit_record(session, user_id=user_id, action="settings.create",
                    detail={"setting": "theme", "value": theme})

    session.commit()
    return RedirectResponse(url=f"/settings?flash=Tema+{theme}+guardado", status_code=303)


@router.post("/seed-demo", response_class=RedirectResponse)
def settings_seed_demo(
    overwrite: str = Form("0"),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """One-click seed realistic bakery demo data.

    - overwrite=0: idempotent (skips if seed already exists)
    - overwrite=1: clears existing seed-like rows and re-seeds

    The tab in settings.html documents both behaviors.
    """
    from app.rms.seed import seed_demo_data

    try:
        do_overwrite = overwrite == "1"
        # Use a short, deterministic seed so the same demo data is reproduced
        report = seed_demo_data(session, overwrite=do_overwrite, seed=20260922)
    except Exception as exc:  # noqa: BLE001
        # Roll back partial work and surface the error
        session.rollback()
        logger.exception(f"seed_demo_data failed: {exc}")
        return RedirectResponse(
            url=f"/settings?flash=Error+al+cargar+ejemplo:+{type(exc).__name__}",
            status_code=303,
        )

    inserted = report.as_dict() if hasattr(report, "as_dict") else {}
    msg = (f"Datos de ejemplo cargados: "
           f"{inserted.get('ingredients', '?')} ingredientes, "
           f"{inserted.get('recipes', '?')} recetas, "
           f"{inserted.get('products', '?')} productos")
    # URL-encode the plus signs manually so they don't get treated as spaces
    msg_url = msg.replace(" ", "+")
    return RedirectResponse(
        url=f"/settings?flash={msg_url}",
        status_code=303,
    )





@router.get("/catalog", response_class=HTMLResponse)
def settings_catalog_page(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Operator-facing catalog configuration page (Phase 4 + 5 + 6).

    Lets Kiki/Saskia manage categories, channels, payment methods,
    message templates, and branding without touching code. All writes
    go through the JSON API endpoints in app/routers/settings_runtime.py.
    """
    return render(request, "settings_catalog.html", {})
__all__ = ["router"]
