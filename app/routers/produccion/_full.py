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
from loguru import logger
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


# Sort key extractors — one per VALID_SORT_KEYS entry. Returns the
# PRIMARY comparison value for a given row; the wrapper below adds the
# product_name tiebreak. Adding a new sortable column = one entry here.
def _lote_final(row: dict):
    return (row.get("qty_to_produce") or 0) + (row.get("pending_pedido_qty") or 0)


_SORT_VALUE_EXTRACTORS = {
    "product": lambda r: (r.get("product_name") or "").lower(),
    "difficulty": lambda r: r.get("recipe_difficulty") or 0,
    "demand": lambda r: r.get("qty_demand_total") or 0,
    "meta": lambda r: r.get("qty_to_produce") or 0,
    "pedidos": lambda r: r.get("pending_pedido_qty") or 0,
    "lote": _lote_final,
    "hecho": lambda r: r.get("completed_qty") or 0,
    "sobrante": lambda r: r.get("batch_surplus_qty") or 0,
    # open < done < cancelled (alpha order), so 'open' sorts first asc
    "closure": lambda r: r.get("closure_status") or "open",
}


def _sort_value(row: dict, key: str):
    """Pull the comparison key out of a row dict. Returns a tuple so ties
    break on product_name (stable ordering). Unknown keys fall back to
    "lote" — matches the previous behavior of the `else: lote_final`
    branch."""
    extractor = _SORT_VALUE_EXTRACTORS.get(key, _lote_final)
    # secondary tiebreak: product name asc (stable)
    return (extractor(row), (row.get("product_name") or "").lower())


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

    def _line_sort_key(ln) -> tuple:
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
    values mean 'no filter for this group'. All filters combine as AND.
    """
    out = rows
    out = _filter_by_allergen(out, allergen)
    out = _filter_by_source(out, source)
    out = _filter_by_pedidos(out, with_pedidos)
    out = _filter_by_hecho(out, with_hecho)
    out = _filter_by_surplus(out, with_surplus)
    return out


def _filter_by_allergen(rows: list[dict], allergen: list[str]) -> list[dict]:
    """Filter rows by allergen match.

    Extracted from _apply_produccion_filters to reduce complexity.
    """
    if not allergen:
        return rows
    wanted = set(allergen)
    return [r for r in rows if _row_allergens(r) & wanted]


def _filter_by_source(rows: list[dict], source: list[str]) -> list[dict]:
    """Filter rows by source match.

    Extracted from _apply_produccion_filters to reduce complexity.
    """
    if not source:
        return rows
    wanted = set(source)
    return [r for r in rows if _row_source(r) in wanted]


def _filter_by_pedidos(rows: list[dict], with_pedidos: str) -> list[dict]:
    """Filter rows by pending pedido qty.

    Extracted from _apply_produccion_filters to reduce complexity.
    """
    if with_pedidos == "1":
        return [r for r in rows if (r.get("pending_pedido_qty") or 0) > 0]
    if with_pedidos == "0":
        return [r for r in rows if (r.get("pending_pedido_qty") or 0) == 0]
    return rows


def _filter_by_hecho(rows: list[dict], with_hecho: str) -> list[dict]:
    """Filter rows by completed qty.

    Extracted from _apply_produccion_filters to reduce complexity.
    """
    if with_hecho == "1":
        return [r for r in rows if (r.get("completed_qty") or 0) > 0]
    if with_hecho == "0":
        return [r for r in rows if (r.get("completed_qty") or 0) == 0]
    return rows


def _filter_by_surplus(rows: list[dict], with_surplus: str) -> list[dict]:
    """Filter rows by batch surplus percentage.

    Extracted from _apply_produccion_filters to reduce complexity.
    """
    if with_surplus == "1":
        return [r for r in rows if (r.get("batch_surplus_pct") or 0) >= 30]
    if with_surplus == "0":
        return [r for r in rows if (r.get("batch_surplus_pct") or 0) < 30]
    return rows


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
        return _produccion_week_view(request, session, week or today)

    if view == "month":
        return _produccion_month_view(request, session, today, month)

    # day view (default)
    return _produccion_day_view(
        request,
        session,
        for_date,
        overrides,
        shift=shift,
        ui=ui,
        sort=sort,
        dir=dir,
        rows=rows,
        page=page,
        show_all=show_all,
        filter_allergen=filter_allergen,
        filter_source=filter_source,
        filter_with_pedidos=filter_with_pedidos,
        filter_with_hecho=filter_with_hecho,
        filter_with_surplus=filter_with_surplus,
        ingredients_sort=ingredients_sort,
        ingredients_dir=ingredients_dir,
        ingredients_filter=ingredients_filter,
    )


# ----------------------------------------------------------------------------
# View-specific helpers for produccion_worksheet.
#
# These were extracted from the original CC=166 monolith (SASKIA-211x batch-3).
# The orchestrator now reads as a 3-branch dispatcher; each view's logic is
# in its own _view helper below. Day-view internals (kwargs) are grouped into
# _step_N helpers within _produccion_day_view for readability.
# ----------------------------------------------------------------------------


# --- _step_1: shared aggregation across N days (week + month) --------------


def _aggregate_plan_across_days(session, days, week_start):
    """Aggregate per-product qty arrays + ingredient requirements across a
    list of dates. Returns (product_rows, ing_required) where each row
    carries a `daily_qtys` list (length = len(days)) keyed by day_idx.
    Shared by week and month views."""
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
                    "daily_qtys": [0.0] * len(days),
                }
            day_idx = (d - week_start).days if week_start else (d.day - 1)
            product_rows[r.product_id]["daily_qtys"][day_idx] = r.qty_to_produce
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
    return product_rows, ing_required


def _sort_product_rows_by_name(product_rows: dict[int, dict]) -> list[dict]:
    """Flatten the aggregation dict into the template-shaped list of
    {product_name, product_id, recipe_id, daily_qtys}, sorted by name."""
    return [
        {
            "product_name": v["product_name"],
            "product_id": pid,
            "recipe_id": v["recipe_id"],
            "daily_qtys": v["daily_qtys"],
        }
        for pid, v in sorted(product_rows.items(), key=lambda x: x[1]["product_name"])
    ]


def _produccion_sales_in_range(session, start_dt, end_dt) -> list[dict]:
    """Top products by units sold in [start_dt, end_dt]. Used by both week
    and month views to render the "Lo que ya vendimos" column."""
    sales_rows = session.execute(
        select(Sale.product_id, Product.name, func.sum(Sale.qty), func.count(Sale.id))
        .join(Product, Sale.product_id == Product.id)
        .where(Sale.sold_at >= start_dt, Sale.sold_at <= end_dt, Sale.voided_at.is_(None))
        .group_by(Sale.product_id, Product.name)
        .order_by(func.sum(Sale.qty).desc())
    ).all()
    return [
        {"product_id": r[0], "product_name": r[1], "total_qty": float(r[2]), "n_sales": r[3]}
        for r in sales_rows
    ]


# --- Week view --------------------------------------------------------------


def _produccion_week_view(request, session, week):
    """Build the 7-day grid. Aggregates plan_production() per day, fetches
    the week's sales, renders produccion.html in week layout."""
    week_start = _week_monday(week)
    days = [week_start + timedelta(days=i) for i in range(7)]
    product_rows, ing_required = _aggregate_plan_across_days(session, days, week_start)
    week_plan_rows = _sort_product_rows_by_name(product_rows)
    week_ingredients = sorted(ing_required.values(), key=lambda x: x["ingredient_name"])
    prev_week = (week_start - timedelta(days=7)).isoformat()
    next_week = (week_start + timedelta(days=7)).isoformat()
    from datetime import timezone as _tz_cls

    week_end_dt = datetime.combine(week_start + timedelta(days=6), datetime.max.time()).replace(
        tzinfo=_tz_cls.utc
    )
    week_start_dt = datetime.combine(week_start, datetime.min.time()).replace(tzinfo=_tz_cls.utc)
    week_sales = _produccion_sales_in_range(session, week_start_dt, week_end_dt)

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


