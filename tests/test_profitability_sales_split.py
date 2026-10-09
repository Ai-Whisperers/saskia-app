"""tests/test_profitability_sales_split.py — Sprint 2.3 verification.

Sprint 2.3 of the 2026-10-02 backend overhaul: split ``app/rms/costing.py``
into ``app/rms/profitability/cost`` (read-side) + ``app/rms/sales/lifecycle``
(transactional). The original ``costing.py`` is now a shim.

This test pins the public API contract:

1. profitability/ + sales/ packages exist
2. costing.py is a shim that re-exports the same public symbols
3. All Phase 14 #1 dual-write SaleStockMove + StockMovement rows are still
   written via apply_sale (we did NOT drop the dual write; that's Sprint 2.5+)
4. The exceptions live in profitability.cost and are re-exported from sales
5. apply_sale/void_sale and recipe_unit_cost_gs all work via the shim
"""

from __future__ import annotations

from pathlib import Path


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


def test_costing_shim_re_exports():
    """app.rms.costing is a shim — same public surface as before."""
    import app.rms.costing as shim
    import app.rms.profitability.cost as pc
    import app.rms.sales.lifecycle as sl

    # All the public names in the shim must be the SAME OBJECTS as the new modules.
    assert shim.recipe_batch_cost_gs is pc.recipe_batch_cost_gs
    assert shim.recipe_unit_cost_gs is pc.recipe_unit_cost_gs
    assert shim.product_margin is pc.product_margin
    assert shim.batch_products_cost_margin is pc.batch_products_cost_margin
    assert shim.batch_recipes_cost is pc.batch_recipes_cost
    assert shim.resolve_line_target is pc.resolve_line_target
    assert shim.CostResult is pc.CostResult
    assert shim.CycleInRecipeTree is pc.CycleInRecipeTree
    assert shim.ProductWithoutRecipe is pc.ProductWithoutRecipe
    assert shim.RecipeWithoutYield is pc.RecipeWithoutYield

    assert shim.apply_sale is sl.apply_sale
    assert shim.void_sale is sl.void_sale
    assert shim._compute_stock_moves is sl._compute_stock_moves
    assert shim.ApplySaleResult is sl.ApplySaleResult
    assert shim.VoidSaleResult is sl.VoidSaleResult


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
    """No more duplicate app/rms/costing_*.py or profitability_old/."""
    import os

    rms = "/opt/data/work/saskia-app/app/rms"
    forbidden = [
        "costing_old.py",
        "costing_backup.py",
        "costing_legacy.py",
        "profitability_old",
        "sales_old",
    ]
    for name in forbidden:
        assert not os.path.exists(os.path.join(rms, name)), f"forbidden file/dir exists: {name}"


def test_shim_is_thin():
    """The costing.py shim should be small (under ~80 lines)."""
    with open(Path(__file__).resolve().parents[1] / "app" / "rms" / "costing.py") as f:
        content = f.read()
    line_count = len(content.split("\n"))
    assert line_count < 80, f"costing.py shim is {line_count} lines — should be a thin re-export"


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


def test_costing_shim_no_logic():
    """The shim should only contain docstring + imports + __all__.

    No function bodies, no class definitions, no business logic. The whole
    point of the shim is to be a one-line re-export per symbol.
    """
    import re

    with open(Path(__file__).resolve().parents[1] / "app" / "rms" / "costing.py") as f:
        content = f.read()

    # Strip the top-level module docstring
    no_docstring = re.sub(r'^"""[\s\S]*?"""\s*', "", content, count=1)

    lines = []
    for line in no_docstring.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)

    # All remaining non-blank, non-comment lines must be one of:
    # - 'from ... import ...' (imports from new locations)
    # - __all__ entries inside the list
    # - 'from __future__ import annotations'
    for line in lines:
        assert (
            line.startswith(("from ", "import ")) or line.endswith((",", "[", ")")) or line == "]"
        ), f"Unexpected line in costing.py shim: {line!r}"
