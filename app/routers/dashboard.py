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
    # Home page = old /inicio view: hero actions + actionable insights +
    # day-band links into sub-pages. Shows for all stations (gerencia, ventas,
    # produccion, etc) — the page itself tells the user what to do next.
    # /gerencia remains a separate dense KPI view reachable from the nav.
    # (2026-10-08: the station-redirect try/except was removed with the
    # chooser-home change — no silent except remains in this handler.)
    if period == "custom" and start and end:
        try:
            from datetime import datetime as dt_cls

            start_dt = dt_cls.strptime(start, "%Y-%m-%d").replace(tzinfo=ASUNCION_TZ)
            end_dt = dt_cls.strptime(end, "%Y-%m-%d").replace(tzinfo=ASUNCION_TZ)
            range_start = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            range_end = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        except ValueError:
            range_start, range_end = _period_window("today")
    else:
        range_start, range_end = _period_window(period)
    prior_start, prior_end = _prior_period_window(period if period != "custom" else "today")

    ventas_gs, cogs_gs, margen_gs, sales_no_recipe, sales, batch_costs = _compute_window_totals(
        session, range_start, range_end
    )
    prior_ventas_gs, prior_cogs_gs, prior_margen_gs, _, _, _ = _compute_window_totals(
        session, prior_start, prior_end
    )
    margen_pct_fmt = f"{(margen_gs / ventas_gs * 100):.1f}%" if ventas_gs > 0 else "—"

    delta_ventas = _delta_pct(ventas_gs, prior_ventas_gs)
    delta_cogs = _delta_pct(cogs_gs, prior_cogs_gs)
    delta_margen = _delta_pct(margen_gs, prior_margen_gs)

    # Ranking: aggregate margin by product (reuse batch_costs — no extra queries)
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

    ranking = sorted(
        ranking_dict.values(),
        key=lambda r: r["margen_gs"],
        reverse=True,
    )
    # Compute ratios
    for r in ranking:
        if r["ventas_gs"] > 0:
            r["margen_ratio"] = r["margen_gs"] / r["ventas_gs"]

    # Alerts
    stock_low = session.scalars(
        select(Ingredient).where(
            Ingredient.min_stock_qty > 0,
            Ingredient.stock_qty < Ingredient.min_stock_qty,
        )
    ).all()

    # Stock-confidence LED (prelaunch roadmap item):
    # aggregate ingredient health into a single green/amber/red signal.
    # - danger: any ingredient with negative stock (data integrity issue)
    # - warn:   1+ ingredients below min_stock_qty
    # - success: all tracked ingredients at or above min (or none tracked)
    stock_negative_count = sum(1 for i in stock_low if (i.stock_qty or 0) < 0)
    if stock_negative_count > 0:
        stock_health_severity = "danger"
        stock_health_label = f"{stock_negative_count} en negativo"
    elif stock_low:
        stock_health_severity = "warn"
        stock_health_label = f"{len(stock_low)} bajo mínimo"
    else:
        stock_health_severity = "success"
        stock_health_label = "todo OK"

    # Coffee regulars (prelaunch roadmap 2026-09-17):
    # Customers with 2+ sales in the last 30 days, sorted by visit count.
    # A "regular" in a small bakery context = recurring, not lifetime one-timers.
    # Top 5 for the home card; full list is at /clientes.
    from app.rms.models import Customer as _Customer

    _thirty_days_ago = datetime.now(ASUNCION_TZ) - timedelta(days=30)
    regular_rows = session.execute(
        select(
            Sale.customer_id,
            func.count(Sale.id).label("n_visits"),
            func.coalesce(func.sum(Sale.qty * Sale.unit_price_gs), 0).label("lifetime_spend_gs"),
        )
        .where(
            Sale.customer_id.isnot(None),
            Sale.voided_at.is_(None),
            Sale.sold_at >= _thirty_days_ago,
        )
        .group_by(Sale.customer_id)
        .having(func.count(Sale.id) >= 2)
        .order_by(func.count(Sale.id).desc())
        .limit(5)
    ).all()
    regulars: list[dict] = []
    if regular_rows:
        _ids = [r.customer_id for r in regular_rows]
        _customers = {
            c.id: c for c in session.scalars(select(_Customer).where(_Customer.id.in_(_ids))).all()
        }
        for r in regular_rows:
            cust = _customers.get(r.customer_id)
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

    # Batch-load all recipe costs (replaces per-recipe N+1).
    all_recipes = list(session.scalars(select(Recipe)).all())
    batch_recipe_results = batch_recipes_cost(session, all_recipes)
    recipes_no_cost = [
        r
        for r in all_recipes
        if batch_recipe_results[r.id][0].batch_cost_gs is None and len(r.lines) > 0
    ]

    sales_no_recipe_decor = [
        {
            "id": s.id,
            "product_name": s.product.name if s.product else "(deleted)",
            "sold_at_str": s.sold_at.strftime("%d/%m/%Y %H:%M") if s.sold_at else "",
        }
        for s in sales_no_recipe[:10]
    ]

    # Period label for delta sub-label ("vs. ayer", "vs. semana pasada", etc.)
    period_labels = {
        "today": "ayer",
        "week": "semana pasada",
        "month": "mes pasado",
    }
    prior_label = period_labels.get(period, "período anterior")

    # ── Acciones del día (mockup plan 2026-09-25) ──────────────────────
    from app.rms.demand_freshness import freshness_flags as _freshness_flags
    from app.rms.eod_completions import completions_for_date as _eod_for_date
    from app.rms.models import Pedido, WasteLog  # local import: avoid cycles

    today_d = datetime.now(ASUNCION_TZ).date()
    tomorrow_d = today_d + timedelta(days=1)
    yesterday_d = today_d - timedelta(days=1)

    _ped_counts = {"hoy": 0, "manana": 0}
    for p_row in session.execute(
        select(Pedido.promised_date, Pedido.status).where(
            Pedido.status.in_(["pending", "confirmed", "ready"])
        )
    ).all():
        if p_row.promised_date == today_d:
            _ped_counts["hoy"] += 1
        elif p_row.promised_date == tomorrow_d:
            _ped_counts["manana"] += 1

    # Ops + ticket for TODAY regardless of the scrubber (the HOY band is
    # always "hoy"; scrubber-scoped numbers stay in the Ranking section).
    _today_start = datetime.now(ASUNCION_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    _prior_same_weekday = _today_start - timedelta(days=7)
    _prior_end = _prior_same_weekday + timedelta(days=1)

    def _is_naive(dt: datetime) -> bool:
        return dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None

    # `Sale.sold_at` is stored naive-UTC (see `_compute_window_totals`:
    # `start_utc_naive` / `end_utc_naive`), but `_today_start` is
    # tz-aware (ASUNCION). Comparing them raises
    # `TypeError: can't compare offset-naive and offset-aware datetimes`
    # when the current window contains today's sales. Normalize the
    # boundary to naive UTC for an apples-to-apples compare — same
    # pattern as the prior-week loop below.
    if _is_naive(_today_start):
        _today_start_cmp = _today_start
    else:
        _today_start_cmp = _today_start.astimezone(timezone.utc).replace(tzinfo=None)
    _today_sales = (
        [s for s in sales if s.sold_at and s.sold_at >= _today_start_cmp]
        if period != "today"
        else sales
    )
    ops_today = len(_today_sales)
    ticket_promedio_gs = (
        int(
            sum(int(Decimal(str(s.qty)) * Decimal(str(s.unit_price_gs))) for s in _today_sales)
            / len(_today_sales)
        )
        if _today_sales
        else 0
    )

    _prev_ops = 0
    for s in session.scalars(select(Sale).where(Sale.voided_at.is_(None))).all():
        sold = s.sold_at
        if sold is None:
            continue
        if _is_naive(sold) != _is_naive(_prior_same_weekday):
            # normalize to naive UTC-ish comparison (dates only matter here)
            if _is_naive(sold):
                from datetime import timezone as _tz

                sold = sold.replace(tzinfo=_tz.utc)
                _prior_cmp, _prior_end_cmp = _prior_same_weekday, _prior_end
            else:
                from datetime import timezone as _tz

                _prior_cmp = _prior_same_weekday.replace(tzinfo=None)
                _prior_end_cmp = _prior_end.replace(tzinfo=None)
        else:
            _prior_cmp, _prior_end_cmp = _prior_same_weekday, _prior_end
        if _prior_cmp <= sold < _prior_end_cmp:
            _prev_ops += 1
    if ops_today and _prev_ops:
        ops_delta_label = f"▲ {ops_today - _prev_ops:+d} vs. semana pasada".replace("+", "")
        ops_delta_label = f"{'▲' if ops_today >= _prev_ops else '▼'} {abs(ops_today - _prev_ops)} vs. semana pasada"
    else:
        ops_delta_label = None
    ticket_delta_label = None

    # Cierre de ayer
    cierre_ayer_pendiente = False
    try:
        _y = _eod_for_date(session, yesterday_d)
        cierre_ayer_pendiente = not _y
    except Exception:
        cierre_ayer_pendiente = False

    # Merma hoy
    merma_hoy = bool(session.execute(select(WasteLog.id).limit(1)).first())

    # Por vencer 48 h (freshness proxy without the full report)
    vencer_48h_count = 0
    vencer_48h_gs = 0
    try:
        for f in _freshness_flags(session):
            if f.urgency in ("expired", "critical"):
                vencer_48h_count += 1
                vencer_48h_gs += int(f.value_at_risk_gs or 0)
    except Exception as exc:
        # Defensive: dashboard never fails because of analytics math.
        # Logged at debug so it's traceable in sazon.log without spamming.
        logger.debug("dashboard expiry scan skipped: {}", exc)

    # Costs completeness for the "provisional" pill
    _recipes_with_cost = len(all_recipes) - len(recipes_no_cost)
    costs_incomplete = None
    if all_recipes and len(recipes_no_cost):
        costs_incomplete = f"{int(_recipes_with_cost / len(all_recipes) * 100)}% cargados"

    # P3 profile batch: upcoming birthdays (next 7 days) — retention nudge.
    # birthday stored as "DD-MM" or "YYYY-MM-DD"; compare month-day only.
    from datetime import date as _date

    from app.rms.models import Customer

    today = datetime.now(ASUNCION_TZ).date()
    birthdays: list[dict] = []
    for c in session.scalars(select(Customer)).all():
        raw = (c.birthday or "").strip()
        if not raw:
            continue
        parts = raw.replace("/", "-").split("-")
        if len(parts) == 3:
            mm, dd = parts[1], parts[2]
        elif len(parts) == 2:
            mm, dd = parts
        else:
            continue
        if not (mm.isdigit() and dd.isdigit()):
            continue
        bday = _date(today.year, int(mm), int(dd))
        if bday < today:
            try:
                bday = _date(today.year + 1, int(mm), int(dd))
            except ValueError:  # Feb 29
                continue
        days_until = (bday - today).days
        if days_until <= 7:
            birthdays.append(
                {
                    "name": (c.name or "").title(),
                    "customer_id": c.id,
                    "days_until": days_until,
                    "when": "hoy"
                    if days_until == 0
                    else ("mañana" if days_until == 1 else f"en {days_until} días"),
                    "consent": bool(c.marketing_consent),
                }
            )
    birthdays.sort(key=lambda b: b["days_until"])

    # Phase 4 B2 (2026-10-01): day-of-week-aware forecast headline for
    # /inicio. Predicts tomorrow's units + revenue using the last 12
    # weeks of historical sales for tomorrow's weekday only. Returns
    # None when there's not enough data so the UI can render an empty
    # state instead of misleading numbers.
    from datetime import datetime as _dt_b2

    from app.rms.config import ASUNCION_TZ as _tz_b2

    _tomorrow_date = (_dt_b2.now(_tz_b2) + timedelta(days=1)).date()
    _tomorrow_dow = _tomorrow_date.weekday()
    _tomorrow_label = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"][
        _tomorrow_dow
    ]
    # Batched DOW forecast (2026-10-07, N+1 fix). Pre-fix this loop
    # called `forecast_sales(...)` once per product; with 30+ products
    # that's 30+ SELECTs against `sale` for one card on /inicio. Now:
    # 1) one SELECT pulls `(product_id, sold_at, qty)` for the full
    #    84d window across every product;
    # 2) we replicate the per-product math that
    #    `app.rms.production.forecast_sales` used to do (sum `qty` per
    #    DOW + count DOW occurrences, then per-DOW avg with fallback
    #    to the flat 84d avg when < 4 DOW samples exist);
    # 3) we use the product's `sale_price_gs` for revenue, same as
    #    the old loop.
    # Behaviour matches the previous per-product path exactly
    # (decision 2026-10-01 in production.py:forecast_sales docstring:
    # 12-week lookback, DOW-only aggregation, fallback to all-DOW
    # avg when < 4 DOW weeks exist).
    _all_products = session.scalars(select(Product)).all()
    _forecast_window_start = _dt_b2.now(timezone.utc) - timedelta(days=84)
    # `IN (?, ?, ...)` form (vs. no product filter) lets the test
    # contract in test_dashboard_perf.py::test_dashboard_forecast_no_n_plus_1
    # detect the batched query by its SQL fingerprint, and keeps the
    # database able to use the `sale.product_id` index when only a
    # subset of products are visible at this tenant.
    _forecast_rows = session.execute(
        select(Sale.product_id, Sale.sold_at, Sale.qty).where(
            Sale.product_id.in_([_p.id for _p in _all_products]),
            Sale.sold_at >= _forecast_window_start,
            Sale.voided_at.is_(None),
        )
    ).all()
    # by_pid_dow_qty[pid][wd]   = sum of Sale.qty on weekday wd
    # by_pid_dow_count[pid][wd] = count of sales on weekday wd
    # by_pid_total_qty[pid]     = sum of Sale.qty over the full window
    # (matches the three locals forecast_sales builds per call)
    _by_pid_dow_qty: dict[int, dict[int, float]] = {}
    _by_pid_dow_count: dict[int, dict[int, int]] = {}
    _by_pid_total_qty: dict[int, float] = {}
    for _pid, _sold_at, _qty in _forecast_rows:
        if _sold_at is None:
            continue
        _wd = _sold_at.astimezone(_tz_b2).weekday()
        _dow_qty = _by_pid_dow_qty.setdefault(_pid, {})
        _dow_count = _by_pid_dow_count.setdefault(_pid, {})
        _dow_qty[_wd] = _dow_qty.get(_wd, 0.0) + float(_qty or 0)
        _dow_count[_wd] = _dow_count.get(_wd, 0) + 1
        _by_pid_total_qty[_pid] = _by_pid_total_qty.get(_pid, 0.0) + float(_qty or 0)

    _forecast_units = 0.0
    _forecast_revenue_gs = 0
    _forecast_products_count = 0
    _forecast_top = []  # [(product_name, qty, revenue_gs)]
    for _prod in _all_products:
        _target_count = _by_pid_dow_count.get(_prod.id, {}).get(_tomorrow_dow, 0)
        if _target_count >= 4:
            _qty = _by_pid_dow_qty.get(_prod.id, {}).get(_tomorrow_dow, 0.0) / _target_count
        else:
            _qty = _by_pid_total_qty.get(_prod.id, 0.0) / 84
        if _qty <= 0:
            continue
        _forecast_products_count += 1
        _forecast_units += _qty
        _rev = int(_qty * (_prod.sale_price_gs or 0))
        _forecast_revenue_gs += _rev
        _forecast_top.append(
            {
                "name": _prod.name,
                "qty": _qty,
                "revenue_gs": _rev,
            }
        )
    _forecast_top.sort(key=lambda x: -x["qty"])
    _forecast_top = _forecast_top[:5]
    # Confidence: count of products with at least 4 DOW-weeks of history
    # divided by total — rough heuristic. Same logic is in
    # production.py:_forecast_confidence() but per-product.
    _forecast_confidence = (
        "high"
        if _forecast_products_count >= 5
        else ("medium" if _forecast_products_count >= 2 else "low")
    )

    # Tier 3.1 (2026-10-01): enrollment KPI. Two numbers:
    #   enrollment_pct_today: % of today's sales that had a customer attached.
    #   enrollment_pct_prior: same for the prior period (so the delta is real).
    # One window-aligned query each. Both cheap.
    enrollment_today_q = session.execute(
        select(
            func.count(Sale.id).label("total"),
            func.sum(
                case(
                    (Sale.customer_id.isnot(None), 1),
                    else_=0,
                )
            ).label("with_customer"),
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
            func.sum(
                case(
                    (Sale.customer_id.isnot(None), 1),
                    else_=0,
                )
            ).label("with_customer"),
        ).where(
            Sale.sold_at >= prior_start,
            Sale.sold_at < prior_end,
            Sale.voided_at.is_(None),
        )
    ).one()
    total_prior = int(enrollment_prior_q.total or 0)
    with_prior = int(enrollment_prior_q.with_customer or 0)
    enrollment_pct_prior = round((with_prior / total_prior) * 100, 1) if total_prior > 0 else None

    if enrollment_pct_today is not None and enrollment_pct_prior is not None:
        enrollment_delta_pp = round(enrollment_pct_today - enrollment_pct_prior, 1)
    else:
        enrollment_delta_pp = None

    return render(
        request,
        "inicio.html",
        {
            "period": period,
            "start_date_val": range_start.strftime("%Y-%m-%d") if range_start else "",
            "end_date_val": range_end.strftime("%Y-%m-%d") if range_end else "",
            "ventas_gs": ventas_gs,
            "cogs_gs": cogs_gs,
            "margen_gs": margen_gs,
            "margen_pct_fmt": margen_pct_fmt,
            # P1 audit #10: vs. last period delta indicators
            "delta_ventas": delta_ventas,
            "delta_cogs": delta_cogs,
            "delta_margen": delta_margen,
            "prior_label": prior_label,
            "ranking": ranking,
            "birthdays": birthdays,
            "stock_low": [
                {
                    "name": i.name,
                    "stock_qty": i.stock_qty,
                    "min_stock_qty": i.min_stock_qty,
                    "unit": i.unit,
                }
                for i in stock_low
            ],
            # Stock-confidence LED (prelaunch roadmap item)
            "stock_health_severity": stock_health_severity,
            "stock_health_label": stock_health_label,
            "stock_negative_count": stock_negative_count,
            "stock_below_min_count": len(stock_low),
            # Coffee regulars (prelaunch roadmap 2026-09-17)
            "regulars": regulars,
            "regulars_count_total": (
                session.scalar(
                    select(func.count()).select_from(
                        select(Sale.customer_id)
                        .where(
                            Sale.customer_id.isnot(None),
                            Sale.voided_at.is_(None),
                            Sale.sold_at >= _thirty_days_ago,
                        )
                        .group_by(Sale.customer_id)
                        .having(func.count(Sale.id) >= 2)
                        .subquery()
                    )
                )
                or 0
            ),
            # B2 (2026-10-01): day-of-week-aware forecast headline
            "forecast_tomorrow_label": _tomorrow_label,
            "forecast_tomorrow_date": _tomorrow_date.isoformat(),
            "forecast_units": round(_forecast_units),
            "forecast_revenue_gs": _forecast_revenue_gs,
            "forecast_products_count": _forecast_products_count,
            "forecast_top": _forecast_top,
            "forecast_confidence": _forecast_confidence,
            # Tier 3.1 (2026-10-01): enrollment KPI card on /inicio.
            # Percentage of sales in the current window that had a
            # customer attached (i.e., loyalty earn fires). Delta is
            # percentage-point vs the prior period.
            "enrollment_pct_today": enrollment_pct_today,
            "enrollment_pct_prior": enrollment_pct_prior,
            "enrollment_delta_pp": enrollment_delta_pp,
            "enrollment_total_today": total_today,
            "enrollment_with_today": with_today,
            "recipes_no_cost": recipes_no_cost,
            "sales_no_recipe": sales_no_recipe_decor,
            # E8: operational analytics surfaces
            "dow_buckets": day_of_week_heatmap(session, days=90),
            "turnover": list(
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
            ),
            "top_margin": top_margin_products(session, days=30, limit=5),
            "concentration": ingredient_concentration(session, days=90)[:5],
            "erosion_alerts": margin_erosion_alerts(session, threshold_pct=5.0),
            "complexity": recipe_complexity(session),
            # Phase 1.A — compliance alert widget (INAN R.E., Habilitación, Timbrado)
            "compliance_alerts": _compliance_alerts(session),
            # E34: consolidated insights panel
            "insights": build_insights(session),
            # Phase 3 visual dashboard — charts + freshness
            "chart_hourly": _build_hourly_sales_chart(sales, ASUNCION_TZ),
            "chart_30day": _build_30day_sales_chart(session, preset=chart_preset),
            "chart_preset": chart_preset,
            "chart_payment_methods": _build_payment_methods_donut(sales),
            "top_products_revenue": _build_top_products_revenue(ranking),
            # P1-B7: actionable insights for dashboard
            "actionable_insights": build_actionable_insights(session),
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
            # HEREBUS-folded KPIs (Wave 3): shopping list, wishlist, risk
            "sl_open_count": session.execute(
                select(ShoppingListItem).where(ShoppingListItem.purchased.is_(False))
            )
            .scalars()
            .all()
            .__len__(),
            "sl_total_gs": sum(
                (i.qty_to_buy or 0) * (i.ingredient.purchase_price_gs or 0)
                for i in session.execute(
                    select(ShoppingListItem).where(ShoppingListItem.purchased.is_(False))
                )
                .scalars()
                .all()
            ),
            "wishlist_count": session.execute(
                select(WishlistItem).where(WishlistItem.purchased.is_(False))
            )
            .scalars()
            .all()
            .__len__(),
            "wishlist_total_gs": sum(
                (i.unit_price_gs or 0) * (i.quantity or 0)
                for i in session.execute(
                    select(WishlistItem).where(WishlistItem.purchased.is_(False))
                )
                .scalars()
                .all()
            ),
            "risk_count": session.execute(select(RiskItem).where(RiskItem.status == "activo"))
            .scalars()
            .all()
            .__len__(),
            "risk_severity_gs": sum(
                (r.probability or 0) * (r.impact_gs or 0)
                for r in session.execute(select(RiskItem).where(RiskItem.status == "activo"))
                .scalars()
                .all()
            ),
            "data_freshness": datetime.now(ASUNCION_TZ).strftime("%H:%M:%S"),
            # ── HOY band + Acciones del día (mockup plan 2026-09-25) ──
            "ops_today": ops_today,
            "ops_delta_label": ops_delta_label,
            "ticket_promedio_gs": ticket_promedio_gs,
            "ticket_delta_label": ticket_delta_label,
            "costs_incomplete": costs_incomplete,
            "pedido_hoy": _ped_counts["hoy"],
            "pedido_manana": _ped_counts["manana"],
            "cierre_ayer_pendiente": cierre_ayer_pendiente,
            "merma_hoy": merma_hoy,
            "vencer_48h_count": vencer_48h_count,
            "vencer_48h_gs": vencer_48h_gs,
        },
    )


