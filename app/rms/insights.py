"""app/rms/insights.py — single dashboard panel of all intelligence.

Aggregates everything from E26-E33 into one InsightsPanel the dashboard
route can render in one query. Splits into:

1. Today's headline numbers
2. Inventory alerts (top 5 reorder-needed)
3. Menu engineering highlights (top star + top dog)
4. Production tomorrow (what to bake)
5. Food cost summary (last 30 days)
6. Sales patterns (peak hour + churn/rising top 3)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.food_cost import food_cost_report
from app.rms.inventory_intel import (
    low_stock_alerts,
    stock_value_gs,
)
from app.rms.menu_engineering import (
    Quadrant,
    classify_products,
)
from app.rms.models import Ingredient, Product
from app.rms.price_history import price_stats
from app.rms.production_scheduler import batch_production_plans
from app.rms.sales_intel import (
    churning_products,
    peak_hour,
    rising_products,
)


@dataclass(frozen=True)
class InsightsPanel:
    generated_at: str
    inventory_capital_gs: int
    low_stock_alerts: list  # InventoryStatus list
    menu_quadrants: dict[str, list[dict]]  # quadrant → list of {name, margin, volume}
    production_tomorrow: list  # ProductionPlan list
    food_cost: Any  # FoodCostReport
    sales_peak_hour: int
    sales_peak_dow: int
    rising_products: list
    churning_products: list
    stars: list
    dogs: list
    price_fluctuation: list = field(default_factory=list)  # [{name, pct_above_avg}]


def build_insights(session: Session) -> InsightsPanel:
    """Build the consolidated insights panel."""
    now = datetime.now(timezone.utc)

    # Inventory
    capital = stock_value_gs(session)
    alerts = low_stock_alerts(session, top_n=5)

    # Menu engineering
    classifications = classify_products(session)
    quadrants: dict[str, list[dict]] = {q.value: [] for q in Quadrant}
    for c in classifications:
        quadrants[c.quadrant.value].append(
            {
                "product_id": c.product_id,
                "product_name": c.product_name,
                "margin_gs": c.margin_gs,
                "volume": c.volume,
            }
        )
    stars = sorted(
        quadrants.get(Quadrant.STAR.value, []), key=lambda x: x["margin_gs"], reverse=True
    )[:3]
    dogs = quadrants.get(Quadrant.DOG.value, [])

    # Production tomorrow (batched — replaces per-product N+1 loop)
    tomorrow_plans = batch_production_plans(session, list(session.scalars(select(Product)).all()))

    # Food cost
    fc_report = food_cost_report(session, period_days=30)

    # Sales patterns
    pk_hour = peak_hour(session)
    pk_dow = _peak_dow_helper(session)
    rising = rising_products(session)[:3]
    churning = churning_products(session)[:3]

    # Price fluctuation (Saskia review Q1): ingredients >20% above 30d avg
    price_fluctuation: list[dict] = []
    for ing in session.scalars(select(Ingredient)).all():
        stats = price_stats(session, ing.id, days=30)
        if stats["count"] < 2 or not stats["avg"]:
            continue
        pct = (stats["current"] - stats["avg"]) / stats["avg"] * 100
        if pct > 20:
            price_fluctuation.append(
                {
                    "name": ing.name,
                    "pct_above_avg": round(pct, 1),
                }
            )
    price_fluctuation.sort(key=lambda x: -x["pct_above_avg"])

    return InsightsPanel(
        generated_at=now.isoformat(),
        inventory_capital_gs=capital,
        low_stock_alerts=list(alerts),
        menu_quadrants=quadrants,
        production_tomorrow=tomorrow_plans,
        food_cost=fc_report,
        sales_peak_hour=pk_hour,
        sales_peak_dow=pk_dow,
        rising_products=rising,
        churning_products=churning,
        stars=stars,
        dogs=dogs,
        price_fluctuation=price_fluctuation,
    )


def _peak_dow_helper(session: Session) -> int:
    from app.rms.sales_intel import peak_day_of_week

    return peak_day_of_week(session)


def restock_urgent(session: Session) -> dict | None:
    """Find ingredients with <3 days of stock, pre-populated reorder."""
    from app.rms.inventory_intel import low_stock_alerts

    alerts = low_stock_alerts(session, top_n=1)
    if not alerts:
        return None

    alert = alerts[0]
    if alert.days_of_stock is None or alert.days_of_stock >= 3:
        return None

    # Pre-populate the ingredient in the reorder URL
    return {
        "id": "restock_urgent",
        "title": "Reposición urgente",
        "detail": f"{alert.ingredient_name} con solo {alert.days_of_stock:.0f} días de stock",
        "action_text": "Reordenar",
        "action_href": f"/reorder?ingredient={alert.ingredient_id}",
        "severity": "warn" if alert.days_of_stock > 0 else "danger",
        "icon": "icon-reorder",
    }


def bestseller_drop(session: Session) -> dict | None:
    """Find top-10 products that sold <50% of trailing 7d avg."""
    from datetime import datetime, timedelta, timezone

    from app.config import ASUNCION_TZ
    from sqlalchemy import select

    from app.rms.models import Product, Sale
    from app.rms.money import to_int_gs

    now_local = datetime.now(ASUNCION_TZ)
    end_utc = now_local.astimezone(timezone.utc).replace(tzinfo=None)
    start_utc = (now_local - timedelta(days=7)).astimezone(timezone.utc).replace(tzinfo=None)

    # Get all products
    products = list(session.scalars(select(Product)).all())

    for product in products[:10]:  # Check only top 10 by name for simplicity
        # Sales in last 7 days
        recent_sales = session.scalars(
            select(Sale).where(
                Sale.product_id == product.id,
                Sale.sold_at >= start_utc,
                Sale.sold_at <= end_utc,
                Sale.voided_at.is_(None),
            )
        ).all()

        recent_total = sum(
            to_int_gs(float(str(s.qty)) * float(str(s.unit_price_gs)))
            for s in recent_sales
            if s.unit_price_gs is not None
        )

        # Sales in prior 7 days for comparison
        prior_start_utc = start_utc - timedelta(days=7)
        prior_sales = session.scalars(
            select(Sale).where(
                Sale.product_id == product.id,
                Sale.sold_at >= prior_start_utc,
                Sale.sold_at < start_utc,
                Sale.voided_at.is_(None),
            )
        ).all()

        prior_total = sum(
            to_int_gs(float(str(s.qty)) * float(str(s.unit_price_gs)))
            for s in prior_sales
            if s.unit_price_gs is not None
        )

        # Check if recent is <50% of prior avg (if prior had sales)
        if prior_total > 0 and recent_total < prior_total * 0.5:
            return {
                "id": "bestseller_drop",
                "title": "Mejor vendedor en caída",
                "detail": f"{product.name} vendió un {recent_total / prior_total * 100:.0f}% menos que el promedio de 7 días",
                "action_text": "Ver análisis",
                "action_href": f"/analisis?focus={product.id}",
                "severity": "warn",
                "icon": "icon-chart-line-down",
            }

    return None


def cash_flow_warning(session: Session) -> dict | None:
    """If past day 25 AND month-to-date revenue <60% of last month's same window."""
    from datetime import datetime, timezone

    from app.config import ASUNCION_TZ
    from app.rms.dashboard import _period_window
    from sqlalchemy import select

    from app.rms.models import Sale
    from app.rms.money import to_int_gs

    now_local = datetime.now(ASUNCION_TZ)
    day_of_month = now_local.day

    # Only trigger past day 25
    if day_of_month < 25:
        return None

    # Get current month-to-date
    month_start, month_end = _period_window("month")
    month_start_utc = month_start.astimezone(timezone.utc).replace(tzinfo=None)
    month_end_utc = month_end.astimezone(timezone.utc).replace(tzinfo=None)

    month_sales = session.scalars(
        select(Sale).where(Sale.sold_at >= month_start_utc, Sale.sold_at <= month_end_utc)
    ).all()

    current_month_revenue = sum(
        to_int_gs(float(str(s.qty)) * float(str(s.unit_price_gs)))
        for s in month_sales
        if s.unit_price_gs is not None
    )

    # Get previous month same window
    prev_month_start = month_start.replace(day=1)
    prev_month_end = prev_month_start + (month_end - month_start)

    prev_month_sales = session.scalars(
        select(Sale).where(
            Sale.sold_at >= prev_month_start.astimezone(timezone.utc).replace(tzinfo=None),
            Sale.sold_at <= prev_month_end.astimezone(timezone.utc).replace(tzinfo=None),
        )
    ).all()

    prev_month_revenue = sum(
        to_int_gs(float(str(s.qty)) * float(str(s.unit_price_gs)))
        for s in prev_month_sales
        if s.unit_price_gs is not None
    )

    # Check if <60% of previous month
    if prev_month_revenue > 0 and current_month_revenue < prev_month_revenue * 0.6:
        return {
            "id": "cash_flow_warn",
            "title": "Alerta de flujo de caja",
            "detail": f"Ventas del mes ({current_month_revenue}) son solo {current_month_revenue / prev_month_revenue * 100:.0f}% del mes pasado",
            "action_text": "Ver reportes",
            "action_href": "/reportes",
            "severity": "danger",
            "icon": "icon-warn",
        }

    return None


def build_actionable_insights(session: Session) -> list[dict]:
    """Build the 3 actionable insights for the dashboard."""
    insights = []

    # Check each insight
    for insight_func in [restock_urgent, bestseller_drop, cash_flow_warning]:
        try:
            insight = insight_func(session)
            if insight:
                insights.append(insight)
        except Exception as e:  # noqa: BLE001 — log but don't break the dashboard
            from loguru import logger

            logger.debug(f"Actionable insight calculation failed: {e}")

    return insights


__all__ = [
    "InsightsPanel",
    "build_actionable_insights",
    "build_insights",
]