# --- Month view -------------------------------------------------------------


_MONTH_NAMES = [
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


def _produccion_month_view(request, session, today, month):
    """Build the month grid. Same shape as week but with a fixed-length
    `daily_qtys` per product (ndays) and an extra revenue total."""
    if month:
        year, mon = (int(x) for x in month.split("-"))
    else:
        year, mon = today.year, today.month
    ndays = _calendar.monthrange(year, mon)[1]
    days = [date(year, mon, d) for d in range(1, ndays + 1)]
    product_rows, ing_required = _aggregate_plan_across_days(session, days, None)
    month_plan_rows = _sort_product_rows_by_name(product_rows)
    month_ingredients = sorted(ing_required.values(), key=lambda x: x["ingredient_name"])
    prev_month = date(year, mon, 1) - timedelta(days=1)
    next_month = date(year, mon, ndays) + timedelta(days=1)
    from datetime import timezone as _tz_cls

    month_end_dt = datetime(year, mon, ndays, 23, 59, 59, tzinfo=_tz_cls.utc)
    month_start_dt = datetime(year, mon, 1, 0, 0, 0, tzinfo=_tz_cls.utc)
    month_sales = _produccion_sales_in_range(session, month_start_dt, month_end_dt)
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
            "month_name": _MONTH_NAMES[mon],
            "month_days": list(range(1, ndays + 1)),
            "month_plan": type("obj", (object,), {"rows": month_plan_rows})(),
            "month_ingredients": month_ingredients,
            "prev_month_iso": prev_month.strftime("%Y-%m"),
            "next_month_iso": next_month.strftime("%Y-%m"),
            "month_sales": month_sales,
            "month_revenue_gs": int(total_revenue),
        },
    )


