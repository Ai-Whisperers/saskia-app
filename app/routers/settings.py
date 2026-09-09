"""app/routers/settings.py — operator UI for /settings.

The settings module (app/rms/settings.py) provides 30 settings with
5 validators. This router surfaces them as a simple HTML form so
the operator can change values without `psql`.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.audit import record as audit_record
from app.rms.dependencies import get_session
from app.rms.settings import (
    list_settings,
    reset_setting_to_default,
    set_setting,
    settings_by_group,
)
from app.services.template_render import render

router = APIRouter(prefix="/settings", dependencies=[Depends(require_login)])


@router.get("", response_class=HTMLResponse)
def settings_index(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    """Render settings grouped by category."""
    grouped = settings_by_group(session)
    # Convert to a structure templates can iterate easily.
    groups = []
    for group_name, rows in grouped.items():
        groups.append({"name": group_name, "label": group_name.capitalize(), "rows": rows})
    return render(request, "settings.html", {
        "groups": groups,
        "total": len(list_settings(session)),
    })


@router.post("")
def settings_update(
    request: Request,
    key: str = Form(...),
    value: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Persist a single setting change."""
    try:
        set_setting(session, key, value, user_id="operator")
        audit_record(
            session,
            user_id="operator",
            action="settings.update",
            request=request,
            detail={"key": key, "value": value[:100]},
        )
        session.commit()
    except Exception:
        # Reset to default if the value is invalid.
        reset_setting_to_default(session, key)
        session.commit()
    return RedirectResponse(url="/settings", status_code=303)


@router.post("/reset")
def settings_reset(
    request: Request,
    key: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Reset a setting to its default."""
    reset_setting_to_default(session, key)
    audit_record(
        session,
        user_id="operator",
        action="settings.reset",
        request=request,
        detail={"key": key},
    )
    session.commit()
    return RedirectResponse(url="/settings", status_code=303)


__all__ = ["router"]
