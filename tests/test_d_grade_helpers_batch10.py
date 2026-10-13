"""Parametrized coverage for two more D-grade helpers with no branch matrix.

S1 batch-10 (test coverage continuation): lock the branch matrix of two
D-grade helpers that lack parametrized coverage:

  (1) `app/rms/prime_cost.py:batch_compute_prime_cost` (CC 28, D-grade)
      Per-product PrimeCostBreakdown orchestrator. Walks a list of
      products, computing materials cost (via recipe_batch_cost_gs),
      yield correction, labor cost (from direct_labor_minutes at the
      operator-configured hourly rate), overhead (materials × pct / 100),
      and the resulting prime + gross-margin + profit %. Branches covered:

      - empty list → returns {} immediately (locks the `if not products`
        early return)
      - ComplianceInfo missing → falls back to the constants'
        DEFAULT_LABOR_COST_PER_HOUR_GS + DEFAULT_OVERHEAD_MULTIPLIER_PCT
        (locks the `ci = session.get(ComplianceInfo, 1)` not-found branch)
      - ComplianceInfo present → uses the operator-configured
        labor_rate_gs_per_h + overhead_pct (locks the ci-row-present path)
      - product WITHOUT recipe → notes "Producto sin receta" and
        materials=None (locks the `else: notes.append("Producto sin
        receta")` branch)
      - product WITH recipe + yield_percentage=0.85 → materials ×
        1/0.85 (locks the `_apply_yield_correction` decimal path AND the
        `0 < yield_pct <= 1.0` validity gate)
      - yield_percentage > 1.0 → notes "yield_percentage inválido"
        and yield_corrected=None (locks the
        `yield_pct <= 0 or yield_pct > 1.0` invalid-yield branch)
      - recipe WITHOUT direct_labor_minutes → notes "sin tiempo de mano
        de obra (informal — no bloquea)" and labor=None (locks the
        `_compute_labor_cost` else-branch)
      - full breakdown (recipe + yield + labor + overhead + sale_price)
        → prime_cost_gs and gross_margin_pct are populated, notes=[]

  (2) `scripts/import_herebus_data.py:import_benchmarks` (CC 26, D-grade)
      Seeds MarketBenchmark rows from the Benchmarks_Market sheet of a
      HEREBUS dump. Locates the real header row (containing "Producto"
      column name), skips TOTAL labels + blanks, looks up each label
      against a {recipe_name: id} map (case-insensitive first-word
      match), and adds a MarketBenchmark row when not already present
      (idempotency by product_label). Branches covered:

      - sheet missing → returns 0 (locks the `if not sheet: return 0`
        branch)
      - header row is row 0 → uses row 0 as the column-name map (locks
        the `hdr_idx = 0` initial path)
      - header row is buried after junk rows → scans up to find the row
        whose cell contains "Producto"/"ID"/"Supplier" (locks the
        `hdr_idx = i` break-out branch)
      - blank Producto cell on a data row → skipped (locks the
        `if not row[idx.get("Producto", 0)]: continue` branch)
      - "TOTAL" string in Producto label → skipped (locks the
        `if "TOTAL" in str(label): continue` branch)
      - row shorter than header → silently skipped (locks the
        `len(row) < n_header_len` guard)
      - label NOT in recipe_map → adds MarketBenchmark with
        recipe_id=None (locks the `recipe_id = None` fallback)
      - label matches an existing recipe → adds MarketBenchmark with
        recipe_id=recipe.id (locks the first-word match path)
      - duplicate product_label already exists → skip (locks the
        `existing = ... ; if existing: continue` idempotency branch)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import pytest
from sqlalchemy import select

# Anchor date is unused by these helpers (they don't filter by date), but
# keeping the import path consistent with batch-5/batch-6/batch-7/batch-8/batch-9
# makes the test scaffolding easier to compare.
from app.rms.constants import (
    DEFAULT_LABOR_COST_PER_HOUR_GS,
    DEFAULT_OVERHEAD_MULTIPLIER_PCT,
)

# ─── batch_compute_prime_cost row spec ────────────────────────────────────────


@dataclass
class _PrimeSpec:
    """One scenario for `batch_compute_prime_cost`.

    Each scenario seeds the minimum DB state needed to exercise one
    branch of batch_compute_prime_cost (Product(s) + optional Recipe +
    optional priced ingredient line + optional ComplianceInfo override).
    The helper's primary input is a list of Product objects (not
    product_ids), so the spec returns the Product list directly.
    """

    id: str = ""
    # ComplianceInfo row to seed (None = no CI row → falls back to defaults)
    compliance_labor_rate: Optional[int] = None
    compliance_overhead_pct: Optional[int] = None
    # Product specs:
    # - name: required
    # - has_recipe: True to attach a recipe with one priced ingredient
    # - recipe_yield_percentage: None / 0.85 / 1.5 — exercises yield gate
    # - recipe_direct_labor_minutes: None / 30 — exercises labor gate
    # - ingredient_purchase_price_gs: cost for the priced ingredient
    # - sale_price_gs: sale price for the product
    products: list[dict] = field(default_factory=list)


def _seed_compliance_info(s: Any, labor_rate: Optional[int], overhead_pct: Optional[int]) -> None:
    """Update ComplianceInfo row (id=1) — or skip if both fields are None.

    Mirrors the pattern in tests/test_costing_yield_labor.py: try
    `session.get(ComplianceInfo, 1)` first, then update or add. This
    avoids the UNIQUE constraint failure when the conftest pre-seeds
    the row.
    """
    if labor_rate is None and overhead_pct is None:
        return  # no ComplianceInfo row seeded → defaults branch
    from app.rms.models import ComplianceInfo

    ci = s.get(ComplianceInfo, 1)
    if ci is None:
        ci = ComplianceInfo(id=1)
        s.add(ci)
    ci.labor_cost_per_hour_gs = (
        labor_rate if labor_rate is not None else DEFAULT_LABOR_COST_PER_HOUR_GS
    )
    ci.overhead_multiplier_pct = (
        overhead_pct if overhead_pct is not None else DEFAULT_OVERHEAD_MULTIPLIER_PCT
    )
    s.flush()


def _seed_prime_spec(s: Any, spec: _PrimeSpec) -> list[Any]:
    """Persist the spec's compliance + products, return the products list.

    Mirrors test products in batch8 (tests/test_d_grade_helpers_batch8.py)
    so the harness stays simple: 1 priced ingredient + 1 recipe + 1 product
    per entry. Setting has_recipe=False omits the recipe + ingredient.
    """
    from tests.factories import ing_line, make_ingredient, make_product, make_recipe

    _seed_compliance_info(s, spec.compliance_labor_rate, spec.compliance_overhead_pct)

    seeded: list[Any] = []
    for prod_spec in spec.products:
        recipe = None
        if prod_spec.get("has_recipe"):
            ing = make_ingredient(
                s,
                unit="kg",
                stock_qty=10.0,
                min_stock_qty=1.0,
                purchase_price_gs=prod_spec.get("ingredient_purchase_price_gs", 3000),
            )
            recipe = make_recipe(
                s,
                lines=[ing_line(ing, qty=1.0, unit="kg")],
                yield_percentage=prod_spec.get("recipe_yield_percentage"),
                direct_labor_minutes=prod_spec.get("recipe_direct_labor_minutes"),
            )
        product = make_product(
            s,
            recipe=recipe,
            sale_price_gs=prod_spec.get("sale_price_gs", 25000),
        )
        seeded.append(product)
    return seeded


# ─── batch_compute_prime_cost scenario definitions ────────────────────────────

_ROWS: list[_PrimeSpec] = [
    pytest.param(
        _PrimeSpec(
            id="empty_list_returns_empty_dict",
            products=[],  # no products → returns {}
        ),
        id="empty_list_returns_empty_dict",
    ),
    pytest.param(
        _PrimeSpec(
            id="no_compliance_info_uses_defaults",
            compliance_labor_rate=None,  # no CI row
            compliance_overhead_pct=None,
            products=[
                {
                    "has_recipe": True,
                    "recipe_yield_percentage": 1.0,
                    "recipe_direct_labor_minutes": 60,  # 1 hour
                    "ingredient_purchase_price_gs": 5000,
                    "sale_price_gs": 25000,
                }
            ],
        ),
        id="no_compliance_info_uses_defaults",
    ),
    pytest.param(
        _PrimeSpec(
            id="compliance_info_present_uses_overrides",
            compliance_labor_rate=50_000,  # override default (25_000)
            compliance_overhead_pct=25,  # override default (15)
            products=[
                {
                    "has_recipe": True,
                    "recipe_yield_percentage": 1.0,
                    "recipe_direct_labor_minutes": 60,
                    "ingredient_purchase_price_gs": 5000,
                    "sale_price_gs": 30000,
                }
            ],
        ),
        id="compliance_info_present_uses_overrides",
    ),
    pytest.param(
        _PrimeSpec(
            id="product_without_recipe_notes_no_recipe",
            compliance_labor_rate=None,
            compliance_overhead_pct=None,
            products=[
                {
                    "has_recipe": False,
                    "sale_price_gs": 25000,
                }
            ],
        ),
        id="product_without_recipe_notes_no_recipe",
    ),
    pytest.param(
        _PrimeSpec(
            id="yield_percentage_085_scales_materials",
            compliance_labor_rate=None,
            compliance_overhead_pct=None,
            products=[
                {
                    "has_recipe": True,
                    "recipe_yield_percentage": 0.85,  # 15% loss → cost × 1.176
                    "recipe_direct_labor_minutes": None,  # no labor
                    "ingredient_purchase_price_gs": 10_000,
                    "sale_price_gs": 25000,
                }
            ],
        ),
        id="yield_percentage_085_scales_materials",
    ),
    pytest.param(
        _PrimeSpec(
            id="yield_percentage_above_1_0_notes_invalid",
            compliance_labor_rate=None,
            compliance_overhead_pct=None,
            products=[
                {
                    "has_recipe": True,
                    "recipe_yield_percentage": 1.5,  # > 1.0 → invalid branch
                    "recipe_direct_labor_minutes": 30,
                    "ingredient_purchase_price_gs": 5000,
                    "sale_price_gs": 25000,
                }
            ],
        ),
        id="yield_percentage_above_1_0_notes_invalid",
    ),
    pytest.param(
        _PrimeSpec(
            id="recipe_without_labor_minutes_notes_informal",
            compliance_labor_rate=None,
            compliance_overhead_pct=None,
            products=[
                {
                    "has_recipe": True,
                    "recipe_yield_percentage": 1.0,
                    "recipe_direct_labor_minutes": None,  # → "sin tiempo..."
                    "ingredient_purchase_price_gs": 5000,
                    "sale_price_gs": 25000,
                }
            ],
        ),
        id="recipe_without_labor_minutes_notes_informal",
    ),
    pytest.param(
        _PrimeSpec(
            id="full_breakdown_populates_prime_and_margin",
            compliance_labor_rate=30_000,
            compliance_overhead_pct=20,
            products=[
                {
                    "has_recipe": True,
                    "recipe_yield_percentage": 0.9,  # 10% loss
                    "recipe_direct_labor_minutes": 45,  # 45 min × 30k / 60 = 22.5k
                    "ingredient_purchase_price_gs": 4000,  # materials = 4_000
                    "sale_price_gs": 30000,
                }
            ],
        ),
        id="full_breakdown_populates_prime_and_margin",
    ),
]


# ─── batch_compute_prime_cost driver ─────────────────────────────────────────


@pytest.mark.parametrize("row", _ROWS, ids=lambda r: r.id)
def test_batch_compute_prime_cost_scenarios(session_factory, row):
    """Drive batch_compute_prime_cost across the 8 scenario rows above.

    Locks one branch of the orchestrator per row. The helper is a pure
    SQLAlchemy consumer (no FastAPI Request/Depends), so it's called
    directly with the session + products list — same shape as
    `compute_prime_cost` but with a list of products instead of one id.
    """
    from app.rms.prime_cost import batch_compute_prime_cost

    with session_factory() as s:
        products = _seed_prime_spec(s, row)
        result = batch_compute_prime_cost(s, products)

        if row.id == "empty_list_returns_empty_dict":
            assert result == {}
            return

        # All other rows seed exactly one product → one breakdown.
        assert len(result) == 1
        ((pid, breakdown),) = result.items()
        assert pid == products[0].id

        if row.id == "no_compliance_info_uses_defaults":
            # materials=5000, yield=1.0 (no correction), labor = 60 × 25_000 / 60
            # = 25_000 (matches DEFAULT_LABOR_COST_PER_HOUR_GS); overhead =
            # 5000 × 15 / 100 = 750. Prime = 5000 + 25000 + 750 = 30750.
            assert breakdown.materials_cost_gs == 5000
            assert breakdown.yield_corrected_cost_gs == 5000
            assert breakdown.labor_cost_gs == 25_000
            assert breakdown.overhead_cost_gs == 750
            assert breakdown.prime_cost_gs == 30_750
            assert breakdown.sale_price_gs == 25_000
            assert breakdown.gross_margin_gs == 25_000 - 30_750
            assert breakdown.notes == []
            return

        if row.id == "compliance_info_present_uses_overrides":
            # Same materials/yield as above, but labor = 60 × 50_000 / 60 = 50_000
            # (operator-configured rate) and overhead = 5000 × 25 / 100 = 1250.
            assert breakdown.materials_cost_gs == 5000
            assert breakdown.yield_corrected_cost_gs == 5000
            assert breakdown.labor_cost_gs == 50_000  # override applied
            assert breakdown.overhead_cost_gs == 1250  # override applied
            assert breakdown.prime_cost_gs == 5000 + 50_000 + 1250
            assert breakdown.notes == []
            return

        if row.id == "product_without_recipe_notes_no_recipe":
            # No recipe → materials=None, labor=None, overhead=None,
            # yield_corrected=None, prime=None, gross_margin=None.
            assert breakdown.materials_cost_gs is None
            assert breakdown.labor_cost_gs is None
            assert breakdown.overhead_cost_gs is None
            assert breakdown.prime_cost_gs is None
            assert breakdown.sale_price_gs == 25_000
            assert breakdown.notes == ["Producto sin receta"]
            return

        if row.id == "yield_percentage_085_scales_materials":
            # 10_000 / 0.85 = 11_764.7 → rounded HALF_UP = 11_765
            assert breakdown.materials_cost_gs == 10_000
            assert breakdown.yield_corrected_cost_gs == 11_765
            # direct_labor_minutes=None → _compute_labor_cost's else-branch
            # appends the "sin tiempo..." note (recipe is not None).
            assert breakdown.labor_cost_gs is None
            # overhead = 10_000 × 15 / 100 = 1_500
            assert breakdown.overhead_cost_gs == 1_500
            assert breakdown.prime_cost_gs == 11_765 + 1_500
            assert any("sin tiempo de mano de obra" in n for n in breakdown.notes)
            return

        if row.id == "yield_percentage_above_1_0_notes_invalid":
            # yield_pct > 1.0 → yield_pct set to None, but the "yield inválido"
            # note is appended and yield_corrected stays None.
            assert breakdown.yield_corrected_cost_gs is None
            assert breakdown.materials_cost_gs == 5_000
            # overhead = 5_000 × 15 / 100 = 750
            assert breakdown.overhead_cost_gs == 750
            # labor = 30 × 25_000 / 60 = 12_500
            assert breakdown.labor_cost_gs == 12_500
            # Prime can't be computed (yield_corrected is None) → prime=None.
            assert breakdown.prime_cost_gs is None
            assert any("yield_percentage inválido" in n for n in breakdown.notes)
            return

        if row.id == "recipe_without_labor_minutes_notes_informal":
            # direct_labor_minutes=None → labor is None, "sin tiempo..."
            # note is added (recipe is not None so the note is emitted).
            assert breakdown.labor_cost_gs is None
            assert breakdown.materials_cost_gs == 5_000
            assert breakdown.yield_corrected_cost_gs == 5_000
            assert breakdown.overhead_cost_gs == 750
            assert breakdown.prime_cost_gs == 5_000 + 750  # labor is None → not added
            assert any("sin tiempo de mano de obra" in n for n in breakdown.notes)
            return

        if row.id == "full_breakdown_populates_prime_and_margin":
            # materials = 4_000; yield_corrected = 4000 / 0.9 = 4444.4 → 4444;
            # labor = 45 × 30_000 / 60 = 22_500; overhead = 4000 × 20 / 100 = 800.
            # prime = 4444 + 22500 + 800 = 27_744.
            assert breakdown.materials_cost_gs == 4_000
            assert breakdown.yield_corrected_cost_gs == 4_444
            assert breakdown.labor_cost_gs == 22_500
            assert breakdown.overhead_cost_gs == 800
            assert breakdown.prime_cost_gs == 27_744
            assert breakdown.sale_price_gs == 30_000
            # gross_margin = 30000 - 27744 = 2256; pct = 2256/27744*100 ≈ 8.1
            assert breakdown.gross_margin_gs == 30_000 - 27_744
            assert breakdown.gross_margin_pct is not None
            assert breakdown.prime_cost_pct_of_sale is not None
            # All inputs known → notes is empty.
            assert breakdown.notes == []
            return

        # Defensive: an unhandled id should fail loudly so we don't silently
        # lock the wrong branch matrix.
        raise AssertionError(f"Unhandled row id: {row.id}")


# ─── import_benchmarks row spec ──────────────────────────────────────────────


@dataclass
class _BenchSpec:
    """One scenario for `import_benchmarks`.

    The helper takes a session + a `dump` (a list of `{"_file": filename,
    sheet_name: [[row, ...]]}` dicts) and returns the number of
    MarketBenchmark rows added. Each scenario seeds the dump + optional
    recipes and asserts the count + the persisted rows.
    """

    id: str = ""
    # Dump shape: list of files; each file has _file + a list of sheet dicts.
    dump: list[dict] = field(default_factory=list)
    # Recipes to seed before running (used for the match-by-recipe-name
    # branch). Each entry is (name, id_after_flush).
    seed_recipes: list[str] = field(default_factory=list)
    # Pre-existing MarketBenchmark labels (used for the duplicate-skip).
    existing_labels: list[str] = field(default_factory=list)
    # Expected: number of rows added by the helper.
    expected_added: int = 0
    # Optional: subset of expected labels and their recipe_ids (None if no match).
    expected_rows: list[dict] = field(default_factory=list)


def _dump_with_sheet(filename: str, sheet_name: str, rows: list[list]) -> list[dict]:
    """Build a dump shaped as `import_benchmarks` expects.

    The helper calls `get_sheet(dump, filename, sheet_name)` and expects
    `dump[i][sheet_name]` to be a list of rows. The first row of the
    first non-junk row contains the column-name header.
    """
    return [{"_file": filename, sheet_name: rows}]


# ─── import_benchmarks scenario definitions ──────────────────────────────────

_ROWS_BENCH: list[_BenchSpec] = [
    pytest.param(
        _BenchSpec(
            id="sheet_missing_returns_zero",
            # dump has no "Benchmarks_Market" sheet → returns 0.
            dump=[
                {
                    "_file": "HEREBUS_Analisis.xlsx",
                    "OtherSheet": [["ignored"], ["row1"]],
                }
            ],
            expected_added=0,
        ),
        id="sheet_missing_returns_zero",
    ),
    pytest.param(
        _BenchSpec(
            id="header_row_is_row_zero",
            dump=_dump_with_sheet(
                "HEREBUS_Analisis.xlsx",
                "Benchmarks_Market",
                [
                    # Row 0: header
                    [
                        "Producto",
                        "Nuestro wholesale ₲",
                        "Nuestro retail ₲",
                        "Competidor A (mín) ₲",
                        "Competidor B (prom) ₲",
                        "Mercado promedio ₲",
                        "Notas / Fuente",
                    ],
                    # Row 1: data — "TOTAL" label must be SKIPPED.
                    ["TOTAL", "1000", "2000", "1500", "2500", "2000", "—"],
                    # Row 2: data — blank Producto cell must be SKIPPED.
                    ["", "1000", "2000", "1500", "2500", "2000", "—"],
                    # Row 3: data — valid row with no matching recipe.
                    ["Muffin_Vainilla", "5000", "7000", "6000", "6500", "6300", "TODO"],
                ],
            ),
            expected_added=1,
            expected_rows=[
                {
                    "label": "Muffin_Vainilla",
                    "our_wholesale_gs": 5000,
                    "our_retail_gs": 7000,
                    "comp_min_gs": 6000,
                    "comp_avg_gs": 6500,
                    "market_avg_gs": 6300,
                    "recipe_id": None,  # no matching recipe
                }
            ],
        ),
        id="header_row_is_row_zero",
    ),
    pytest.param(
        _BenchSpec(
            id="header_buried_after_junk_rows",
            # Rows 0-2 are "junk" (no cell containing "Producto"/"ID"/"Supplier").
            # Row 3 is the real header. The helper scans to find it.
            dump=_dump_with_sheet(
                "HEREBUS_Analisis.xlsx",
                "Benchmarks_Market",
                [
                    ["Some banner text", "to", "be", "skipped"],
                    ["Continued", "banner", "rows", ""],
                    ["More", "noise", "here", ""],
                    [
                        "Producto",
                        "Nuestro wholesale ₲",
                        "Nuestro retail ₲",
                        "Competidor A (mín) ₲",
                        "Competidor B (prom) ₲",
                        "Mercado promedio ₲",
                        "Notas / Fuente",
                    ],
                    ["Muffin_Vainilla", "5000", "7000", "6000", "6500", "6300", "TODO"],
                ],
            ),
            expected_added=1,
            expected_rows=[{"label": "Muffin_Vainilla", "recipe_id": None}],
        ),
        id="header_buried_after_junk_rows",
    ),
    pytest.param(
        _BenchSpec(
            id="row_shorter_than_header_skipped",
            dump=_dump_with_sheet(
                "HEREBUS_Analisis.xlsx",
                "Benchmarks_Market",
                [
                    [
                        "Producto",
                        "Nuestro wholesale ₲",
                        "Nuestro retail ₲",
                        "Competidor A (mín) ₲",
                        "Competidor B (prom) ₲",
                        "Mercado promedio ₲",
                        "Notas / Fuente",
                    ],
                    # Too short → `len(row) < n_header_len` → skipped.
                    ["Muffin_Vainilla"],
                ],
            ),
            expected_added=0,
        ),
        id="row_shorter_than_header_skipped",
    ),
    pytest.param(
        _BenchSpec(
            id="label_matches_existing_recipe_first_word",
            # Seed a recipe named "Muffin Vainilla" → label "Muffin Vainilla"
            # (lowercased: "muffin vainilla") → first_word = "muffin vainilla",
            # `rn_low.startswith(first_word)` → True.
            seed_recipes=["Muffin Vainilla"],
            dump=_dump_with_sheet(
                "HEREBUS_Analisis.xlsx",
                "Benchmarks_Market",
                [
                    [
                        "Producto",
                        "Nuestro wholesale ₲",
                        "Nuestro retail ₲",
                        "Competidor A (mín) ₲",
                        "Competidor B (prom) ₲",
                        "Mercado promedio ₲",
                        "Notas / Fuente",
                    ],
                    ["Muffin Vainilla", "5000", "7000", "6000", "6500", "6300", "TODO"],
                ],
            ),
            expected_added=1,
            expected_rows=[
                # recipe_id must be populated (the helper matched the recipe).
                {"label": "Muffin Vainilla", "recipe_id_match": "Muffin Vainilla"},
            ],
        ),
        id="label_matches_existing_recipe_first_word",
    ),
    pytest.param(
        _BenchSpec(
            id="duplicate_product_label_skipped",
            # Pre-seed a MarketBenchmark with the same product_label →
            # the helper must skip it (locks the `existing: continue` branch).
            existing_labels=["Muffin_Vainilla"],
            dump=_dump_with_sheet(
                "HEREBUS_Analisis.xlsx",
                "Benchmarks_Market",
                [
                    [
                        "Producto",
                        "Nuestro wholesale ₲",
                        "Nuestro retail ₲",
                        "Competidor A (mín) ₲",
                        "Competidor B (prom) ₲",
                        "Mercado promedio ₲",
                        "Notas / Fuente",
                    ],
                    ["Muffin_Vainilla", "5000", "7000", "6000", "6500", "6300", "TODO"],
                ],
            ),
            expected_added=0,
        ),
        id="duplicate_product_label_skipped",
    ),
    pytest.param(
        _BenchSpec(
            id="mixed_skip_and_add",
            # Three rows: TOTAL (skip), blank Producto (skip), real (add).
            dump=_dump_with_sheet(
                "HEREBUS_Analisis.xlsx",
                "Benchmarks_Market",
                [
                    [
                        "Producto",
                        "Nuestro wholesale ₲",
                        "Nuestro retail ₲",
                        "Competidor A (mín) ₲",
                        "Competidor B (prom) ₲",
                        "Mercado promedio ₲",
                        "Notas / Fuente",
                    ],
                    ["TOTAL", "1000", "2000", "1500", "2500", "2000", "—"],
                    ["", "1000", "2000", "1500", "2500", "2000", "—"],
                    ["Brownie_Chocolate", "8000", "14000", "12000", "13500", "13000", "TODO"],
                ],
            ),
            expected_added=1,
            expected_rows=[{"label": "Brownie_Chocolate", "recipe_id": None}],
        ),
        id="mixed_skip_and_add",
    ),
]


# ─── import_benchmarks driver ────────────────────────────────────────────────


@pytest.mark.parametrize("row", _ROWS_BENCH, ids=lambda r: r.id)
def test_import_benchmarks_scenarios(session_factory, row):
    """Drive import_benchmarks across the 7 scenario rows above.

    The helper is a pure SQLAlchemy + openpyxl-style consumer (no
    FastAPI Request/Depends, no filesystem — `dump` is an in-memory
    list of dicts). Called directly with session + dump. The dump
    shape mirrors what the `from_file(dry_run=False)` path
    constructs from the workbook.
    """
    # Import lazily inside the test so the test file remains importable
    # even if the script path ever moves.
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from app.rms.models import MarketBenchmark, Recipe
    from scripts.import_herebus_data import import_benchmarks

    with session_factory() as s:
        # Seed recipes (if any) so the recipe_map lookup has entries.
        seeded_recipes: dict[str, int] = {}
        for recipe_name in row.seed_recipes:
            rec = Recipe(name=recipe_name, yield_qty=12.0, yield_unit="und")
            s.add(rec)
            s.flush()
            seeded_recipes[recipe_name] = rec.id

        # Pre-seed MarketBenchmark rows for the duplicate-skip branch.
        for label in row.existing_labels:
            s.add(
                MarketBenchmark(
                    product_label=label,
                    recipe_id=None,
                    our_wholesale_gs=0,
                    our_retail_gs=0,
                    comp_min_gs=0,
                    comp_avg_gs=0,
                    market_avg_gs=0,
                    source="<pre-seeded for test>",
                )
            )
            s.flush()

        # Run the helper.
        added = import_benchmarks(s, row.dump)

        assert added == row.expected_added

        # Validate the persisted rows.
        persisted = s.execute(select(MarketBenchmark).order_by(MarketBenchmark.id)).scalars().all()

        # When the spec pre-seeded labels, those rows are still there plus
        # whatever the helper added. Count the helper-added ones.
        helper_added_rows = [
            r for r in persisted if not r.source or r.source != "<pre-seeded for test>"
        ]
        assert len(helper_added_rows) == row.expected_added

        if row.expected_rows:
            persisted_by_label = {r.product_label: r for r in helper_added_rows}
            for expected in row.expected_rows:
                label = expected["label"]
                assert label in persisted_by_label, (
                    f"Expected label {label!r} not in added rows ({list(persisted_by_label)})"
                )
                got = persisted_by_label[label]
                if "our_wholesale_gs" in expected:
                    assert got.our_wholesale_gs == expected["our_wholesale_gs"]
                if "our_retail_gs" in expected:
                    assert got.our_retail_gs == expected["our_retail_gs"]
                if "comp_min_gs" in expected:
                    assert got.comp_min_gs == expected["comp_min_gs"]
                if "comp_avg_gs" in expected:
                    assert got.comp_avg_gs == expected["comp_avg_gs"]
                if "market_avg_gs" in expected:
                    assert got.market_avg_gs == expected["market_avg_gs"]
                if "recipe_id" in expected:
                    assert got.recipe_id == expected["recipe_id"]
                if "recipe_id_match" in expected:
                    # recipe_id must point to the seeded recipe
                    assert got.recipe_id == seeded_recipes[expected["recipe_id_match"]]


# ─── Row-count doc-lock ────────────────────────────────────────────────────────


# Locks the row counts so a future addition/removal forces a CHANGELOG note.
assert len(_ROWS) == 8, f"batch_compute_prime_cost scenarios: expected 8 rows, got {len(_ROWS)}"
assert len(_ROWS_BENCH) == 7, (
    f"import_benchmarks scenarios: expected 7 rows, got {len(_ROWS_BENCH)}"
)
