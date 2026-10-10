"""app/routers/dashboard.py — Inicio: ventas/COGS/margen/ranking/avisos.

Per dev plan §9 Task 7 + v2 §11 (timezone).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, Response
from loguru import logger
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.analytics import (
    batch_stock_turnover,
    day_of_week_heatmap,
    ingredient_concentration,
    margin_erosion_alerts,
    recipe_complexity,
    top_margin_products,
)
from app.rms.charts import (
    bar_chart,
    line_chart,
    pie_donut,
)
from app.rms.config import ASUNCION_TZ
from app.rms.constants import DEFAULT_TAX_REGIME
from app.rms.costing import batch_products_cost_margin, batch_recipes_cost
from app.rms.dependencies import get_session
from app.rms.insights import build_actionable_insights, build_insights
from app.rms.models import (
    Ingredient,
    Product,
    Recipe,
    RiskItem,
    Sale,
    ShoppingListItem,
    WishlistItem,
)
from app.rms.money import to_int_gs
from app.services.template_render import render

router = APIRouter(dependencies=[Depends(require_login)])


def _period_window(period: str) -> tuple[datetime, datetime]:
    """Return [start, end) of the current period in Asunción local time.

    today: 00:00:00 → 23:59:59.999 (Asunción)
    week: Monday 00:00 → now (current ISO week)
    month: 1st of month 00:00 → now (current calendar month)
    """
    now_local = datetime.now(ASUNCION_TZ)
    if period == "today":
        start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    elif period == "week":
        iso_weekday = now_local.isoweekday()  # 1=Mon, 7=Sun
        monday_date = now_local.date() - timedelta(days=iso_weekday - 1)
        start = datetime.combine(monday_date, datetime.min.time()).replace(tzinfo=ASUNCION_TZ)
        end = now_local + timedelta(microseconds=1)
    elif period == "month":
        start = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now_local + timedelta(microseconds=1)
    elif period == "custom":
        # Fall back to "today" window if start/end aren't parsed;
        # the route handler is responsible for overriding these.
        start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    else:
        raise ValueError(f"Unknown period: {period}")
    return start, end


def _prior_period_window(period: str) -> tuple[datetime, datetime]:
    """Return [start, end) of the prior comparable period (Asunción local).

    today: yesterday 00:00 → 23:59:59.999
    week:  previous Mon-Sun, ending where this week started
    month: 1st of previous month → last day of previous month
    """
    now_local = datetime.now(ASUNCION_TZ)
    if period == "today":
        end = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        start = end - timedelta(days=1)
    elif period == "week":
        iso_weekday = now_local.isoweekday()
        this_monday_date = now_local.date() - timedelta(days=iso_weekday - 1)
        end = datetime.combine(this_monday_date, datetime.min.time()).replace(tzinfo=ASUNCION_TZ)
        start = end - timedelta(days=7)
    elif period == "month":
        first_this_month = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = first_this_month
        prev_month_last_day = first_this_month - timedelta(microseconds=1)
        start = prev_month_last_day.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        raise ValueError(f"Unknown period: {period}")
    return start, end


def _compute_window_totals(
    session: Session, start: datetime, end: datetime
) -> tuple[int, int, int, list[Sale], list[Sale], dict]:
    """Compute ventas/cogs/margen for sales in [start, end).

    Returns (ventas_gs, cogs_gs, margen_gs, sales_no_recipe, sales, batch_costs).
    batch_costs is exposed for downstream use by the ranking loop.
    """
    # Sales are stored naive-UTC; convert window to UTC for DB comparison.
    start_utc_naive = start.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc_naive = end.astimezone(timezone.utc).replace(tzinfo=None)

    sales = session.scalars(
        select(Sale).where(
            Sale.sold_at >= start_utc_naive,
            Sale.sold_at < end_utc_naive,
        )
    ).all()

    ventas_gs = sum(to_int_gs(Decimal(str(s.qty)) * Decimal(str(s.unit_price_gs))) for s in sales)

    products_in_window = sorted(
        {s.product for s in sales if s.product is not None},
        key=lambda p: p.id,
    )
    batch_costs = batch_products_cost_margin(session, products_in_window)

    cogs_gs = 0
    sales_no_recipe: list[Sale] = []
    for s in sales:
        if s.product is None or s.product.recipe_id is None:
            sales_no_recipe.append(s)
            continue
        cost, _margin = batch_costs.get(s.product_id, (None, (None, None)))
        if cost is None or cost.batch_cost_gs is None:
            sales_no_recipe.append(s)
            continue
        cogs_gs += to_int_gs(Decimal(str(s.qty)) * Decimal(str(cost.batch_cost_gs)))

    margen_gs = ventas_gs - cogs_gs
    return ventas_gs, cogs_gs, margen_gs, sales_no_recipe, sales, batch_costs


def _delta_pct(current: int, prior: int) -> dict[str, float | str | None]:
    """Compute percentage delta from prior to current.

    Returns {"pct": float|None, "direction": "up"|"down"|"neutral"|"new",
             "label": "12% arriba"|"8% abajo"|"—"|None}.

    2026-09-25 Inicio-v2 critique: when the current window has ZERO sales we
    suppress the delta entirely — "↓100% abajo" on an empty morning is a
    divide-by-zero artifact that reads as "the business died" every day
    until the first sale lands. Show a neutral label instead.
    """
    if prior == 0 and current == 0:
        return {"pct": None, "direction": "neutral", "label": None}
    if current == 0:
        # Empty current window: neutral state, never a -100% alarm.
        return {"pct": None, "direction": "neutral", "label": "sin ventas en el período"}
    if prior == 0:
        return {"pct": None, "direction": "new", "label": "nuevo"}
    pct = (current - prior) / prior * 100
    if abs(pct) < 0.5:
        return {"pct": 0.0, "direction": "neutral", "label": "sin cambio"}
    direction = "up" if pct > 0 else "down"
    label = f"{abs(pct):.0f}% {'arriba' if pct > 0 else 'abajo'}"
    return {"pct": pct, "direction": direction, "label": label}


def _compliance_alerts(session: Session) -> list[dict]:
    """Phase 1.A — Return list of expiring / missing regulatory IDs.

    Returns a list of dicts with 'severity', 'icon', 'message', 'days_remaining'.
    Empty list means everything is in order.
    """
    from datetime import date, datetime

    from app.rms.models import ComplianceInfo

    today = datetime.now(ASUNCION_TZ).date()
    alerts: list[dict] = []

    ci = session.get(ComplianceInfo, 1)
    if ci is None:
        return alerts

    def _parse_iso(s: str | None) -> datetime | date | None:
        if not s:
            return None
        try:
            dt = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=ASUNCION_TZ)
            return dt.date()
        except (ValueError, TypeError):
            return None

    checks = [
        ("inan_re_expiry", "INAN R.E. (Registro de Establecimiento)"),
        ("municipal_habilitacion_expiry", "Habilitación Municipal"),
        ("timbrado_expiry", "Timbrado (RESIMPLE)"),
    ]
    for field, label in checks:
        expiry = _parse_iso(getattr(ci, field))
        if expiry is None:
            continue
        days_left = (expiry - today).days
        if days_left < 0:
            alerts.append(
                {
                    "severity": "danger",
                    "icon": "⚠",
                    "message": f"{label} VENCIDO hace {abs(days_left)} días ({expiry.isoformat()}). Renová ya.",
                    "days_remaining": days_left,
                }
            )
        elif days_left <= 30:
            alerts.append(
                {
                    "severity": "warn",
                    "icon": "⏰",
                    "message": f"{label} vence en {days_left} días ({expiry.isoformat()}). Programá renovación.",
                    "days_remaining": days_left,
                }
            )

    # R.S.P.A. expiry check on products (only when requires_rspa=True)
    from app.rms.models import Product

    for p in (
        session.execute(
            select(Product).where(
                Product.requires_rspa.is_(True),
                Product.rspa_expiry.is_not(None),
            )
        )
        .scalars()
        .all()
    ):
        expiry = _parse_iso(p.rspa_expiry)
        if expiry is None:
            continue
        days_left = (expiry - today).days
        if days_left < 0:
            alerts.append(
                {
                    "severity": "danger",
                    "icon": "⚠",
                    "message": f"R.S.P.A. de '{p.name}' VENCIDA hace {abs(days_left)} días ({expiry.isoformat()}).",
                    "days_remaining": days_left,
                }
            )
        elif days_left <= 30:
            alerts.append(
                {
                    "severity": "warn",
                    "icon": "⏰",
                    "message": f"R.S.P.A. de '{p.name}' vence en {days_left} días.",
                    "days_remaining": days_left,
                }
            )

    # Missing critical IDs (info-level)
    missing = []
    if not ci.ruc:
        missing.append("RUC")
    if not ci.inan_re_number:
        missing.append("INAN R.E. N°")
    if not ci.director_tecnico:
        missing.append("Director Técnico")
    if ci.tax_regime == DEFAULT_TAX_REGIME and not ci.timbrado_number:
        missing.append("Timbrado (RESIMPLE)")
    if missing and not alerts:
        alerts.append(
            {
                "severity": "info",
                "icon": "ℹ",
                "message": f"Configurá: {', '.join(missing)} en Configuración → Información de Negocio.",
                "days_remaining": None,
            }
        )

    return alerts


@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> Response:
    """Home = the chooser. Same page as /puesto.

    The chooser is the navigation hub Kyrian made: it asks
    "¿Qué vas a hacer?" and shows the station cards (Cocina,
    Ventas, Inventario, Gerencia) plus a Dashboard card. The
    owner picks what to do; staff are auto-redirected to their
    pinned station by the gate middleware (decide()).
    """

    # noqa: arch-rule — uses `puesto` (current station) helper from stations; legitimate cross-router utility use
    from app.routers.stations import puesto

    return puesto(request)


@router.get("/inicio", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    period: str = Query("today", pattern="^(today|week|month|custom)$"),
    start: str | None = Query(None, description="Start date for custom range (YYYY-MM-DD)"),
    end: str | None = Query(None, description="End date for custom range (YYYY-MM-DD)"),
    chart_preset: str = Query("30d", pattern="^(7d|30d|90d|current_month|last_month)$"),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Home page = old /inicio view: hero actions + actionable insights +
    day-band links into sub-pages. Shows for all stations (gerencia, ventas,
    produccion, etc) — the page itself tells the user what to do next.
    /gerencia remains a separate dense KPI view reachable from the nav.
    (2026-10-08: the station-redirect try/except was removed with the
    chooser-home change — no silent except remains in this handler.)
    """
    range_start, range_end = _resolve_period_window(period, start, end)
    prior_start, prior_end = _prior_period_window(period if period != "custom" else "today")

    kpis = _build_kpi_cards(session, range_start, range_end, prior_start, prior_end)
    ranking = _build_product_ranking(session, range_start, range_end)
    stock_health = _build_stock_health(session)
    regulars_data = _build_regular_customers(session)
    birthdays = _build_birthdays(session)
    forecast = _build_forecast_headline(session)
    enrollment = _build_enrollment_kpis(session, range_start, range_end, prior_start, prior_end)
    ops_today_data = _build_ops_today_data(session, period)
    freshness = _build_freshness_data(session)
    recipes_status = _build_recipes_status(session, range_start, range_end)
    shopping_data = _build_shopping_data(session)
    wishlist_data = _build_wishlist_data(session)
    risk_data = _build_risk_data(session)

    return render(
        request,
        "inicio.html",
        {
            "period": period,
            "start_date_val": range_start.strftime("%Y-%m-%d") if range_start else "",
            "end_date_val": range_end.strftime("%Y-%m-%d") if range_end else "",
            **kpis,
            "ranking": ranking,
            "birthdays": birthdays,
            **stock_health,
            **regulars_data,
            **forecast,
            **enrollment,
            "recipes_no_cost": recipes_status["recipes_no_cost"],
            "sales_no_recipe": recipes_status["sales_no_recipe"],
            "dow_buckets": day_of_week_heatmap(session, days=90),
            "turnover": _build_turnover(session),
            "top_margin": top_margin_products(session, days=30, limit=5),
            "concentration": ingredient_concentration(session, days=90)[:5],
            "erosion_alerts": margin_erosion_alerts(session, threshold_pct=5.0),
            "complexity": recipe_complexity(session),
            "compliance_alerts": _compliance_alerts(session),
            "insights": build_insights(session),
            "chart_hourly": _build_hourly_sales_chart(kpis.get("_sales", []), ASUNCION_TZ),
            "chart_30day": _build_30day_sales_chart(session, preset=chart_preset),
            "chart_preset": chart_preset,
            "chart_payment_methods": _build_payment_methods_donut(kpis.get("_sales", [])),
            "top_products_revenue": _build_top_products_revenue(ranking),
            "actionable_insights": build_actionable_insights(session),
            **shopping_data,
            **wishlist_data,
            **risk_data,
            "data_freshness": datetime.now(ASUNCION_TZ).strftime("%H:%M:%S"),
            **ops_today_data,
            **freshness,
            "costs_incomplete": recipes_status["costs_incomplete"],
        },
    )


