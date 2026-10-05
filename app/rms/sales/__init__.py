"""app/rms/sales/ — Sale lifecycle (apply, void, stock-move computation).

Sprint 2.3 of the 2026-10-02 backend overhaul: split the read-side costing
from the transactional sale path.

Submodules:
- lifecycle: apply_sale, void_sale, _compute_stock_moves (transactions)
"""

from app.rms.profitability.cost import (
    CycleInRecipeTree,
    ProductWithoutRecipe,
    RecipeWithoutYield,
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
    "CycleInRecipeTree",
    "ProductWithoutRecipe",
    "RecipeWithoutYield",
    "VoidSaleResult",
    "_compute_stock_moves",
    "apply_sale",
    "void_sale",
]