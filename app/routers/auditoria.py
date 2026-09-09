"""app/routers/auditoria.py — /auditoria (Audit log viewer).

Built on app/rms/audit.py list_recent() + AuditLog model.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.audit import list_recent
from app.rms.dependencies import get_session
from app.services.template_render import render

router = APIRouter(prefix="/auditoria", dependencies=[Depends(require_login)])


@router.get("", response_class=HTMLResponse)
def auditoria_index(
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    action_filter: str | None = Query(None),
    start_date: str | None = Query(None, description="ISO date YYYY-MM-DD"),
    end_date: str | None = Query(None, description="ISO date YYYY-MM-DD"),
    ip_filter: str | None = Query(None, description="Filter by client IP"),
    user_filter: str | None = Query(None, description="Filter by user_id"),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """List recent audit log entries with optional date-range filter.

    start_date / end_date are ISO dates (YYYY-MM-DD). Filter is
    inclusive of the start date and exclusive of end_date (+1 day
    recommended for a single-day filter).

    audit_log.occurred_at is stored as UTC-naive datetime (legacy);
    we compare naive UTC explicitly.
    """
    from datetime import datetime, timedelta

    rows = list_recent(
        session,
        limit=limit,
        action_filter=action_filter,
    )

    # Apply date-range filter in Python (limit=100 bounds memory).
    if start_date:
        try:
            sd = datetime.fromisoformat(start_date)
        except ValueError:
            sd = None
        if sd is not None:
            rows = [r for r in rows if r.occurred_at and r.occurred_at >= sd]
    if end_date:
        try:
            ed = datetime.fromisoformat(end_date) + timedelta(days=1)
        except ValueError:
            ed = None
        if ed is not None:
            rows = [r for r in rows if r.occurred_at and r.occurred_at < ed]

    # IP + user_id filter (substring match for forgiving UX).
    if ip_filter:
        rows = [r for r in rows if r.ip and ip_filter in r.ip]
    if user_filter:
        rows = [r for r in rows if r.user_id and user_filter in r.user_id]

    return render(request, "auditoria.html", {
        "rows": rows,
        "limit": limit,
        "action_filter": action_filter,
        "start_date": start_date or "",
        "end_date": end_date or "",
        "ip_filter": ip_filter or "",
        "user_filter": user_filter or "",
    })


__all__ = ["router"]
