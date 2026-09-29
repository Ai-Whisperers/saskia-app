"""app/routers/eod.py — /eod (End-of-day checklist).

Built on app/rms/workflow.py which has fresh_eod_checklist() + eod_progress().
"""
from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.config import ASUNCION_TZ
from app.rms.dependencies import get_session
from app.rms.eod_completions import completions_for_date, upsert_completion
from app.rms.errors import BadRequest
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
    today = datetime.now(ASUNCION_TZ).date()
    today_plan = plan_production(session, for_date=today)
    completions = completions_for_date(session, today)

    # Load saved EOD checklist progress from app_meta so refreshing the
    # page shows the operator's checked items.
    saved_keys = set()
    saved_notes = ""
    saved_prefix = f"eod_check_{today.isoformat()}_"
    saved_notes_key = f"eod_notes_{today}"
    from app.rms.models import AppMeta
    rows = session.scalars(
        select(AppMeta).where(AppMeta.key.like(f"{saved_prefix}%"))
    ).all()
    for r in rows:
        # key is "eod_check_<date>_<item_key>"
        item_key = r.key[len(saved_prefix):]
        if r.value == "1":
            saved_keys.add(item_key)
    notes_row = session.scalar(
        select(AppMeta).where(AppMeta.key == saved_notes_key)
    )
    if notes_row:
        saved_notes = notes_row.value or ""

    # Mark each checklist item as DONE using the saved set so the form
    # renders with the operator's progress preserved across reloads.
    from app.rms.workflow import EODItemStatus
    for item in items:
        if item.key in saved_keys:
            item.status = EODItemStatus.DONE

    # CIE-02: restock step — show ingredients below minimum with a link to
    # /reorder. Checking the close step means she has looked at it.
    from app.rms.reorder import compute_reorder_list
    reorder_items = compute_reorder_list(session)
    # Cap at top 5 most urgent for the dashboard
    reorder_items_top = reorder_items[:5]
    reorder_count = len(reorder_items)
    reorder_total_gs = sum(i.estimated_cost_gs for i in reorder_items if i.has_price)

    return render(request, "eod.html", {
        "items": items,
        "progress": progress,
        "today_plan": today_plan,
        "completions": completions,
        "today_iso": today.isoformat(),
        "saved_notes": saved_notes,
        # CIE-02: restock context for the close
        "reorder_items": reorder_items_top,
        "reorder_count": reorder_count,
        "reorder_total_gs": reorder_total_gs,
    })


@router.post("/check")
def eod_check_save(
    request: Request,
    session: Session = Depends(get_session),
    cash_count: str = Form(""),
    sales_reconciled: str = Form(""),
    low_stock_reviewed: str = Form(""),
    ingredients_reordered: str = Form(""),
    waste_logged: str = Form(""),
    tomorrow_prep: str = Form(""),
    cash_deposit: str = Form(""),
    equipment_cleaned: str = Form(""),
    receipts_filed: str = Form(""),
    notes_for_next: str = Form(""),
) -> RedirectResponse:
    """Persist the operator's EOD checklist progress.

    The form submits one checkbox per checklist item (HTML input `name={key}`).
    Each item's "done" state is stored in app_meta so it survives a page
    reload. The notes_for_next textarea is also persisted (Text column on
    app_meta).
    """
    from datetime import datetime, timezone

    from app.rms.models import AppMeta

    today = datetime.now(ASUNCION_TZ).date().isoformat()
    now_iso = datetime.now(timezone.utc).isoformat()
    checkboxes = {
        "cash_count": cash_count,
        "sales_reconciled": sales_reconciled,
        "low_stock_reviewed": low_stock_reviewed,
        "ingredients_reordered": ingredients_reordered,
        "waste_logged": waste_logged,
        "tomorrow_prep": tomorrow_prep,
        "cash_deposit": cash_deposit,
        "equipment_cleaned": equipment_cleaned,
        "receipts_filed": receipts_filed,
    }
    for key, value in checkboxes.items():
        is_done = value in ("on", "true", "1", "yes")
        meta_key = f"eod_check_{today}_{key}"
        existing = session.scalar(select(AppMeta).where(AppMeta.key == meta_key))
        if is_done:
            if existing:
                existing.value = "1"
                existing.updated_at = now_iso
            else:
                session.add(AppMeta(key=meta_key, value="1", updated_at=now_iso))
        elif existing:
            session.delete(existing)

    # Notes for next shift (optional free text)
    if notes_for_next.strip():
        meta_key = f"eod_notes_{today}"
        existing = session.scalar(select(AppMeta).where(AppMeta.key == meta_key))
        if existing:
            existing.value = notes_for_next.strip()[:2000]
            existing.updated_at = now_iso
        else:
            session.add(AppMeta(
                key=meta_key, value=notes_for_next.strip()[:2000], updated_at=now_iso,
            ))

    session.commit()
    return RedirectResponse(url="/eod?flash=Cierre+guardado", status_code=303)


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
        # BadRequest inherits HTTPException via the global handler, but
        # now carries reason_code="bad_request" + AppError.context for
        # the audit log. The original str(exc) is preserved via
        # `cause` so the Python repr stays in the local traceback
        # (visible to operators) but the user sees a clean Spanish
        # message (no SQLAlchemy/internal text leak).
        raise BadRequest(
            "Datos inválidos en el cierre del día.",
            context={"original_error": str(exc)},
        ) from exc
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
