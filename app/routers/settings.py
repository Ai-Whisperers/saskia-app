"""app/routers/settings.py — settings management + business info.

Business information, theme settings, fiscal configuration, and application settings.
"""

from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.models import AppMeta, User
from app.rms.dependencies import get_session
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
    except Exception:
        return None


@router.post("/business", response_class=RedirectResponse)
def save_business_settings(
    request: Request,
    business_name: str = Form(""),
    business_ruc: str = Form(""),
    business_address: str = Form(""),
    business_phone: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Save business information settings.

    Validates business_ruc (Paraguay format) and business_phone (digits).
    """
    from app.rms.validation import (
        optional_text, validate_ruc, validate_phone,
    )

    name = optional_text(business_name, max_len=200)
    ruc = validate_ruc(business_ruc)
    address = optional_text(business_address, max_len=300)
    phone = validate_phone(business_phone)

    settings = [
        ("business_name", name or ""),
        ("business_ruc", ruc or ""),
        ("business_address", address or ""),
        ("business_phone", phone or ""),
    ]
    now_iso = datetime.now(timezone.utc).isoformat()
    for key, value in settings:
        existing = session.scalar(select(AppMeta).where(AppMeta.key == key))
        if existing:
            existing.value = value
            existing.updated_at = now_iso
        else:
            session.add(AppMeta(key=key, value=value, updated_at=now_iso))

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
    from app.rms.audit import record as audit_record
    from app.auth import current_user_id

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
    from app.rms.audit import record as audit_record
    from app.auth import current_user_id

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
    except Exception as exc:
        # Roll back partial work and surface the error
        session.rollback()
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


__all__ = ["router"]