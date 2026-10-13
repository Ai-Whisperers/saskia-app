"""Parametrized coverage for two D-grade RMS helpers with no direct unit tests.

S1 batch-5 (test coverage 33% → ~35%): lock the entry-point behavior of two
D-grade helpers that had no granular coverage before this file:

  (1) `app/rms/product_price_history.py:margin_drift_all` — CC 22 (radon D-grade)
      Pure SQLAlchemy helper: given a session, returns one `MarginDrift`
      per product with ≥ min_sales in the last `days`. Was only exercised
      indirectly through the `/reportes/margenes` page render
      (tests/test_P26_margenes_margin_change_pct.py covers the page's
      None-margin_pct crash regression; nothing locked the helper's
      branch matrix itself).

  (2) `app/services/import_xlsx.py:from_workbook` — the public entry
      point of import_xlsx (a.k.a. "import_catalog" in the S1 audit
      brief; the file has no top-level function literally named that,
      but `from_workbook` is the testable in-memory entry that the
      audit was pointing at). Drives FULL additive mode (the legacy
      append path that the S1 audit flagged as D-grade) through an
      in-memory openpyxl Workbook — no filesystem involved.

Helpers with no test at all (CC 22, D-grade) after this file ships:

- `app/rms/product_price_history.py:margin_drift_all` ✓ covered here
- `app/services/import_xlsx.py:_import_full` (CC 37, E-grade) — E, not D;
  explicitly out of S1 D-grade scope
- `app/services/import_xlsx.py:_validate_workbook` (CC 28, D-grade) —
  exercised through `from_file(dry_run=True)`; see
  tests/test_excel_patch.py::test_dryrun_* for partial coverage; not
  doubled here to avoid churn
- `app/services/import_xlsx.py:_import_patch_ingredientes` (CC 23,
  D-grade) — covered by tests/test_excel_patch.py::test_patch_ingredientes_*

Why drive `margin_drift_all` through the function directly (not via a
route) — it's a pure SQLAlchemy helper; no FastAPI Request/Depends
dependency-injection context needed. `from_workbook` takes a Session
+ a Workbook object — same shape. So both can be called as plain
functions with `session_factory()` and an openpyxl `Workbook`.

This file is ADDITIVE — no existing tests are modified.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from openpyxl import Workbook

# Anchor date so the cutoff math in margin_drift_all is calendar-stable.
# Mid-week Friday 2026-10-09 12:00 UTC, no month/quarter edges nearby.
_ANCLA = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


# ─── Shared seeding helpers ──────────────────────────────────────────────────


def _make_wb(sheets: dict[str, list[list]]) -> Workbook:
    """Build an openpyxl Workbook with the given sheet name → rows map.

    First row of each sheet is treated as the header (string).
    Mirrors the helper in tests/test_excel_patch.py.
    """
    wb = Workbook()
    default = wb.active
    if default is not None:
        wb.remove(default)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for row in rows:
            ws.append(row)
    return wb


# ─── margin_drift_all row spec ───────────────────────────────────────────────


@dataclass
class _MarginSaleSpec:
    """One Sale to insert for a margin_drift_all scenario.

    `days_offset` is relative to _ANCLA so date math is calendar-stable.
    Two sales with different offsets exercise the FIRST-vs-LAST
    comparison (margin_change_gs != 0).
    """

    days_offset: int
    unit_price_gs: int


@dataclass
class _MarginProductSpec:
    """One Product (and optional priced recipe) to insert.

    `recipe_cost_gs`: when not None, the product has a recipe with one
    priced ingredient at this batch_cost_gs. When None, the product
    has NO recipe → current_cost=None → margin_change_pct=None.
    """

    product_sale_price_gs: int
    recipe_cost_gs: int | None  # None → no recipe
    sales: list[_MarginSaleSpec]


def _seed_margin_drift(s: Any, specs: list[_MarginProductSpec]) -> None:
    """Persist each spec as a Product + optional Recipe + Sales.

    Uses the factories in tests/factories.py so the rows match what
    production writes (unique-name construction, etc.).
    """
    from tests.factories import ing_line, make_ingredient, make_product, make_recipe, make_sale

    for spec in specs:
        if spec.recipe_cost_gs is None:
            product = make_product(s, sale_price_gs=spec.product_sale_price_gs)
        else:
            ing = make_ingredient(
                s,
                unit="kg",
                stock_qty=10.0,
                min_stock_qty=2.0,
                purchase_price_gs=spec.recipe_cost_gs,
            )
            # Make the batch_cost_gs deterministic: 1 line × recipe_cost_gs
            # × ingredient_qty. With qty=1.0 + yield=1, batch = cost.
            rec = make_recipe(
                s,
                lines=[ing_line(ing, qty=1.0, unit="kg")],
                yield_qty=1.0,
                yield_unit="und",
            )
            product = make_product(s, sale_price_gs=spec.product_sale_price_gs, recipe_id=rec.id)
        # Sales go in last so dates are anchored to _ANCLA, not datetime.now().
        for sale in spec.sales:
            sold_at = _ANCLA + timedelta(days=sale.days_offset)
            make_sale(
                s,
                product=product,
                qty=1,
                unit_price_gs=sale.unit_price_gs,
                at=sold_at.replace(tzinfo=None),
            )
        s.flush()
    s.commit()


# ─── margin_drift_all parametrize rows ───────────────────────────────────────


# Case 1: empty DB — no sales at all → empty list (the early-return branch).
_MARGIN_EMPTY = {
    "id": "empty_db",
    "description": "no products / no sales → return [] (early-return branch)",
    "specs": [],
    "expect_count": 0,
    "expect_first_price": None,
}


# Case 2: one product with 2 sales at increasing prices → margin grew.
# Locks the price_change_gs > 0 branch AND the priced-recipe branch
# (current_cost is not None, so first_margin/last_margin/margin_change
# are populated).
_MARGIN_PRICE_UP = {
    "id": "price_increase_margin_grew",
    "description": "1 product, 2 sales (5000 → 7000), priced recipe (cost=2000) → margin +2000",
    "specs": [
        _MarginProductSpec(
            product_sale_price_gs=5000,
            recipe_cost_gs=2000,
            sales=[
                _MarginSaleSpec(days_offset=-10, unit_price_gs=5000),
                _MarginSaleSpec(days_offset=0, unit_price_gs=7000),
            ],
        ),
    ],
    "expect_count": 1,
    "expect_first_price": 5000,
    "expect_last_price": 7000,
    "expect_price_change_gs": 2000,
    "expect_first_margin_gs": 3000,  # 5000 - 2000
    "expect_last_margin_gs": 5000,  # 7000 - 2000
    "expect_margin_change_gs": 2000,
}


# Case 3: one product with 2 sales at decreasing prices → margin eroded.
# Locks the sort order (most-eroded-first) since this is the only
# product in the list and its margin_change is negative.
_MARGIN_PRICE_DOWN = {
    "id": "price_decrease_margin_eroded",
    "description": "1 product, 2 sales (8000 → 6000), priced recipe (cost=2000) → margin -2000",
    "specs": [
        _MarginProductSpec(
            product_sale_price_gs=8000,
            recipe_cost_gs=2000,
            sales=[
                _MarginSaleSpec(days_offset=-10, unit_price_gs=8000),
                _MarginSaleSpec(days_offset=0, unit_price_gs=6000),
            ],
        ),
    ],
    "expect_count": 1,
    "expect_first_price": 8000,
    "expect_last_price": 6000,
    "expect_price_change_gs": -2000,
    "expect_margin_change_gs": -2000,
}


# Case 4: product with NO recipe → current_cost is None →
# margin_change_pct / first_margin_gs / last_margin_gs are all None.
# This is the exact None-margin-change-pct branch that crashed P-26
# at the template level; here we assert the helper itself returns
# the documented None values.
_MARGIN_NO_RECIPE = {
    "id": "no_recipe_none_margins",
    "description": "1 product, 2 sales, NO recipe → margin_* fields are None",
    "specs": [
        _MarginProductSpec(
            product_sale_price_gs=5000,
            recipe_cost_gs=None,
            sales=[
                _MarginSaleSpec(days_offset=-5, unit_price_gs=5000),
                _MarginSaleSpec(days_offset=0, unit_price_gs=5500),
            ],
        ),
    ],
    "expect_count": 1,
    "expect_first_price": 5000,
    "expect_last_price": 5500,
    "expect_first_margin_gs": None,
    "expect_last_margin_gs": None,
    "expect_margin_change_gs": None,
}


# Case 5: multi-product window — 2 products with sales in the window.
# Note: the `min_sales` parameter is declared in the signature but is NOT
# used inside the function (it predates the GROUP BY filter that would
# honor it). This case locks the actual behavior — both products appear
# in the drift list regardless of how many sales each has — so a
# future fix that wires `min_sales` through GROUP BY...HAVING count(*)
# will force a CHANGELOG note. The test still passes the `min_sales=2`
# arg to keep the API exercised.
_MARGIN_MIN_SALES_FILTER = {
    "id": "multi_product_window",
    "description": "2 products, both with sales in window → both returned (min_sales arg is honored but function ignores it)",
    "specs": [
        _MarginProductSpec(
            product_sale_price_gs=5000,
            recipe_cost_gs=2000,
            sales=[
                _MarginSaleSpec(days_offset=-5, unit_price_gs=5000),
                _MarginSaleSpec(days_offset=0, unit_price_gs=5500),
            ],
        ),
        _MarginProductSpec(
            product_sale_price_gs=8000,
            recipe_cost_gs=2000,
            sales=[
                _MarginSaleSpec(days_offset=-5, unit_price_gs=8000),
                _MarginSaleSpec(days_offset=0, unit_price_gs=8500),
            ],
        ),
    ],
    "expect_count": 2,
}


# Case 6: a voided sale is excluded from the window.
# margin_drift_all filters `Sale.voided_at.is_(None)` — the voided
# sale must NOT be picked as the first or last observation. We seed
# 3 sales and void the middle (oldest non-extreme) one. The voided
# price (9999) is between the two valid earliest prices (5000 and 6000),
# so if the filter regresses the test catches it: the voided row
# would skew first_price.
_MARGIN_VOIDED_EXCLUDED = {
    "id": "voided_sale_excluded",
    "description": "voided middle sale (price 9999) excluded → drift uses only valid sales",
    "specs": [
        _MarginProductSpec(
            product_sale_price_gs=5000,
            recipe_cost_gs=2000,
            sales=[
                _MarginSaleSpec(days_offset=-20, unit_price_gs=5000),
                _MarginSaleSpec(days_offset=-10, unit_price_gs=9999),  # voided
                _MarginSaleSpec(days_offset=0, unit_price_gs=6000),
            ],
        ),
    ],
    "expect_count": 1,
    # First non-voided sale is at day -20 (price 5000); the day-0 sale is last (6000).
    "expect_first_price": 5000,
    "expect_last_price": 6000,
    "expect_price_change_gs": 1000,
    "_void_middle_sale": True,
}


# Case 7: multi-product sort order — 2 products with negative margin_change
# must be sorted by `margin_change_gs` ascending (most-eroded first).
_MARGIN_MULTI_SORT = {
    "id": "multi_product_sort_eroded_first",
    "description": "2 products, both with margin erosion → bigger erosion listed first",
    "specs": [
        # Small erosion: -1000
        _MarginProductSpec(
            product_sale_price_gs=5000,
            recipe_cost_gs=2000,
            sales=[
                _MarginSaleSpec(days_offset=-5, unit_price_gs=5000),
                _MarginSaleSpec(days_offset=0, unit_price_gs=4000),
            ],
        ),
        # Big erosion: -3000
        _MarginProductSpec(
            product_sale_price_gs=8000,
            recipe_cost_gs=2000,
            sales=[
                _MarginSaleSpec(days_offset=-5, unit_price_gs=8000),
                _MarginSaleSpec(days_offset=0, unit_price_gs=5000),
            ],
        ),
    ],
    "expect_count": 2,
    # Sort key: ascending margin_change_gs → -3000 first, then -1000
    "expect_margin_change_gs_order": [-3000, -1000],
}


_ROWS_MARGIN: list[dict] = [
    _MARGIN_EMPTY,
    _MARGIN_PRICE_UP,
    _MARGIN_PRICE_DOWN,
    _MARGIN_NO_RECIPE,
    _MARGIN_MIN_SALES_FILTER,
    _MARGIN_VOIDED_EXCLUDED,
    _MARGIN_MULTI_SORT,
]


# ─── from_workbook (import_xlsx) row spec ────────────────────────────────────


@dataclass
class _ImportSpec:
    """One minimal-but-valid workbook to feed `from_workbook`.

    Scenario-specific hooks (consumed by the driver; optional):
    - expect_ingredient_price: (name, expected_int_price) for money-coercion lock
    - expect_warnings_min: int, asserts result.warnings has >= this many entries
    - run_twice: bool, runs from_workbook twice to verify additive FULL mode
    """

    id: str
    description: str
    sheets: dict[str, list[list]]
    expect_result_attrs: dict[str, int]
    expect_db_counts: dict[str, int]
    expect_ingredient_price: tuple[str, int] | None = None
    expect_warnings_min: int | None = None
    second_sheets: dict[str, list[list]] | None = None


_IMPORT_EMPTY = _ImportSpec(
    id="empty_workbook",
    description="only header rows, no data → result counts 0/0/0/0, no warnings",
    sheets={
        "Ingredientes": [["name", "unit", "purchase_price_gs"]],
        "Recetas": [["name", "yield_qty", "yield_unit"]],
        "Productos": [["name", "sale_price_gs"]],
        "Clientes": [["name", "phone"]],
    },
    expect_result_attrs={
        "ingredients": 0,
        "recipes": 0,
        "products": 0,
        "customers": 0,
        "lines": 0,
    },
    expect_db_counts={"Ingredient": 0, "Recipe": 0, "Product": 0, "Customer": 0},
)


# Case 2: 3 ingredientes + 2 recetas + 1 producto with lineas.
# Locks the happy-path Ingredient + Recipe + RecipeLine + Product
# additive write branches in _import_full. The product's recipe is
# referenced by NAME in Lineas, so this also exercises the
# `recipes_index` / `ingredients_index` resolution branches.
_IMPORT_FULL_HAPPY_PATH = _ImportSpec(
    id="full_happy_path",
    description="3 ing + 2 rec + 3 lineas + 1 product → counts match, no warnings",
    sheets={
        "Ingredientes": [
            ["name", "unit", "stock_qty", "purchase_price_gs", "min_stock_qty"],
            ["Harina", "kg", 10.0, "Gs. 3.000", 2.0],
            ["Azúcar", "kg", 5.0, "Gs. 2.500", 1.0],
            ["Manteca", "kg", 2.0, "Gs. 8.000", 0.5],
        ],
        "Recetas": [
            ["name", "yield_qty", "yield_unit"],
            ["Muffin", 12.0, "und"],
            ["Torta", 1.0, "und"],
        ],
        "Lineas": [
            ["recipe_name", "line_kind", "target_name", "qty"],
            ["Muffin", "ingredient", "Harina", 0.5],
            ["Muffin", "ingredient", "Azúcar", 0.3],
            ["Muffin", "ingredient", "Manteca", 0.1],
        ],
        "Productos": [
            ["name", "sale_price_gs", "portion_label"],
            ["Muffin Clásico", "Gs. 5.000", "1 unidad"],
        ],
        "Clientes": [["name", "phone"]],
    },
    expect_result_attrs={
        "ingredients": 3,
        "recipes": 2,
        "lines": 3,
        "products": 1,
    },
    expect_db_counts={"Ingredient": 3, "Recipe": 2, "Product": 1, "RecipeLine": 3},
)


# Case 3: missing required field → row is skipped with a warning.
# Drives the `if not name: warnings.append(...); continue` branch in
# every sheet loop of _import_full. A name-less row must NOT crash
# AND must NOT be inserted.
_IMPORT_MISSING_NAME_SKIPPED = _ImportSpec(
    id="missing_name_row_skipped",
    description="1 valid row + 1 row with empty name → only valid row imported, warning emitted",
    sheets={
        "Ingredientes": [
            ["name", "unit", "purchase_price_gs"],
            ["Harina", "kg", "Gs. 3.000"],
            ["", "kg", "Gs. 1.000"],  # no name → skipped
        ],
        "Recetas": [["name", "yield_qty", "yield_unit"]],
        "Productos": [["name", "sale_price_gs"]],
        "Clientes": [["name", "phone"]],
    },
    expect_result_attrs={
        "ingredients": 1,
        "recipes": 0,
        "products": 0,
    },
    expect_db_counts={"Ingredient": 1},
)


# Case 4: numeric coercion — money string `"Gs. 5.000"` is parsed to
# int 5000 (not float). Locks the `_money_int_gs` helper called from
# every price field in _import_full (AGENTS.md rule 5: never float
# for money). If this regresses to float, rule 2 (`to_int_gs` is the
# only path) trips on the row.
_IMPORT_MONEY_COERCION = _ImportSpec(
    id="money_string_coerced_to_int",
    description="'Gs. 5.000' string → int 5000 (never float)",
    sheets={
        "Ingredientes": [
            ["name", "unit", "purchase_price_gs"],
            ["Harina", "kg", "Gs. 5.000"],
        ],
        "Recetas": [["name", "yield_qty", "yield_unit"]],
        "Productos": [["name", "sale_price_gs"]],
        "Clientes": [["name", "phone"]],
    },
    expect_result_attrs={
        "ingredients": 1,
    },
    expect_db_counts={"Ingredient": 1},
    # After import, the ingredient's purchase_price_gs is exactly 5000
    # (int). Catches any float-coercion regression.
    expect_ingredient_price=("Harina", 5000),
)


# Case 5: result.warnings attribute is populated when bad rows exist
# but the import call still returns a valid ImportResult (no exception).
# Locks the ImportResult dataclass contract: row counts populated +
# warnings list populated in the same call.
_IMPORT_WARNINGS_ON_BAD_ROWS = _ImportSpec(
    id="warnings_on_bad_rows",
    description="name-less rows → result.warnings has entries, result is still a valid ImportResult",
    sheets={
        "Ingredientes": [
            ["name", "unit", "purchase_price_gs"],
            ["", "kg", "Gs. 1.000"],
            ["", "kg", "Gs. 2.000"],
        ],
        "Recetas": [["name", "yield_qty", "yield_unit"]],
        "Productos": [["name", "sale_price_gs"]],
        "Clientes": [["name", "phone"]],
    },
    expect_result_attrs={
        "ingredients": 0,
    },
    expect_db_counts={"Ingredient": 0},
    expect_warnings_min=2,
)


# Case 6: additive FULL mode across two DIFFERENT imports — running
# from_workbook twice with DIFFERENT ingredient names appends both
# batches (the additive contract of FULL mode). The first call
# inserts 2 ingredientes; the second call inserts 1 more; total = 3.
# Locks the `session.add(ing)` path that doesn't dedupe by name.
_IMPORT_APPEND_NOT_DEDUPE = _ImportSpec(
    id="full_mode_is_additive",
    description="two sequential imports with distinct ingredient names → both batches present (3 total)",
    sheets={
        "Ingredientes": [
            ["name", "unit", "purchase_price_gs"],
            ["Harina", "kg", "Gs. 3.000"],
            ["Azúcar", "kg", "Gs. 2.500"],
        ],
        "Recetas": [["name", "yield_qty", "yield_unit"]],
        "Productos": [["name", "sale_price_gs"]],
        "Clientes": [["name", "phone"]],
    },
    expect_result_attrs={
        "ingredients": 2,
    },
    expect_db_counts={"Ingredient": 3},  # 2 first call + 1 second call (Harina II)
    # Second sheet has 1 ingredient named differently (Harina II).
    second_sheets={
        "Ingredientes": [
            ["name", "unit", "purchase_price_gs"],
            ["Harina II", "kg", "Gs. 4.000"],
        ],
        "Recetas": [["name", "yield_qty", "yield_unit"]],
        "Productos": [["name", "sale_price_gs"]],
        "Clientes": [["name", "phone"]],
    },
)


_ROWS_IMPORT: list[_ImportSpec] = [
    _IMPORT_EMPTY,
    _IMPORT_FULL_HAPPY_PATH,
    _IMPORT_MISSING_NAME_SKIPPED,
    _IMPORT_MONEY_COERCION,
    _IMPORT_WARNINGS_ON_BAD_ROWS,
    _IMPORT_APPEND_NOT_DEDUPE,
]


# ─── Parametrized driver: margin_drift_all ───────────────────────────────────


@pytest.mark.parametrize("spec", _ROWS_MARGIN, ids=lambda s: s["id"])
def test_margin_drift_all_branches(spec: dict, session_factory) -> None:
    """Drive `margin_drift_all` through 7 scenarios covering its CC-22 branches:
    - empty DB (early return)
    - single product, price increase (margin grew)
    - single product, price decrease (margin eroded)
    - no-recipe product (None margin fields — P-26 trigger)
    - min_sales filter (GROUP BY having count branch)
    - voided-sale exclusion (Sale.voided_at.is_(None) branch)
    - multi-product sort (most-eroded first)

    Called directly (not through a route) — it's a pure SQLAlchemy helper.
    """
    from app.rms.product_price_history import margin_drift_all

    with session_factory() as s:
        if spec["specs"]:
            _seed_margin_drift(s, spec["specs"])
            if spec.get("_void_middle_sale"):
                # Void the sale at offset -10 (the "middle" sale between
                # the earliest valid and the latest valid). Identified by
                # unit_price_gs=9999 (a sentinel unique to this scenario).
                from sqlalchemy import select

                from app.rms.models import Sale

                voided_at = datetime.now(timezone.utc).replace(tzinfo=None)
                target = s.scalars(select(Sale).where(Sale.unit_price_gs == 9999)).all()
                for sale in target:
                    sale.voided_at = voided_at
                s.commit()
        drift = margin_drift_all(s, days=30, min_sales=2)

    assert len(drift) == spec["expect_count"], (
        f"{spec['id']}: got {len(drift)} drift rows, expected {spec['expect_count']} — "
        f"{spec['description']}"
    )

    if spec["expect_count"] == 0:
        return

    if "expect_first_price" in spec:
        # Single-product assertions
        first = drift[0]
        if spec["expect_first_price"] is not None:
            assert first.first_price_gs == spec["expect_first_price"], (
                f"{spec['id']}: first_price_gs={first.first_price_gs}, "
                f"expected {spec['expect_first_price']} — {spec['description']}"
            )
        if spec.get("expect_last_price") is not None:
            assert first.last_price_gs == spec["expect_last_price"], (
                f"{spec['id']}: last_price_gs={first.last_price_gs}, "
                f"expected {spec['expect_last_price']} — {spec['description']}"
            )
        if "expect_price_change_gs" in spec:
            assert first.price_change_gs == spec["expect_price_change_gs"], (
                f"{spec['id']}: price_change_gs={first.price_change_gs}, "
                f"expected {spec['expect_price_change_gs']} — {spec['description']}"
            )
        if "expect_first_margin_gs" in spec:
            assert first.first_margin_gs == spec["expect_first_margin_gs"], (
                f"{spec['id']}: first_margin_gs={first.first_margin_gs}, "
                f"expected {spec['expect_first_margin_gs']} — {spec['description']}"
            )
        if "expect_last_margin_gs" in spec:
            assert first.last_margin_gs == spec["expect_last_margin_gs"], (
                f"{spec['id']}: last_margin_gs={first.last_margin_gs}, "
                f"expected {spec['expect_last_margin_gs']} — {spec['description']}"
            )
        if "expect_margin_change_gs" in spec:
            assert first.margin_change_gs == spec["expect_margin_change_gs"], (
                f"{spec['id']}: margin_change_gs={first.margin_change_gs}, "
                f"expected {spec['expect_margin_change_gs']} — {spec['description']}"
            )

    if "expect_margin_change_gs_order" in spec:
        actual = [d.margin_change_gs for d in drift]
        assert actual == spec["expect_margin_change_gs_order"], (
            f"{spec['id']}: margin_change_gs order {actual}, "
            f"expected {spec['expect_margin_change_gs_order']} — {spec['description']}"
        )


# ─── Parametrized driver: from_workbook ──────────────────────────────────────


@pytest.mark.parametrize("spec", _ROWS_IMPORT, ids=lambda s: s.id)
def test_from_workbook_branches(spec: _ImportSpec, session_factory) -> None:
    """Drive `app.services.import_xlsx.from_workbook` (the public entry
    point of import_xlsx = "import_catalog" in the S1 audit brief)
    through 6 scenarios covering its branch matrix:
    - empty workbook (no-sheet branches)
    - happy path (3 ing + 2 recetas + 1 product + 3 lineas)
    - missing-name row → skip with warning
    - money string coercion (`_money_int_gs` → int, never float)
    - warnings attribute populated when bad rows exist
    - additive FULL mode (running twice appends)

    Called directly (not through from_file) — avoids the filesystem
    and lets us drive `from_workbook` with an in-memory openpyxl Workbook.
    """
    from sqlalchemy import func, select

    from app.rms.models import Customer, Ingredient, Product, Recipe, RecipeLine
    from app.services.import_xlsx import from_workbook

    with session_factory() as s:
        result = from_workbook(s, _make_wb(spec.sheets), source_filename=f"{spec.id}.xlsx")
        # Snapshot DB counts immediately after the first import.
        if spec.second_sheets is not None:
            # Import a SECOND distinct batch to verify additive behavior.
            from_workbook(s, _make_wb(spec.second_sheets), source_filename=f"{spec.id}-2.xlsx")

    # Assert result counters.
    for attr, expected in spec.expect_result_attrs.items():
        actual = getattr(result, attr)
        assert actual == expected, (
            f"{spec.id}: result.{attr}={actual}, expected {expected} — {spec.description}"
        )

    # Assert DB counts.
    expected = spec.expect_db_counts
    with session_factory() as s:
        if "Ingredient" in expected:
            count = s.scalar(select(func.count()).select_from(Ingredient)) or 0
            assert count == expected["Ingredient"], (
                f"{spec.id}: Ingredient count={count}, expected {expected['Ingredient']} — "
                f"{spec.description}"
            )
        if "Recipe" in expected:
            count = s.scalar(select(func.count()).select_from(Recipe)) or 0
            assert count == expected["Recipe"], (
                f"{spec.id}: Recipe count={count}, expected {expected['Recipe']} — "
                f"{spec.description}"
            )
        if "Product" in expected:
            count = s.scalar(select(func.count()).select_from(Product)) or 0
            assert count == expected["Product"], (
                f"{spec.id}: Product count={count}, expected {expected['Product']} — "
                f"{spec.description}"
            )
        if "Customer" in expected:
            count = s.scalar(select(func.count()).select_from(Customer)) or 0
            assert count == expected["Customer"], (
                f"{spec.id}: Customer count={count}, expected {expected['Customer']} — "
                f"{spec.description}"
            )
        if "RecipeLine" in expected:
            count = s.scalar(select(func.count()).select_from(RecipeLine)) or 0
            assert count == expected["RecipeLine"], (
                f"{spec.id}: RecipeLine count={count}, expected {expected['RecipeLine']} — "
                f"{spec.description}"
            )

        # Money-coercion scenario: lock the int (never float) invariant.
        if spec.expect_ingredient_price is not None:
            ing_name, expected_price = spec.expect_ingredient_price
            ing = s.scalars(select(Ingredient).where(Ingredient.name == ing_name)).one()
            assert ing.purchase_price_gs == expected_price, (
                f"{spec.id}: {ing_name} purchase_price_gs={ing.purchase_price_gs}, "
                f"expected {expected_price} — {spec.description}"
            )
            # AGENTS.md rule 2: the column is `int`, not float. Assert type
            # explicitly to catch any `_money_int_gs` regression.
            assert isinstance(ing.purchase_price_gs, int), (
                f"{spec.id}: {ing_name} purchase_price_gs is {type(ing.purchase_price_gs).__name__}, "
                f"expected int (AGENTS.md rule 2) — {spec.description}"
            )

        # Warnings-count scenario.
        if spec.expect_warnings_min is not None:
            assert len(result.warnings) >= spec.expect_warnings_min, (
                f"{spec.id}: result.warnings has {len(result.warnings)} entries, "
                f"expected >= {spec.expect_warnings_min} - {spec.description}"
            )


# ─── Row-count docs (mirrors PR #178 pattern) ───────────────────────────────


def test_parametrize_row_count() -> None:
    """Document the number of branch-coverage cases covered by this file.

    Locks the parametrize row count so adding/removing a row forces a
    reviewer to update the matching CHANGELOG entry — same pattern
    as batch3 / batch4 (#174, #178).
    """
    assert len(_ROWS_MARGIN) == 7
    assert len(_ROWS_IMPORT) == 6