def _resolve_period_window(period: str, start: str | None, end: str | None) -> tuple:
    """Resolve the date range for the dashboard period.

    Extracted from dashboard to reduce complexity.
    """
    if period == "custom" and start and end:
        try:
            from datetime import datetime as dt_cls

            start_dt = dt_cls.strptime(start, "%Y-%m-%d").replace(tzinfo=ASUNCION_TZ)
            end_dt = dt_cls.strptime(end, "%Y-%m-%d").replace(tzinfo=ASUNCION_TZ)
            return (
                start_dt.replace(hour=0, minute=0, second=0, microsecond=0),
                end_dt.replace(hour=23, minute=59, second=59, microsecond=999999),
            )
        except ValueError:
            return _period_window("today")
    return _period_window(period)


def _build_kpi_cards(session, range_start, range_end, prior_start, prior_end):
    """Build KPI cards: ventas, cogs, margen with deltas.

    Extracted from dashboard to reduce complexity.
    """
    ventas_gs, cogs_gs, margen_gs, _sales_no_recipe, sales, _batch_costs = _compute_window_totals(
        session, range_start, range_end
    )
    prior_ventas_gs, prior_cogs_gs, prior_margen_gs, _, _, _ = _compute_window_totals(
        session, prior_start, prior_end
    )
    margen_pct_fmt = f"{(margen_gs / ventas_gs * 100):.1f}%" if ventas_gs > 0 else "—"

    return {
        "ventas_gs": ventas_gs,
        "cogs_gs": cogs_gs,
        "margen_gs": margen_gs,
        "margen_pct_fmt": margen_pct_fmt,
        "delta_ventas": _delta_pct(ventas_gs, prior_ventas_gs),
        "delta_cogs": _delta_pct(cogs_gs, prior_cogs_gs),
        "delta_margen": _delta_pct(margen_gs, prior_margen_gs),
        "_sales": sales,
    }


