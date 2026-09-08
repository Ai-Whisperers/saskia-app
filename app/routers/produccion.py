"""app/routers/produccion.py — /produccion (Production worksheet).

Built on top of app/rms/production.py which has all the helpers:
- plan_production() returns ProductionPlan with rows + ingredient lines
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.production import plan_production
from app.services.template_render import render

router = APIRouter(prefix="/produccion", dependencies=[Depends(require_login)])


def get_session(request: Request) -> Session:
    return request.app.state.session_factory()


@router.get("", response_class=HTMLResponse)
def produccion_worksheet(
    request: Request,
    for_date: date | None = Query(None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Tomorrow's production plan with seasonal multiplier."""
    plan = plan_production(session, for_date=for_date)
    return render(request, "produccion.html", {
        "plan": plan,
        "for_date": plan.for_date.isoformat() if plan.for_date else "",
    })


__all__ = ["router"]
