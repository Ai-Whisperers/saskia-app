"""app/rms/profitability/ — Recipe cost + product margin (read-side).

Sprint 2.3 of the 2026-10-02 backend overhaul: split the read-side costing
from the transactional sale path.

Submodules:
- cost: recipe_batch_cost_gs, recipe_unit_cost_gs, product_margin, _walk_recipe_cost
"""

from app.rms.profitability.cost import (
    CostResult,
    CycleInRecipeTree,
    ProductWithoutRecipe,
    RecipeWithoutYield,
    batch_products_cost_margin,
    batch_recipes_cost,
    product_margin,
    product_unit_cost_gs,
    recipe_batch_cost_gs,
    recipe_unit_cost_gs,
    resolve_line_target,
)

__all__ = [
    "CostResult",
    "CycleInRecipeTree",
    "ProductWithoutRecipe",
    "RecipeWithoutYield",
    "batch_products_cost_margin",
    "batch_recipes_cost",
    "product_margin",
    "product_unit_cost_gs",
    "recipe_batch_cost_gs",
    "recipe_unit_cost_gs",
    "resolve_line_target",
]