def _build_product_ranking(session, range_start, range_end):
    """Build product ranking by margin.

    Extracted from dashboard to reduce complexity.
    """
    _, _, _, _, sales, batch_costs = _compute_window_totals(session, range_start, range_end)
    ranking_dict = _aggregate_product_sales(sales, batch_costs)
    ranking = sorted(ranking_dict.values(), key=lambda r: r["margen_gs"], reverse=True)
    for r in ranking:
        if r["ventas_gs"] > 0:
            r["margen_ratio"] = r["margen_gs"] / r["ventas_gs"]
    return ranking


def _aggregate_product_sales(sales, batch_costs) -> dict[int, dict]:
    """Aggregate sales by product with margin calculation.

    Extracted from _build_product_ranking to reduce complexity.
    """
    ranking_dict: dict[int, dict] = {}
    for s in sales:
        if s.product is None:
            continue
        rid = s.product_id
        if rid not in ranking_dict:
            ranking_dict[rid] = {
                "name": s.product.name,
                "ventas_gs": 0,
                "margen_gs": 0,
                "qty": 0.0,
                "margen_ratio": None,
            }
        ranking_dict[rid]["ventas_gs"] += to_int_gs(
            Decimal(str(s.qty)) * Decimal(str(s.unit_price_gs))
        )
        ranking_dict[rid]["qty"] += s.qty
        if s.product.recipe_id is not None:
            cost, _margin = batch_costs.get(rid, (None, (None, None)))
            if cost is not None and cost.batch_cost_gs is not None:
                line_margin = to_int_gs(
                    Decimal(str(s.qty))
                    * (Decimal(str(s.unit_price_gs)) - Decimal(str(cost.batch_cost_gs)))
                )
                ranking_dict[rid]["margen_gs"] += line_margin
    return ranking_dict