# --- Day view ---------------------------------------------------------------
#
# The day view is the dense one. It is itself split into _step_1..5 helpers
# below so the orchestrator below reads like a flowchart.


def _step_1_load_pending_pedidos(session, target_date):
    """Load pending/confirmed/ready pedidos for target_date (kitchen ticket
    panel) plus a per-product unit count for the plan-row "+N por pedidos"
    badges. Returns (pending_pedidos_list, ped_units_by_pid)."""
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
    ped_units_by_pid: dict[int, float] = {}
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
            ped_units_by_pid[ln.product_id] = ped_units_by_pid.get(ln.product_id, 0.0) + float(
                ln.qty
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
    return pending_pedidos, ped_units_by_pid


def _step_2_load_completions(session, target_date):
    """Load ProductionCompletion rows for target_date and bucket them into:
    - completions_by_pid: dict[pid -> qty completed today]
    - closure_status_by_pid, closure_notes_by_pid: closure state from the
      cook's "Cerrar turno" tap."""
    from app.rms.eod_completions import completions_for_date as _eod_for_date
    from app.rms.models import ProductionCompletion

    completions_by_pid = _eod_for_date(session, target_date)
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
    return completions_by_pid, closure_status_by_pid, closure_notes_by_pid


def _step_3_load_recipe_pricing(session):
    """Load recipe_pricing rows keyed by recipe_id. Returns a dict of
    {cost_per_unit_gs, retail_gs} namedtuple-like."""
    from sqlalchemy import text as _sa_text

    pricing_rows = session.execute(
        _sa_text("SELECT recipe_id, cost_per_unit_gs, retail_gs FROM recipe_pricing")
    ).all()
    return {
        row.recipe_id: type(
            "P", (), {"cost_per_unit_gs": row.cost_per_unit_gs, "retail_gs": row.retail_gs}
        )()
        for row in pricing_rows
    }


def _step_4_filter_plan_rows(session, plan):
    """M1: drop plan rows for soft-deleted (is_available=False) products so
    the active plan never shows "Producto eliminado". Logs a debug hint
    when rows are filtered. Returns (plan_rows_source, product_by_id)."""
    import logging as _logging

    _all_products = session.execute(select(Product).order_by(Product.name)).scalars().all()
    product_by_id = {p.id: p for p in _all_products}
    visible_product_ids = {p.id for p in _all_products if p.is_available}
    plan_rows_filtered = [r for r in plan.rows if r.product_id in visible_product_ids]
    if len(plan_rows_filtered) != len(plan.rows):
        _logging.getLogger(__name__).info(
            "M1: hid %d plan rows for inactive products",
            len(plan.rows) - len(plan_rows_filtered),
        )
    return plan_rows_filtered, product_by_id


def _step_5_build_recipe_row(
    r,
    *,
    completions_by_pid,
    ped_units_by_pid,
    recipe_by_id,
    product_by_id,
    pricing_by_recipe_id,
    demand_by_pid,
    closure_status_by_pid,
    closure_notes_by_pid,
):
    """Build the per-product row dict the day-view table renders. Encapsulates
    the 25+ field dict literal + ternaries so the orchestrator stays flat."""
    recipe_obj = recipe_by_id.get(r.recipe_id) if r.recipe_id else None
    product_obj = product_by_id.get(r.product_id)
    yield_qty = recipe_obj.yield_qty if recipe_obj else None
    pricing_obj = pricing_by_recipe_id.get(r.recipe_id) if r.recipe_id else None
    demand = demand_by_pid.get(r.product_id)
    surplus = (
        _batch_surplus(qty_demand=r.qty_to_produce, yield_qty=yield_qty)
        if (r.recipe_id and recipe_obj and yield_qty and r.qty_to_produce > 0)
        else None
    )
    return {
        "product_id": r.product_id,
        "product_name": r.product_name,
        "recipe_id": r.recipe_id,
        "qty_to_produce": r.qty_to_produce,
        "forecast_source": r.forecast_source,
        "confidence_pct": r.confidence_pct,
        "completed_qty": completions_by_pid.get(r.product_id, 0.0),
        "pending_pedido_qty": ped_units_by_pid.get(r.product_id, 0.0),
        "is_ad_hoc": False,
        # T-2026-10-04 (P0): batch-size context (recipe yield labels).
        "batch_qty": yield_qty if yield_qty else None,
        "batch_unit": (recipe_obj.yield_unit if recipe_obj and yield_qty else None),
        # T-2026-10-05 (B.3): fermentation reminder per row.
        "fermentation_reminder": (
            _fermentation_reminder(getattr(recipe_obj, "fermentation_minutes", None))
            if recipe_obj and getattr(recipe_obj, "fermentation_minutes", None)
            else None
        ),
        "portion_label": (product_obj.portion_label if product_obj else None),
        # T-2026-10-05 (B.9): surplus estimate per recipe batch.
        "batch_surplus_qty": (surplus["surplus_qty"] if surplus else None),
        "batch_surplus_pct": (surplus["surplus_pct"] if surplus else None),
        # T-2026-10-04 (C.5): inline cost + margin per row.
        "cost_per_unit_gs": int(pricing_obj.cost_per_unit_gs) if pricing_obj else 0,
        "retail_gs": int(pricing_obj.retail_gs) if pricing_obj else 0,
        # T-2026-10-04 (C.6): allergen + difficulty badges.
        "recipe_difficulty": (recipe_obj.difficulty if recipe_obj else None),
        "recipe_allergens": (recipe_obj.allergens if recipe_obj else None),
        # PRODUCCION-V2 cutover: demand fields (ui is always "v2" now).
        "qty_demand_total": float(demand.qty_total) if demand else 0.0,
        "qty_demand_pedidos": float(demand.qty_pedidos) if demand else 0.0,
        "qty_demand_pedidos_pending": (
            float(demand.qty_pedidos - demand.qty_pedidos_confirmed) if demand else 0.0
        ),
        "qty_demand_forecast": float(demand.qty_forecast) if demand else 0.0,
        # PRODUCCION-V2 Fase 2: closure state per product.
        "closure_status": closure_status_by_pid.get(r.product_id, "open"),
        "closure_notes": closure_notes_by_pid.get(r.product_id),
        # PRODUCCION-V3 Phase 2: 4 source buckets + 5-band confidence.
        "source_bucket": source_to_bucket(r.forecast_source, is_ad_hoc=False),
        "confidence_band": _confidence_band_for_pct(r.confidence_pct),
    }


def _step_6_append_ad_hoc_rows(
    plan_rows_view,
    *,
    completions_by_pid,
    ped_units_by_pid,
    demand_by_pid,
    closure_status_by_pid,
    closure_notes_by_pid,
    session,
):
    """Append rows for products COMPLETED today but NOT in the plan row
    list (walk-ins, ad-hoc bakes). Filters inactive products and skipped
    rows that already appear in plan_rows_view."""
    planned_pids = {r["product_id"] for r in plan_rows_view}
    for pid, qty in completions_by_pid.items():
        if pid in planned_pids:
            continue
        prod_obj = session.get(Product, pid)
        if prod_obj is None or not prod_obj.is_available:
            continue
        demand = demand_by_pid.get(pid)
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
                "source_bucket": "horneado-extra",
                "confidence_band": "conf-vhigh",
                "batch_qty": None,
                "batch_unit": None,
                "portion_label": prod_obj.portion_label,
                "batch_surplus_qty": None,
                "batch_surplus_pct": None,
                "cost_per_unit_gs": 0,
                "retail_gs": 0,
                "recipe_difficulty": None,
                "recipe_allergens": None,
                "qty_demand_total": float(demand.qty_total) if demand else 0.0,
                "qty_demand_pedidos": float(demand.qty_pedidos) if demand else 0.0,
                "qty_demand_pedidos_pending": (
                    float(demand.qty_pedidos - demand.qty_pedidos_confirmed) if demand else 0.0
                ),
                "qty_demand_forecast": float(demand.qty_forecast) if demand else 0.0,
                "closure_status": closure_status_by_pid.get(pid, "open"),
                "closure_notes": closure_notes_by_pid.get(pid),
            }
        )