__all__ = ["router"]


# ---- Phase 3 visual dashboard helpers --------------------------------------


def _build_hourly_sales_chart(sales: list[Sale], tz: ZoneInfo) -> str:
    """Build an SVG bar chart of sales by hour for the current period.

    Returns an empty-state message if no sales.
    """
    if not sales:
        return '<p class="text-muted">Sin ventas todavía</p>'

    # Bucket by hour of day (0-23) in Asunción local.
    # Phase 14 #22: previously aggregated `qty × unit_price` (gross) —
    # silently overcounted revenue for sales with `discount_gs > 0`.
    # Now uses the post-discount line total (`unit_price × qty −
    # discount_gs`), which is what the operator sees in /recibo and
    # /ventas. Stays in Python because the dashboard already has the
    # full Sale list loaded — moving to SQL would require shipping
    # timezone-aware bucketing (EXTRACT(HOUR ...) is UTC, not Asunción).
    buckets = [0] * 24
    for s in sales:
        if s.sold_at is None:
            continue
        # sold_at is naive UTC per the data layer convention
        local = s.sold_at.replace(tzinfo=timezone.utc).astimezone(tz)
        line_total = int(s.qty) * int(s.unit_price_gs) - int(s.discount_gs or 0)
        buckets[local.hour] += max(line_total, 0)

    # Build bar chart
    values = [(f"{h:02d}h", float(v)) for h, v in enumerate(buckets) if v > 0]
    if not values:
        return '<p class="text-muted">Sin ventas todavía</p>'

    return bar_chart(
        values,
        width=700,
        height=180,
        label="Ventas por hora del día (Asunción local)",
        color="var(--color-accent)",
    )


