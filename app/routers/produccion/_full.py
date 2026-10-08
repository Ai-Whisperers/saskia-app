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
from datetime import date, datetime, time, timedelta

from fastapi import Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.rms.dependencies import get_session
from app.rms.eod_completions import completions_for_date as get_day_completions
from app.rms.models import (
    Pedido,
    PedidoLine,
    Product,
    ProductionClosedDay,
    Recipe,
    Sale,
    WasteLog,
)
from app.rms.production import get_weekly_template, plan_production
from app.rms.production_demand import get_demand
from app.routers.produccion._helpers import (
    CONFIDENCE_BANDS,
    FORECAST_SOURCE_HELP,
    FORECAST_SOURCE_LABELS,
    SOURCE_BUCKETS,
    _asuncion_today,
    _batch_surplus,
    _confidence_band_for_pct,
    _fermentation_reminder,
    _parse_overrides,
    _week_monday,
    source_to_bucket,
)
from app.routers.produccion._router import router

# Sazon-Improvement v2 (2026-10-06) Phase E: the HACCP + substitution
# helpers are now defined in app/routers/produccion/analytics.py.
# The day-view worksheet still uses them, so we re-import here.
from app.routers.produccion.analytics import (
    _count_haccp_missing_for_date,
    _get_haccp_latest_for_date,
    _haccp_alert_for_entry,
    _list_haccp_missing_for_date,
    expand_missing_items,
)
from app.services.template_render import render

VALID_SORT_KEYS = frozenset(
    {
        "product",  # product_name
        "difficulty",  # recipe_difficulty
        "demand",  # qty_demand_total
        "meta",  # qty_to_produce (batches)
        "pedidos",  # pending_pedido_qty
        "lote",  # meta + pedidos (= lote final total) — DEFAULT
        "hecho",  # completed_qty
        "sobrante",  # batch_surplus_qty
        "closure",  # closure_status
    }
)


def _sort_value(row: dict, key: str):  # noqa: ANN202
    """Pull the comparison key out of a row dict. Returns a tuple so ties
    break on product_name (stable ordering)."""
    lote_final = (row.get("qty_to_produce") or 0) + (row.get("pending_pedido_qty") or 0)
    if key == "product":
        primary = (row.get("product_name") or "").lower()
    elif key == "difficulty":
        primary = row.get("recipe_difficulty") or 0
    elif key == "demand":
        primary = row.get("qty_demand_total") or 0
    elif key == "meta":
        primary = row.get("qty_to_produce") or 0
    elif key == "pedidos":
        primary = row.get("pending_pedido_qty") or 0
    elif key == "lote":
        primary = lote_final
    elif key == "hecho":
        primary = row.get("completed_qty") or 0
    elif key == "sobrante":
        primary = row.get("batch_surplus_qty") or 0
    elif key == "closure":
        # open < done < cancelled (alpha order), so 'open' sorts first asc
        primary = row.get("closure_status") or "open"
    else:
        primary = lote_final
    # secondary tiebreak: product name asc (stable)
    return (primary, (row.get("product_name") or "").lower())


def _sort_produccion_rows(rows: list[dict], sort: str, dir: str) -> list[dict]:
    """Sort by `sort` (white-listed) in `dir` direction. Ad-hoc rows always
    last — they're "extras" the cook decided on, not the plan's suggestion."""
    safe_sort = sort if sort in VALID_SORT_KEYS else "lote"
    safe_dir = dir if dir in ("asc", "desc") else "desc"
    reverse = safe_dir == "desc"
    planned = [r for r in rows if not r.get("is_ad_hoc")]
    ad_hoc = [r for r in rows if r.get("is_ad_hoc")]
    planned.sort(key=lambda r: _sort_value(r, safe_sort), reverse=reverse)
    # Ad-hoc rows are always at the bottom regardless of sort direction.
    return planned + ad_hoc


# 2026-10-07c: ingredient-line sort helper. plan.lines entries have
# these sortable attributes: ingredient_name (str), qty_required (num),
# stock_on_hand (num), and we derive "to_buy" and "severity" on the fly.
_VALID_INGREDIENT_SORT_KEYS = {
    "ingredient",
    "required",
    "stock",
    "to_buy",
    "severity",
}


