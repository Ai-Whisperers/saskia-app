"""app/routers/produccion.py — /produccion (Production worksheet + calendar).

Views:
  day   (default) — one day's plan table (backward compat: for_date param)
  week  — 7-day grid via the calendar macro (the operator: "calendario cíclico
          por semana")
  month — month grid via the calendar macro

POST /produccion/override — per-day manual qty override (query-param
persistence: the override lands in the redirect URL as ov_{product_id}
so the day view re-renders with manual_forecast applied. Nothing is
stored in the DB — an override is a what-if re-plan, not an edit.)

Seasonal-multiplier editor intentionally absent: blocked on T-0.1
(forecast_source semantics clarification with the operator).
"""

from __future__ import annotations

import calendar as _calendar
import csv
import io
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.auth import require_login_or_disabled as require_login
from app.rms.config import ASUNCION_TZ
from app.rms.dependencies import get_session
from app.rms.eod_completions import close_day_for_product
from app.rms.eod_completions import completions_for_date as get_day_completions
from app.rms.eod_completions import upsert_completion as _upsert_completion
from app.rms.models import (
    FreezerTemperatureLog,  # B.6 HACCP freezer temp log
    Ingredient,
    Pedido,
    PedidoLine,
    Product,
    ProductionClosedDay,
    ProductionPlanOverride,
    Recipe,
    Sale,
    WasteLog,
)
from app.rms.observability import record_audit
from app.rms.plan_accuracy import compute_plan_accuracy, date_range_presets
from app.rms.production import get_weekly_template, plan_production
from app.rms.production_demand import get_demand, persist_plan_audit
from app.routers.produccion._helpers import (
    CONFIDENCE_BANDS,
    DEFAULT_BAKE_START_HOUR,
    FORECAST_SOURCE_HELP,
    FORECAST_SOURCE_LABELS,
    SOURCE_BUCKETS,
    _asuncion_today,
    _batch_surplus,
    _confidence_band_for_pct,
    _current_user_display_name,
    _day_counts,
    _fermentation_reminder,
    _parse_overrides,
    _week_monday,
    source_to_bucket,
)
# Sazon-Improvement v2 (2026-10-06) Phase E: the HACCP + substitution
# helpers are now defined in app/routers/produccion/analytics.py.
# The day-view worksheet still uses them, so we re-import here.
from app.routers.produccion.analytics import (
    _build_substitution_suggestions,
    _count_haccp_missing_for_date,
    _get_haccp_latest_for_date,
    _haccp_alert_for_entry,
)
from app.routers.produccion._router import router
from app.services.template_render import render