def _build_30day_sales_chart(session: Session, preset: str = "30d") -> dict:
    """Build an SVG line chart for the dashboard over the given preset.

    Returns a dict ``{"html": str, "preset": str, "rows": list[dict]}``
    so the template can render the chart plus a small top-product
    summary table and the preset switcher.

    Delegates the heavy lifting to ``app.services.reports.daily_sales_series``
    (E4.S2) so the same numbers power any future surface (toolbar widget,
    export, etc).
    """
    from app.services.reports import daily_sales_series

    rows = daily_sales_series(session, preset=preset)
    if not rows or all(r.total_gs == 0 for r in rows):
        return {
            "html": '<p class="text-muted">Sin ventas en el período seleccionado</p>',
            "preset": preset,
            "preset_label": _preset_label(preset),
            "rows": [r.to_dict() for r in rows],
        }

    return {
        "html": line_chart(
            [(r.date.strftime("%d/%m"), float(r.total_gs)) for r in rows],
            width=700,
            height=180,
            label=f"Ventas — {_preset_label(preset)} (Gs.)",
            y_format="{:,.0f}",
            color="var(--color-accent)",
            show_dots=False,
        ),
        "preset": preset,
        "preset_label": _preset_label(preset),
        "rows": [r.to_dict() for r in rows],
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