def _sort_ingredient_lines(lines: list, sort: str, dir: str) -> list:
    """Sort ingredient plan lines. Unknown sort keys fall back to
    `severity` (Falta first)."""
    safe_sort = sort if sort in _VALID_INGREDIENT_SORT_KEYS else "severity"
    safe_dir = dir if dir in ("asc", "desc") else "asc"
    reverse = safe_dir == "desc"
    severity_order = {"falta": 0, "justo": 1, "suficiente": 2}

    def _line_sort_key(ln) -> tuple:  # noqa: ANN001
        delta = ln.stock_on_hand - ln.qty_required
        pct = (ln.stock_on_hand / ln.qty_required * 100) if ln.qty_required > 0 else 100
        sev = severity_order.get(
            "falta" if delta < 0 else ("justo" if pct < 80 else "suficiente"), 9
        )
        if safe_sort == "ingredient":
            return (ln.ingredient_name or "").lower()
        if safe_sort == "required":
            return ln.qty_required or 0
        if safe_sort == "stock":
            return ln.stock_on_hand or 0
        if safe_sort == "to_buy":
            return max(0.0, -delta)
        # severity default
        return (sev, ln.ingredient_name or "")

    return sorted(lines, key=_line_sort_key, reverse=reverse)


# Allergen → list of strings in recipe_allergens that match (semicolon OR
# comma separated). Multi-select: row must contain AT LEAST one of the
# selected allergens (union semantics — operator picks "gluten OR dairy").
_ALLERGEN_TOKENS = {
    "gluten": ("gluten", "trigo", "wheat", "harina"),
    "dairy": ("dairy", "lácteo", "lactosa", "leche", "milk", "manteca", "butter"),
    "eggs": ("eggs", "huevo", "egg"),
    "nuts": ("nuts", "frutos secos", "nuez", "nueces", "almendra", "maní"),
}


def _row_allergens(row: dict) -> set[str]:
    raw = (row.get("recipe_allergens") or "").lower()
    if not raw:
        return set()
    tokens = {t.strip() for t in raw.replace(";", ",").split(",") if t.strip()}
    found = set()
    for canonical, synonyms in _ALLERGEN_TOKENS.items():
        if any(syn in t for t in tokens for syn in synonyms):
            found.add(canonical)
    return found


def _row_source(row: dict) -> str:
    if row.get("is_ad_hoc"):
        return "horneado-extra"
    bucket = row.get("source_bucket") or "historial"
    return bucket