def _build_stock_health(session) -> dict:
    """Build stock health LED data.

    Extracted from dashboard to reduce complexity.
    """
    stock_low = session.scalars(
        select(Ingredient).where(
            Ingredient.min_stock_qty > 0,
            Ingredient.stock_qty < Ingredient.min_stock_qty,
        )
    ).all()

    stock_negative_count = sum(1 for i in stock_low if (i.stock_qty or 0) < 0)
    if stock_negative_count > 0:
        severity = "danger"
        label = f"{stock_negative_count} en negativo"
    elif stock_low:
        severity = "warn"
        label = f"{len(stock_low)} bajo mínimo"
    else:
        severity = "success"
        label = "todo OK"

    return {
        "stock_low": [
            {
                "name": i.name,
                "stock_qty": i.stock_qty,
                "min_stock_qty": i.min_stock_qty,
                "unit": i.unit,
            }
            for i in stock_low
        ],
        "stock_health_severity": severity,
        "stock_health_label": label,
        "stock_negative_count": stock_negative_count,
        "stock_below_min_count": len(stock_low),
        "low_stock_alerts": [
            {
                "name": i.name,
                "stock_qty": i.stock_qty,
                "min_stock_qty": i.min_stock_qty,
                "unit": i.unit,
            }
            for i in stock_low[:5]
        ],
        "low_stock_alerts_with_severity": [
            {
                "name": i.name,
                "severity": "danger" if i.stock_qty < 0 else "warn",
                "detail": f"{i.stock_qty:.2f} {i.unit} (mínimo {i.min_stock_qty:.2f} {i.unit})",
            }
            for i in stock_low[:5]
        ],
    }


def _build_regular_customers(session) -> dict:
    """Build coffee regulars data (customers with 2+ sales in 30 days).

    Extracted from dashboard to reduce complexity.
    """
    from app.rms.models import Customer as _Customer

    thirty_days_ago = datetime.now(ASUNCION_TZ) - timedelta(days=30)
    regular_rows = session.execute(
        select(
            Sale.customer_id,
            func.count(Sale.id).label("n_visits"),
            func.coalesce(func.sum(Sale.qty * Sale.unit_price_gs), 0).label("lifetime_spend_gs"),
        )
        .where(
            Sale.customer_id.isnot(None),
            Sale.voided_at.is_(None),
            Sale.sold_at >= thirty_days_ago,
        )
        .group_by(Sale.customer_id)
        .having(func.count(Sale.id) >= 2)
        .order_by(func.count(Sale.id).desc())
        .limit(5)
    ).all()

    regulars: list[dict] = []
    if regular_rows:
        ids = [r.customer_id for r in regular_rows]
        customers = {
            c.id: c for c in session.scalars(select(_Customer).where(_Customer.id.in_(ids))).all()
        }
        for r in regular_rows:
            cust = customers.get(r.customer_id)
            if cust is None:
                continue
            regulars.append(
                {
                    "id": r.customer_id,
                    "name": (cust.name or "").strip(),
                    "n_visits": int(r.n_visits),
                    "lifetime_spend_gs": int(r.lifetime_spend_gs or 0),
                }
            )

    return {
        "regulars": regulars,
        "regulars_count_total": (
            session.scalar(
                select(func.count()).select_from(
                    select(Sale.customer_id)
                    .where(
                        Sale.customer_id.isnot(None),
                        Sale.voided_at.is_(None),
                        Sale.sold_at >= thirty_days_ago,
                    )
                    .group_by(Sale.customer_id)
                    .having(func.count(Sale.id) >= 2)
                    .subquery()
                )
            )
            or 0
        ),
    }


