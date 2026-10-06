"""app/routers/produccion/templates_ops.py - Weekly template POST routes.

Sazon-Improvement v2 (2026-10-06) Phase E step 4: extracted from
app/routers/produccion/_full.py lines 931-1153. Behavior unchanged.

Routes (2 POSTs):
  POST /produccion/template            - set a weekday's product qty
  POST /produccion/template/fork-week  - copy this week's template to a target week
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.dependencies import get_session
from app.rms.models import (
    Product,
    ProductionPlanOverride,
)
from app.rms.observability import record_audit
from app.rms.production import get_weekly_template, plan_production
from app.routers.produccion._helpers import _asuncion_today
from app.routers.produccion._router import router
from app.services.template_render import render


@router.post("/template")
def produccion_template_set(
    request: Request,
    weekday: int = Form(...),
    product_id: int = Form(...),
    qty: float = Form(...),
    notes: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Set a single (weekday, product) row in the weekly template.

    PRO-01: this saves a row to production_plan_template. Affects every
    occurrence of this weekday from now on, until the row is changed.
    """
    from app.rms.rate_limit import is_write_rate_limited

    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )
    if not (0 <= weekday <= 6):
        raise HTTPException(status_code=400, detail="weekday debe ser 0 (Lun) a 6 (Dom)")
    if qty < 0:
        raise HTTPException(status_code=400, detail="La cantidad no puede ser negativa")
    if session.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    from app.auth import current_user_id
    from app.rms.audit import record as audit_record
    from app.rms.production import upsert_template_row

    user_id = current_user_id(request) or "operator"
    user_id = str(user_id)
    # PRODUCCION-V2 Fase 1: capture the prior template row's qty for the
    # audit log. The template doesn't carry for_date, so we record the
    # change against the NEXT occurrence of that weekday (the soonest
    # date the new qty will be in effect). This gives /accuracy a way
    # to "expand" the audit to a per-day view.
    from datetime import timedelta as _td

    from app.rms.models import ProductionPlanTemplate

    prior_template = (
        session.query(ProductionPlanTemplate)
        .filter(
            ProductionPlanTemplate.weekday == weekday,
            ProductionPlanTemplate.product_id == product_id,
        )
        .one_or_none()
    )
    old_qty = float(prior_template.qty) if prior_template is not None else None

    # Compute the next-occurrence date for for_date in the audit row.
    # If today happens to be the target weekday, use today; otherwise
    # the upcoming one. We never use a date in the past (audit rows
    # for past dates are noise). Use ASUNCION_TZ per the app's rule
    # (see app/rms/config.py + AGENTS.md "Time rules").
    today = datetime.now(ASUNCION_TZ).date()
    days_ahead = (weekday - today.weekday()) % 7
    next_occurrence = today + _td(days=days_ahead)
    upsert_template_row(
        session,
        weekday=weekday,
        product_id=product_id,
        qty=qty,
        notes=notes or None,
        updated_by=user_id,
    )
    persist_plan_audit(
        session,
        for_date=next_occurrence,
        product_id=product_id,
        old_qty=old_qty,
        new_qty=qty,
        change_source="template",
        changed_by=user_id,
        notes=notes or None,
    )

    audit_record(
        session,
        user_id=user_id,
        action="write.produccion.template",
        request=request,
        detail={"weekday": weekday, "product_id": product_id, "qty": qty},
    )
    session.commit()
    return RedirectResponse(url="/produccion?view=week", status_code=303)


@router.post("/template/fork-week")
def produccion_template_fork_week(
    request: Request,
    from_date: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """S7 Decision C2 — "Fork current week" button.

    Reads the overrides in the week containing ``from_date`` and clones
    them into the weekly template, summing qty per (weekday, product)
    across the 7 days of the source week. Existing template rows for
    the same (weekday, product) are overwritten — the operator can then
    tweak rather than type from scratch.

    Use case (audio review): "the next day is what you put the day before".
    The operator finishes a week, wants next week's template to start from
    this week's actual plan (since overrides represent what was actually
    done / sold).
    """
    from app.rms.rate_limit import is_write_rate_limited

    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )
    from datetime import datetime as _dt
    from datetime import timedelta as _td

    try:
        src = _dt.strptime(from_date, "%Y-%m-%d").replace(tzinfo=ASUNCION_TZ).date()
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="from_date debe ser YYYY-MM-DD") from None
    # Source week: Monday-of(src.date()) .. Monday+6
    monday = src - _td(days=src.weekday())
    end_exclusive = monday + _td(days=7)

    overrides = session.scalars(
        select(ProductionPlanOverride)
        .where(ProductionPlanOverride.for_date >= monday)
        .where(ProductionPlanOverride.for_date < end_exclusive)
    ).all()
    if not overrides:
        return RedirectResponse(
            url="/produccion?view=week&fork=empty",
            status_code=303,
        )

    # Sum qty per (weekday, product) across the 7-day window
    from collections import defaultdict

    bucket: dict[tuple[int, int], float] = defaultdict(float)
    for ov in overrides:
        wd = ov.for_date.weekday()  # 0=Mon .. 6=Sun
        bucket[(wd, ov.product_id)] += float(ov.qty or 0.0)

    from app.auth import current_user_id
    from app.rms.audit import record as audit_record
    from app.rms.production import upsert_template_row

    user_id = current_user_id(request) or "operator"
    user_id = str(user_id)
    # PRODUCCION-V2 Fase 1: audit each template row we overwrite. The
    # template doesn't have for_date, so we log against the next
    # occurrence (same convention as /template above).
    from datetime import timedelta as _td_fork

    from app.rms.models import ProductionPlanTemplate

    today = datetime.now(ASUNCION_TZ).date()
    rows_written = 0
    for (wd, pid), qty in bucket.items():
        if qty <= 0:
            continue
        prior_fork_template = (
            session.query(ProductionPlanTemplate)
            .filter(
                ProductionPlanTemplate.weekday == wd,
                ProductionPlanTemplate.product_id == pid,
            )
            .one_or_none()
        )
        old_qty = (
            float(prior_fork_template.qty) if prior_fork_template is not None else None
        )
        days_ahead = (wd - today.weekday()) % 7
        next_occurrence = today + _td_fork(days=days_ahead)
        upsert_template_row(
            session,
            weekday=wd,
            product_id=pid,
            qty=qty,
            notes=None,
            updated_by=user_id,
        )
        persist_plan_audit(
            session,
            for_date=next_occurrence,
            product_id=pid,
            old_qty=old_qty,
            new_qty=qty,
            change_source="fork_week",
            changed_by=user_id,
            notes=f"forked from {monday.isoformat()}..{end_exclusive.isoformat()}",
        )
        rows_written += 1

    audit_record(
        session,
        user_id=user_id,
        action="write.produccion.template.fork_week",
        request=request,
        detail={
            "from_date": from_date,
            "week_start": monday.isoformat(),
            "rows_written": rows_written,
        },
    )
    session.commit()
    return RedirectResponse(
        url=f"/produccion?view=week&fork=ok&rows={rows_written}",
        status_code=303,
    )


__all__ = ["router"]


# --- Live forecast API for /pedidos/nuevo (T-2026-10-01) ---
# Pings when the operator picks a product+qty in the pedido form,
# returns the qty the production plan will bake for that date so the
# form can warn "Pediste N pero el plan dice M".
