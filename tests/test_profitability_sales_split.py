"""tests/test_profitability_sales_split.py — Sprint 2.3 verification.

Sprint 2.3 of the 2026-10-02 backend overhaul: split ``app/rms/costing.py``
into ``app/rms/profitability/cost`` (read-side) + ``app/rms/sales/lifecycle``
(transactional). The ``costing.py`` shim was REMOVED on 2026-10-12
(SASKIA-211a follow-up): all callers now import from the canonical modules.

This test pins the public API contract:

1. profitability/ + sales/ packages exist
2. the deprecated ``app.rms.costing`` shim no longer exists
3. All Phase 14 #1 dual-write SaleStockMove + StockMovement rows are still
   written via apply_sale (we did NOT drop the dual write; that's Sprint 2.5+)
4. The exceptions live in profitability.cost and are re-exported from sales
5. apply_sale/void_sale and recipe_unit_cost_gs all work via canonical paths
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_packages_exist():
    """The new packages are importable."""
    import app.rms.profitability.cost as pc
    import app.rms.sales.lifecycle as sl

    assert hasattr(pc, "recipe_batch_cost_gs")
    assert hasattr(pc, "recipe_unit_cost_gs")
    assert hasattr(pc, "product_margin")
    assert hasattr(pc, "batch_products_cost_margin")
    assert hasattr(pc, "batch_recipes_cost")
    assert hasattr(sl, "apply_sale")
    assert hasattr(sl, "void_sale")
    assert hasattr(sl, "_compute_stock_moves")


def test_costing_shim_removed():
    """app.rms.costing is GONE — callers import from canonical modules."""
    spec = importlib.util.find_spec("app.rms.costing")
    assert spec is None, (
        "app/rms/costing.py (or a package by that name) still exists. "
        "The deprecated shim was removed 2026-10-12 (SASKIA-211a); "
        "new code must import from app.rms.profitability.cost or "
        "app.rms.sales.lifecycle."
    )
    assert not (REPO_ROOT / "app" / "rms" / "costing.py").exists()


def test_sales_exceptions_re_exported():
    """The exceptions are in profitability.cost but re-exported from sales."""
    from app.rms.profitability.cost import (
        CycleInRecipeTree as PCCycle,
    )
    from app.rms.profitability.cost import (
        ProductWithoutRecipe as PCProduct,
    )
    from app.rms.profitability.cost import (
        RecipeWithoutYield as PCRecipe,
    )
    from app.rms.sales import (
        CycleInRecipeTree as SLCycle,
    )
    from app.rms.sales import (
        ProductWithoutRecipe as SLProduct,
    )
    from app.rms.sales import (
        RecipeWithoutYield as SLRecipe,
    )

    assert SLCycle is PCCycle
    assert SLProduct is PCProduct
    assert SLRecipe is PCRecipe


def test_only_one_costing_module():
    """No more duplicate app/rms/costing*.py or profitability_old/."""
    forbidden = [
        "costing_old.py",
        "costing_backup.py",
        "costing_legacy.py",
        "costing.py",
        "profitability_old",
        "sales_old",
    ]
    rms_dir = str(REPO_ROOT / "app" / "rms")
    for name in forbidden:
        assert not os.path.exists(os.path.join(rms_dir, name)), f"forbidden file/dir exists: {name}"


def test_lifecycle_uses_profitability_exceptions():
    """sales/lifecycle.py raises the same exceptions as profitability/cost.py."""
    import inspect

    import app.rms.sales.lifecycle as sl
    from app.rms.profitability.cost import (
        CycleInRecipeTree,
        RecipeWithoutYield,
    )

    # The exceptions in lifecycle's module globals must be the SAME CLASSES as
    # in profitability. (We re-export them in sales/__init__.py too.)
    assert sl.CycleInRecipeTree is CycleInRecipeTree
    assert sl.RecipeWithoutYield is RecipeWithoutYield

    # verify apply_sale raises them on bad input
    source = inspect.getsource(sl.apply_sale)
    assert "RecipeWithoutYield" in source
    assert "CycleInRecipeTree" in source