def _build_birthdays(session) -> list[dict]:
    """Build upcoming birthdays (next 7 days).

    Extracted from dashboard to reduce complexity.
    """
    from app.rms.models import Customer

    today = datetime.now(ASUNCION_TZ).date()
    customers = session.scalars(select(Customer)).all()
    birthdays = []
    for c in customers:
        bday_info = _parse_customer_birthday(c, today)
        if bday_info is None:
            continue
        days_until = (bday_info["date"] - today).days
        if days_until <= 7:
            birthdays.append(_format_birthday(c, bday_info, days_until))
    birthdays.sort(key=lambda b: b["days_until"])
    return birthdays


def _parse_customer_birthday(customer, today):
    """Parse customer birthday string and return next occurrence.

    Extracted from _build_birthdays to reduce complexity.
    Returns dict with 'date' key, or None if invalid.
    """
    from datetime import date as _date

    raw = (customer.birthday or "").strip()
    if not raw:
        return None
    parts = raw.replace("/", "-").split("-")
    if len(parts) == 3:
        mm, dd = parts[1], parts[2]
    elif len(parts) == 2:
        mm, dd = parts
    else:
        return None
    if not (mm.isdigit() and dd.isdigit()):
        return None
    try:
        bday = _date(today.year, int(mm), int(dd))
    except ValueError:
        return None
    if bday < today:
        try:
            bday = _date(today.year + 1, int(mm), int(dd))
        except ValueError:
            return None
    return {"date": bday}


def _format_birthday(customer, bday_info, days_until) -> dict:
    """Format birthday for template.

    Extracted from _build_birthdays to reduce complexity.
    """
    return {
        "name": (customer.name or "").title(),
        "customer_id": customer.id,
        "days_until": days_until,
        "when": "hoy"
        if days_until == 0
        else ("mañana" if days_until == 1 else f"en {days_until} días"),
        "consent": bool(customer.marketing_consent),
    }


def _build_forecast_headline(session) -> dict:
    """Build day-of-week-aware forecast for tomorrow.

    Extracted from dashboard to reduce complexity.
    """
    from datetime import datetime as _dt_b2

    from app.rms.config import ASUNCION_TZ as _tz_b2

    tomorrow_date = (_dt_b2.now(_tz_b2) + timedelta(days=1)).date()
    tomorrow_dow = tomorrow_date.weekday()
    tomorrow_label = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"][
        tomorrow_dow
    ]
    all_products = session.scalars(select(Product)).all()
    forecast_window_start = _dt_b2.now(timezone.utc) - timedelta(days=84)
    forecast_rows = session.execute(
        select(Sale.product_id, Sale.sold_at, Sale.qty).where(
            Sale.product_id.in_([p.id for p in all_products]),
            Sale.sold_at >= forecast_window_start,
            Sale.voided_at.is_(None),
        )
    ).all()

    by_pid_dow_qty: dict[int, dict[int, float]] = {}
    by_pid_dow_count: dict[int, dict[int, int]] = {}
    by_pid_total_qty: dict[int, float] = {}
    for pid, sold_at, qty in forecast_rows:
        if sold_at is None:
            continue
        wd = sold_at.astimezone(_tz_b2).weekday()
        dow_qty = by_pid_dow_qty.setdefault(pid, {})
        dow_count = by_pid_dow_count.setdefault(pid, {})
        dow_qty[wd] = dow_qty.get(wd, 0.0) + float(qty or 0)
        dow_count[wd] = dow_count.get(wd, 0) + 1
        by_pid_total_qty[pid] = by_pid_total_qty.get(pid, 0.0) + float(qty or 0)

    forecast_units = 0.0
    forecast_revenue_gs = 0
    forecast_products_count = 0
    forecast_top = []
    for prod in all_products:
        target_count = by_pid_dow_count.get(prod.id, {}).get(tomorrow_dow, 0)
        if target_count >= 4:
            qty = by_pid_dow_qty.get(prod.id, {}).get(tomorrow_dow, 0.0) / target_count
        else:
            qty = by_pid_total_qty.get(prod.id, 0.0) / 84
        if qty <= 0:
            continue
        forecast_products_count += 1
        forecast_units += qty
        rev = int(qty * (prod.sale_price_gs or 0))
        forecast_revenue_gs += rev
        forecast_top.append({"name": prod.name, "qty": qty, "revenue_gs": rev})
    forecast_top.sort(key=lambda x: -x["qty"])
    forecast_top = forecast_top[:5]
    forecast_confidence = (
        "high"
        if forecast_products_count >= 5
        else ("medium" if forecast_products_count >= 2 else "low")
    )

    return {
        "forecast_tomorrow_label": tomorrow_label,
        "forecast_tomorrow_date": tomorrow_date.isoformat(),
        "forecast_units": round(forecast_units),
        "forecast_revenue_gs": forecast_revenue_gs,
        "forecast_products_count": forecast_products_count,
        "forecast_top": forecast_top,
        "forecast_confidence": forecast_confidence,
    }