def _apply_produccion_filters(
    rows: list[dict],
    *,
    allergen: list[str],
    source: list[str],
    with_pedidos: str,
    with_hecho: str,
    with_surplus: str,
) -> list[dict]:
    """Return only the rows that pass every active filter. Empty filter
    values mean 'no filter for this group'. All filters combine as AND."""
    out = rows
    if allergen:
        wanted = set(allergen)
        out = [r for r in out if _row_allergens(r) & wanted]

    if source:
        wanted = set(source)
        out = [r for r in out if _row_source(r) in wanted]

    if with_pedidos == "1":
        out = [r for r in out if (r.get("pending_pedido_qty") or 0) > 0]
    elif with_pedidos == "0":
        out = [r for r in out if (r.get("pending_pedido_qty") or 0) == 0]

    if with_hecho == "1":
        out = [r for r in out if (r.get("completed_qty") or 0) > 0]
    elif with_hecho == "0":
        out = [r for r in out if (r.get("completed_qty") or 0) == 0]

    if with_surplus == "1":
        out = [r for r in out if (r.get("batch_surplus_pct") or 0) >= 30]
    elif with_surplus == "0":
        out = [r for r in out if (r.get("batch_surplus_pct") or 0) < 30]

    return out


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
    # 2026-10-07 table overhaul: server-side sort + page-size + filter chips.
    # All state lives in the URL so the operator can share / deep-link a
    # particular view. Unknown sort keys fall back to "lote" so the page
    # never 500s on a typo or stale bookmark.
    sort: str = Query("lote", pattern=r"^[a-z_]+$"),
    dir: str = Query("desc", pattern=r"^(asc|desc)$"),
    # Page size: hard-cap at 100 (operator-settable to 10/15/20/30/50/100).
    # We don't use Query(le=100) so any URL works; the clamp happens here.
    rows: int = Query(20),
    # Pagination + load-all. `page` is 1-based; `show_all` accepts 0/1
    # (any other int falls back to 0). Operator: "I never want a hard
    # cap on total products" — show_all=1 disables pagination.
    page: int = Query(1, ge=1),
    show_all: int = Query(0),
    filter_allergen: list[str] = Query(default_factory=list),
    filter_source: list[str] = Query(default_factory=list),
    filter_with_pedidos: str = Query("", pattern=r"^(1|0|)?$"),
    filter_with_hecho: str = Query("", pattern=r"^(1|0|)?$"),
    filter_with_surplus: str = Query("", pattern=r"^(1|0|)?$"),
    # Ingredients table — sort + filter (2026-10-07c).
    # `ingredients_filter` is one of "falta" | "justo" | "suficiente" | ""
    # (empty = show all). Default "falta" so the operator sees urgent
    # rows first.
    ingredients_sort: str = Query("severity", pattern=r"^[a-z_]+$"),
    ingredients_dir: str = Query("asc", pattern=r"^(asc|desc)$"),
    ingredients_filter: str = Query("", pattern=r"^[a-z]*$"),
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
    # M1: hide inactive products from the daily_target sum.
    # NOTE: query the full row (not just id) so the comprehension below
    # sees Product objects, not int scalars.
    _inactive_pids = {
        p.id
        for p in session.execute(select(Product).where(not Product.is_available)).scalars().all()
    }
    daily_target = sum(
        r.qty_to_produce
        for r in plan.rows
        if r.qty_to_produce > 0 and r.product_id not in _inactive_pids
    )
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
    # M1: Filter plan rows so soft-deleted (is_available=False) products
    # don't appear in the active plan. Previously a row could show
    # "Producto eliminado" because the plan was built before the product
    # was hidden. See: deliver_sazon polish round 2026-10-06 screenshot.
    _all_products = session.execute(select(Product).order_by(Product.name)).scalars().all()
    product_by_id = {p.id: p for p in _all_products}
    visible_product_ids = {p.id for p in _all_products if p.is_available}
    plan_rows_filtered = [r for r in plan.rows if r.product_id in visible_product_ids]
    if len(plan_rows_filtered) != len(plan.rows):
        # Quick operator hint (debug log only; template handles empty plan)
        import logging as _logging

        _log = _logging.getLogger(__name__)
        _log.info(
            "M1: hid %d plan rows for inactive products", len(plan.rows) - len(plan_rows_filtered)
        )
    # downstream uses plan.rows in many places — alias to filtered
    plan_rows_source = plan_rows_filtered
    recipe_by_id = {
        r.id: r for r in (session.execute(select(Recipe).order_by(Recipe.name)).scalars().all())
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
    except Exception:
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
        for r in plan_rows_source  # M1: use filtered rows (skip is_available=False)
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
        # M1: skip ad-hoc completions for inactive products
        if not prod_obj.is_available:
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
                    float(demand_by_pid[pid].qty_total) if pid in demand_by_pid else 0.0
                ),
                "qty_demand_pedidos": (
                    float(demand_by_pid[pid].qty_pedidos) if pid in demand_by_pid else 0.0
                ),
                "qty_demand_pedidos_pending": (
                    float(demand_by_pid[pid].qty_pedidos - demand_by_pid[pid].qty_pedidos_confirmed)
                    if pid in demand_by_pid
                    else 0.0
                ),
                "qty_demand_forecast": (
                    float(demand_by_pid[pid].qty_forecast) if pid in demand_by_pid else 0.0
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
    has_weekly_template = bool(_template_rows)

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
    if sum(1 for r in plan_rows_view if r["qty_to_produce"] > 0) == 0 and cold_start_kind is None:
        # Only downgrade to "no_rows" when nothing else applies — a fresh
        # install (no sales) must keep the "no_sales" onboarding card
        # instead of being swallowed by this generic empty-plan state.
        cold_start_kind = "no_rows"

    # PRODUCCION-V3 Phase 3: hero stats. Compute 3 numbers the cook
    # wants at a glance: total products in the plan, total lote final
    # (meta + pedidos), and weighted-average confidence (so the cook
    # can see "this plan is only 38% confident" before they bake).
    # Ad-hoc rows are excluded from the confidence average (they're
    # 100% by definition — the cook decided).
    day_lote_final_total = sum(
        float(r.get("qty_to_produce", 0) or 0) + float(r.get("pending_pedido_qty", 0) or 0)
        for r in plan_rows_view
    )
    day_pedidos_total = sum(float(r.get("pending_pedido_qty", 0) or 0) for r in plan_rows_view)
    _conf_rows = [
        r
        for r in plan_rows_view
        if not r.get("is_ad_hoc", False) and (r.get("confidence_pct") or 0) > 0
    ]
    day_confidence_pct = (
        round(sum(r.get("confidence_pct", 0) for r in _conf_rows) / len(_conf_rows))
        if _conf_rows
        else 0
    )
    # PRODUCCION-V3 Phase 4: ad-hoc count (already in plan_rows_view
    # with is_ad_hoc=True). Surfaced in the ad-hoc card so the cook
    # can see "3 horneados extra" without scrolling.
    day_adhoc_count = sum(1 for r in plan_rows_view if r.get("is_ad_hoc", False))

    # M2: split plan_rows_view into "needs action" vs "no recent demand"
    # so the operator doesn't scroll through 30+ products that already
    # have stock from yesterday. A row is "no demand" when:
    #   - it's not ad-hoc
    #   - qty_to_produce > 0 (it's planned for today, just from a template)
    #   - pending_pedido_qty == 0 (no pedidos demand it)
    #   - forecast_source in ('template', 'manual', 'override') meaning
    #     it was pre-loaded but has no recent rolling-4o demand signal
    # We surface "no demand" rows in a <details> at the bottom so the
    # operator can still see & override them, but they're not in the
    # main scroll path.
    _NO_DEMAND_SOURCES = {"template", "manual", "override"}
    primary_rows = []
    zero_demand_rows = []
    for r in plan_rows_view:
        if (
            not r.get("is_ad_hoc", False)
            and (r.get("pending_pedido_qty") or 0) == 0
            and r.get("forecast_source") in _NO_DEMAND_SOURCES
        ):
            zero_demand_rows.append(r)
        else:
            primary_rows.append(r)

    # 2026-10-07 table overhaul: apply filter chips, then sort, then page.
    # Filters apply ONLY to primary_rows — zero_demand_rows is a separate
    # <details> so its members are always shown in full when expanded.
    # `rows` is hard-clamped so any URL works (no 4xx).
    # `page` (1-based) plus `rows` gives the visible window; `show_all=1`
    # disables pagination entirely (operator asked: "we don't limit the
    # total amount — only per page").
    rows = max(1, min(100, int(rows)))
    show_all = 1 if int(show_all) == 1 else 0
    page = max(1, int(page))
    primary_rows = _apply_produccion_filters(
        primary_rows,
        allergen=filter_allergen,
        source=filter_source,
        with_pedidos=filter_with_pedidos,
        with_hecho=filter_with_hecho,
        with_surplus=filter_with_surplus,
    )
    primary_rows = _sort_produccion_rows(primary_rows, sort=sort, dir=dir)
    total_filtered = len(primary_rows)
    if show_all == 1:
        visible_rows = primary_rows
        page = 1
        total_pages = 1
    else:
        page = max(1, min(page, max(1, (total_filtered + rows - 1) // rows)))
        total_pages = max(1, (total_filtered + rows - 1) // rows)
        start = (page - 1) * rows
        visible_rows = primary_rows[start : start + rows]
    hidden_count = max(0, total_filtered - len(visible_rows))

    # 2026-10-07c: ingredients table smart-features. Filter by severity
    # then sort by the operator-chosen column. We mutate plan.lines in
    # place (a list copy) so the rest of the route doesn't see the
    # reordering. Unknown sort keys fall back to "severity" so a typo
    # never 500s.
    if ingredients_filter in ("falta", "justo", "suficiente"):
        plan_lines_filtered = []
        for ln in plan.lines:
            delta = ln.stock_on_hand - ln.qty_required
            pct = (ln.stock_on_hand / ln.qty_required * 100) if ln.qty_required > 0 else 100
            sev = "falta" if delta < 0 else ("justo" if pct < 80 else "suficiente")
            if sev == ingredients_filter:
                plan_lines_filtered.append(ln)
        # Sort the filtered list.
        plan.lines = _sort_ingredient_lines(
            plan_lines_filtered, sort=ingredients_sort, dir=ingredients_dir
        )
    else:
        plan.lines = _sort_ingredient_lines(
            list(plan.lines), sort=ingredients_sort, dir=ingredients_dir
        )

    return render(
        request,
        "produccion.html",
        {
            "plan": plan,
            "plan_rows_view": plan_rows_view,
            "primary_rows": primary_rows,
            "visible_rows": visible_rows,
            "hidden_count": hidden_count,
            "total_filtered": total_filtered,
            "rows_per_page": rows,
            "current_page": page,
            "total_pages": total_pages,
            "show_all": show_all == 1,
            "current_sort": sort,
            "current_dir": dir,
            "current_ingredients_sort": ingredients_sort,
            "current_ingredients_dir": ingredients_dir,
            "ingredients_filter": ingredients_filter,
            "active_filters": {
                "allergen": filter_allergen,
                "source": filter_source,
                "with_pedidos": filter_with_pedidos,
                "with_hecho": filter_with_hecho,
                "with_surplus": filter_with_surplus,
            },
            "zero_demand_rows": zero_demand_rows,
            "template_nudge": template_nudge,
            "has_weekly_template": has_weekly_template,
            "cold_start_kind": cold_start_kind,
            "for_date": plan.for_date.isoformat() if plan.for_date else "",
            # PRODUCCION-V3 Phase 1: day navigation. prev/next are ISO
            # strings for the prev/next calendar day. `today` is the
            # Asunción-local current date (the nav's "Hoy" button always
            # points to it, even when the current for_date is in the past).
            "prev_for_date": (plan.for_date - timedelta(days=1)).isoformat()
            if plan.for_date
            else "",
            "next_for_date": (plan.for_date + timedelta(days=1)).isoformat()
            if plan.for_date
            else "",
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
            "products_for_adhoc": [
                # T-2026-10-06e: enrich the product picker with forecast +
                # pending-pedidos demand so the modal can pre-fill the qty
                # input with a meaningful number instead of leaving it empty
                # (the previous version was opening qty=0, forcing the cook
                # to type the demand manually every time).
                {
                    "id": p.id,
                    "name": p.name,
                    "forecast_qty": float(
                        (demand_by_pid.get(p.id, None) and demand_by_pid[p.id].qty_forecast) or 0.0
                    ),
                    "pending_pedidos": float(ped_units_by_pid.get(p.id, 0.0)),
                }
                for p in session.execute(select(Product).order_by(Product.name)).scalars().all()
            ],
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
            # T-2026-10-06 (B.6+): expanded chip-list for drill-down
            # so the cook can see WHICH freezers/shifts are pending.
            "haccp_missing_items": expand_missing_items(
                _list_haccp_missing_for_date(session, plan.for_date)
            ),
            # T-2026-10-04 (C.4): substitution suggestions. For every
            # ingredient the plan is short on, surface alternative
            # products the cook can bake instead — ranked by Jaccard
            # similarity so the substitute tastes similar. Skipped when
            # the plan is fully stocked (avoids noise).
            # P38 (2026-10-07, Ivan): substitution_suggestions removed entirely.
            # The catalog has 58 products that are mostly 7-9-ingredient
            # variations of each other, so auto-suggested substitutes were
            # misleading (Stroopwafel as a substitute for Pan lactal). Pass
            # the short-lines to the template instead — the operator gets
            # the count and a /reorder link, period.
            "short_plan_lines": [
                ln for ln in plan.lines if (ln.stock_on_hand - ln.qty_required) < 0
            ],
        },
    )