@router.get("", response_class=HTMLResponse)
def produccion_worksheet(
    request: Request,
    view: str = Query("day", pattern="^(day|week|month)$"),
    for_date: date | None = Query(None),
    week: date | None = Query(None),
    month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    # T-2026-10-04 (D.2): shift-context deep-link. Cooks get a WhatsApp
    # message like "Mirá /produccion?for_date=2026-10-05&shift=PM" — the
    # page surfaces a "Turno PM" badge so they know which shift's
    # quantities to mark. The shift param is purely visual (production
    # data is per-date, not per-shift) but it prevents the
    # AM-vs-PM-confusion footgun where one cook updates the wrong
    # column. Validated to AM|PM|empty.
    shift: str = Query("", pattern="^(AM|PM)?$"),
    # PRODUCCION-V2 cutover (2026-10-05): default is now 'v2' (the
    # DEMANDA-column grilla). 'v1' is removed — passing ?ui=v1 returns
    # 422. To temporarily roll back, set the
    # `production.ui_version_default` setting to "v1" (the route reads
    # it on startup). See docs/plans/2026-10-05-produccion-v2-spec.md
    # §"UI v2 cutover" for the rollout plan.
    ui: str = Query("v2", pattern="^v2$"),
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
            {
                "product_name": v["product_name"],
                "product_id": pid,
                "recipe_id": v["recipe_id"],
                "daily_qtys": v["daily_qtys"],
            }
            for pid, v in sorted(product_rows.items(), key=lambda x: x[1]["product_name"])
        ]
        week_ingredients = sorted(ing_required.values(), key=lambda x: x["ingredient_name"])
        prev_week = (week_start - timedelta(days=7)).isoformat()
        next_week = (week_start + timedelta(days=7)).isoformat()

        # Sales data for this week (actual sales in the period)
        from datetime import timezone as tz_cls

        week_end_dt = datetime.combine(week_start + timedelta(days=6), datetime.max.time()).replace(
            tzinfo=tz_cls.utc
        )
        week_start_dt = datetime.combine(week_start, datetime.min.time()).replace(tzinfo=tz_cls.utc)
        sales_rows = session.execute(
            select(Sale.product_id, Product.name, func.sum(Sale.qty), func.count(Sale.id))
            .join(Product, Sale.product_id == Product.id)
            .where(
                Sale.sold_at >= week_start_dt, Sale.sold_at <= week_end_dt, Sale.voided_at.is_(None)
            )
            .group_by(Sale.product_id, Product.name)
            .order_by(func.sum(Sale.qty).desc())
        ).all()
        week_sales = [
            {"product_id": r[0], "product_name": r[1], "total_qty": float(r[2]), "n_sales": r[3]}
            for r in sales_rows
        ]

        return render(
            request,
            "produccion.html",
            {
                "view": "week",
                "week_start": week_start.strftime("%d %b %Y"),
                "weekdays": ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"],
                "week_plan": type("obj", (object,), {"rows": week_plan_rows})(),
                "week_ingredients": week_ingredients,
                "prev_week_iso": prev_week,
                "next_week_iso": next_week,
                "week_sales": week_sales,
            },
        )

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
            {
                "product_name": v["product_name"],
                "product_id": pid,
                "recipe_id": v["recipe_id"],
                "daily_qtys": v["daily_qtys"],
            }
            for pid, v in sorted(product_rows.items(), key=lambda x: x[1]["product_name"])
        ]
        month_ingredients = sorted(ing_required.values(), key=lambda x: x["ingredient_name"])
        month_names = [
            "",
            "Enero",
            "Febrero",
            "Marzo",
            "Abril",
            "Mayo",
            "Junio",
            "Julio",
            "Agosto",
            "Septiembre",
            "Octubre",
            "Noviembre",
            "Diciembre",
        ]
        prev_month = date(year, mon, 1) - timedelta(days=1)
        next_month = date(year, mon, ndays) + timedelta(days=1)

        # Sales data for this month (actual sales)
        from datetime import timezone as tz_cls

        month_end_dt = datetime(year, mon, ndays, 23, 59, 59, tzinfo=tz_cls.utc)
        month_start_dt = datetime(year, mon, 1, 0, 0, 0, tzinfo=tz_cls.utc)
        sales_rows = session.execute(
            select(Sale.product_id, Product.name, func.sum(Sale.qty), func.count(Sale.id))
            .join(Product, Sale.product_id == Product.id)
            .where(
                Sale.sold_at >= month_start_dt,
                Sale.sold_at <= month_end_dt,
                Sale.voided_at.is_(None),
            )
            .group_by(Sale.product_id, Product.name)
            .order_by(func.sum(Sale.qty).desc())
        ).all()
        month_sales = [
            {"product_id": r[0], "product_name": r[1], "total_qty": float(r[2]), "n_sales": r[3]}
            for r in sales_rows
        ]
        total_revenue = (
            session.execute(
                select(func.sum(Sale.qty * Sale.unit_price_gs)).where(
                    Sale.sold_at >= month_start_dt,
                    Sale.sold_at <= month_end_dt,
                    Sale.voided_at.is_(None),
                )
            ).scalar()
            or 0
        )

        return render(
            request,
            "produccion.html",
            {
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
            },
        )

    # day view (default)
    plan = plan_production(session, for_date=for_date, manual_forecast=overrides or None)

    # T-2026-10-04 (P1): Closed-day flag — if for_date is marked as closed,
    # the plan is empty regardless of forecast/template. Surface the
    # reason to the operator and short-circuit the table render.
    target_date = for_date or _asuncion_today()
    closed_day = session.get(ProductionClosedDay, target_date)
    closed_day_active = closed_day is not None

    # T-2026-10-04 (Tier 3-B): fetch today's merma count + cost for the
    # "Mermas de hoy" banner. Operators register waste via /merma; we
    # surface the running total on the production page so the cook can
    # see "we lost 2.3 kg of flour today" before deciding the next batch.
    day_start = datetime.combine(target_date, time.min)
    day_end = datetime.combine(target_date, time.max)
    todays_waste = session.execute(
        select(
            func.count(WasteLog.id).label("n"),
            func.coalesce(func.sum(WasteLog.cost_gs), 0).label("cost"),
        )
        .where(WasteLog.recorded_at >= day_start)
        .where(WasteLog.recorded_at <= day_end)
    ).one()
    today_waste_count = int(todays_waste.n or 0)
    today_waste_cost_gs = int(todays_waste.cost or 0)

    # Also compute last-7-days average cost (so cook can spot trend)
    seven_days_ago = target_date - timedelta(days=7)
    week_start = datetime.combine(seven_days_ago, time.min)
    last7 = (
        session.execute(
            select(func.coalesce(func.sum(WasteLog.cost_gs), 0))
            .where(WasteLog.recorded_at >= week_start)
            .where(WasteLog.recorded_at <= day_end)
        ).scalar()
        or 0
    )
    avg_daily_waste_cost_gs = int(last7) // 7 if last7 else 0

    # T-2026-10-04 (Tier 3-C): yesterday snapshot — show what the cook
    # actually produced yesterday as a "ground truth" reference next to
    # today's suggested quantities. "You made 23 yesterday, today's plan
    # says 19." Reduces morning anxiety about over/under-baking.
    yesterday = target_date - timedelta(days=1)
    yesterday_completions = get_day_completions(session, yesterday)
    yesterday_total_qty = sum(yesterday_completions.values())
    yesterday_count = len(yesterday_completions)

    # US 4.4 — Surface incoming pedidos for the SAME day as a "kitchen ticket"
    # panel so the cook sees "we owe 3 tortas + 1 cookie tray today" alongside
    # the demand-driven production plan. Includes pending/confirmed/ready
    # (not fulfilled — those are done — and not cancelled — those are gone).
    pending_pedidos = []
    pedido_rows = (
        session.execute(
            select(Pedido)
            .options(selectinload(Pedido.lines).selectinload(PedidoLine.product))
            .where(
                Pedido.promised_date == target_date,
                Pedido.status.in_(("pending", "confirmed", "ready")),
            )
            .order_by(Pedido.promised_time.asc().nullslast(), Pedido.created_at.asc())
        )
        .scalars()
        .all()
    )
    for p in pedido_rows:
        line_items = []
        for ln in p.lines:
            if ln.qty <= 0:
                continue
            line_items.append(
                {
                    "product_id": ln.product_id,
                    "product_name": ln.product.name if ln.product else "(deleted)",
                    "qty": float(ln.qty),
                    "unit_price_gs": ln.unit_price_gs,
                }
            )
        if not line_items:
            continue
        pending_pedidos.append(
            {
                "id": p.id,
                "customer_name": p.customer_name or "(sin nombre)",
                "customer_phone": p.customer_phone or "",
                "promised_time": p.promised_time or "",
                "channel": p.channel,
                "status": p.status,
                "notes": p.notes or "",
                "line_items": line_items,
            }
        )

    # P-14: template produccion.html:102 references daily_target but the day
    # view never passed it, raising Jinja UndefinedError. Compute target
    # (sum of plan rows) and actual (sum of non-voided Sale.qty for the day).
    daily_target = sum(r.qty_to_produce for r in plan.rows if r.qty_to_produce > 0)
    from datetime import datetime as _dt_cls
    from datetime import timezone as _tz_cls

    target_start = datetime.combine(target_date, _dt_cls.min.time()).replace(tzinfo=_tz_cls.utc)
    target_end = datetime.combine(target_date, _dt_cls.max.time()).replace(tzinfo=_tz_cls.utc)
    daily_actual = (
        session.execute(
            select(func.sum(Sale.qty)).where(
                Sale.sold_at >= target_start,
                Sale.sold_at <= target_end,
                Sale.voided_at.is_(None),
            )
        ).scalar()
        or 0
    )

    # Sprint 1: pull actual production completions for the day so the
    # shift-execution table can render pre-filled "Progreso" values
    # instead of blank inputs.
    from app.rms.eod_completions import completions_for_date as _eod_for_date
    from app.rms.models import ProductionCompletion

    completions_by_pid = _eod_for_date(session, target_date)
    # PRODUCCION-V2 Fase 2: pull closure status per product so the UI
    # can render the "Cerrado" badge and the "Cerrar turno" button
    # toggles to "Reabrir". The status defaults to 'open' for rows
    # that have a completion (qty > 0) but haven't been closed yet;
    # and 'open' for products with NO completion row at all.
    closure_status_by_pid: dict[int, str] = {}
    closure_notes_by_pid: dict[int, str | None] = {}
    completion_rows = (
        session.execute(
            select(ProductionCompletion).where(ProductionCompletion.for_date == target_date)
        )
        .scalars()
        .all()
    )
    for cr in completion_rows:
        closure_status_by_pid[cr.product_id] = cr.status or "open"
        closure_notes_by_pid[cr.product_id] = cr.closure_notes
    # Day-level closure counts (PRODUCCION-V2 Fase 2: "Total cerradas /
    # Total del dia" header). Counts only the rows in plan_rows_view,
    # NOT every row in the table — i.e. we only count products that
    # were actually on today's plan. Ad-hoc rows that get closed are
    # also counted (they show up in plan_rows_view with a virtual pid).
    day_open_count = 0
    day_done_count = 0
    day_cancelled_count = 0
    # We compute per-row status below; aggregate after enrichment.

    # Sprint 3: demand fusion — count how many units of each product are
    # already owed by pedidos for the same day. We surface this as a
    # per-row "+N por pedidos" badge so the cook knows the plan number
    # is a baseline, not the final bake count.
    ped_units_by_pid: dict[int, float] = {}
    for p in pedido_rows:
        for ln in p.lines:
            if ln.qty <= 0:
                continue
            ped_units_by_pid[ln.product_id] = ped_units_by_pid.get(ln.product_id, 0.0) + float(
                ln.qty
            )

    # Wrap each ProductionRow with the completion + pedido data the
    # template needs (ProductionRow is a dataclass — attribute injection
    # is safe inside this function but we don't mutate the original).
    # T-2026-10-04 (P0): also include recipe yield info so the kitchen
    # sees "1 × Docena muffins (12 und)" instead of bare "1".
    recipe_by_id = {
        r.id: r for r in (session.execute(select(Recipe).order_by(Recipe.name)).scalars().all())
    }
    product_by_id = {
        p.id: p for p in (session.execute(select(Product).order_by(Product.name)).scalars().all())
    }
    # T-2026-10-04 (C.5): RecipePricing lookup by recipe_id for inline
    # cost/margin display on /produccion rows. The pricing table has
    # cost_per_unit_gs + retail_gs; we join by recipe_id and surface
    # both in plan_rows_view so the template can render "Gs X total
    # cost, Y% margin" without a second round-trip.
    # NOTE: we use raw SQL via text() to avoid importing the full
    # models.sales module (which carries a deprecated SaleStockMove
    # relationship forward-ref that breaks mapper config in tests).
    from sqlalchemy import text as _sa_text

    pricing_rows = session.execute(
        _sa_text("SELECT recipe_id, cost_per_unit_gs, retail_gs FROM recipe_pricing")
    ).all()
    pricing_by_recipe_id = {
        row.recipe_id: type(
            "P", (), {"cost_per_unit_gs": row.cost_per_unit_gs, "retail_gs": row.retail_gs}
        )()
        for row in pricing_rows
    }

    # PRODUCCION-V2 cutover (2026-10-05): `ui` is always "v2", so
    # demand is always populated. The try/except is preserved so a
    # bad cache state can never break the page.
    demand_by_pid: dict = {}
    try:
        demand_by_pid = get_demand(session, for_date=target_date)
    except Exception:  # noqa: BLE001 — demand is enrichment, never break the page
        demand_by_pid = {}

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
                if r.recipe_id
                and r.recipe_id in recipe_by_id
                and recipe_by_id[r.recipe_id].yield_qty
                else None
            ),
            "batch_unit": (
                recipe_by_id[r.recipe_id].yield_unit
                if r.recipe_id
                and r.recipe_id in recipe_by_id
                and recipe_by_id[r.recipe_id].yield_qty
                else None
            ),
            # T-2026-10-05 (B.3): fermentation reminder per row. None if
            # recipe has no fermentation_minutes (quick breads).
            "fermentation_reminder": (
                _fermentation_reminder(recipe_by_id[r.recipe_id].fermentation_minutes)
                if r.recipe_id
                and r.recipe_id in recipe_by_id
                and getattr(recipe_by_id[r.recipe_id], "fermentation_minutes", None)
                else None
            ),
            "portion_label": (
                product_by_id[r.product_id].portion_label if r.product_id in product_by_id else None
            ),
            # T-2026-10-05 (B.9): surplus estimate. If the recipe batch yields
            # more than the cook needs, there will be unsold leftovers. We
            # compute (ceil(qty/yield) * yield - qty) so the cook sees the
            # concrete surplus and can decide to:
            #   - lower the forecast to match one fewer batch
            #   - bake it anyway and offer a promo at close
            #   - swap to a different recipe entirely
            # Saved ~150-300k Gs/month when at least 3 batches/turn are
            # over-baked. The pct field lets the template color-code the
            # severity: >30% surplus = red, 10-30% = yellow.
            "batch_surplus_qty": (
                _batch_surplus(
                    qty_demand=r.qty_to_produce,
                    yield_qty=recipe_by_id[r.recipe_id].yield_qty,
                )["surplus_qty"]
                if r.recipe_id
                and r.recipe_id in recipe_by_id
                and recipe_by_id[r.recipe_id].yield_qty
                and r.qty_to_produce > 0
                else None
            ),
            "batch_surplus_pct": (
                _batch_surplus(
                    qty_demand=r.qty_to_produce,
                    yield_qty=recipe_by_id[r.recipe_id].yield_qty,
                )["surplus_pct"]
                if r.recipe_id
                and r.recipe_id in recipe_by_id
                and recipe_by_id[r.recipe_id].yield_qty
                and r.qty_to_produce > 0
                else None
            ),
            # T-2026-10-04 (C.5): inline cost + margin on the row so the
            # cook sees "this batch costs Gs 12.500 to make and yields
            # Gs 18.750 at retail → 33% margin" without leaving the page.
            # RecipePricing has cost_per_unit_gs and retail_gs; we expose
            # both plus the line-total cost (cost × qty_to_produce) and
            # the margin %.
            "cost_per_unit_gs": int(
                pricing_by_recipe_id.get(
                    r.recipe_id, type("P", (), {"cost_per_unit_gs": 0})()
                ).cost_per_unit_gs
            )
            if r.recipe_id and r.recipe_id in pricing_by_recipe_id
            else 0,
            "retail_gs": int(
                pricing_by_recipe_id.get(r.recipe_id, type("P", (), {"retail_gs": 0})()).retail_gs
            )
            if r.recipe_id and r.recipe_id in pricing_by_recipe_id
            else 0,
            # T-2026-10-04 (C.6): allergen + difficulty badges. Recipe
            # has difficulty (1-5) and allergens (text, comma-separated).
            # We expose them so the template renders inline badges
            # (celiacos, lactosa, etc.) and a difficulty star.
            "recipe_difficulty": (
                recipe_by_id[r.recipe_id].difficulty
                if r.recipe_id and r.recipe_id in recipe_by_id
                else None
            ),
            "recipe_allergens": (
                recipe_by_id[r.recipe_id].allergens
                if r.recipe_id and r.recipe_id in recipe_by_id
                else None
            ),
            # PRODUCCION-V2 cutover (2026-10-05): `ui` is always "v2"
            # now (the default AND the only accepted value). The
            # demand fields below are always populated when
            # demand_by_pid has the product_id.
            "qty_demand_total": (
                float(demand_by_pid[r.product_id].qty_total)
                if r.product_id in demand_by_pid
                else 0.0
            ),
            "qty_demand_pedidos": (
                float(demand_by_pid[r.product_id].qty_pedidos)
                if r.product_id in demand_by_pid
                else 0.0
            ),
            "qty_demand_pedidos_pending": (
                float(
                    demand_by_pid[r.product_id].qty_pedidos
                    - demand_by_pid[r.product_id].qty_pedidos_confirmed
                )
                if r.product_id in demand_by_pid
                else 0.0
            ),
            "qty_demand_forecast": (
                float(demand_by_pid[r.product_id].qty_forecast)
                if r.product_id in demand_by_pid
                else 0.0
            ),
            # PRODUCCION-V2 Fase 2: closure state per product. 'open' is
            # the default for products with no completion row at all;
            # 'done' once the cook taps "Cerrar turno"; 'cancelled' for
            # "horneé 0, no se vendió" rows. closure_notes is the
            # optional justification (NULL when blank).
            "closure_status": closure_status_by_pid.get(r.product_id, "open"),
            "closure_notes": closure_notes_by_pid.get(r.product_id),
            # PRODUCCION-V3 Phase 2: 4 source buckets (legend) and
            # 5-band confidence (modal trigger). Pre-computed in the
            # route so the template stays a thin renderer.
            "source_bucket": source_to_bucket(r.forecast_source, is_ad_hoc=False),
            "confidence_band": _confidence_band_for_pct(r.confidence_pct),
        }
        for r in plan.rows
    ]

    # Ad-hoc bakes: products COMPLETED for the day but NOT in the plan
    # row list. These are the walk-ins / on-the-fly decisions that the
    # forecast engine never proposed but the operator actually produced.
    planned_pids = {r["product_id"] for r in plan_rows_view}
    for pid, qty in completions_by_pid.items():
        if pid in planned_pids:
            continue
        prod_obj = session.get(Product, pid)
        if prod_obj is None:
            continue
        plan_rows_view.append(
            {
                "product_id": pid,
                "product_name": prod_obj.name,
                "recipe_id": None,
                "qty_to_produce": 0.0,
                "forecast_source": "ad_hoc",
                "confidence_pct": 100,
                "completed_qty": qty,
                "pending_pedido_qty": ped_units_by_pid.get(pid, 0.0),
                "is_ad_hoc": True,
                # PRODUCCION-V3 Phase 2: ad-hoc rows always bucket to
                # "horneado-extra". Confidence is 100 (the cook
                # decided — there's no forecast to be uncertain about).
                "source_bucket": "horneado-extra",
                "confidence_band": "conf-vhigh",
                "batch_qty": None,
                "batch_unit": None,
                "portion_label": prod_obj.portion_label if prod_obj else None,
                # T-2026-10-05 (B.9): ad-hoc rows have no recipe_id, so no
                # batch context. Surplus fields stay None.
                "batch_surplus_qty": None,
                "batch_surplus_pct": None,
                # T-2026-10-04 (C.5): ad-hoc rows have no recipe, so
                # cost/margin are 0. Allergen/difficulty also N/A.
                "cost_per_unit_gs": 0,
                "retail_gs": 0,
                "recipe_difficulty": None,
                "recipe_allergens": None,
                # PRODUCCION-V2 cutover (2026-10-05): same as the
                # recipe rows above. `ui` is always "v2" now.
                "qty_demand_total": (
                    float(demand_by_pid[pid].qty_total)
                    if pid in demand_by_pid
                    else 0.0
                ),
                "qty_demand_pedidos": (
                    float(demand_by_pid[pid].qty_pedidos)
                    if pid in demand_by_pid
                    else 0.0
                ),
                "qty_demand_pedidos_pending": (
                    float(
                        demand_by_pid[pid].qty_pedidos
                        - demand_by_pid[pid].qty_pedidos_confirmed
                    )
                    if pid in demand_by_pid
                    else 0.0
                ),
                "qty_demand_forecast": (
                    float(demand_by_pid[pid].qty_forecast)
                    if pid in demand_by_pid
                    else 0.0
                ),
                # PRODUCCION-V2 Fase 2: closure state for ad-hoc rows.
                # These rows have completions (we're building the dict
                # from completions_by_pid) so the status is whatever
                # was last set — open by default.
                "closure_status": closure_status_by_pid.get(pid, "open"),
                "closure_notes": closure_notes_by_pid.get(pid),
            }
        )

    # PRO-TEMPLATE-NUDGE: aviso si no hay template para el weekday de for_date
    _weekday = plan.for_date.weekday() if plan.for_date else 0
    _template_rows = get_weekly_template(session).get(_weekday, {})
    _has_sales = (
        session.scalar(
            select(func.count())
            .select_from(Sale)
            .where(
                Sale.product_id.in_(select(Product.id)),
            )
        )
        or 0
    )
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
    elif (
        all(getattr(r, "qty_to_produce", 0) == 1.0 for r in plan_rows_view)
        and len(plan_rows_view) > 0
    ):
        cold_start_kind = "cold_plan"

    # PRODUCCION-V2 Fase 2: aggregate per-row closure state into the
    # day-level header counts ("Total cerradas / Total del día"). We
    # tally from plan_rows_view, NOT from closure_status_by_pid, so
    # a product with a completion row that's NOT in today's plan
    # doesn't pollute the count. Example: a leftover bake from
    # yesterday closed in production_completion.for_date = today by
    # mistake — the cook shouldn't see "1/5 cerradas" inflated.
    for r in plan_rows_view:
        _cs = r.get("closure_status", "open")
        if _cs == "done":
            day_done_count += 1
        elif _cs == "cancelled":
            day_cancelled_count += 1
        else:
            day_open_count += 1
    day_total_count = day_open_count + day_done_count + day_cancelled_count
    if sum(1 for r in plan_rows_view if r["qty_to_produce"] > 0) == 0:
        cold_start_kind = "no_rows"

    # PRODUCCION-V3 Phase 3: hero stats. Compute 3 numbers the cook
    # wants at a glance: total products in the plan, total lote final
    # (meta + pedidos), and weighted-average confidence (so the cook
    # can see "this plan is only 38% confident" before they bake).
    # Ad-hoc rows are excluded from the confidence average (they're
    # 100% by definition — the cook decided).
    day_lote_final_total = sum(
        float(r.get("qty_to_produce", 0) or 0)
        + float(r.get("pending_pedido_qty", 0) or 0)
        for r in plan_rows_view
    )
    day_pedidos_total = sum(
        float(r.get("pending_pedido_qty", 0) or 0)
        for r in plan_rows_view
    )
    _conf_rows = [
        r for r in plan_rows_view
        if not r.get("is_ad_hoc", False) and (r.get("confidence_pct") or 0) > 0
    ]
    day_confidence_pct = (
        int(round(sum(r.get("confidence_pct", 0) for r in _conf_rows) / len(_conf_rows)))
        if _conf_rows
        else 0
    )
    # PRODUCCION-V3 Phase 4: ad-hoc count (already in plan_rows_view
    # with is_ad_hoc=True). Surfaced in the ad-hoc card so the cook
    # can see "3 horneados extra" without scrolling.
    day_adhoc_count = sum(1 for r in plan_rows_view if r.get("is_ad_hoc", False))

    return render(
        request,
        "produccion.html",
        {
            "plan": plan,
            "plan_rows_view": plan_rows_view,
            "template_nudge": template_nudge,
            "cold_start_kind": cold_start_kind,
            "for_date": plan.for_date.isoformat() if plan.for_date else "",
            # PRODUCCION-V3 Phase 1: day navigation. prev/next are ISO
            # strings for the prev/next calendar day. `today` is the
            # Asunción-local current date (the nav's "Hoy" button always
            # points to it, even when the current for_date is in the past).
            "prev_for_date": (plan.for_date - timedelta(days=1)).isoformat() if plan.for_date else "",
            "next_for_date": (plan.for_date + timedelta(days=1)).isoformat() if plan.for_date else "",
            "today_for_date": _asuncion_today().isoformat(),
            "view": "day",
            "ui_version": ui,  # PRODUCCION-V2 Fase 1: 'v1' (default) or 'v2' (demand fields)
            # PRODUCCION-V2 Fase 2: day-level closure counts for the
            # "Total cerradas / Total del día" header badge. Counts
            # only the rows in plan_rows_view (not every completion
            # row in the table) so the number is meaningful.
            "day_open_count": day_open_count,
            "day_done_count": day_done_count,
            "day_cancelled_count": day_cancelled_count,
            "day_total_count": day_total_count,
            # PRODUCCION-V3 Phase 3: hero stats. The 3 numbers + product
            # count surface at the top of the day view so the cook sees
            # "what's the day look like" before reading the table.
            "day_productos_count": len(plan_rows_view),
            "day_lote_final_total": day_lote_final_total,
            "day_pedidos_total": day_pedidos_total,
            "day_confidence_pct": day_confidence_pct,
            "day_adhoc_count": day_adhoc_count,
            "source_labels": FORECAST_SOURCE_LABELS,
            "source_help": FORECAST_SOURCE_HELP,
            # PRODUCCION-V3 Phase 2: 4-bucket legend + 5-band confidence.
            "source_buckets": SOURCE_BUCKETS,
            # NOTE: key named `confidence_bands_def` to avoid collision with
            # the pre-existing `confidence_bands` dict (counts per band:
            # high / medium / low / no_data) injected a few lines below.
            "confidence_bands_def": CONFIDENCE_BANDS,
            "overrides": overrides,
            "recipes": session.execute(select(Recipe).order_by(Recipe.name)).scalars().all(),
            "pending_pedidos": pending_pedidos,
            "daily_target": daily_target,
            "daily_actual": float(daily_actual),
            "shift_saved": int(request.query_params.get("shift_saved", 0)),
            "adhoc_added": request.query_params.get("adhoc_added") == "1",
            # T-2026-10-04 (Tier 5-K): concurrent-edit warning flag.
            "concurrent_modify": request.query_params.get("concurrent_modify") == "1",
            "products_for_adhoc": session.execute(select(Product).order_by(Product.name))
            .scalars()
            .all(),
            # T-2026-10-04 (Tier 4-G): quick-seed list for cold-start.
            # Top 5 products with one-click "venta de 1 unidad" CTA.
            "seed_products": [
                {"product_id": p.id, "product_name": p.name}
                for p in session.execute(select(Product).order_by(Product.name).limit(5))
                .scalars()
                .all()
            ],
            # T-2026-10-04 (P2): closed-day flag.
            "closed_day_active": closed_day_active,
            "closed_day_reason": closed_day.reason if closed_day else None,
            "closed_day_at": closed_day.closed_at.isoformat() if closed_day else None,
            # T-2026-10-04 (P2): confidence calibration — surface low-confidence
            # rows so the cook knows which auto-suggestions need manual review.
            "low_confidence_count": sum(
                1
                for r in plan_rows_view
                if r.get("confidence_pct", 0) < 70 and not r.get("is_ad_hoc", False)
            ),
            "confidence_bands": {
                "high": sum(1 for r in plan_rows_view if r.get("confidence_pct", 0) >= 70),
                "medium": sum(
                    1
                    for r in plan_rows_view
                    if 50 <= r.get("confidence_pct", 0) < 70 and not r.get("is_ad_hoc", False)
                ),
                "low": sum(
                    1
                    for r in plan_rows_view
                    if 0 < r.get("confidence_pct", 0) < 50 and not r.get("is_ad_hoc", False)
                ),
                "no_data": sum(
                    1
                    for r in plan_rows_view
                    if r.get("confidence_pct", 0) == 0 and not r.get("is_ad_hoc", False)
                ),
            },
            # T-2026-10-04 (Tier 3-B): today's waste totals for the banner.
            "today_waste_count": today_waste_count,
            "today_waste_cost_gs": today_waste_cost_gs,
            "avg_daily_waste_cost_gs": avg_daily_waste_cost_gs,
            # T-2026-10-04 (Tier 3-C): yesterday snapshot.
            "yesterday_total_qty": yesterday_total_qty,
            "yesterday_count": yesterday_count,
            # T-2026-10-04 (D.2): shift-context deep-link (AM|PM|"")
            "shift": shift,
            # T-2026-10-04 (B.6): HACCP freezer-temperature banner data.
            # The /produccion day view shows the most recent reading and
            # a soft "missing" nudge if the cook hasn't logged AM/PM for
            # the default freezer locations.
            "haccp_latest": _get_haccp_latest_for_date(session, plan.for_date),
            "haccp_alert": _haccp_alert_for_entry(
                _get_haccp_latest_for_date(session, plan.for_date)
            ),
            "haccp_missing_count": _count_haccp_missing_for_date(session, plan.for_date),
            # T-2026-10-04 (C.4): substitution suggestions. For every
            # ingredient the plan is short on, surface alternative
            # products the cook can bake instead — ranked by Jaccard
            # similarity so the substitute tastes similar. Skipped when
            # the plan is fully stocked (avoids noise).
            "substitution_suggestions": _build_substitution_suggestions(
                session,
                list(
                    {
                        ln.ingredient_name
                        for ln in plan.lines
                        if (ln.stock_on_hand - ln.qty_required) < 0
                    }
                ),
                plan_rows_view,
            ),
        },
    )


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
    # PRODUCCION-V2 Fase 1: capture old_qty for the audit log BEFORE the
    # upsert/delete so the audit row shows before/after. None for first write.
    prior_row = (
        session.query(ProductionPlanOverride)
        .filter(
            ProductionPlanOverride.product_id == product_id,
            ProductionPlanOverride.for_date == for_date,
        )
        .one_or_none()
    )
    old_qty = float(prior_row.qty) if prior_row is not None else None
    if qty == 0:
        # Remove the override so the weekly template can take over
        if prior_row:
            session.delete(prior_row)
            session.flush()
    else:
        upsert_override(
            session,
            product_id=product_id,
            for_date=for_date,
            qty=qty,
            updated_by=user_id,
        )

    persist_plan_audit(
        session,
        for_date=for_date,
        product_id=product_id,
        old_qty=old_qty,
        new_qty=qty,
        change_source="override",
        changed_by=user_id,
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


@router.post("/copy-last-week")
def produccion_copy_last_week(
    request: Request,
    for_date: date = Form(...),
    source_date: date | None = Form(None),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Copy last week's plan into this date as ProductionPlanOverride rows.

    Sazon-Improvement v2 (2026-10-06) Phase C: saves the operator ~20
    minutes per menu-planning session. Reads source_date's
    plan_production() output and creates one override per row. The
    target date keeps its own fresh forecast_source (the override is
    just a manual adjustment on top).

    Default source_date is 7 days before for_date if not given.
    Idempotent: existing overrides for the same (product, for_date) are
    overwritten with the source qty. No data is lost; existing overrides
    not present in the source are kept (so this is additive, not a
    destructive replace).
    """
    from app.auth import current_user_id
    from app.rms.models import ProductionPlanOverride
    from app.rms.production import plan_production, upsert_override

    target = for_date
    src = source_date or (for_date - timedelta(days=7))

    # Rate-limit the same as a manual override (1 per 6s)
    from app.rms.rate_limit import is_write_rate_limited

    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )

    user_id = current_user_id(request) or "operator"
    user_id = str(user_id)

    # Read source plan (may be empty if source has no forecast)
    src_plan = plan_production(session, for_date=src)
    created = 0
    for r in src_plan.rows:
        if r.qty_to_produce <= 0:
            continue
        # Find existing override for (product, target) to know old_qty
        prior = session.query(ProductionPlanOverride).filter(
            ProductionPlanOverride.product_id == r.product_id,
            ProductionPlanOverride.for_date == target,
        ).one_or_none()
        old_qty = float(prior.qty) if prior is not None else None
        upsert_override(
            session,
            product_id=r.product_id,
            for_date=target,
            qty=float(r.qty_to_produce),
            updated_by=user_id,
        )
        created += 1
        persist_plan_audit(
            session,
            for_date=target,
            product_id=r.product_id,
            old_qty=old_qty,
            new_qty=float(r.qty_to_produce),
            change_source="copy_last_week",
            changed_by=user_id,
        )

    record_audit(
        request,
        session=session,
        action="write.production.copy_last_week",
        target_type="production",
        target_id=None,
        detail={
            "source_date": src.isoformat(),
            "target_date": target.isoformat(),
            "overrides_created": created,
        },
    )
    session.commit()
    return RedirectResponse(
        url=f"/produccion?for_date={target.isoformat()}",
        status_code=303,
    )


@router.post("/closed")
def produccion_closed_toggle(
    request: Request,
    for_date: date = Form(...),
    action: str = Form(..., pattern="^(close|reopen)$"),
    reason: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """T-2026-10-04 (P1): Mark a date as closed (holiday/no-bake).

    action='close': insert a ProductionClosedDay row with the optional
                    reason. If reason is empty, defaults to 'Cerrado'.
    action='reopen': delete the ProductionClosedDay row for for_date.

    Returns 303 redirect to the day view so the operator sees the
    banner / banner removal immediately.
    """
    from app.auth import current_user_id
    from app.rms.rate_limit import is_write_rate_limited

    if is_write_rate_limited(session, request, max_per_minute=10):
        from fastapi import HTTPException

        raise HTTPException(status_code=429, detail="rate_limited")

    if action == "close":
        existing = session.get(ProductionClosedDay, for_date)
        closed_by_user = current_user_id(request) or "operator"
        if existing is None:
            row = ProductionClosedDay(
                for_date=for_date,
                reason=(reason or "Cerrado")[:120],
                closed_by=closed_by_user,
                closed_at=datetime.utcnow(),  # noqa: DTZ003 — DB-naive-UTC convention
            )
            session.add(row)
            record_audit(
                request,
                session=session,
                action="production_closed",
                target_type="production_closed_day",
                target_id=for_date.isoformat(),
                detail={"reason": row.reason},
            )
        else:
            # Update reason in case operator wants to refine it
            existing.reason = (reason or existing.reason or "Cerrado")[:120]
            existing.closed_at = datetime.utcnow()  # noqa: DTZ003 — DB-naive-UTC convention
    else:  # reopen
        existing = session.get(ProductionClosedDay, for_date)
        if existing is not None:
            session.delete(existing)
            record_audit(
                request,
                session=session,
                action="production_reopened",
                target_type="production_closed_day",
                target_id=for_date.isoformat(),
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
            raise HTTPException(status_code=400, detail="La cantidad no puede ser negativa")
        entries[pid] = qty

    applied = 0
    for pid, qty in entries.items():
        if session.get(Product, pid) is None:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        # PRODUCCION-V2 Fase 1: capture old_qty for the audit log BEFORE
        # the upsert/delete so the audit row shows before/after.
        prior_bulk_row = (
            session.query(ProductionPlanOverride)
            .filter(
                ProductionPlanOverride.product_id == pid,
                ProductionPlanOverride.for_date == for_date,
            )
            .one_or_none()
        )
        old_qty = float(prior_bulk_row.qty) if prior_bulk_row is not None else None
        if qty == 0:
            if prior_bulk_row:
                session.delete(prior_bulk_row)
                session.flush()
        else:
            upsert_override(
                session,
                product_id=pid,
                for_date=for_date,
                qty=qty,
                updated_by=user_id,
            )
        persist_plan_audit(
            session,
            for_date=for_date,
            product_id=pid,
            old_qty=old_qty,
            new_qty=qty,
            change_source="override_bulk",
            changed_by=user_id,
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
# The day view renders a "Ejecución del turno" form that lets the operator
# mark checkboxes + enter a qty per product. Until Sprint 1 this form
# posted to /produccion/override, which IGNORED the `completed_*`
# fields and only wrote production_plan_override (which is the PLAN,
# not the actual). The actual production is what the operator really baked;
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
    """Persist actual production qty per product (the "ya salió del horno" tracker).

    T-2026-10-04 (Tier 5-K): if the form was opened before the latest
    `updated_at` for this date (meaning another cook saved while you were
    typing), we surface a soft warning via the redirect (no hard block —
    last-write-wins remains, but the user knows they may have stomped).
    The check uses the optional `form_opened_at` form field; older clients
    without the field skip the check.
    """
    from datetime import datetime, timezone

    from app.auth import current_user_id
    from app.rms.rate_limit import is_write_rate_limited

    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )

    # PRODUCCION-V3 Phase 0: backdate cap. Reject for_date older than
    # BACKDATE_WINDOW_DAYS (default 7) — otherwise a stray 2020-01-01
    # backfill would corrupt the 14-day rolling forecast. Also reject
    # future dates (use /produccion/override for tomorrow's plan).
    from datetime import timedelta
    from app.rms.config import ASUNCION_TZ, BACKDATE_WINDOW_DAYS

    today_local = datetime.now(ASUNCION_TZ).date()
    if for_date > today_local:
        raise HTTPException(
            status_code=400,
            detail=(
                f"La fecha no puede ser futura ({for_date.isoformat()}). "
                f"Para planificar el futuro, usá /produccion/override."
            ),
        )
    if for_date < today_local - timedelta(days=BACKDATE_WINDOW_DAYS):
        raise HTTPException(
            status_code=400,
            detail=(
                f"La fecha {for_date.isoformat()} está fuera de la ventana de "
                f"{BACKDATE_WINDOW_DAYS} días hacia atrás. Si necesitás backfill "
                f"más viejo, cambiá AIW_RMS_BACKDATE_DAYS en el servidor."
            ),
        )

    form = await request.form()
    form_opened_at_raw = form.get("form_opened_at")
    user_id = str(current_user_id(request) or "operator")

    # T-2026-10-04 (Tier 5-K): detect concurrent modification. Compare
    # the form's open-time against the latest updated_at on this date.
    # If form_opened_at < max(updated_at), someone else saved while
    # we were filling it out.
    concurrent_modify = False
    if form_opened_at_raw:
        try:
            # The form sends naive local time; treat as UTC for compare.
            form_opened_at = datetime.fromisoformat(str(form_opened_at_raw))
            if form_opened_at.tzinfo is None:
                form_opened_at = form_opened_at.replace(tzinfo=timezone.utc)
            # Read max(updated_at) for this date.
            latest_row = session.execute(
                __import__("sqlalchemy").text(
                    "SELECT MAX(updated_at) FROM production_completion WHERE for_date = :d"
                ),
                {"d": for_date.isoformat()},
            ).scalar()
            if latest_row is not None:
                # SQLite returns strings; normalize.
                if isinstance(latest_row, str):
                    latest_ts = datetime.fromisoformat(latest_row)
                    if latest_ts.tzinfo is None:
                        latest_ts = latest_ts.replace(tzinfo=timezone.utc)
                else:
                    latest_ts = latest_row
                if latest_ts > form_opened_at:
                    concurrent_modify = True
        except (ValueError, TypeError) as exc:
            # T-2026-10-04: log the parse failure (was silent pass; now
            # the operator log + test_no_silent_excepts can see it).
            # Bad/missing format — skip the concurrent-edit check.
            logger.debug(f"produccion.shift_execute: bad form_opened_at format: {exc!r}")

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
        # PRODUCCION-V2 Fase 1: capture old_qty for the audit log BEFORE
        # the upsert so the audit row shows before/after.
        from app.rms.models import ProductionCompletion

        prior_completion = (
            session.query(ProductionCompletion)
            .filter(
                ProductionCompletion.product_id == product_id,
                ProductionCompletion.for_date == for_date,
            )
            .one_or_none()
        )
        old_qty = float(prior_completion.completed_qty) if prior_completion is not None else None
        _upsert_completion(
            session,
            product_id=product_id,
            for_date=for_date,
            completed_qty=qty,
        )
        persist_plan_audit(
            session,
            for_date=for_date,
            product_id=product_id,
            old_qty=old_qty,
            new_qty=qty,
            change_source="shift_execute",
            changed_by=user_id,
        )
        saved += 1

    # PRODUCCION-V3 Phase 0: persist closure status from the
    # `done_<product_id>` checkbox. Previously the cook checked the
    # box, the page rendered the row as done (CSS strikethrough), but
    # the DB never saw `status='done'` — silent data loss. Now we
    # scan for done_<pid> fields AFTER the completed_<pid> loop so a
    # `done_<pid>=1` with no corresponding `completed_<pid>` still
    # creates a row (cook marked it done with 0 units baked).
    from app.rms.eod_completions import close_day_for_product

    closed_count = 0
    for key, value in form.multi_items():
        if not isinstance(value, str):
            continue
        if not key.startswith("done_"):
            continue
        try:
            product_id = int(key.removeprefix("done_"))
        except ValueError:
            continue
        if session.get(Product, product_id) is None:
            continue
        if value == "1":
            close_day_for_product(
                session,
                product_id=product_id,
                for_date=for_date,
                status="done",
            )
            closed_count += 1

    record_audit(
        request,
        session=session,
        action="write.production.shift.execute",
        target_type="production_shift",
        target_id=for_date.isoformat(),
        detail={
            "saved": saved,
            "skipped": skipped,
            "for_date": for_date.isoformat(),
            "concurrent_modify": concurrent_modify,  # T-2026-10-04 (Tier 5-K)
            "closed": closed_count,  # PRODUCCION-V3 Phase 0
        },
    )
    session.commit()
    redirect_url = f"/produccion?for_date={for_date.isoformat()}&shift_saved={saved}"
    # T-2026-10-04 (D.2): preserve shift context on redirect. If the
    # cook deep-linked into the PM shift and saved, we want to send
    # them back to the PM view (not default to ""). The form was
    # already parsed at the top of the function — reuse it.
    shift_ctx = str(form.get("shift", "")).strip()
    if shift_ctx in ("AM", "PM"):
        redirect_url += f"&shift={shift_ctx}"
    if concurrent_modify:
        # T-2026-10-04 (Tier 5-K): append the flag so the day view can
        # render the "se actualizó mientras escribías" warning.
        redirect_url += "&concurrent_modify=1"
    return RedirectResponse(
        url=redirect_url,
        status_code=303,
    )


# --- Ad-hoc bake entry (Sprint 4) ---
#
# the operator might bake a product that was NOT in the plan (walk-in order,
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
    from app.auth import current_user_id
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

    user_id = str(current_user_id(request) or "operator")
    tag = "ad_hoc"
    if notes.strip():
        tag = f"ad_hoc: {notes.strip()[:200]}"
    # PRODUCCION-V2 Fase 1: capture old_qty for the audit log BEFORE the upsert.
    from app.rms.models import ProductionCompletion

    prior_adhoc = (
        session.query(ProductionCompletion)
        .filter(
            ProductionCompletion.product_id == product_id,
            ProductionCompletion.for_date == for_date,
        )
        .one_or_none()
    )
    old_qty = float(prior_adhoc.completed_qty) if prior_adhoc is not None else None
    _upsert_completion(
        session,
        product_id=product_id,
        for_date=for_date,
        completed_qty=qty,
        notes=tag,
    )
    persist_plan_audit(
        session,
        for_date=for_date,
        product_id=product_id,
        old_qty=old_qty,
        new_qty=qty,
        change_source="adhoc",
        changed_by=user_id,
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


# ─────────────────────────────────────────────────────────────────────
# T-2026-10-05 (B.7) — Bulk ad-hoc bakes via CSV upload
# ─────────────────────────────────────────────────────────────────────
# On a busy Saturday the operator has 8-12 walk-ins. Typing each into
# the form takes 4 form fills × ~10s = 40s. A single CSV paste drops
# that to ~5s of paste + ~2s of commit.
#
# Format:  product_id,qty,notes
#          42,1.5,Cliente VIP
#          15,2.0,
#
# Validation rules:
#   - Header is optional. If present, must contain product_id,qty,notes
#     (order-independent, notes column may be omitted).
#   - product_id must exist; skip with warning if not.
#   - qty > 0; skip with warning if not.
#   - max 200 rows per upload (anti-fat-finger DoS).
#   - Rate-limited like the single-row form (10 writes/minute).


# --- PRODUCCION-V2 Fase 2: Close-day endpoint ---
#
# The cook taps "Cerrar turno" on each row at end of shift. This endpoint
# flips production_completion.status from 'open' to 'done' (or 'cancelled'
# when they actually baked nothing). closure_notes is OPTIONAL — the audit
# log captures who closed and when regardless of notes, so the operator doesn't
# have to type a justification for the rare zero-qty case.
#
# Bulk semantics: this endpoint takes a SINGLE product per POST. The
# "Cerrar todas" button on the day view fires N POSTs in a loop via
# fetch(). One POST per row keeps the audit log 1-row-per-product and
# avoids partial-failure ambiguity (any failure is per-product visible).


@router.post("/close-day")
def produccion_close_day(
    request: Request,
    for_date: date = Form(...),
    product_id: int = Form(...),
    status: str = Form("done", pattern="^(done|cancelled)$"),
    closure_notes: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Mark a single product's shift as closed for the given date.

    PRODUCCION-V2 Fase 2: replaces the implicit "anyone can edit
    forever" behavior of production_completion. After the cook closes
    the day, the row is still editable (we don't lock the table — the
    audit log + visibility of the closed state is the social contract),
    but the UI surfaces a "Cerrado" badge so the next cook knows.
    """
    from app.auth import current_user_id
    from app.rms.rate_limit import is_write_rate_limited

    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )
    if session.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    user_id = str(current_user_id(request) or "operator")
    notes = closure_notes.strip()[:500] or None  # truncate; NULL when blank
    try:
        close_day_for_product(
            session,
            product_id=product_id,
            for_date=for_date,
            closure_notes=notes,
            status=status,
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Audit the closure (Fase 1's persist_plan_audit) so the change_source
    # shows up in /accuracy timelines. The completion row itself
    # (completed_qty, recorded_at) doesn't change; the audit log just
    # records the close action.
    persist_plan_audit(
        session,
        for_date=for_date,
        product_id=product_id,
        old_qty=None,  # closure isn't a qty change
        new_qty=0.0,  # the audit row's new_qty is 0 since we're not changing qty
        change_source=f"close_day_{status}",
        changed_by=user_id,
        notes=notes,
    )
    record_audit(
        request,
        session=session,
        action="write.production.close_day",
        target_type="production_completion",
        target_id=f"{for_date.isoformat()}:{product_id}",
        detail={"status": status, "closure_notes": notes or ""},
    )
    session.commit()
    # Preserve the ui=v2 flag on redirect so the cook lands back on the
    # new grilla.
    ui_q = ""
    ui_param = str(request.query_params.get("ui") or "")
    if ui_param == "v2":
        ui_q = "&ui=v2"
    return RedirectResponse(
        url=f"/produccion?for_date={for_date.isoformat()}{ui_q}",
        status_code=303,
    )


@router.post("/close-day/reopen")
def produccion_close_day_reopen(
    request: Request,
    for_date: date = Form(...),
    product_id: int = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Reopen a closed row so the cook can correct a mistake.

    Reverses the close-day action. We don't keep a separate reopen
    audit row — the `close_day_done` audit row already captures the
    close, and the row's status='open' field is enough to render the
    right state. Future Fase 3 might add a reopen audit; for now
    /accuracy treats reopens as "in flight" and the cook can re-close.
    """
    from app.auth import current_user_id
    from app.rms.rate_limit import is_write_rate_limited

    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )
    if session.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    user_id = str(current_user_id(request) or "operator")
    try:
        close_day_for_product(
            session,
            product_id=product_id,
            for_date=for_date,
            closure_notes=None,  # keep the existing notes
            status="open",
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    persist_plan_audit(
        session,
        for_date=for_date,
        product_id=product_id,
        old_qty=None,
        new_qty=0.0,
        change_source="close_day_reopen",
        changed_by=user_id,
        notes=None,
    )
    record_audit(
        request,
        session=session,
        action="write.production.close_day.reopen",
        target_type="production_completion",
        target_id=f"{for_date.isoformat()}:{product_id}",
        detail={},
    )
    session.commit()
    ui_q = ""
    ui_param = str(request.query_params.get("ui") or "")
    if ui_param == "v2":
        ui_q = "&ui=v2"
    return RedirectResponse(
        url=f"/produccion?for_date={for_date.isoformat()}{ui_q}",
        status_code=303,
    )


@router.post("/ad-hoc/bulk")
async def produccion_ad_hoc_bulk(
    request: Request,
    for_date: date = Form(...),
    csv: str = Form(""),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """T-2026-10-05 (B.7) — Paste-many ad-hoc bakes via CSV.

    Returns a JSON-ish redirect-friendly page with the import summary
    (created / skipped / errors). Skips invalid lines instead of
    failing the whole batch — partial success is more useful than
    nothing. Operators see what worked and what didn't.
    """
    from app.rms.rate_limit import is_write_rate_limited

    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )

    csv = (csv or "").strip()
    if not csv:
        raise HTTPException(status_code=400, detail="CSV vacío")

    MAX_ROWS = 200
    lines = [ln for ln in csv.splitlines() if ln.strip()]
    # Detect optional header
    if lines and lines[0].lower().startswith("product_id"):
        header = [c.strip().lower() for c in lines[0].split(",")]
        has_notes = "notes" in header or "notas" in header
        data_lines = lines[1:]
    else:
        header = ["product_id", "qty", "notes"]
        has_notes = True
        data_lines = lines

    if len(data_lines) > MAX_ROWS:
        raise HTTPException(
            status_code=400,
            detail=f"Demasiadas filas (max {MAX_ROWS}). Subí en lotes.",
        )

    # Cache product lookups
    valid_product_ids: set[int] = set(session.execute(select(Product.id)).scalars().all())

    # PRODUCCION-V2 Fase 1: get the cook's user id for the audit log.
    from app.auth import current_user_id

    bulk_user_id = str(current_user_id(request) or "operator")
    from app.rms.models import ProductionCompletion

    created: list[dict] = []
    skipped: list[dict] = []
    for row_num, raw in enumerate(data_lines, start=2 if len(lines) != len(data_lines) else 1):
        cells = [c.strip() for c in raw.split(",")]
        if len(cells) < 2:
            skipped.append(
                {"line": row_num, "raw": raw, "reason": "Faltan columnas (minimo product_id, qty)"}
            )
            continue
        try:
            pid = int(cells[0])
            qty = float(cells[1])
        except ValueError:
            skipped.append(
                {"line": row_num, "raw": raw, "reason": "product_id o qty no son números"}
            )
            continue
        notes = cells[2] if has_notes and len(cells) > 2 else ""
        if pid not in valid_product_ids:
            skipped.append({"line": row_num, "raw": raw, "reason": f"Producto {pid} no existe"})
            continue
        if qty <= 0:
            skipped.append({"line": row_num, "raw": raw, "reason": "qty debe ser > 0"})
            continue

        tag = "ad_hoc"
        if notes.strip():
            tag = f"ad_hoc: {notes.strip()[:200]}"
        # PRODUCCION-V2 Fase 1: capture old_qty for the audit log.
        prior_bulk_completion = (
            session.query(ProductionCompletion)
            .filter(
                ProductionCompletion.product_id == pid,
                ProductionCompletion.for_date == for_date,
            )
            .one_or_none()
        )
        old_qty = (
            float(prior_bulk_completion.completed_qty)
            if prior_bulk_completion is not None
            else None
        )
        _upsert_completion(
            session,
            product_id=pid,
            for_date=for_date,
            completed_qty=qty,
            notes=tag,
        )
        persist_plan_audit(
            session,
            for_date=for_date,
            product_id=pid,
            old_qty=old_qty,
            new_qty=qty,
            change_source="adhoc_bulk",
            changed_by=bulk_user_id,
            notes=tag,
        )
        created.append({"line": row_num, "product_id": pid, "qty": qty, "notes": notes})

    if created:
        record_audit(
            request,
            session=session,
            action="write.production.ad_hoc_bulk",
            target_type="production_ad_hoc",
            target_id=for_date.isoformat(),
            detail={
                "for_date": for_date.isoformat(),
                "created_count": len(created),
                "skipped_count": len(skipped),
                "product_ids": [c["product_id"] for c in created],
            },
        )
        session.commit()

    # Render the summary as a tiny HTML page so the operator sees what
    # worked. Redirect to /produccion would lose the per-line detail.
    summary_html = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        "<title>Importación bulk — /produccion</title>",
        "<link rel='stylesheet' href='/static/app.css'>",
        "</head><body><main class='container'>",
        f"<h1>📥 Importación bulk ({for_date.isoformat()})</h1>",
        f"<p class='alert alert-success' role='alert'>✅ {len(created)} horneadas registradas, "
        f"{len(skipped)} omitidas.</p>",
        "<h2>Registradas</h2>",
        "<table class='table'><thead><tr><th>Línea</th><th>Producto</th><th>Cantidad</th><th>Notas</th></tr></thead><tbody>",
    ]
    prod_id_to_name: dict[int, str] = {
        p.id: p.name for p in session.execute(select(Product.id, Product.name)).all()
    }
    summary_html.extend(
        f"<tr><td>{c['line']}</td><td>{prod_id_to_name.get(c['product_id'], c['product_id'])}</td>"
        f"<td>{c['qty']}</td><td>{c['notes']}</td></tr>"
        for c in created
    )
    summary_html.append("</tbody></table>")
    if skipped:
        summary_html.append(
            "<h2>⚠️ Omitidas</h2><table class='table'><thead><tr><th>Línea</th><th>Texto</th><th>Motivo</th></tr></thead><tbody>"
        )
        summary_html.extend(
            f"<tr><td>{s['line']}</td><td><code>{s['raw']}</code></td><td>{s['reason']}</td></tr>"
            for s in skipped
        )
        summary_html.append("</tbody></table>")
    summary_html.append(
        f"<p><a class='btn' href='/produccion?for_date={for_date.isoformat()}&adhoc_added=1'>Volver al plan</a></p>"
        "</main></body></html>"
    )
    from fastapi.responses import HTMLResponse

    return HTMLResponse(content="".join(summary_html))


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
        raise HTTPException(status_code=400, detail=f"for_date inválido: {for_date!r}") from None

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
        ev
        for ev in calendar_for_year(tomorrow.year)
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
    products_by_id = {p.id: p for p in session.execute(select(Product)).scalars()}
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
            select(Pedido)
            .where(
                Pedido.promised_date == tomorrow,
                Pedido.status.in_(["pending", "confirmed", "ready"]),
            )
            .order_by(Pedido.promised_time.nulls_last(), Pedido.id)
        ).scalars()
    ]

    return render(
        request,
        "produccion_manana.html",
        {
            "pedidos_manana": pedidos_manana,
            "today": today.isoformat(),
            # PRODUCCION-V3 Phase 6: alias for the manana page-nav to
            # link to /produccion?for_date=<today>.
            "today_iso": today.isoformat(),
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
    days: int = Query(1, ge=1, le=14),
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

    T-2026-10-04 (Tier 5-H): ?days=N renders N consecutive days as a
    single print job. Each day is its own printable section with
    page-break-after: always. Capped at 14 (2 weeks).
    """
    from app.rms.eod_completions import completions_for_date as _eod_for_date

    target_date = for_date or _asuncion_today()

    # T-2026-10-04 (Tier 5-H): build a list of date -> print_rows, one
    # entry per day in the pack. Single-day is the common case (days=1).
    days_pack: list[dict] = []
    for day_idx in range(days):
        d = target_date + timedelta(days=day_idx)
        plan = plan_production(session, for_date=d)
        completions_by_pid = _eod_for_date(session, d)

        recipes_by_id = {
            r.id: r for r in session.execute(select(Recipe).order_by(Recipe.name)).scalars().all()
        }
        products_by_id = {
            p.id: p for p in session.execute(select(Product).order_by(Product.name)).scalars().all()
        }

        # Build a flat list of (product, qty_to_produce, qty_completed) — one
        # row per product, no overrides, no forecast_source explanation.
        print_rows: list[dict] = []
        for r in plan.rows:
            if r.qty_to_produce <= 0 and r.product_id not in completions_by_pid:
                continue
            recipe = recipes_by_id.get(r.recipe_id) if r.recipe_id else None
            product = products_by_id.get(r.product_id)
            print_rows.append(
                {
                    "product_id": r.product_id,
                    "product_name": r.product_name,
                    "qty_to_produce": r.qty_to_produce,
                    "qty_completed": completions_by_pid.get(r.product_id, 0.0),
                    "recipe_id": r.recipe_id,
                    # T-2026-10-04 (P0): batch info.
                    "yield_qty": recipe.yield_qty if recipe and recipe.yield_qty else None,
                    "yield_unit": recipe.yield_unit if recipe and recipe.yield_qty else None,
                    "portion_label": product.portion_label if product else None,
                }
            )
        # Include ad-hoc bakes (walk-ins / on-the-fly decisions that the
        # forecast never proposed but the operator actually produced).
        planned_pids = {r["product_id"] for r in print_rows}
        for pid, qty in completions_by_pid.items():
            if pid in planned_pids:
                continue
            prod_obj = session.get(Product, pid)
            if prod_obj is None:
                continue
            print_rows.append(
                {
                    "product_id": pid,
                    "product_name": prod_obj.name,
                    "qty_to_produce": 0.0,
                    "qty_completed": qty,
                    "recipe_id": None,
                    "yield_qty": None,
                    "yield_unit": None,
                    "portion_label": prod_obj.portion_label if prod_obj else None,
                }
            )
        days_pack.append({"date": d.isoformat(), "rows": print_rows})

    # T-2026-10-04 (D.4): print-pack header metadata — the printed
    # sheet now shows the ISO week number and the cook's display name
    # so the operator can verify which cook took which day at a glance.
    # Multi-day packs get a "Semana N" header; single-day prints get
    # just the date.
    from datetime import date as _date

    target_date_obj = target_date if isinstance(target_date, _date) else None
    iso_year, iso_week, _ = target_date_obj.isocalendar() if target_date_obj else (None, None, None)
    cook_name = _current_user_display_name(request)
    return render(
        request,
        "produccion_print.html",
        {
            "for_date": target_date.isoformat(),
            "print_rows": days_pack[0]["rows"] if days_pack else [],  # backward compat
            "days_pack": days_pack,
            "days_count": days,
            "shift_saved": int(request.query_params.get("shift_saved", 0)),
            # T-2026-10-04 (Tier 3-D): worksheet mode strips filled-in
            # quantities so the operator can use the printout as a blank
            # sheet to fill by hand. Default = "filled" (current behavior).
            "worksheet_mode": request.query_params.get("mode") == "worksheet",
            # T-2026-10-04 (D.4): print-pack header metadata.
            "iso_week": iso_week,
            "iso_year": iso_year,
            "cook_name": cook_name,
        },
    )


# Sazon-Improvement v2 (2026-10-06) Phase A: CSV export of the daily plan.
# Operators want to paste the plan into WhatsApp for the team or import
# into Excel. The CSV mirrors the day-view columns and uses the same
# SOURCE_BUCKETS / confidence-band mapping as the HTML view so a printed
# row matches the screen. PII (customer names, phones) is NEVER included;
# this endpoint is for production plan only — sales / pedidos have their
# own /ventas/export.csv and /pedidos/export routes.
@router.get("/export.csv")
def produccion_export_csv(
    for_date: date | None = Query(None, description="Plan date (defaults to today Asunción-local)"),
    view: str = Query("day", pattern="^(day|week|month)$"),
    session: Session = Depends(get_session),
) -> Response:
    """Return the production plan as CSV. Columns: product_name, qty_to_produce, source, confidence, is_ad_hoc."""
    target = for_date or _asuncion_today()
    plan = plan_production(session, for_date=target)
    # Sort by descending qty so the largest batches are at the top of the
    # pasted-into-WhatsApp message (cook reads top-down).
    rows = sorted(
        plan.rows,
        key=lambda r: (-r.qty_to_produce, r.product_name),
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["product_name", "qty_to_produce", "source", "confidence", "is_ad_hoc"])
    for r in rows:
        bucket = source_to_bucket(r.forecast_source, is_ad_hoc=False)
        writer.writerow([
            r.product_name,
            # Format as int when possible so 50.0 doesn't show as "50.0"
            f"{r.qty_to_produce:g}" if r.qty_to_produce == int(r.qty_to_produce) else f"{r.qty_to_produce}",
            bucket,
            r.confidence_pct,
            False,  # Plan rows are not ad-hoc by definition
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="produccion-{target.isoformat()}.csv"',
            # Cache for 1 minute so a retry doesn't hit the planner twice.
            # Plan computation is fast but no point redoing it.
            "Cache-Control": "private, max-age=60",
        },
    )


@router.get("/prep", response_class=HTMLResponse)
def produccion_prep(
    request: Request,
    week: date | None = Query(None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """T-2026-10-04 (P2): Weekly ingredient prep sheet for the kitchen.

    Aggregates the production plan across 7 days (Monday → Sunday) and
    shows the ingredient totals the kitchen needs to buy and prep.
    Sorted by severity (Falta first, then Justo, then Suficiente) so
    the cook sees the urgent items first.
    """
    today = _asuncion_today()
    week_start = _week_monday(week or today)
    days = [week_start + timedelta(days=i) for i in range(7)]

    # Aggregate across the week (mirrors the week view's logic).
    ing_required: dict[int, dict] = {}
    for d in days:
        plan = plan_production(session, for_date=d)
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

    # Compute severity (mirrors produccion.html's logic).
    prep_rows = []
    for v in ing_required.values():
        delta = v["stock_on_hand"] - v["qty_required"]
        if delta < 0:
            severity = "falta"
            to_buy = v["qty_required"] - v["stock_on_hand"]
        elif delta < v["qty_required"] * 0.2:
            severity = "justo"
            to_buy = 0.0
        else:
            severity = "suficiente"
            to_buy = 0.0
        prep_rows.append(
            {
                **v,
                "severity": severity,
                "to_buy": to_buy,
                "delta": delta,
            }
        )

    # Sort by severity (Falta first) then by name
    severity_order = {"falta": 0, "justo": 1, "suficiente": 2}
    prep_rows.sort(key=lambda x: (severity_order.get(x["severity"], 9), x["ingredient_name"]))

    counts = {
        "falta": sum(1 for r in prep_rows if r["severity"] == "falta"),
        "justo": sum(1 for r in prep_rows if r["severity"] == "justo"),
        "suficiente": sum(1 for r in prep_rows if r["severity"] == "suficiente"),
    }

    return render(
        request,
        "produccion_prep.html",
        {
            "week_start": week_start.strftime("%d %b %Y"),
            "week_start_iso": week_start.isoformat(),
            "prev_week_iso": (week_start - timedelta(days=7)).isoformat(),
            "next_week_iso": (week_start + timedelta(days=7)).isoformat(),
            "prep_rows": prep_rows,
            "counts": counts,
        },
    )