def _build_enrollment_kpis(session, range_start, range_end, prior_start, prior_end) -> dict:
    """Build enrollment KPI (% of sales with customer attached).

    Extracted from dashboard to reduce complexity.
    """
    enrollment_today_q = session.execute(
        select(
            func.count(Sale.id).label("total"),
            func.sum(case((Sale.customer_id.isnot(None), 1), else_=0)).label("with_customer"),
        ).where(
            Sale.sold_at >= range_start,
            Sale.sold_at < range_end,
            Sale.voided_at.is_(None),
        )
    ).one()
    total_today = int(enrollment_today_q.total or 0)
    with_today = int(enrollment_today_q.with_customer or 0)
    enrollment_pct_today = round((with_today / total_today) * 100, 1) if total_today > 0 else None

    enrollment_prior_q = session.execute(
        select(
            func.count(Sale.id).label("total"),
            func.sum(case((Sale.customer_id.isnot(None), 1), else_=0)).label("with_customer"),
        ).where(
            Sale.sold_at >= prior_start,
            Sale.sold_at < prior_end,
            Sale.voided_at.is_(None),
        )
    ).one()
    total_prior = int(enrollment_prior_q.total or 0)
    with_prior = int(enrollment_prior_q.with_customer or 0)
    enrollment_pct_prior = round((with_prior / total_prior) * 100, 1) if total_prior > 0 else None

    enrollment_delta_pp = (
        round(enrollment_pct_today - enrollment_pct_prior, 1)
        if enrollment_pct_today is not None and enrollment_pct_prior is not None
        else None
    )

    return {
        "enrollment_pct_today": enrollment_pct_today,
        "enrollment_pct_prior": enrollment_pct_prior,
        "enrollment_delta_pp": enrollment_delta_pp,
        "enrollment_total_today": total_today,
        "enrollment_with_today": with_today,
    }


def _build_ops_today_data(session, period) -> dict:
    """Build ops today data (operations count, ticket promedio, pedido counts).

    Extracted from dashboard to reduce complexity.
    """
    from app.rms.models import Pedido

    today_d = datetime.now(ASUNCION_TZ).date()
    tomorrow_d = today_d + timedelta(days=1)
    yesterday_d = today_d - timedelta(days=1)

    ped_counts = {"hoy": 0, "manana": 0}
    for p_row in session.execute(
        select(Pedido.promised_date, Pedido.status).where(
            Pedido.status.in_(["pending", "confirmed", "ready"])
        )
    ).all():
        if p_row.promised_date == today_d:
            ped_counts["hoy"] += 1
        elif p_row.promised_date == tomorrow_d:
            ped_counts["manana"] += 1

    return {
        "ops_today": _compute_ops_today(session, period),
        "ops_delta_label": _compute_ops_delta(session),
        "ticket_promedio_gs": _compute_ticket_promedio(session, period),
        "ticket_delta_label": None,
        "pedido_hoy": ped_counts["hoy"],
        "pedido_manana": ped_counts["manana"],
        "cierre_ayer_pendiente": _check_cierre_ayer(session, yesterday_d),
        "merma_hoy": _check_merma_hoy(session),
    }


