"""app/rms/menu_inventory.py — per-product stock ceilings for the POS.

Ports the FloCafe pattern (addon-inventory.ts): expose a
`stock_ceiling` per product so the POS qty input can cap at
"how many units we can actually make with current ingredient stock".

Sazon's pre_sale_check already runs the same arithmetic for shortage
DETECTION at sale time. This module exposes it for the qty input MAX
attribute so the bad value is never typed in the first place.

Three functions:
- product_stock_ceiling(session, product_id) -> float | None
    Maximum whole-units we can make. None = no restriction (no recipe,
    or ingredients with unlimited stock).
- product_low_stock_threshold(session, product_id) -> float | None
    Below this many units, show a "low stock" pill. None = don't show.
- product_is_sold_out(session, product_id) -> bool
    True when the recipe's limiting ingredient is at/below zero.

Arithmetic (matches pre_sale_check.py):
    per_unit_demand(ingredient) = line.qty / recipe.yield_qty
    per_product_units = ingredient.stock_qty / per_unit_demand(ingredient)
    product_stock_ceiling = min over all recipe lines

Used by:
    - app/templates/ventas.html (qty input max)
    - app/routers/sales.py (menu context, optional)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.rms.models import Ingredient, Product, Recipe, RecipeLine

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _recipe_per_unit_demand(session: "Session", recipe: Recipe) -> dict[int, float]:
    """Return {ingredient_id: qty consumed per 1 unit sold}.

    Formula matches lifecycle._compute_stock_moves:
        per_unit = float(line.qty) / float(recipe.yield_qty)
    Returns {} if recipe.yield_qty <= 0 (uncatchable recipes — caller
    should treat as "no ceiling").
    """
    if recipe.yield_qty is None or recipe.yield_qty <= 0:
        return {}
    demand: dict[int, float] = {}
    lines = session.query(RecipeLine).filter(
        RecipeLine.recipe_id == recipe.id,
        RecipeLine.line_kind == "ingredient",
    ).all()
    for line in lines:
        if line.qty is None or line.qty <= 0:
            continue
        # line.qty is Decimal on SQLite; cast to float for arithmetic
        demand[line.line_ref_id] = float(line.qty) / float(recipe.yield_qty)
    return demand


def product_stock_ceiling(session: "Session", product_id: int) -> float | None:
    """Return max units we can make with current ingredient stock.

    None = no restriction (no recipe or uncatchable recipe).
    0.0 = sold out (recipe exists but all ingredients exhausted).
    """
    product = session.get(Product, product_id)
    if product is None or product.recipe_id is None:
        return None
    recipe = session.get(Recipe, product.recipe_id)
    if recipe is None:
        return None
    demand = _recipe_per_unit_demand(session, recipe)
    if not demand:
        return None
    min_units: float | None = None
    for ing_id, per_unit in demand.items():
        ing = session.get(Ingredient, ing_id)
        if ing is None or ing.stock_qty is None:
            continue
        # Floor at 0 — can't make negative units
                # Floor at 0 — can't make negative units
        units_from_this = max(0.0, float(ing.stock_qty) / per_unit)
        if min_units is None or units_from_this < min_units:
            min_units = units_from_this
    return float(min_units) if min_units is not None else None


def product_low_stock_threshold(
    session: "Session",
    product_id: int,
    *,
    units: float | None = None,
) -> float:
    """Below this many units, surface a "low stock" pill.

    Returns a fixed units threshold (not derived from ceiling). This
    matches the FloCafe pattern: the threshold is an operator-tunable
    constant ("show a low-stock badge when fewer than N units can be
    made"), not a percentage of current stock.

    Operators can override via the env var
    SAZON_MENU_LOW_STOCK_UNITS (added in app/rms/config.py).
    Default: 5 units (about half a tray of most products in Sazon's
    typical scale).

    Returns 0.0 for products with no recipe (no ceiling concept → no
    threshold needed; template can hide the badge).
    """
    if units is None:
        from app.rms import config
        units = float(config.SAZON_MENU_LOW_STOCK_UNITS)
    product = session.get(Product, product_id)
    if product is None or product.recipe_id is None:
        return 0.0  # template hides badge
    return units


def product_is_sold_out(session: "Session", product_id: int) -> bool:
    """True when the recipe's limiting ingredient is at/below zero."""
    ceiling = product_stock_ceiling(session, product_id)
    return ceiling is not None and ceiling <= 0.0