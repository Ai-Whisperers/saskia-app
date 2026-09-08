"""app/routers/eod.py — /eod (End-of-day checklist).

Built on app/rms/workflow.py which has fresh_eod_checklist() + eod_progress().
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.workflow import eod_progress, fresh_eod_checklist
from app.services.template_render import render

router = APIRouter(prefix="/eod", dependencies=[Depends(require_login)])


def get_session(request: Request) -> Session:
    return request.app.state.session_factory()


@router.get("", response_class=HTMLResponse)
def eod_view(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    """Show today's EOD checklist."""
    items = fresh_eod_checklist()
    progress = eod_progress(items)
    return render(request, "eod.html", {
        "items": items,
        "progress": progress,
    })


__all__ = ["router"]
