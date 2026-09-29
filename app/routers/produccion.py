"""app/routers/produccion.py — /produccion (Production worksheet + calendar).

Views:
  day   (default) — one day's plan table (backward compat: for_date param)
  week  — 7-day grid via the calendar macro (Saskia: "calendario cíclico
          por semana")
  month — month grid via the calendar macro

POST /produccion/override — per-day manual qty override (query-param
persistence: the override lands in the redirect URL as ov_{product_id}
so the day view re-renders with manual_forecast applied. Nothing is
stored in the DB — an override is a what-if re-plan, not an edit.)

Seasonal-multiplier editor intentionally absent: blocked on T-0.1
(forecast_source semantics clarification with Saskia).
"""
from __future__ import annotations

import calendar as _calendar
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.auth import require_login_or_disabled as require_login
from app.rms.config import ASUNCION_TZ
from app.rms.dependencies import get_session
from app.rms.models import Pedido, PedidoLine, Product, ProductionPlanOverride, Recipe, Sale
from app.rms.production import plan_production
from app.services.template_render import render

router = APIRouter(prefix="/produccion", dependencies=[Depends(require_login)])

FORECAST_SOURCE_LABELS = {
    "rolling_14d_avg": "Sugerido por ventas",
    "seasonal_event": "Sugerido por evento",
    "manual": "Manual",
    "template": "Plan semanal",  # PRO-01
    "override": "Ajuste del día",  # PRO-01
}
FORECAST_SOURCE_HELP = {
    "rolling_14d_avg": "Calculado del promedio de ventas de los últimos 14 días",
    "seasonal_event": "Ajustado por evento estacional en la fecha",
    "manual": "Cantidad cargada a mano",
    "template": "Viene del plan semanal (se repite cada semana)",
    "override": "Anulado solo para esta fecha; no afecta otras semanas",
}


def _asuncion_today() -> date:
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo

    return datetime.now(timezone.utc).astimezone(ZoneInfo("America/Asuncion")).date()


def _week_monday(any_date: date) -> date:
    return any_date - timedelta(days=any_date.weekday())


def _day_counts(session: Session, days: list[date]) -> dict[str, int]:
    """item_count per day: number of products with qty>0 in that day's plan."""
    counts: dict[str, int] = {}
    for d in days:
        plan = plan_production(session, for_date=d)
        counts[d.isoformat()] = len([r for r in plan.rows if r.qty_to_produce > 0])
    return counts


def _parse_overrides(params: object) -> dict[int, float]:
    """Override params look like ov_12=10.5 -> {12: 10.5}."""
    out: dict[int, float] = {}
    for key, value in params.items():
        if key.startswith("ov_"):
            try:
                out[int(key[3:])] = float(value)
            except (TypeError, ValueError):
                continue
    return out