def _step_7_compute_closure_counts(plan_rows_view):
    """PRODUCCION-V2 Fase 2: tally per-row closure state into the day-level
    header counts. Counts only rows in plan_rows_view (a product with a
    completion that's NOT in today's plan doesn't pollute the count)."""
    day_open_count = 0
    day_done_count = 0
    day_cancelled_count = 0
    for r in plan_rows_view:
        _cs = r.get("closure_status", "open")
        if _cs == "done":
            day_done_count += 1
        elif _cs == "cancelled":
            day_cancelled_count += 1
        else:
            day_open_count += 1
    day_total_count = day_open_count + day_done_count + day_cancelled_count
    return {
        "day_open_count": day_open_count,
        "day_done_count": day_done_count,
        "day_cancelled_count": day_cancelled_count,
        "day_total_count": day_total_count,
    }


def _step_8_compute_hero_stats(plan_rows_view):
    """PRODUCCION-V3 Phase 3 + 4: hero stats — total products, total lote
    final (meta + pedidos), weighted-average confidence, ad-hoc count.
    Excludes ad-hoc rows from the confidence average (they're 100% by
    definition)."""
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
    day_adhoc_count = sum(1 for r in plan_rows_view if r.get("is_ad_hoc", False))
    return {
        "day_productos_count": len(plan_rows_view),
        "day_lote_final_total": day_lote_final_total,
        "day_pedidos_total": day_pedidos_total,
        "day_confidence_pct": day_confidence_pct,
        "day_adhoc_count": day_adhoc_count,
    }


