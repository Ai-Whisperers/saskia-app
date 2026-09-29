"""app/routers/dashboard.py — Inicio: ventas/COGS/margen/ranking/avisos.

Per dev plan §9 Task 7 + v2 §11 (timezone).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from loguru import logger
from sqlalchemy import select
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
from app.rms.insights import build_insights
from app.rms.models import Ingredient, Recipe, RiskItem, Sale, ShoppingListItem, WishlistItem
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
            alerts.append({
                "severity": "danger",
                "icon": "⚠",
                "message": f"{label} VENCIDO hace {abs(days_left)} días ({expiry.isoformat()}). Renová ya.",
                "days_remaining": days_left,
            })
        elif days_left <= 30:
            alerts.append({
                "severity": "warn",
                "icon": "⏰",
                "message": f"{label} vence en {days_left} días ({expiry.isoformat()}). Programá renovación.",
                "days_remaining": days_left,
            })

    # R.S.P.A. expiry check on products (only when requires_rspa=True)
    from app.rms.models import Product
    for p in session.execute(
        select(Product).where(
            Product.requires_rspa.is_(True),
            Product.rspa_expiry.is_not(None),
        )
    ).scalars().all():
        expiry = _parse_iso(p.rspa_expiry)
        if expiry is None:
            continue
        days_left = (expiry - today).days
        if days_left < 0:
            alerts.append({
                "severity": "danger",
                "icon": "⚠",
                "message": f"R.S.P.A. de '{p.name}' VENCIDA hace {abs(days_left)} días ({expiry.isoformat()}).",
                "days_remaining": days_left,
            })
        elif days_left <= 30:
            alerts.append({
                "severity": "warn",
                "icon": "⏰",
                "message": f"R.S.P.A. de '{p.name}' vence en {days_left} días.",
                "days_remaining": days_left,
            })

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
        alerts.append({
            "severity": "info",
            "icon": "ℹ",
            "message": f"Configurá: {', '.join(missing)} en Configuración → Información de Negocio.",
            "days_remaining": None,
        })

    return alerts


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    period: str = Query("today", pattern="^(today|week|month|custom)$"),
    start: str | None = Query(None, description="Start date for custom range (YYYY-MM-DD)"),
    end: str | None = Query(None, description="End date for custom range (YYYY-MM-DD)"),
    session: Session = Depends(get_session),
) -> HTMLResponse:
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
        ranking_dict[rid]["ventas_gs"] += to_int_gs(Decimal(str(s.qty)) * Decimal(str(s.unit_price_gs)))
        ranking_dict[rid]["qty"] += s.qty
        if s.product.recipe_id is not None:
            cost, _margin = batch_costs.get(rid, (None, (None, None)))
            if cost is not None and cost.batch_cost_gs is not None:
                line_margin = to_int_gs(Decimal(str(s.qty)) * (Decimal(str(s.unit_price_gs)) - Decimal(str(cost.batch_cost_gs))))
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
    _today_sales = [s for s in sales if s.sold_at and s.sold_at >= _today_start] if period != "today" else sales
    ops_today = len(_today_sales)
    ticket_promedio_gs = (
        int(sum(int(Decimal(str(s.qty)) * Decimal(str(s.unit_price_gs))) for s in _today_sales) / len(_today_sales))
        if _today_sales
        else 0
    )
    _prior_same_weekday = _today_start - timedelta(days=7)
    _prior_end = _prior_same_weekday + timedelta(days=1)

    def _is_naive(dt: datetime) -> bool:
        return dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None

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
    except Exception:  # noqa: BLE001 — defensive default
        cierre_ayer_pendiente = False

    # Merma hoy
    merma_hoy = bool(
        session.execute(
            select(WasteLog.id).limit(1)
        ).first()
    )

    # Por vencer 48 h (freshness proxy without the full report)
    vencer_48h_count = 0
    vencer_48h_gs = 0
    try:
        for f in _freshness_flags(session):
            if f.urgency in ("expired", "critical"):
                vencer_48h_count += 1
                vencer_48h_gs += int(f.value_at_risk_gs or 0)
    except Exception as exc:  # noqa: BLE001 — defensive default
        # Defensive: dashboard never fails because of analytics math.
        # Logged at debug so it's traceable in saskia.log without spamming.
        logger.debug("dashboard expiry scan skipped: {}", exc)

    # Costs completeness for the "provisional" pill
    _recipes_with_cost = len(all_recipes) - len(recipes_no_cost)
    costs_incomplete = None
    if all_recipes and len(recipes_no_cost):
        costs_incomplete = f"{int(_recipes_with_cost / len(all_recipes) * 100)}% cargados"

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
            "stock_low": [
                {
                    "name": i.name,
                    "stock_qty": i.stock_qty,
                    "min_stock_qty": i.min_stock_qty,
                    "unit": i.unit,
                }
                for i in stock_low
            ],
            "recipes_no_cost": recipes_no_cost,
            "sales_no_recipe": sales_no_recipe_decor,
            # E8: operational analytics surfaces
            "dow_buckets": day_of_week_heatmap(session, days=90),
            "turnover": list(
                batch_stock_turnover(
                    session,
                    [ing.id for ing in session.scalars(
                        select(Ingredient).where(Ingredient.stock_qty > 0).limit(8)
                    ).all()],
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
            "chart_30day": _build_30day_sales_chart(session),
            "chart_payment_methods": _build_payment_methods_donut(sales),
            "top_products_revenue": _build_top_products_revenue(ranking),
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
            ).scalars().all().__len__(),
            "sl_total_gs": sum(
                (i.qty_to_buy or 0) * (i.ingredient.purchase_price_gs or 0)
                for i in session.execute(
                    select(ShoppingListItem).where(ShoppingListItem.purchased.is_(False))
                ).scalars().all()
            ),
            "wishlist_count": session.execute(
                select(WishlistItem).where(WishlistItem.purchased.is_(False))
            ).scalars().all().__len__(),
            "wishlist_total_gs": sum(
                (i.unit_price_gs or 0) * (i.quantity or 0)
                for i in session.execute(
                    select(WishlistItem).where(WishlistItem.purchased.is_(False))
                ).scalars().all()
            ),
            "risk_count": session.execute(
                select(RiskItem).where(RiskItem.status == "activo")
            ).scalars().all().__len__(),
            "risk_severity_gs": sum(
                (r.probability or 0) * (r.impact_gs or 0)
                for r in session.execute(
                    select(RiskItem).where(RiskItem.status == "activo")
                ).scalars().all()
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

    # Bucket by hour of day (0-23) in Asunción local
    buckets = [0] * 24
    for s in sales:
        if s.sold_at is None:
            continue
        # sold_at is naive UTC per the data layer convention
        local = s.sold_at.replace(tzinfo=timezone.utc).astimezone(tz)
        buckets[local.hour] += to_int_gs(Decimal(str(s.qty)) * Decimal(str(s.unit_price_gs)))

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


def _build_30day_sales_chart(session: Session) -> str:
    """Build an SVG line chart of sales over the last 30 days."""
    end = datetime.now(ASUNCION_TZ).replace(hour=23, minute=59, second=59)
    start = (end - timedelta(days=29)).replace(hour=0, minute=0, second=0)

    # Query sales in the range
    start_utc = start.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = end.astimezone(timezone.utc).replace(tzinfo=None)

    sales_30d = session.scalars(
        select(Sale).where(
            Sale.sold_at >= start_utc,
            Sale.sold_at <= end_utc,
        )
    ).all()

    if not sales_30d:
        return '<p class="text-muted">Sin ventas en los últimos 30 días</p>'

    # Bucket by day
    buckets: dict[str, int] = {}
    for s in sales_30d:
        if s.sold_at is None:
            continue
        local = s.sold_at.replace(tzinfo=timezone.utc).astimezone(ASUNCION_TZ)
        key = local.strftime("%d/%m")
        buckets[key] = buckets.get(key, 0) + to_int_gs(Decimal(str(s.qty)) * Decimal(str(s.unit_price_gs)))

    # Fill in missing days with 0
    values = []
    cur = start
    while cur <= end:
        key = cur.strftime("%d/%m")
        values.append((key, float(buckets.get(key, 0))))
        cur += timedelta(days=1)

    return line_chart(
        values,
        width=700,
        height=180,
        label="Ventas — últimos 30 días (Gs.)",
        y_format="{:,.0f}",
        color="var(--color-accent)",
        show_dots=False,
    )


def _build_payment_methods_donut(sales: list[Sale]) -> str:
    """Build a donut chart of payment method distribution."""
    buckets: dict[str, int] = {}
    for s in sales:
        pm = s.payment_method or "Sin especificar"
        buckets[pm] = buckets.get(pm, 0) + to_int_gs(Decimal(str(s.qty)) * Decimal(str(s.unit_price_gs)))

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
