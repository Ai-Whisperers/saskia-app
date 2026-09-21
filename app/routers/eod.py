"""app/routers/eod.py — /eod (End-of-day checklist).

Built on app/rms/workflow.py which has fresh_eod_checklist() + eod_progress().
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.dependencies import get_session
from app.rms.eod_completions import completions_for_date, upsert_completion
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
    today = date.today()
    today_plan = plan_production(session, for_date=today)
    completions = completions_for_date(session, today)
    return render(request, "eod.html", {
        "items": items,
        "progress": progress,
        "today_plan": today_plan,
        "completions": completions,
        "today_iso": today.isoformat(),
    })


@router.post("/completar")
def eod_completar(
    request: Request,
    product_id: int = Form(...),
    for_date: date = Form(...),
    completed_qty: float = Form(...),
    notes: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Record how much of a planned product was actually produced (T5)."""
    from app.rms.rate_limit import is_write_rate_limited
    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )
    try:
        upsert_completion(
            session,
            product_id=product_id,
            for_date=for_date,
            completed_qty=completed_qty,
            notes=notes or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Producto no encontrado") from exc

    from app.auth import current_user_id
    from app.rms.audit import record as audit_record
    audit_record(
        session,
        user_id=current_user_id(request) or "operator",
        action="write.eod.completion",
        request=request,
        detail={"product_id": product_id, "for_date": for_date.isoformat(), "completed_qty": completed_qty},
    )
    session.commit()
    return RedirectResponse(url="/eod", status_code=303)


__all__ = ["router"]
