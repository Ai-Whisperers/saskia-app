"""app/rms/costing.py — DEPRECATED shim, re-exports from profitability + sales.

Sprint 2.3 of the 2026-10-02 backend overhaul: this module was split into:

- ``app.rms.profitability.cost`` — recipe/product cost (read-side)
- ``app.rms.sales.lifecycle``   — apply/void sale (transactional)

This shim keeps the public surface stable for the many existing call sites.
New code should import from the new locations.
"""

from __future__ import annotations

from app.rms.profitability.cost import (
    CostResult,
    CycleInRecipeTree,
    ProductWithoutRecipe,
    RecipeWithoutYield,
    _walk_recipe_cost,
    batch_products_cost_margin,
    batch_recipes_cost,
    product_margin,
    product_unit_cost_gs,
    recipe_batch_cost_gs,
    recipe_unit_cost_gs,
    resolve_line_target,
)
from app.rms.sales.lifecycle import (
    ApplySaleResult,
    VoidSaleResult,
    _compute_stock_moves,
    apply_sale,
    void_sale,
)

__all__ = [
    "ApplySaleResult",
    "CostResult",
    "CycleInRecipeTree",
    "ProductWithoutRecipe",
    "RecipeWithoutYield",
    "VoidSaleResult",
    "_compute_stock_moves",
    "_walk_recipe_cost",
    "apply_sale",
    "batch_products_cost_margin",
    "batch_recipes_cost",
    "product_margin",
    "product_unit_cost_gs",
    "recipe_batch_cost_gs",
    "recipe_unit_cost_gs",
    "resolve_line_target",
    "void_sale",
]