@router.get("", response_class=HTMLResponse)
def produccion_worksheet(
    request: Request,
    view: str = Query("day", pattern="^(day|week|month)$"),
    for_date: date | None = Query(None),
    week: date | None = Query(None),
    month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Production plan: day table, week grid, or month grid."""
    today = _asuncion_today()
    overrides = _parse_overrides(request.query_params)

    if view == "week":
        week_start = _week_monday(week or today)
        days = [week_start + timedelta(days=i) for i in range(7)]
        # Build week plan: aggregate plan_production() across all 7 days
        product_rows: dict[int, dict] = {}
        # Ingredient aggregation across the week
        ing_required: dict[int, dict] = {}  # ing_id -> {name, unit, required, stock}
        for d in days:
            plan = plan_production(session, for_date=d)
            for r in plan.rows:
                if r.qty_to_produce <= 0:
                    continue
                if r.product_id not in product_rows:
                    product_rows[r.product_id] = {
                        "product_name": r.product_name,
                        "recipe_id": r.recipe_id,
                        "daily_qtys": [0.0] * 7,
                    }
                day_idx = (d - week_start).days
                product_rows[r.product_id]["daily_qtys"][day_idx] = r.qty_to_produce
            # Aggregate ingredients
            for ln in plan.lines:
                if ln.ingredient_id not in ing_required:
                    ing_required[ln.ingredient_id] = {
                        "ingredient_name": ln.ingredient_name,
                        "unit": ln.unit,
                        "qty_required": 0.0,
                        "stock_on_hand": ln.stock_on_hand,
                        "ingredient_id": ln.ingredient_id,
                    }
                ing_required[ln.ingredient_id]["qty_required"] += ln.qty_required

        week_plan_rows = [
            {"product_name": v["product_name"], "product_id": pid,
             "recipe_id": v["recipe_id"], "daily_qtys": v["daily_qtys"]}
            for pid, v in sorted(product_rows.items(), key=lambda x: x[1]["product_name"])
        ]
        week_ingredients = sorted(ing_required.values(), key=lambda x: x["ingredient_name"])
        prev_week = (week_start - timedelta(days=7)).isoformat()
        next_week = (week_start + timedelta(days=7)).isoformat()

        # Sales data for this week (actual sales in the period)
        from datetime import timezone as tz_cls
        week_end_dt = datetime.combine(week_start + timedelta(days=6), datetime.max.time()).replace(tzinfo=tz_cls.utc)
        week_start_dt = datetime.combine(week_start, datetime.min.time()).replace(tzinfo=tz_cls.utc)
        sales_rows = session.execute(
            select(
                Sale.product_id, Product.name, func.sum(Sale.qty), func.count(Sale.id)
            )
            .join(Product, Sale.product_id == Product.id)
            .where(Sale.sold_at >= week_start_dt, Sale.sold_at <= week_end_dt, Sale.voided_at.is_(None))
            .group_by(Sale.product_id, Product.name)
            .order_by(func.sum(Sale.qty).desc())
        ).all()
        week_sales = [{"product_id": r[0], "product_name": r[1], "total_qty": float(r[2]), "n_sales": r[3]} for r in sales_rows]

        return render(request, "produccion.html", {
            "view": "week",
            "week_start": week_start.strftime("%d %b %Y"),
            "weekdays": ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"],
            "week_plan": type("obj", (object,), {"rows": week_plan_rows})(),
            "week_ingredients": week_ingredients,
            "prev_week_iso": prev_week,
            "next_week_iso": next_week,
            "week_sales": week_sales,
        })

    if view == "month":
        if month:
            year, mon = (int(x) for x in month.split("-"))
        else:
            year, mon = today.year, today.month
        ndays = _calendar.monthrange(year, mon)[1]
        days = [date(year, mon, d) for d in range(1, ndays + 1)]
        # Build month plan: aggregate plan_production() across all days
        product_rows: dict[int, dict] = {}
        ing_required: dict[int, dict] = {}
        for d in days:
            plan = plan_production(session, for_date=d)
            for r in plan.rows:
                if r.qty_to_produce <= 0:
                    continue
                if r.product_id not in product_rows:
                    product_rows[r.product_id] = {
                        "product_name": r.product_name,
                        "recipe_id": r.recipe_id,
                        "daily_qtys": [0.0] * ndays,
                    }
                product_rows[r.product_id]["daily_qtys"][d.day - 1] = r.qty_to_produce
            for ln in plan.lines:
                if ln.ingredient_id not in ing_required:
                    ing_required[ln.ingredient_id] = {
                        "ingredient_name": ln.ingredient_name,
                        "unit": ln.unit,
                        "qty_required": 0.0,
                        "stock_on_hand": ln.stock_on_hand,
                        "ingredient_id": ln.ingredient_id,
                    }
                ing_required[ln.ingredient_id]["qty_required"] += ln.qty_required

        month_plan_rows = [
            {"product_name": v["product_name"], "product_id": pid,
             "recipe_id": v["recipe_id"], "daily_qtys": v["daily_qtys"]}
            for pid, v in sorted(product_rows.items(), key=lambda x: x[1]["product_name"])
        ]
        month_ingredients = sorted(ing_required.values(), key=lambda x: x["ingredient_name"])
        month_names = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                       "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        prev_month = date(year, mon, 1) - timedelta(days=1)
        next_month = date(year, mon, ndays) + timedelta(days=1)

        # Sales data for this month (actual sales)
        from datetime import timezone as tz_cls
        month_end_dt = datetime(year, mon, ndays, 23, 59, 59, tzinfo=tz_cls.utc)
        month_start_dt = datetime(year, mon, 1, 0, 0, 0, tzinfo=tz_cls.utc)
        sales_rows = session.execute(
            select(
                Sale.product_id, Product.name, func.sum(Sale.qty), func.count(Sale.id)
            )
            .join(Product, Sale.product_id == Product.id)
            .where(Sale.sold_at >= month_start_dt, Sale.sold_at <= month_end_dt, Sale.voided_at.is_(None))
            .group_by(Sale.product_id, Product.name)
            .order_by(func.sum(Sale.qty).desc())
        ).all()
        month_sales = [{"product_id": r[0], "product_name": r[1], "total_qty": float(r[2]), "n_sales": r[3]} for r in sales_rows]
        total_revenue = session.execute(
            select(func.sum(Sale.qty * Sale.unit_price_gs)).where(
                Sale.sold_at >= month_start_dt, Sale.sold_at <= month_end_dt, Sale.voided_at.is_(None)
            )
        ).scalar() or 0

        return render(request, "produccion.html", {
            "view": "month",
            "year": year,
            "month": mon,
            "month_name": month_names[mon],
            "month_days": list(range(1, ndays + 1)),
            "month_plan": type("obj", (object,), {"rows": month_plan_rows})(),
            "month_ingredients": month_ingredients,
            "prev_month_iso": prev_month.strftime("%Y-%m"),
            "next_month_iso": next_month.strftime("%Y-%m"),
            "month_sales": month_sales,
            "month_revenue_gs": int(total_revenue),
        })

    # day view (default)
    plan = plan_production(session, for_date=for_date, manual_forecast=overrides or None)

    # US 4.4 — Surface incoming pedidos for the SAME day as a "kitchen ticket"
    # panel so the cook sees "we owe 3 tortas + 1 cookie tray today" alongside
    # the demand-driven production plan. Includes pending/confirmed/ready
    # (not fulfilled — those are done — and not cancelled — those are gone).
    pending_pedidos = []
    target_date = for_date or _asuncion_today()
    pedido_rows = session.execute(
        select(Pedido)
        .options(selectinload(Pedido.lines).selectinload(PedidoLine.product))
        .where(
            Pedido.promised_date == target_date,
            Pedido.status.in_(("pending", "confirmed", "ready")),
        )
        .order_by(Pedido.promised_time.asc().nullslast(), Pedido.created_at.asc())
    ).scalars().all()
    for p in pedido_rows:
        line_items = []
        for ln in p.lines:
            if ln.qty <= 0:
                continue
            line_items.append({
                "product_id": ln.product_id,
                "product_name": ln.product.name if ln.product else "(deleted)",
                "qty": float(ln.qty),
                "unit_price_gs": ln.unit_price_gs,
            })
        if not line_items:
            continue
        pending_pedidos.append({
            "id": p.id,
            "customer_name": p.customer_name or "(sin nombre)",
            "customer_phone": p.customer_phone or "",
            "promised_time": p.promised_time or "",
            "channel": p.channel,
            "status": p.status,
            "notes": p.notes or "",
            "line_items": line_items,
        })

    # P-14: template produccion.html:102 references daily_target but the day
    # view never passed it, raising Jinja UndefinedError. Compute target
    # (sum of plan rows) and actual (sum of non-voided Sale.qty for the day).
    daily_target = sum(
        r.qty_to_produce for r in plan.rows if r.qty_to_produce > 0
    )
    from datetime import datetime as _dt_cls
    from datetime import timezone as _tz_cls
    target_start = datetime.combine(target_date, _dt_cls.min.time()).replace(tzinfo=_tz_cls.utc)
    target_end = datetime.combine(target_date, _dt_cls.max.time()).replace(tzinfo=_tz_cls.utc)
    daily_actual = session.execute(
        select(func.sum(Sale.qty)).where(
            Sale.sold_at >= target_start,
            Sale.sold_at <= target_end,
            Sale.voided_at.is_(None),
        )
    ).scalar() or 0

    return render(request, "produccion.html", {
        "plan": plan,
        "for_date": plan.for_date.isoformat() if plan.for_date else "",
        "view": "day",
        "source_labels": FORECAST_SOURCE_LABELS,
        "source_help": FORECAST_SOURCE_HELP,
        "overrides": overrides,
        "recipes": session.execute(
            select(Recipe).order_by(Recipe.name)
        ).scalars().all(),
        "pending_pedidos": pending_pedidos,
        "daily_target": daily_target,
        "daily_actual": float(daily_actual),
    })


@router.post("/override")
def produccion_override(
    request: Request,
    for_date: date = Form(...),
    product_id: int = Form(...),
    qty: float = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Per-day manual qty override.

    PRO-01: this saves a row to production_plan_override (date-scoped). The
    weekly template is NOT affected — only this specific date. If qty is 0,
    the override row is removed (so the weekly template takes over again).
    """
    from app.rms.rate_limit import is_write_rate_limited
    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )
    if qty < 0:
        raise HTTPException(status_code=400, detail="La cantidad no puede ser negativa")
    if session.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    from app.auth import current_user_id
    from app.rms.audit import record as audit_record
    from app.rms.models import ProductionPlanOverride
    from app.rms.production import upsert_override

    user_id = current_user_id(request) or "operator"
    user_id = str(user_id)
    if qty == 0:
        # Remove the override so the weekly template can take over
        existing = session.query(ProductionPlanOverride).filter(
            ProductionPlanOverride.product_id == product_id,
            ProductionPlanOverride.for_date == for_date,
        ).one_or_none()
        if existing:
            session.delete(existing)
            session.flush()
    else:
        upsert_override(
            session,
            product_id=product_id,
            for_date=for_date,
            qty=qty,
            updated_by=user_id,
        )

    audit_record(
        session,
        user_id=user_id,
        action="write.produccion.override",
        request=request,
        detail={"product_id": product_id, "for_date": for_date.isoformat(), "qty": qty},
    )
    session.commit()
    return RedirectResponse(
        url=f"/produccion?for_date={for_date.isoformat()}",
        status_code=303,
    )


# --- PRO-01: weekly template ---

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
    upsert_template_row(
        session,
        weekday=weekday,
        product_id=product_id,
        qty=qty,
        notes=notes or None,
        updated_by=user_id,
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
    rows_written = 0
    for (wd, pid), qty in bucket.items():
        if qty <= 0:
            continue
        upsert_template_row(
            session,
            weekday=wd,
            product_id=pid,
            qty=qty,
            notes=None,
            updated_by=user_id,
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
