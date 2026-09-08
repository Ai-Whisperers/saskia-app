"""app/routers/auditoria.py — /auditoria (Audit log viewer).

Built on app/rms/audit.py list_recent() + AuditLog model.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.audit import list_recent
from app.services.template_render import render

router = APIRouter(prefix="/auditoria", dependencies=[Depends(require_login)])


def get_session(request: Request) -> Session:
    return request.app.state.session_factory()


@router.get("", response_class=HTMLResponse)
def auditoria_index(
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    action_filter: str | None = Query(None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """List recent audit log entries."""
    rows = list_recent(
        session,
        limit=limit,
        action_filter=action_filter,
    )
    return render(request, "auditoria.html", {
        "rows": rows,
        "limit": limit,
        "action_filter": action_filter,
    })


__all__ = ["router"]
