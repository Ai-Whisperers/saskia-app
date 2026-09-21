"""app/routers/eod.py — /eod (End-of-day checklist).

Built on app/rms/workflow.py which has fresh_eod_checklist() + eod_progress().
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.dependencies import get_session
from app.rms.production import plan_production
from app.rms.workflow import eod_progress, fresh_eod_checklist
from app.services.template_render import render

router = APIRouter(prefix="/eod", dependencies=[Depends(require_login)])


@router.get("", response_class=HTMLResponse)
def eod_view(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    """Show today's EOD checklist + today's production plan summary."""
    items = fresh_eod_checklist()
    progress = eod_progress(items)
    # Today's production plan — "se debe registrar cuánto de la producción se completó"
    # (Saskia review, T5). We display the forecast so she can reconcile against
    # what was actually produced. Persistence of completions deferred to a future
    # phase; this view surfaces the forecast side.
    from datetime import date as _date

    today_plan = plan_production(session, for_date=_date.today())
    return render(request, "eod.html", {
        "items": items,
        "progress": progress,
        "today_plan": today_plan,
        "today_iso": _date.today().isoformat(),
    })


__all__ = ["router"]
