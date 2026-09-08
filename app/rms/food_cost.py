"""app/rms/food_cost.py — true food cost: theoretical vs actual.

Theoretical food cost = sum(sales × recipe_cost) for a period
Actual food cost       = ingredient purchases − current stock + waste
Food cost %            = actual / sales_revenue

The ratio between theoretical and actual food cost is the key metric:
- 1.00 = perfect (no waste, no theft, no spillage)
- >1.00 = actual exceeds recipe-based estimate (waste, theft, spillage)
- <1.00 = recipe-based estimate too high (recipe or price outdated)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import (
    Ingredient,
    Product,
    Recipe,
    Sale,
    SaleStockMove,
    WasteLog,
)

# ---------------------------------------------------------------------------
# Theoretical food cost (sales × recipe_cost)
# ---------------------------------------------------------------------------

def theoretical_food_cost(session: Session,
                          start: datetime,
                          end: datetime) -> int:
    """Total Gs. of ingredient cost implied by sales in [start, end).

    Walks each sale's product → recipe → ingredients → sum(qty × price).
    """
    sales = list(session.execute(
        select(Sale).where(
            Sale.sold_at >= start,
            Sale.sold_at < end,
            Sale.voided_at.is_(None),
        )
    ).scalars().all())

    # Cache recipe costs per product (avoid repeating for each sale).
    product_cost_cache: dict[int, int | None] = {}

    total = 0
    for sale in sales:
        if sale.product_id is None:
            continue
        if sale.product_id not in product_cost_cache:
            product = session.get(Product, sale.product_id)
            product_cost_cache[sale.product_id] = (
                _recipe_total_cost(session, product) if product else None
            )
        cost_per_unit = product_cost_cache[sale.product_id]
        if cost_per_unit is None:
            continue
        total += cost_per_unit * int(sale.qty or 0)
    return total


def _recipe_total_cost(session: Session, product: Product) -> int | None:
    """Cost per single portion (recipe total / yield_qty).

    Returns None if product has no recipe. Returns int Gs.
    """
    if product is None or product.recipe_id is None:
        return None
    recipe = session.get(Recipe, product.recipe_id)
    if recipe is None or not recipe.yield_qty:
        return None
    from app.rms.models import RecipeLine
    lines = session.scalars(
        select(RecipeLine).where(RecipeLine.recipe_id == recipe.id)
    ).all()
    total = 0
    for line in lines:
        if line.line_kind != "ingredient":
            continue
        ing = session.get(Ingredient, line.line_ref_id)
        if ing is None:
            continue
        price = int(ing.purchase_price_gs or 0)
        total += int(line.qty * price)
    yield_qty = int(recipe.yield_qty or 1)
    if yield_qty <= 0:
        return None
    return total // yield_qty


# ---------------------------------------------------------------------------
# Sales revenue
# ---------------------------------------------------------------------------

def sales_revenue(session: Session,
                  start: datetime,
                  end: datetime) -> int:
    """Total Gs. revenue from sales in [start, end)."""
    rows = session.execute(
        select(Sale.qty, Sale.unit_price_gs).where(
            Sale.sold_at >= start,
            Sale.sold_at < end,
            Sale.voided_at.is_(None),
        )
    ).all()
    return sum(int(qty or 0) * int(price or 0) for qty, price in rows)


# ---------------------------------------------------------------------------
# Actual food cost (stock-move based)
# ---------------------------------------------------------------------------

def actual_ingredient_consumption(session: Session,
                                   start: datetime,
                                   end: datetime) -> int:
    """Sum of negative sale_stock_move × ingredient_price.

    Assumes all stock movement is from sales (no waste / production moves).
    """
    rows = session.execute(
        select(SaleStockMove.ingredient_id, SaleStockMove.qty_delta)
    ).all()
    # No timestamp on SaleStockMove → use all moves as approximation.
    total = 0
    for ing_id, qty_delta in rows:
        if qty_delta is None or qty_delta >= 0:
            continue
        ing = session.get(Ingredient, ing_id)
        if ing is None:
            continue
        price = int(ing.purchase_price_gs or 0)
        total += int(abs(qty_delta) * price)
    return total


def waste_cost(session: Session,
               start: datetime,
               end: datetime) -> int:
    """Sum of waste_log.cost_gs in [start, end).

    Returns 0 if WasteLog table is empty or unavailable.
    """
    try:
        rows = list(session.execute(
            select(WasteLog.cost_gs).where(
                WasteLog.recorded_at >= start,
                WasteLog.recorded_at < end,
            )
        ).all())
    except Exception:
        return 0

    return sum(int(cost or 0) for (cost,) in rows)


# ---------------------------------------------------------------------------
# Combined report
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FoodCostReport:
    period_start: str
    period_end: str
    sales_revenue_gs: int
    theoretical_food_cost_gs: int
    actual_food_cost_gs: int
    waste_cost_gs: int
    theoretical_food_cost_pct: float
    actual_food_cost_pct: float
    ratio: float  # actual / theoretical


def food_cost_report(session: Session,
                     period_days: int = 30) -> FoodCostReport:
    """Build a FoodCostReport for the last N days."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=period_days)

    revenue = sales_revenue(session, start, end)
    theoretical = theoretical_food_cost(session, start, end)
    actual = actual_ingredient_consumption(session, start, end)
    waste = waste_cost(session, start, end)

    theoretical_pct = (theoretical / revenue * 100) if revenue > 0 else 0.0
    actual_pct = (actual / revenue * 100) if revenue > 0 else 0.0
    ratio = (actual / theoretical) if theoretical > 0 else 0.0

    return FoodCostReport(
        period_start=start.strftime("%Y-%m-%d"),
        period_end=end.strftime("%Y-%m-%d"),
        sales_revenue_gs=revenue,
        theoretical_food_cost_gs=theoretical,
        actual_food_cost_gs=actual,
        waste_cost_gs=waste,
        theoretical_food_cost_pct=theoretical_pct,
        actual_food_cost_pct=actual_pct,
        ratio=ratio,
    )


__all__ = [
    "FoodCostReport",
    "actual_ingredient_consumption",
    "food_cost_report",
    "sales_revenue",
    "theoretical_food_cost",
    "waste_cost",
]