def _step_9_split_zero_demand(plan_rows_view):
    """M2: split into "needs action" (primary) vs "no recent demand"
    (zero_demand). A row is "no demand" when it's not ad-hoc, has zero
    pending-pedido demand, and its forecast_source is template/manual/override
    (pre-loaded but with no recent rolling demand signal)."""
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
    return primary_rows, zero_demand_rows


def _step_10_pagination(primary_rows, rows_per_page, page, show_all):
    """Apply filter + sort + pagination. `rows` is hard-clamped so any URL
    works (no 4xx). `show_all=1` disables pagination entirely. Returns
    (visible_rows, total_filtered, total_pages, current_page, hidden_count)."""
    page = max(1, min(page, max(1, (len(primary_rows) + rows_per_page - 1) // rows_per_page)))
    total_pages = max(1, (len(primary_rows) + rows_per_page - 1) // rows_per_page)
    if show_all == 1:
        visible_rows = primary_rows
        page = 1
        total_pages = 1
    else:
        start = (page - 1) * rows_per_page
        visible_rows = primary_rows[start : start + rows_per_page]
    total_filtered = len(primary_rows)
    hidden_count = max(0, total_filtered - len(visible_rows))
    return visible_rows, total_filtered, total_pages, page, hidden_count


def _step_11_cold_start_state(session, plan, plan_rows_view, _has_sales):
    """PRO-TEMPLATE-NUDGE + cold-start bootstrap state. Returns
    (cold_start_kind, template_nudge, has_weekly_template)."""
    _weekday = plan.for_date.weekday() if plan.for_date else 0
    _template_rows = get_weekly_template(session).get(_weekday, {})
    template_nudge = (not _template_rows) and _has_sales > 0
    has_weekly_template = bool(_template_rows)
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
    if sum(1 for r in plan_rows_view if r["qty_to_produce"] > 0) == 0 and cold_start_kind is None:
        cold_start_kind = "no_rows"
    return cold_start_kind, template_nudge, has_weekly_template


def _step_12_waste_totals(session, target_date):
    """PRODUCCION-V2 Tier 3-B: today's merma count + cost + 7-day avg."""
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
    return today_waste_count, today_waste_cost_gs, avg_daily_waste_cost_gs


def _step_13_daily_target_actual(session, target_date, plan):
    """P-14: daily_target (sum of plan rows, M1 hides inactive) and
    daily_actual (sum of non-voided Sale.qty for the day)."""
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
    return daily_target, float(daily_actual)


def _step_14_load_demand_safe(session, target_date):
    """PRODUCCION-V2 cutover: get_demand(session, for_date). The try/except
    is preserved so a bad cache state can never break the page."""
    try:
        return get_demand(session, for_date=target_date)
    except Exception:
        return {}


def _step_15_confidence_calibration(plan_rows_view):
    """T-2026-10-04 (P2): confidence calibration — surface low-confidence
    rows + the 4-band count dict so the cook knows which auto-suggestions
    need manual review."""
    low_confidence_count = sum(
        1
        for r in plan_rows_view
        if r.get("confidence_pct", 0) < 70 and not r.get("is_ad_hoc", False)
    )
    confidence_bands = {
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
    }
    return low_confidence_count, confidence_bands


def _produccion_day_view(
    request,
    session,
    for_date,
    overrides,
    *,
    shift: str = "",
    ui: str = "v2",
    sort: str = "lote",
    dir: str = "desc",
    rows: int = 20,
    page: int = 1,
    show_all: int = 0,
    filter_allergen: list[str] | None = None,
    filter_source: list[str] | None = None,
    filter_with_pedidos: str = "",
    filter_with_hecho: str = "",
    filter_with_surplus: str = "",
    ingredients_sort: str = "severity",
    ingredients_dir: str = "asc",
    ingredients_filter: str = "",
):
    """The dense day-view table. Orchestrates _step_1..15 helpers below."""
    plan = plan_production(session, for_date=for_date, manual_forecast=overrides or None)
    target_date = for_date or _asuncion_today()

    if filter_allergen is None:
        filter_allergen = []
    if filter_source is None:
        filter_source = []

    # _step_1..2: load pedidos + completions
    pending_pedidos, ped_units_by_pid = _step_1_load_pending_pedidos(session, target_date)
    completions_by_pid, closure_status_by_pid, closure_notes_by_pid = _step_2_load_completions(
        session, target_date
    )

    # _step_3..4: pricing + filtered plan rows
    pricing_by_recipe_id = _step_3_load_recipe_pricing(session)
    plan_rows_source, product_by_id = _step_4_filter_plan_rows(session, plan)
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
        # Demand forecast fallback — empty dict keeps the plan grid rendering
        # without forecasts; operator can still manually set quantities.
        logger.debug("get_demand fallback in produccion day view", exc_info=True)
        demand_by_pid = {}

    # _step_5..6: build plan_rows_view (recipe rows + ad-hoc rows)
    plan_rows_view = [
        _step_5_build_recipe_row(
            r,
            completions_by_pid=completions_by_pid,
            ped_units_by_pid=ped_units_by_pid,
            recipe_by_id=recipe_by_id,
            product_by_id=product_by_id,
            pricing_by_recipe_id=pricing_by_recipe_id,
            demand_by_pid=demand_by_pid,
            closure_status_by_pid=closure_status_by_pid,
            closure_notes_by_pid=closure_notes_by_pid,
        )
        for r in plan_rows_source
    ]
    _step_6_append_ad_hoc_rows(
        plan_rows_view,
        completions_by_pid=completions_by_pid,
        ped_units_by_pid=ped_units_by_pid,
        demand_by_pid=demand_by_pid,
        closure_status_by_pid=closure_status_by_pid,
        closure_notes_by_pid=closure_notes_by_pid,
        session=session,
    )

    # _step_7..9: hero stats + closure counts + zero-demand split
    closure_counts = _step_7_compute_closure_counts(plan_rows_view)
    hero_stats = _step_8_compute_hero_stats(plan_rows_view)
    primary_rows, zero_demand_rows = _step_9_split_zero_demand(plan_rows_view)

    # _step_11..13: cold-start, waste, daily target/actual
    _has_sales = (
        session.scalar(
            select(func.count()).select_from(Sale).where(Sale.product_id.in_(select(Product.id)))
        )
        or 0
    )
    cold_start_kind, template_nudge, has_weekly_template = _step_11_cold_start_state(
        session, plan, plan_rows_view, _has_sales
    )
    today_waste_count, today_waste_cost_gs, avg_daily_waste_cost_gs = _step_12_waste_totals(
        session, target_date
    )
    daily_target, daily_actual = _step_13_daily_target_actual(session, target_date, plan)

    # Yesterday snapshot
    yesterday = target_date - timedelta(days=1)
    yesterday_completions = get_day_completions(session, yesterday)
    yesterday_total_qty = sum(yesterday_completions.values())
    yesterday_count = len(yesterday_completions)

    # 2026-10-07 table overhaul: filter → sort → paginate
    rows_per_page = max(1, min(100, int(rows)))
    show_all_int = 1 if int(show_all) == 1 else 0
    current_page = max(1, int(page))
    primary_rows = _apply_produccion_filters(
        primary_rows,
        allergen=filter_allergen,
        source=filter_source,
        with_pedidos=filter_with_pedidos,
        with_hecho=filter_with_hecho,
        with_surplus=filter_with_surplus,
    )
    primary_rows = _sort_produccion_rows(primary_rows, sort=sort, dir=dir)
    visible_rows, total_filtered, total_pages, current_page, hidden_count = _step_10_pagination(
        primary_rows, rows_per_page, current_page, show_all_int
    )

    # 2026-10-07c: ingredients table smart-features
    if ingredients_filter in ("falta", "justo", "suficiente"):
        plan_lines_filtered = []
        for ln in plan.lines:
            delta = ln.stock_on_hand - ln.qty_required
            pct = (ln.stock_on_hand / ln.qty_required * 100) if ln.qty_required > 0 else 100
            sev = "falta" if delta < 0 else ("justo" if pct < 80 else "suficiente")
            if sev == ingredients_filter:
                plan_lines_filtered.append(ln)
        plan.lines = _sort_ingredient_lines(
            plan_lines_filtered, sort=ingredients_sort, dir=ingredients_dir
        )
    else:
        plan.lines = _sort_ingredient_lines(
            list(plan.lines), sort=ingredients_sort, dir=ingredients_dir
        )

    # Confidence calibration
    low_confidence_count, confidence_bands = _step_15_confidence_calibration(plan_rows_view)

    # Closed-day flag
    closed_day = session.get(ProductionClosedDay, target_date)

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
            "rows_per_page": rows_per_page,
            "current_page": current_page,
            "total_pages": total_pages,
            "show_all": show_all_int == 1,
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
            "prev_for_date": (plan.for_date - timedelta(days=1)).isoformat()
            if plan.for_date
            else "",
            "next_for_date": (plan.for_date + timedelta(days=1)).isoformat()
            if plan.for_date
            else "",
            "today_for_date": _asuncion_today().isoformat(),
            "view": "day",
            "ui_version": ui,
            **closure_counts,
            **hero_stats,
            "source_labels": FORECAST_SOURCE_LABELS,
            "source_help": FORECAST_SOURCE_HELP,
            "source_buckets": SOURCE_BUCKETS,
            "confidence_bands_def": CONFIDENCE_BANDS,
            "overrides": overrides,
            "recipes": session.execute(select(Recipe).order_by(Recipe.name)).scalars().all(),
            "pending_pedidos": pending_pedidos,
            "daily_target": daily_target,
            "daily_actual": daily_actual,
            "shift_saved": int(request.query_params.get("shift_saved", 0)),
            "adhoc_added": request.query_params.get("adhoc_added") == "1",
            "concurrent_modify": request.query_params.get("concurrent_modify") == "1",
            "products_for_adhoc": [
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
            "seed_products": [
                {"product_id": p.id, "product_name": p.name}
                for p in session.execute(select(Product).order_by(Product.name).limit(5))
                .scalars()
                .all()
            ],
            "closed_day_active": closed_day is not None,
            "closed_day_reason": closed_day.reason if closed_day else None,
            "closed_day_at": closed_day.closed_at.isoformat() if closed_day else None,
            "low_confidence_count": low_confidence_count,
            "confidence_bands": confidence_bands,
            "today_waste_count": today_waste_count,
            "today_waste_cost_gs": today_waste_cost_gs,
            "avg_daily_waste_cost_gs": avg_daily_waste_cost_gs,
            "yesterday_total_qty": yesterday_total_qty,
            "yesterday_count": yesterday_count,
            "shift": shift,
            "haccp_latest": _get_haccp_latest_for_date(session, plan.for_date),
            "haccp_alert": _haccp_alert_for_entry(
                _get_haccp_latest_for_date(session, plan.for_date)
            ),
            "haccp_missing_count": _count_haccp_missing_for_date(session, plan.for_date),
            "haccp_missing_items": expand_missing_items(
                _list_haccp_missing_for_date(session, plan.for_date)
            ),
            "short_plan_lines": [
                ln for ln in plan.lines if (ln.stock_on_hand - ln.qty_required) < 0
            ],
        },
    )
