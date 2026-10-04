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
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.auth import require_login_or_disabled as require_login
from app.rms.config import ASUNCION_TZ
from app.rms.dependencies import get_session
from app.rms.eod_completions import upsert_completion as _upsert_completion
from app.rms.models import Pedido, PedidoLine, Product, ProductionPlanOverride, Recipe, Sale
from app.rms.observability import record_audit
from app.rms.plan_accuracy import compute_plan_accuracy, date_range_presets
from app.rms.production import get_weekly_template, plan_production
from app.services.template_render import render

router = APIRouter(prefix="/produccion", dependencies=[Depends(require_login)])

FORECAST_SOURCE_LABELS = {
    "rolling_14d_avg": "Sugerido por ventas",
    "oculto": "Oculto (sin auto-sugerencia)",
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

    # Sprint 1: pull actual production completions for the day so the
    # shift-execution table can render pre-filled "Progreso" values
    # instead of blank inputs.
    from app.rms.eod_completions import completions_for_date as _eod_for_date
    completions_by_pid = _eod_for_date(session, target_date)

    # Sprint 3: demand fusion — count how many units of each product are
    # already owed by pedidos for the same day. We surface this as a
    # per-row "+N por pedidos" badge so the cook knows the plan number
    # is a baseline, not the final bake count.
    ped_units_by_pid: dict[int, float] = {}
    for p in pedido_rows:
        for ln in p.lines:
            if ln.qty <= 0:
                continue
            ped_units_by_pid[ln.product_id] = (
                ped_units_by_pid.get(ln.product_id, 0.0) + float(ln.qty)
            )

    # Wrap each ProductionRow with the completion + pedido data the
    # template needs (ProductionRow is a dataclass — attribute injection
    # is safe inside this function but we don't mutate the original).
    # T-2026-10-04 (P0): also include recipe yield info so the kitchen
    # sees "1 × Docena muffins (12 und)" instead of bare "1".
    recipe_by_id = {r.id: r for r in (session.execute(
        select(Recipe).order_by(Recipe.name)
    ).scalars().all())}
    product_by_id = {p.id: p for p in (session.execute(
        select(Product).order_by(Product.name)
    ).scalars().all())}

    plan_rows_view = [
        {
            "product_id": r.product_id,
            "product_name": r.product_name,
            "recipe_id": r.recipe_id,
            "qty_to_produce": r.qty_to_produce,
            "forecast_source": r.forecast_source,
            "confidence_pct": r.confidence_pct,
            "completed_qty": completions_by_pid.get(r.product_id, 0.0),
            "pending_pedido_qty": ped_units_by_pid.get(r.product_id, 0.0),
            "is_ad_hoc": False,
            # T-2026-10-04 (P0): batch-size context.
            # recipe.yield_qty + yield_unit describe one batch (e.g., 12 muffins).
            # We don't multiply here — that would be a unit-conversion decision.
            # We just expose the labels so the template shows them.
            "batch_qty": (
                recipe_by_id[r.recipe_id].yield_qty
                if r.recipe_id and r.recipe_id in recipe_by_id
                and recipe_by_id[r.recipe_id].yield_qty
                else None
            ),
            "batch_unit": (
                recipe_by_id[r.recipe_id].yield_unit
                if r.recipe_id and r.recipe_id in recipe_by_id
                and recipe_by_id[r.recipe_id].yield_qty
                else None
            ),
            "portion_label": (
                product_by_id[r.product_id].portion_label
                if r.product_id in product_by_id
                else None
            ),
        }
        for r in plan.rows
    ]

    # Ad-hoc bakes: products COMPLETED for the day but NOT in the plan
    # row list. These are the walk-ins / on-the-fly decisions that the
    # forecast engine never proposed but Saskia actually produced.
    planned_pids = {r["product_id"] for r in plan_rows_view}
    for pid, qty in completions_by_pid.items():
        if pid in planned_pids:
            continue
        prod_obj = session.get(Product, pid)
        if prod_obj is None:
            continue
        plan_rows_view.append({
            "product_id": pid,
            "product_name": prod_obj.name,
            "recipe_id": None,
            "qty_to_produce": 0.0,
            "forecast_source": "ad_hoc",
            "confidence_pct": 100,
            "completed_qty": qty,
            "pending_pedido_qty": ped_units_by_pid.get(pid, 0.0),
            "is_ad_hoc": True,
            "batch_qty": None,
            "batch_unit": None,
            "portion_label": prod_obj.portion_label if prod_obj else None,
        })

    # PRO-TEMPLATE-NUDGE: aviso si no hay template para el weekday de for_date
    _weekday = plan.for_date.weekday() if plan.for_date else 0
    _template_rows = get_weekly_template(session).get(_weekday, {})
    _has_sales = session.scalar(
        select(func.count()).select_from(Sale).where(
            Sale.product_id.in_(select(Product.id)),
        )
    ) or 0
    template_nudge = (not _template_rows) and _has_sales > 0

    # T-2026-10-04 (P1): cold-start bootstrap state. Distinguish 3 cases:
    # - no_sales: zero sales ever recorded → "set up your template"
    # - no_template: sales exist but no weekly template → "promote forecasts"
    # - cold_plan: plan rows exist but all qty=1.0 → "your forecast is
    #   uniform; check data window"
    cold_start_kind = None
    if _has_sales == 0:
        cold_start_kind = "no_sales"
    elif not _template_rows:
        cold_start_kind = "no_template"
    elif all(
        getattr(r, "qty_to_produce", 0) == 1.0
        for r in plan_rows_view
    ) and len(plan_rows_view) > 0:
        cold_start_kind = "cold_plan"
    elif sum(1 for r in plan_rows_view if r["qty_to_produce"] > 0) == 0:
        cold_start_kind = "no_rows"

    return render(request, "produccion.html", {
        "plan": plan,
        "plan_rows_view": plan_rows_view,
        "template_nudge": template_nudge,
        "cold_start_kind": cold_start_kind,
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
        "shift_saved": int(request.query_params.get("shift_saved", 0)),
        "adhoc_added": request.query_params.get("adhoc_added") == "1",
        "products_for_adhoc": session.execute(
            select(Product).order_by(Product.name)
        ).scalars().all(),
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

    record_audit(
        request,
        session=session,
        action="write.production.override.set",
        target_type="production",
        target_id=product_id,
        detail={"for_date": for_date.isoformat(), "qty": qty},
    )
    session.commit()
    return RedirectResponse(
        url=f"/produccion?for_date={for_date.isoformat()}",
        status_code=303,
    )


@router.post("/override-bulk")
async def produccion_override_bulk(
    request: Request,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Bulk per-day qty overrides from /produccion/manana's unified form.

    The manana page (da0abe8 redesign) renders ONE form with per-row
    ``qty[<product_id>]`` inputs and a single Save button. This endpoint
    consumes that shape: each non-empty qty[<id>] field becomes (or clears,
    at qty=0) a date-scoped ProductionPlanOverride — same semantics as the
    single-row /produccion/override, applied N times in one commit.
    """
    from app.rms.rate_limit import is_write_rate_limited
    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )

    from app.auth import current_user_id
    from app.rms.models import Product, ProductionPlanOverride
    from app.rms.production import upsert_override

    form = await request.form()
    raw_for_date = str(form.get("for_date") or "").strip()
    try:
        for_date = date.fromisoformat(raw_for_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha inválida") from None

    user_id = str(current_user_id(request) or "operator")

    # Collect qty[<product_id>] fields
    entries: dict[int, float] = {}
    for key, value in form.items():
        if not key.startswith("qty[") or not key.endswith("]"):
            continue
        raw = str(value).strip()
        if raw == "":
            continue  # untouched row — leave the forecast as-is
        try:
            pid = int(key[4:-1])
            qty = float(raw)
        except (TypeError, ValueError):
            continue
        if qty < 0:
            raise HTTPException(
                status_code=400, detail="La cantidad no puede ser negativa"
            )
        entries[pid] = qty

    applied = 0
    for pid, qty in entries.items():
        if session.get(Product, pid) is None:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        if qty == 0:
            existing = session.query(ProductionPlanOverride).filter(
                ProductionPlanOverride.product_id == pid,
                ProductionPlanOverride.for_date == for_date,
            ).one_or_none()
            if existing:
                session.delete(existing)
                session.flush()
        else:
            upsert_override(
                session, product_id=pid, for_date=for_date, qty=qty,
                updated_by=user_id,
            )
        record_audit(
            request,
            session=session,
            action="write.production.override.set",
            target_type="production",
            target_id=pid,
            detail={"for_date": for_date.isoformat(), "qty": qty, "bulk": True},
        )
        applied += 1

    session.commit()
    return RedirectResponse(
        url=f"/produccion/manana?saved={applied}",
        status_code=303,
    )


# --- Shift execution layer (Sprint 1) ---
#
# The day view renders a "Ejecución del turno" form that lets Saskia
# mark checkboxes + enter a qty per product. Until Sprint 1 this form
# posted to /produccion/override, which IGNORED the `completed_*`
# fields and only wrote production_plan_override (which is the PLAN,
# not the actual). The actual production is what Saskia really baked;
# the helper `upsert_completion()` in app.rms.eod_completions already
# writes the right table — we just need an endpoint that accepts the
# bulk form.
#
# This endpoint iterates over form keys `done_{pid}` + `completed_{pid}`
# and writes one upsert per product with a non-zero value. Items with
# `done_{pid}` checked AND `completed_{pid} == 0` are recorded as 0
# (operator said "I marked this done but produced nothing" — honest).


@router.post("/shift-execute")
async def produccion_shift_execute(
    request: Request,
    for_date: date = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Persist actual production qty per product (the "ya salió del horno" tracker)."""
    from app.rms.rate_limit import is_write_rate_limited

    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )

    form = await request.form()
    saved = 0
    skipped = 0
    for key, value in form.multi_items():
        if not isinstance(value, str):
            # skip file uploads / non-str values
            continue
        if not key.startswith("completed_"):
            continue
        try:
            product_id = int(key.removeprefix("completed_"))
        except ValueError:
            skipped += 1
            continue
        try:
            qty = float(value)
        except (TypeError, ValueError):
            skipped += 1
            continue
        if qty < 0:
            skipped += 1
            continue
        if session.get(Product, product_id) is None:
            skipped += 1
            continue
        _upsert_completion(
            session,
            product_id=product_id,
            for_date=for_date,
            completed_qty=qty,
        )
        saved += 1

    record_audit(
        request,
        session=session,
        action="write.production.shift.execute",
        target_type="production_shift",
        target_id=for_date.isoformat(),
        detail={"saved": saved, "skipped": skipped, "for_date": for_date.isoformat()},
    )
    session.commit()
    return RedirectResponse(
        url=f"/produccion?for_date={for_date.isoformat()}&shift_saved={saved}",
        status_code=303,
    )


# --- Ad-hoc bake entry (Sprint 4) ---
#
# Saskia might bake a product that was NOT in the plan (walk-in order,
# decided on a whim, leftover ingredients). This endpoint writes a
# ProductionCompletion row with notes="ad_hoc" so the actual count
# shows up in the day view + EOD, even though the forecast engine
# never proposed it.


@router.post("/ad-hoc")
async def produccion_ad_hoc(
    request: Request,
    for_date: date = Form(...),
    product_id: int = Form(...),
    qty: float = Form(...),
    notes: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Record an unplanned bake: walked-in, decided-on-the-fly, leftovers."""
    from app.rms.rate_limit import is_write_rate_limited

    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )
    if qty <= 0:
        raise HTTPException(
            status_code=400,
            detail="La cantidad debe ser mayor a cero.",
        )
    if session.get(Product, product_id) is None:
        raise HTTPException(
            status_code=404,
            detail="Producto no encontrado",
        )

    tag = "ad_hoc"
    if notes.strip():
        tag = f"ad_hoc: {notes.strip()[:200]}"
    _upsert_completion(
        session,
        product_id=product_id,
        for_date=for_date,
        completed_qty=qty,
        notes=tag,
    )
    record_audit(
        request,
        session=session,
        action="write.production.ad_hoc",
        target_type="production_ad_hoc",
        target_id=f"{for_date.isoformat()}:{product_id}",
        detail={
            "for_date": for_date.isoformat(),
            "product_id": product_id,
            "qty": qty,
            "notes": notes.strip()[:200] or None,
        },
    )
    session.commit()
    return RedirectResponse(
        url=f"/produccion?for_date={for_date.isoformat()}&adhoc_added=1",
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


# --- Live forecast API for /pedidos/nuevo (T-2026-10-01) ---
# Pings when the operator picks a product+qty in the pedido form,
# returns the qty the production plan will bake for that date so the
# form can warn "Pediste N pero el plan dice M".
@router.get("/api/forecast")
def produccion_api_forecast(
    for_date: str = Query(...),
    product_id: int | None = Query(None, ge=1),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Return production-plan rows for a date (filtered to one product if given).

    Shape:
            {"for_date": "YYYY-MM-DD",
             "rows": [{"product_id": int, "product_name": str,
                       "qty_to_produce": float, "forecast_source": str,
                       "confidence_pct": int}, ...]}
    """
    try:
        parsed = date.fromisoformat(for_date)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"for_date inválido: {for_date!r}"
        ) from None

    plan = plan_production(session, for_date=parsed)

    rows = [
        {
            "product_id": r.product_id,
            "product_name": r.product_name,
            "qty_to_produce": float(r.qty_to_produce),
            "forecast_source": r.forecast_source,
            "confidence_pct": r.confidence_pct,
        }
        for r in plan.rows
    ]

    if product_id is not None:
        rows = [r for r in rows if r["product_id"] == product_id]

    return JSONResponse({"for_date": parsed.isoformat(), "rows": rows})


# --- P1-B2 forecast enchufado: tomorrow-focused view ---
@router.get("/manana", response_class=HTMLResponse)
def produccion_manana(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Tomorrow's production plan with confidence scores + seasonal events.

    The roadmap asks for: "mañana vas a necesitar ~120 chipitas (confianza 78%)"
    Each row shows:
      - product name + qty to produce
      - confidence % (color: <50 red, 50-75 amber, >=75 green)
      - source: rolling_14d_avg / override / template / manual
      - seasonal event note (if a calendar event applies tomorrow)

    Operators can override the qty by typing a number; the form posts to
    /produccion/override as usual.
    """
    from app.rms.config import ASUNCION_TZ
    from app.rms.seasonal import calendar_for_year

    today = datetime.now(ASUNCION_TZ).date()
    tomorrow = today + timedelta(days=1)
    # B2 (2026-10-01): /produccion/manana now uses the DOW-aware
    # forecast with a 12-week lookback. Only this surface opts in;
    # week/month views keep the legacy flat 14-day avg (unchanged).
    plan = plan_production(
        session,
        for_date=tomorrow,
        days_history=84,
        use_dow_forecast=True,
    )

    # Pull seasonal events for tomorrow's date (calendar uses SEASONAL_CALENDAR_2026)
    # The calendar dict has 'start'/'end' fields (date ranges), not 'date'.
    tomorrow_iso = tomorrow.isoformat()
    events = [
        ev for ev in calendar_for_year(tomorrow.year)
        if ev.get("start", "") <= tomorrow_iso <= ev.get("end", "")
    ]
    seasonal_multiplier = None  # already baked into plan.rows[*].qty
    seasonal_note = None
    if events:
        # Take the first event as the headline; plan.notes carries the multiplier
        head = events[0]
        seasonal_note = f"{head.get('name', 'Evento estacional')} (×{head.get('multiplier', 1.0)})"

    # Sort: highest confidence first, lowest qty last
    rows = sorted(plan.rows, key=lambda r: (-r.confidence_pct, r.product_name))

    # Total estimated production in Gs (sum of qty * product.sale_price_gs)
    products_by_id = {
        p.id: p for p in session.execute(select(Product)).scalars()
    }
    estimated_revenue_gs = 0
    for row in rows:
        p = products_by_id.get(row.product_id)
        if p is not None and p.sale_price_gs:
            estimated_revenue_gs += int(row.qty_to_produce * p.sale_price_gs)

    # Override form pre-fill (read existing overrides for tomorrow)
    from app.rms.production import get_overrides_for_date
    overrides_tomorrow = get_overrides_for_date(session, tomorrow)

    # PRO-PED (2026-09-30): pedidos confirmados con entrega/retiro mañana —
    # el planificador ve los encargos reales en la misma pantalla donde
    # planifica (antes solo vivían en Pedidos y en el card de Inicio).
    from app.rms.models import Pedido
    from app.routers.pedidos import _pedido_total_gs
    pedidos_manana = [
        {
            "id": p_.id,
            "customer_name": p_.customer_name,
            "promised_time": p_.promised_time,
            "channel": p_.channel,
            "status": p_.status,
            "total_gs": _pedido_total_gs(p_),
        }
        for p_ in session.execute(
            select(Pedido).where(
                Pedido.promised_date == tomorrow,
                Pedido.status.in_(["pending", "confirmed", "ready"]),
            ).order_by(Pedido.promised_time.nulls_last(), Pedido.id)
        ).scalars()
    ]

    return render(
        request,
        "produccion_manana.html",
        {
            "pedidos_manana": pedidos_manana,
            "today": today.isoformat(),
            "tomorrow": tomorrow.isoformat(),
            "rows": rows,
            "plan": plan,
            "seasonal_note": seasonal_note,
            "seasonal_multiplier": seasonal_multiplier,
            "estimated_revenue_gs": estimated_revenue_gs,
            "overrides_tomorrow": overrides_tomorrow,
            "low_confidence_count": sum(1 for r in rows if r.confidence_pct < 70),
        },
    )


@router.get("/print", response_class=HTMLResponse)
def produccion_print(
    request: Request,
    for_date: date | None = Query(None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Printable worksheet for the kitchen shift.

    T-2026-10-04 (P0): Bakers need a paper sheet. The day-view HTML is too
    busy (nav, banners, source explanations, ad-hoc form) to print. This
    view is a stripped-down worksheet: title, date, products, qty,
    checkboxes. No CSS-included chrome — the @media print rules in
    produccion.html + base.html hide the nav/header/footer when printing.

    The handler reuses the same plan_production() call as the day view so
    the printed sheet always matches what the operator sees on screen.
    """
    from app.rms.eod_completions import completions_for_date as _eod_for_date

    target_date = for_date or _asuncion_today()
    plan = plan_production(session, for_date=target_date)
    completions_by_pid = _eod_for_date(session, target_date)

    # T-2026-10-04 (P0): batch-size awareness — load recipe+product once
    # so each row knows its yield_qty + portion_label.
    recipes_by_id = {r.id: r for r in session.execute(
        select(Recipe).order_by(Recipe.name)
    ).scalars().all()}
    products_by_id = {p.id: p for p in session.execute(
        select(Product).order_by(Product.name)
    ).scalars().all()}

    # Build a flat list of (product, qty_to_produce, qty_completed) — one
    # row per product, no overrides, no forecast_source explanation.
    print_rows = []
    for r in plan.rows:
        if r.qty_to_produce <= 0 and r.product_id not in completions_by_pid:
            continue
        recipe = recipes_by_id.get(r.recipe_id) if r.recipe_id else None
        product = products_by_id.get(r.product_id)
        print_rows.append({
            "product_id": r.product_id,
            "product_name": r.product_name,
            "qty_to_produce": r.qty_to_produce,
            "qty_completed": completions_by_pid.get(r.product_id, 0.0),
            "recipe_id": r.recipe_id,
            # T-2026-10-04 (P0): batch info.
            "yield_qty": recipe.yield_qty if recipe and recipe.yield_qty else None,
            "yield_unit": recipe.yield_unit if recipe and recipe.yield_qty else None,
            "portion_label": product.portion_label if product else None,
        })
    # Include ad-hoc bakes (walk-ins / on-the-fly decisions that the
    # forecast never proposed but Saskia actually produced).
    planned_pids = {r["product_id"] for r in print_rows}
    for pid, qty in completions_by_pid.items():
        if pid in planned_pids:
            continue
        prod_obj = session.get(Product, pid)
        if prod_obj is None:
            continue
        print_rows.append({
            "product_id": pid,
            "product_name": prod_obj.name,
            "qty_to_produce": 0.0,
            "qty_completed": qty,
            "recipe_id": None,
            "yield_qty": None,
            "yield_unit": None,
            "portion_label": prod_obj.portion_label if prod_obj else None,
        })

    return render(request, "produccion_print.html", {
        "for_date": target_date.isoformat(),
        "print_rows": print_rows,
        "shift_saved": int(request.query_params.get("shift_saved", 0)),
    })


@router.get("/accuracy", response_class=HTMLResponse)
def produccion_accuracy(
    request: Request,
    preset: str = Query("30d", pattern="^(7d|30d|90d)$"),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """BACKLOG #29 + #33: plan-vs-actual accuracy dashboard.

    Aggregates the production plan (per day, per product) against the
    actual completions + sold quantities for the period. Surfaces
    under-baked days (ran out) and over-baked days (wasted capacity)
    per-period. Pure read-only analytics — never writes.
    """
    ranges = date_range_presets()
    start_date, end_date = ranges[preset]
    days_in_period = (end_date - start_date).days + 1

    # Build planned_qty_by_pid_day from plan_production() for each day in range.
    # We call the planner per-day; this matches the existing /produccion page
    # path so the dashboard shows exactly what the operator saw that morning.
    planned: dict[tuple[int, date], float] = {}
    cur = start_date
    while cur <= end_date:
        plan = plan_production(session, for_date=cur)
        for r in plan.rows:
            if r.qty_to_produce <= 0:
                continue
            planned[(r.product_id, cur)] = planned.get(
                (r.product_id, cur), 0.0
            ) + float(r.qty_to_produce)
        cur = cur + timedelta(days=1)

    report = compute_plan_accuracy(session, start_date, end_date, planned)

    return render(
        request,
        "produccion_accuracy.html",
        {
            "preset": preset,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days_in_period": days_in_period,
            "report": report,
        },
    )
