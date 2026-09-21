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
        quadrants[c.quadrant.value].append({
            "product_id": c.product_id,
            "product_name": c.product_name,
            "margin_gs": c.margin_gs,
            "volume": c.volume,
        })
    stars = sorted(quadrants.get(Quadrant.STAR.value, []),
                   key=lambda x: x["margin_gs"], reverse=True)[:3]
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
            price_fluctuation.append({
                "name": ing.name,
                "pct_above_avg": round(pct, 1),
            })
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


__all__ = [
    "InsightsPanel",
    "build_insights",
]
