"""Predictive restocking helpers (BACKLOG #7).

Given 30+ days of `sale_stock_move` rows (qty_delta negative on sale),
fit a per-ingredient simple forecast:
- Average daily consumption (over window)
- Velocity trend (is consumption trending up/down?)
- Days-of-stock remaining
- Projected stockout date

Used by /reorder to suggest restock qty + urgency date.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.rms.models import Ingredient, Sale, SaleStockMove, IngredientPriceEvent


@dataclass
class ConsumptionForecast:
    ingredient_id: int
    name: str
    current_stock_qty: float
    min_stock_qty: float
    avg_daily_consumption: float  # in ingredient unit, last 30d
    trend_pct: float  # % change in consumption vs prior 30d
    days_of_stock: float  # current_stock / avg_daily (∞ if 0 consumption)
    projected_stockout_at: datetime | None  # UTC
    recommended_restock_qty: float  # to bring stock back to 2x min
    last_restock_price_gs: int | None  # from IngredientPriceEvent


def _empty_forecast(ing: Ingredient) -> ConsumptionForecast:
    return ConsumptionForecast(
        ingredient_id=ing.id,
        name=ing.name,
        current_stock_qty=ing.stock_qty or 0.0,
        min_stock_qty=ing.min_stock_qty or 0.0,
        avg_daily_consumption=0.0,
        trend_pct=0.0,
        days_of_stock=float("inf"),
        projected_stockout_at=None,
        recommended_restock_qty=max(0.0, (ing.min_stock_qty or 0) * 2 - (ing.stock_qty or 0)),
        last_restock_price_gs=ing.purchase_price_gs,
    )


def forecast_ingredient_consumption(
    session: Session,
    ingredient_id: int,
    *,
    days_back: int = 30,
) -> ConsumptionForecast:
    """Forecast consumption for a single ingredient.

    Returns a ConsumptionForecast. If there's not enough data, returns
    a "no consumption" forecast with current_stock_qty snapshot.
    """
    ing = session.get(Ingredient, ingredient_id)
    if ing is None:
        raise ValueError(f"Ingredient {ingredient_id} not found")

    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(days=days_back)
    prior_cutoff = now - timedelta(days=days_back * 2)

    # Recent consumption (positive total of |qty_delta|).
    # SaleStockMove has no recorded_at column — join to Sale.sold_at.
    recent_q = session.scalar(
        select(func.coalesce(func.sum(-SaleStockMove.qty_delta), 0.0))
        .join(Sale, Sale.id == SaleStockMove.sale_id)
        .where(SaleStockMove.ingredient_id == ingredient_id)
        .where(Sale.sold_at >= recent_cutoff)
    ) or 0.0

    prior_q = session.scalar(
        select(func.coalesce(func.sum(-SaleStockMove.qty_delta), 0.0))
        .join(Sale, Sale.id == SaleStockMove.sale_id)
        .where(SaleStockMove.ingredient_id == ingredient_id)
        .where(Sale.sold_at >= prior_cutoff)
        .where(Sale.sold_at < recent_cutoff)
    ) or 0.0

    avg_daily_recent = recent_q / days_back
    avg_daily_prior = prior_q / days_back

    # Trend: pct change in avg_daily_consumption
    if avg_daily_prior > 0:
        trend_pct = (avg_daily_recent - avg_daily_prior) / avg_daily_prior * 100.0
    else:
        trend_pct = 0.0

    # Days of stock
    if avg_daily_recent > 0:
        days = (ing.stock_qty or 0.0) / avg_daily_recent
        if days < 1_000_000:  # avoid `inf`
            days_of_stock = days
            projected_stockout = now + timedelta(days=int(days))
        else:
            days_of_stock = float("inf")
            projected_stockout = None
    else:
        days_of_stock = float("inf")
        projected_stockout = None

    # Recommended: bring to 2x minimum, only if consumption is non-zero
    if avg_daily_recent > 0:
        target_stock = max(
            (ing.min_stock_qty or 0) * 2,
            avg_daily_recent * 14,  # 2 weeks of consumption
        )
        restock_qty = max(0.0, target_stock - (ing.stock_qty or 0))
    else:
        restock_qty = max(0.0, (ing.min_stock_qty or 0) * 2 - (ing.stock_qty or 0))

    # Last restock price for cost
    last_evt = session.scalar(
        select(IngredientPriceEvent)
        .where(IngredientPriceEvent.ingredient_id == ingredient_id)
        .where(IngredientPriceEvent.source == "restock")
        .order_by(IngredientPriceEvent.recorded_at.desc())
        .limit(1)
    )
    last_price = last_evt.price_gs if last_evt else ing.purchase_price_gs

    return ConsumptionForecast(
        ingredient_id=ing.id,
        name=ing.name,
        current_stock_qty=ing.stock_qty or 0.0,
        min_stock_qty=ing.min_stock_qty or 0.0,
        avg_daily_consumption=avg_daily_recent,
        trend_pct=trend_pct,
        days_of_stock=days_of_stock,
        projected_stockout_at=projected_stockout,
        recommended_restock_qty=restock_qty,
        last_restock_price_gs=last_price,
    )


def forecast_all_ingredients(
    session: Session,
    *,
    days_back: int = 30,
    limit: int = 100,
) -> list[ConsumptionForecast]:
    """Forecast consumption for all ingredients.

    Returns ingredients sorted by days_of_stock (most urgent first).
    """
    ings = session.scalars(
        select(Ingredient).order_by(Ingredient.name).limit(limit)
    ).all()
    forecasts = [forecast_ingredient_consumption(session, ing.id, days_back=days_back) for ing in ings]
    # Sort: finite days_of_stock first, ascending (most urgent)
    forecasts.sort(key=lambda f: (f.days_of_stock == float("inf"), f.days_of_stock))
    return forecasts


def projected_stockout_in_7_days(forecast: ConsumptionForecast) -> bool:
    """Returns True if forecast suggests stockout within 7 days."""
    return (
        forecast.days_of_stock != float("inf")
        and forecast.days_of_stock < 7
    )


def batch_forecast_ingredients(
    session: Session,
    ingredient_ids: list[int],
    *,
    days_back: int = 30,
) -> dict[int, ConsumptionForecast]:
    """Compute forecasts for multiple ingredients with a single SQL query.

    Returns {ingredient_id: ConsumptionForecast} for efficient
    rendering on list pages (e.g., /reorder).

    For typical 30 ingredients in a bakery this turns 30 queries into 1.
    """
    if not ingredient_ids:
        return {}

    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(days=days_back)
    prior_cutoff = now - timedelta(days=days_back * 2)

    # Recent consumption per ingredient (single GROUP BY query, joined to Sale
    # to use sold_at timestamp — SaleStockMove has no recorded_at column).
    from sqlalchemy import and_
    recent_rows = dict(session.execute(
        select(SaleStockMove.ingredient_id, func.coalesce(func.sum(-SaleStockMove.qty_delta), 0.0))
        .join(Sale, Sale.id == SaleStockMove.sale_id)
        .where(SaleStockMove.ingredient_id.in_(ingredient_ids))
        .where(Sale.sold_at >= recent_cutoff)
        .group_by(SaleStockMove.ingredient_id)
    ).all())

    prior_rows = dict(session.execute(
        select(SaleStockMove.ingredient_id, func.coalesce(func.sum(-SaleStockMove.qty_delta), 0.0))
        .join(Sale, Sale.id == SaleStockMove.sale_id)
        .where(SaleStockMove.ingredient_id.in_(ingredient_ids))
        .where(Sale.sold_at >= prior_cutoff)
        .where(Sale.sold_at < recent_cutoff)
        .group_by(SaleStockMove.ingredient_id)
    ).all())

    # Last restock price per ingredient (single query)
    last_price_rows = dict(session.execute(
        select(IngredientPriceEvent.ingredient_id, func.max(IngredientPriceEvent.recorded_at))
        .where(IngredientPriceEvent.ingredient_id.in_(ingredient_ids))
        .where(IngredientPriceEvent.source == "restock")
        .group_by(IngredientPriceEvent.ingredient_id)
    ).all())

    last_price_evts = {}
    if last_price_rows:
        evts = session.scalars(
            select(IngredientPriceEvent).where(IngredientPriceEvent.ingredient_id.in_(last_price_rows.keys()))
        ).all()
        for e in evts:
            key = (e.ingredient_id, e.recorded_at)
            cur = last_price_evts.get(e.ingredient_id)
            if cur is None or e.recorded_at > cur.recorded_at:
                last_price_evts[e.ingredient_id] = e

    # Now build forecast per ingredient
    ingredients = {ing.id: ing for ing in session.scalars(
        select(Ingredient).where(Ingredient.id.in_(ingredient_ids))
    )}

    out: dict[int, ConsumptionForecast] = {}
    for ing_id in ingredient_ids:
        ing = ingredients.get(ing_id)
        if ing is None:
            continue

        recent_q = recent_rows.get(ing_id, 0.0)
        prior_q = prior_rows.get(ing_id, 0.0)
        avg_daily_recent = recent_q / days_back
        avg_daily_prior = prior_q / days_back

        if avg_daily_prior > 0:
            trend_pct = (avg_daily_recent - avg_daily_prior) / avg_daily_prior * 100.0
        else:
            trend_pct = 0.0

        if avg_daily_recent > 0:
            days = (ing.stock_qty or 0.0) / avg_daily_recent
            days_of_stock = days if days < 1_000_000 else float("inf")
            projected_stockout = now + timedelta(days=int(days)) if days < 1_000_000 else None
        else:
            days_of_stock = float("inf")
            projected_stockout = None

        if avg_daily_recent > 0:
            target_stock = max(
                (ing.min_stock_qty or 0) * 2,
                avg_daily_recent * 14,
            )
            restock_qty = max(0.0, target_stock - (ing.stock_qty or 0))
        else:
            restock_qty = max(0.0, (ing.min_stock_qty or 0) * 2 - (ing.stock_qty or 0))

        last_price = ing.purchase_price_gs
        evt = last_price_evts.get(ing_id)
        if evt is not None:
            last_price = evt.price_gs

        out[ing_id] = ConsumptionForecast(
            ingredient_id=ing.id,
            name=ing.name,
            current_stock_qty=ing.stock_qty or 0.0,
            min_stock_qty=ing.min_stock_qty or 0.0,
            avg_daily_consumption=avg_daily_recent,
            trend_pct=trend_pct,
            days_of_stock=days_of_stock,
            projected_stockout_at=projected_stockout,
            recommended_restock_qty=restock_qty,
            last_restock_price_gs=last_price,
        )

    return out