def _compute_ops_today(session, period) -> int:
    """Compute operations count for today.

    Extracted from _build_ops_today_data to reduce complexity.
    """
    today_start = datetime.now(ASUNCION_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    if period != "today":
        return 0

    def is_naive(dt):
        return dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None

    today_start_cmp = (
        today_start
        if is_naive(today_start)
        else today_start.astimezone(timezone.utc).replace(tzinfo=None)
    )
    return (
        session.scalar(
            select(func.count(Sale.id)).where(
                Sale.sold_at >= today_start_cmp, Sale.voided_at.is_(None)
            )
        )
        or 0
    )


def _compute_ops_delta(session) -> str | None:
    """Compute ops delta vs prior week.

    Extracted from _build_ops_today_data to reduce complexity.
    """
    today_start = datetime.now(ASUNCION_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    prior_same_weekday = today_start - timedelta(days=7)
    prior_end = prior_same_weekday + timedelta(days=1)

    def is_naive(dt):
        return dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None

    prev_ops = 0
    for s in session.scalars(select(Sale).where(Sale.voided_at.is_(None))).all():
        sold = s.sold_at
        if sold is None:
            continue
        if is_naive(sold) != is_naive(prior_same_weekday):
            from datetime import timezone as _tz

            if is_naive(sold):
                sold = sold.replace(tzinfo=_tz.utc)
                prior_cmp, prior_end_cmp = prior_same_weekday, prior_end
            else:
                prior_cmp = prior_same_weekday.replace(tzinfo=None)
                prior_end_cmp = prior_end.replace(tzinfo=None)
        else:
            prior_cmp, prior_end_cmp = prior_same_weekday, prior_end
        if prior_cmp <= sold < prior_end_cmp:
            prev_ops += 1
    return None


def _compute_ticket_promedio(session, period) -> int:
    """Compute average ticket for today.

    Extracted from _build_ops_today_data to reduce complexity.
    """
    if period != "today":
        return 0
    today_start = datetime.now(ASUNCION_TZ).replace(hour=0, minute=0, second=0, microsecond=0)

    def is_naive(dt):
        return dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None

    today_start_cmp = (
        today_start
        if is_naive(today_start)
        else today_start.astimezone(timezone.utc).replace(tzinfo=None)
    )
    sales = session.scalars(
        select(Sale).where(Sale.sold_at >= today_start_cmp, Sale.voided_at.is_(None))
    ).all()
    if not sales:
        return 0
    total = sum(int(Decimal(str(s.qty)) * Decimal(str(s.unit_price_gs))) for s in sales)
    return int(total / len(sales))


def _check_cierre_ayer(session, yesterday_d) -> bool:
    """Check if yesterday's EOD is pending.

    Extracted from _build_ops_today_data to reduce complexity.
    """
    from app.rms.eod_completions import completions_for_date

    try:
        return not completions_for_date(session, yesterday_d)
    except Exception:
        return False


def _check_merma_hoy(session) -> bool:
    """Check if there's any waste log today.

    Extracted from _build_ops_today_data to reduce complexity.
    """
    from app.rms.models import WasteLog

    return bool(session.execute(select(WasteLog.id).limit(1)).first())


def _build_freshness_data(session) -> dict:
    """Build freshness/expiry data (48h expiry proxy).

    Extracted from dashboard to reduce complexity.
    """
    from app.rms.demand_freshness import freshness_flags

    vencer_48h_count = 0
    vencer_48h_gs = 0
    try:
        for f in freshness_flags(session):
            if f.urgency in ("expired", "critical"):
                vencer_48h_count += 1
                vencer_48h_gs += int(f.value_at_risk_gs or 0)
    except Exception as exc:
        logger.debug("dashboard expiry scan skipped: {}", exc)
    return {
        "vencer_48h_count": vencer_48h_count,
        "vencer_48h_gs": vencer_48h_gs,
    }


def _build_recipes_status(session, range_start, range_end) -> dict:
    """Build recipes status (costs completeness, no-cost recipes).

    Extracted from dashboard to reduce complexity.
    """
    all_recipes = list(session.scalars(select(Recipe)).all())
    batch_recipe_results = batch_recipes_cost(session, all_recipes)
    recipes_no_cost = [
        r
        for r in all_recipes
        if batch_recipe_results[r.id][0].batch_cost_gs is None and len(r.lines) > 0
    ]

    _, _, _, sales_no_recipe, _, _ = _compute_window_totals(session, range_start, range_end)
    sales_no_recipe_decor = [
        {
            "id": s.id,
            "product_name": s.product.name if s.product else "(deleted)",
            "sold_at_str": s.sold_at.strftime("%d/%m/%Y %H:%M") if s.sold_at else "",
        }
        for s in sales_no_recipe[:10]
    ]

    recipes_with_cost = len(all_recipes) - len(recipes_no_cost)
    costs_incomplete = None
    if all_recipes and len(recipes_no_cost):
        costs_incomplete = f"{int(recipes_with_cost / len(all_recipes) * 100)}% cargados"

    return {
        "recipes_no_cost": recipes_no_cost,
        "sales_no_recipe": sales_no_recipe_decor,
        "costs_incomplete": costs_incomplete,
    }


def _build_turnover(session) -> list:
    """Build stock turnover for top 8 ingredients.

    Extracted from dashboard to reduce complexity.
    """
    return list(
        batch_stock_turnover(
            session,
            [
                ing.id
                for ing in session.scalars(
                    select(Ingredient).where(Ingredient.stock_qty > 0).limit(8)
                ).all()
            ],
            days=30,
        ).values()
    )


def _build_shopping_data(session) -> dict:
    """Build shopping list data.

    Extracted from dashboard to reduce complexity.
    """
    items = (
        session.execute(select(ShoppingListItem).where(ShoppingListItem.purchased.is_(False)))
        .scalars()
        .all()
    )
    return {
        "sl_open_count": len(items),
        "sl_total_gs": sum(
            (i.qty_to_buy or 0) * (i.ingredient.purchase_price_gs or 0) for i in items
        ),
    }


def _build_wishlist_data(session) -> dict:
    """Build wishlist data.

    Extracted from dashboard to reduce complexity.
    """
    items = (
        session.execute(select(WishlistItem).where(WishlistItem.purchased.is_(False)))
        .scalars()
        .all()
    )
    return {
        "wishlist_count": len(items),
        "wishlist_total_gs": sum((i.unit_price_gs or 0) * (i.quantity or 0) for i in items),
    }


def _build_risk_data(session) -> dict:
    """Build risk data.

    Extracted from dashboard to reduce complexity.
    """
    items = session.execute(select(RiskItem).where(RiskItem.status == "activo")).scalars().all()
    return {
        "risk_count": len(items),
        "risk_severity_gs": sum((r.probability or 0) * (r.impact_gs or 0) for r in items),
    }


def _preset_label(preset: str) -> str:
    return {
        "7d": "últimos 7 días",
        "30d": "últimos 30 días",
        "90d": "últimos 90 días",
        "current_month": "mes en curso",
        "last_month": "mes anterior",
    }.get(preset, preset)


def _build_payment_methods_donut(sales: list[Sale]) -> str:
    """Build a donut chart of payment method distribution.

    Phase 14 #22 (sibling to hourly chart fix): uses post-discount
    line totals so the donut matches /recibo and /ventas. Previously
    aggregated `qty × unit_price` and overcounted discounted sales.
    """
    buckets: dict[str, int] = {}
    for s in sales:
        pm = s.payment_method or "Sin especificar"
        line_total = int(s.qty) * int(s.unit_price_gs) - int(s.discount_gs or 0)
        buckets[pm] = buckets.get(pm, 0) + max(line_total, 0)

    if not buckets:
        return '<p class="text-muted">Sin datos de pagos</p>'

    values = [(k, float(v)) for k, v in sorted(buckets.items(), key=lambda x: -x[1])]
    return pie_donut(
        values,
        size=140,
        label="Distribución de pagos",
    )


def _build_top_products_revenue(ranking: list[dict]) -> list[dict]:
    """Return top 5 products by revenue (already sorted by margin in dashboard).

    Re-sorts by revenue for the visual ranking.
    """
    by_revenue = sorted(ranking, key=lambda r: r["ventas_gs"], reverse=True)[:5]
    return [{"name": r["name"], "value": r["ventas_gs"]} for r in by_revenue]


def _build_hourly_sales_chart(sales: list[Sale], tz: ZoneInfo) -> str:
    """Return an HTML bar chart of sales by hour of day (Asunción local).

    The sibling refactor wave deleted this function. Re-implementing
    minimal: aggregates qty × unit_price by `hour` from each sale's
    ASUNCION-local timestamp. Returns empty-state HTML if no sales.
    """
    buckets: dict[int, float] = {h: 0.0 for h in range(24)}
    for s in sales:
        local = s.sold_at.astimezone(tz) if s.sold_at else None
        if local is None:
            continue
        # Use discounted line total to match _build_payment_methods_donut.
        line_total = int(s.qty) * int(s.unit_price_gs) - int(s.discount_gs or 0)
        buckets[local.hour] += max(line_total, 0) / 1_000_000  # → M ₲

    if sum(buckets.values()) <= 0:
        return '<p class="text-muted">Sin datos de ventas por hora</p>'

    values = [(f"{h:02d}h", v) for h, v in sorted(buckets.items())]
    return bar_chart(values, height=140, label="Ventas por hora (M₲)")


def _build_30day_sales_chart(session: Session, preset: str) -> dict:
    """Return a simple namespace with .preset, .preset_label, .html.

    The sibling refactor wave deleted this function. Re-implementing
    minimal: a sparkline-like line chart of daily sales totals for
    the requested preset window. Returns 0-data state if no sales.
    """
    days = {"7d": 7, "30d": 30, "90d": 90}.get(preset)
    if days is None:
        days = 30  # current_month / last_month → default 30d
    today = datetime.now(ASUNCION_TZ).date()
    start = today - timedelta(days=days - 1)

    rows = session.execute(
        select(Sale.sold_at, Sale.qty, Sale.unit_price_gs, Sale.discount_gs).where(
            Sale.sold_at >= datetime.combine(start, datetime.min.time(), tzinfo=ASUNCION_TZ)
        )
    ).all()
    daily: dict[str, float] = {}
    for r in rows:
        if r.sold_at is None:
            continue
        local = r.sold_at.astimezone(ASUNCION_TZ)
        key = local.date().isoformat()
        line_total = int(r.qty) * int(r.unit_price_gs) - int(r.discount_gs or 0)
        daily[key] = daily.get(key, 0.0) + max(line_total, 0) / 1_000_000  # M₲

    # Fill missing days with 0 so the chart x-axis is contiguous.
    series: list[tuple[str, float]] = []
    for i in range(days):
        d = (start + timedelta(days=i)).isoformat()
        series.append((d[-5:], daily.get(d, 0.0)))  # MM-DD label

    if sum(v for _, v in series) <= 0:
        html = '<p class="text-muted">Sin datos en el período</p>'
    else:
        html = line_chart(series, height=140, label=f"Tendencia ({_preset_label(preset)})")

    return {
        "preset": preset,
        "preset_label": _preset_label(preset),
        "html": html,
    }
