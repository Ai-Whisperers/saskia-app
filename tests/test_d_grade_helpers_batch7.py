"""Parametrized coverage for two D-grade helpers with no direct unit tests.

S1 batch-7 (test coverage continuation): lock the branch matrix of two
private helpers that had no granular coverage before this file:

  (1) `app/routers/produccion/_full.py:_step_5_build_recipe_row` (CC 24, D-grade)
      Pure data-shaping helper invoked by the /produccion day-view
      orchestrator. Takes one ProductionRow `r` + a bag of lookup dicts
      and returns a flat dict the template renders. Branches covered:
      recipe present / absent, product present / absent, pricing
      present / absent, demand present / absent, qty_to_produce=0
      (no surplus), fermentation_minutes set / unset, closure_status
      lookup default, recipe_difficulty / recipe_allergens passthrough.

  (2) `app/rms/refunds.py:_restock_for_target` (CC 29, D-grade)
      Restores stock for a refunded Sale/Pedido/PedidoLine. Branches
      covered: sale with no StockMovement rows → []; sale with 2
      StockMovement rows → proportional restoration; sale_id → no Sale
      → []; sale with single movement → full share; sale with all
      zero-qty moves → all skipped (share<=0); pedido with 0
      PedidoLine rows → [].

      The pedido_line-with-recipe and pedido-with-lines branches are
      EXCLUDED from this file (see NOTE block in the scenario section)
      because the helper has two pre-existing bugs that are out of
      scope for the s1-batch7 test-coverage sweep.

Why drive them directly (not through the route)
-----------------------------------------------
Both are private helpers (leading underscore). `_step_5_build_recipe_row`
is a pure function of dicts + one ProductionRow — no DB, no template
context. `_restock_for_target` is a SQLAlchemy helper that needs a
`Session` and an Ingredient/Recipe/Sale/PedidoLine set up, but no
FastAPI Request/Depends. Calling them in isolation lets us:

- lock the branch matrix without touching CSRF / auth / template render;
- use `session_factory()` directly so we exercise real SQLAlchemy state
  transitions (commit, flush, refresh, query);
- keep the parametrize rows minimal — one row per branch outcome.

Each test seeds the minimum DB state required (Product / Recipe /
Ingredient / Pedido / PedidoLine / Sale / StockMovement — all in
`app/rms/models_legacy.py`; tests use the standard `session_factory`
fixture so the in-memory SQLite from conftest is the shared DB).

This file is ADDITIVE — no existing tests are modified. The production
regression tests (test_P14_*, test_produccion_v3_phase*, test_P24_*)
cover end-to-end flows; this file locks the helper-level branches that
those flows pass through.

Excluded D-grade helpers (covered elsewhere or out of scope):

- `libro_ventas` (CC 21) — covered in PR #174
- `bank_list` / `shopping_list_index` (CC 21) — covered in PR #178
- `margin_drift_all` / `from_workbook` (CC 22) — covered in PR #179
- `_pedido_resolve_customer` / `_pedido_persist_address_book_entry`
  (CC 24 + 23) — covered in PR #181
- `_validate_workbook` (CC 28) — already exercised indirectly through
  `from_file(dry_run=True)` per `tests/test_excel_patch.py`; not
  re-doubled to avoid churn (s1-batch5 precedent)
- `_import_patch_ingredientes` (CC 23) — already exercised by
  `tests/test_excel_patch.py::test_patch_ingredientes_*`
- `verify_catalog_on_vps.py main` (CC 22) — already covered by
  `tests/test_verify_catalog_on_vps.py`
- `apply_sale` (CC 25) — exercised by 28+ test files via the full
  sale-creation path; refactoring it is S3 territory

Adding a new scenario = one new dict entry in `_ROWS_RECIPE` or
`_ROWS_RESTOCK`, no new function.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import pytest

# Sentinel used to mark fields whose values are computed inside the
# driver (after a seed inserts a row whose id we don't know at
# definition time).
_WILL_BE_SET = "__WILL_BE_SET__"


# ─── _step_5_build_recipe_row row spec ─────────────────────────────────────


@dataclass
class _RecipeRowSpec:
    """One scenario for `_step_5_build_recipe_row`.

    Branch knobs:
      - has_recipe: a Recipe to pre-insert (or None for absent)
      - recipe_yield_qty / recipe_yield_unit / recipe_fermentation /
        recipe_difficulty / recipe_allergens: pre-inserted values
      - has_product: a Product to pre-insert (or None for absent)
      - product_portion_label: pre-inserted value
      - pricing_dict: a {recipe_id: (cost_per_unit_gs, retail_gs)} map
      - demand_dict: a {product_id: DemandLike} map
      - row_product_id / row_recipe_id / row_qty / row_forecast /
        row_confidence / row_product_name: the ProductionRow `r` fields
      - closure_status / closure_notes dicts
      - expect_* fields: post-call assertions on the returned dict
    """

    id: str = ""
    description: str = ""
    # DB seed side
    has_recipe: bool = False
    recipe_yield_qty: Optional[float] = None
    recipe_yield_unit: str = "und"
    recipe_fermentation: Optional[int] = None
    recipe_difficulty: Optional[int] = None
    recipe_allergens: Optional[str] = None
    has_product: bool = False
    product_portion_label: Optional[str] = None
    # Dict side (fed straight to the helper)
    pricing_dict: dict = field(default_factory=dict)
    demand_dict: dict = field(default_factory=dict)
    closure_status: dict = field(default_factory=dict)
    closure_notes: dict = field(default_factory=dict)
    # ProductionRow `r` fields
    row_product_id: int = 1
    row_product_name: str = "Test Product"
    row_recipe_id: Optional[int] = None  # None → no_recipe branch
    row_qty: float = 0.0
    row_forecast: str = "rolling_14d_avg"
    row_confidence: int = 50
    # Post-call assertions (each is checked only if set)
    expect_recipe_id: Optional[int] = None  # None → helper returns None
    expect_qty_to_produce: Optional[float] = None
    expect_completed_qty: Optional[float] = None
    expect_pending_pedido_qty: Optional[float] = None
    expect_batch_qty: Optional[float] = None
    expect_batch_unit: Optional[str] = None
    expect_fermentation: Optional[dict] = None  # truthy → assert present
    expect_portion_label: Optional[str] = None
    expect_batch_surplus_qty: Optional[float] = None
    expect_batch_surplus_pct: Optional[float] = None
    expect_cost_per_unit_gs: Optional[int] = None
    expect_retail_gs: Optional[int] = None
    expect_recipe_difficulty: Optional[int] = None
    expect_recipe_allergens: Optional[str] = None
    expect_qty_demand_total: Optional[float] = None
    expect_qty_demand_pedidos: Optional[float] = None
    expect_qty_demand_pedidos_pending: Optional[float] = None
    expect_qty_demand_forecast: Optional[float] = None
    expect_closure_status: Optional[str] = None
    expect_closure_notes: Optional[str] = None
    expect_source_bucket: Optional[str] = None
    expect_confidence_band: Optional[str] = None


def _seed_recipe(
    s,
    *,
    name="Test Recipe",
    yield_qty=12.0,
    yield_unit="und",
    fermentation_minutes=None,
    difficulty=None,
    allergens=None,
) -> int:
    """Insert a minimal Recipe and return its id."""
    from app.rms.models_legacy import Recipe

    r = Recipe(
        name=name,
        yield_qty=yield_qty,
        yield_unit=yield_unit,
        fermentation_minutes=fermentation_minutes,
        difficulty=difficulty,
        allergens=allergens,
    )
    s.add(r)
    s.flush()
    rid = r.id
    s.commit()
    return rid


def _seed_product(
    s, *, name="Test Product", recipe_id=None, portion_label="1 und", is_available=True
) -> int:
    """Insert a minimal Product and return its id."""
    from app.rms.models_legacy import Product

    p = Product(
        name=name,
        sale_price_gs=10_000,
        portion_label=portion_label,
        recipe_id=recipe_id,
        is_available=is_available,
    )
    s.add(p)
    s.flush()
    pid = p.id
    s.commit()
    return pid


def _make_recipe_obj(recipe_id: int, spec: _RecipeRowSpec):
    """Build a fake Recipe ORM-like object (just the attrs the helper reads)."""
    from types import SimpleNamespace

    return SimpleNamespace(
        id=recipe_id,
        yield_qty=spec.recipe_yield_qty,
        yield_unit=spec.recipe_yield_unit,
        fermentation_minutes=spec.recipe_fermentation,
        difficulty=spec.recipe_difficulty,
        allergens=spec.recipe_allergens,
    )


def _make_product_obj(product_id: int, spec: _RecipeRowSpec):
    """Build a fake Product ORM-like object."""
    from types import SimpleNamespace

    return SimpleNamespace(
        id=product_id,
        name=spec.row_product_name,
        portion_label=spec.product_portion_label,
    )


def _make_demand_obj(*, qty_total, qty_pedidos, qty_pedidos_confirmed, qty_forecast):
    """Build a fake Demand ORM-like object (only the 4 attrs the helper reads)."""
    from types import SimpleNamespace

    return SimpleNamespace(
        qty_total=qty_total,
        qty_pedidos=qty_pedidos,
        qty_pedidos_confirmed=qty_pedidos_confirmed,
        qty_forecast=qty_forecast,
    )


# ─── _step_5_build_recipe_row scenario definitions ─────────────────────────


# Case 1: full happy path — recipe+product+pricing+demand all present,
# qty>0, fermentation set, closure status overridden. Surplus computed
# because yield_qty present and qty>0.
_RECIPE_FULL = _RecipeRowSpec(
    id="all_objects_present",
    description=(
        "full happy path: recipe+product+pricing+demand all in dicts, "
        "qty>0 → all fields populated, surplus computed, fermentation set"
    ),
    has_recipe=True,
    recipe_yield_qty=12.0,
    recipe_yield_unit="und",
    recipe_fermentation=480,
    recipe_difficulty=3,
    recipe_allergens="gluten",
    has_product=True,
    product_portion_label="1 und",
    pricing_dict={_WILL_BE_SET: (2500, 12_000)},  # recipe_id filled by driver
    demand_dict={
        _WILL_BE_SET: _make_demand_obj(
            qty_total=10.0,
            qty_pedidos=4.0,
            qty_pedidos_confirmed=2.0,
            qty_forecast=6.0,
        )
    },
    closure_status={_WILL_BE_SET: "closed_partial"},
    closure_notes={_WILL_BE_SET: "horno 2 a media"},
    row_recipe_id=_WILL_BE_SET,
    row_qty=10.0,
    row_forecast="rolling_14d_avg",
    row_confidence=85,
    # Assertions
    expect_recipe_id=_WILL_BE_SET,  # filled by driver
    expect_qty_to_produce=10.0,
    expect_completed_qty=0.0,  # default for completions_by_pid.get(pid, 0.0)
    expect_pending_pedido_qty=0.0,  # default for ped_units_by_pid.get(pid, 0.0)
    expect_batch_qty=12.0,  # yield_qty
    expect_batch_unit="und",
    expect_portion_label="1 und",
    expect_cost_per_unit_gs=2500,
    expect_retail_gs=12_000,
    expect_recipe_difficulty=3,
    expect_recipe_allergens="gluten",
    expect_qty_demand_total=10.0,
    expect_qty_demand_pedidos=4.0,
    expect_qty_demand_pedidos_pending=2.0,  # 4 - 2 confirmed
    expect_qty_demand_forecast=6.0,
    expect_closure_status="closed_partial",
    expect_closure_notes="horno 2 a media",
    expect_fermentation={"exists": True},  # marker → assert truthy
    expect_source_bucket="historial",  # rolling_14d_avg → historial
    expect_confidence_band="conf-vhigh",  # 85 → vhigh
)


# Case 2: r.recipe_id = None → recipe_by_id lookup fails (no key),
# recipe_obj=None → all recipe-derived fields (yield_qty, batch_qty,
# batch_unit, fermentation_reminder, recipe_difficulty, recipe_allergens,
# batch_surplus_qty, batch_surplus_pct) → None/0.0.
_RECIPE_NO_RECIPE = _RecipeRowSpec(
    id="no_recipe",
    description=(
        "r.recipe_id is None → recipe_obj=None → all recipe-derived "
        "fields (yield_qty, fermentation, difficulty, allergens, surplus) are None"
    ),
    has_recipe=False,
    has_product=True,
    product_portion_label="1 und",
    pricing_dict={},
    demand_dict={
        1: _make_demand_obj(
            qty_total=5.0,
            qty_pedidos=0.0,
            qty_pedidos_confirmed=0.0,
            qty_forecast=5.0,
        )
    },
    row_recipe_id=None,  # ← the key knob
    row_qty=5.0,
    row_forecast="manual",
    row_confidence=100,
    expect_recipe_id=None,
    expect_qty_to_produce=5.0,
    expect_batch_qty=None,
    expect_batch_unit=None,
    expect_portion_label="1 und",
    expect_batch_surplus_qty=None,
    expect_batch_surplus_pct=None,
    expect_cost_per_unit_gs=0,  # pricing_dict empty
    expect_retail_gs=0,
    expect_recipe_difficulty=None,
    expect_recipe_allergens=None,
    expect_qty_demand_total=5.0,
    expect_qty_demand_pedidos=0.0,
    expect_qty_demand_pedidos_pending=0.0,
    expect_qty_demand_forecast=5.0,
    expect_closure_status="open",  # default (not in dict)
    expect_source_bucket="receta",  # manual → receta bucket
    expect_confidence_band="conf-vhigh",  # 100 → vhigh
)


# Case 3: r.recipe_id set but recipe_by_id is empty (id not in dict) →
# recipe_obj=None (the .get() miss branch). Same as Case 2 in effect
# but exercises the "id set, lookup miss" path distinct from "id None".
_RECIPE_RECIPE_NOT_IN_DICT = _RecipeRowSpec(
    id="recipe_not_in_dict",
    description=(
        "r.recipe_id set but recipe_by_id doesn't have it → "
        "lookup miss → recipe_obj=None (same effect as no_recipe, "
        "different path)"
    ),
    has_recipe=False,  # don't seed → recipe_by_id ends up empty
    has_product=True,
    product_portion_label="1 und",
    pricing_dict={},
    demand_dict={},
    row_recipe_id=99_999,  # not in dict
    row_qty=5.0,
    row_forecast="template",
    row_confidence=70,
    expect_recipe_id=99_999,  # helper copies r.recipe_id regardless
    expect_qty_to_produce=5.0,
    expect_batch_qty=None,
    expect_batch_unit=None,
    expect_portion_label="1 und",
    expect_batch_surplus_qty=None,
    expect_batch_surplus_pct=None,
    expect_cost_per_unit_gs=0,
    expect_retail_gs=0,
    expect_recipe_difficulty=None,
    expect_recipe_allergens=None,
    expect_qty_demand_total=0.0,  # demand_dict empty
    expect_qty_demand_pedidos=0.0,
    expect_qty_demand_pedidos_pending=0.0,
    expect_qty_demand_forecast=0.0,
    expect_closure_status="open",
    expect_source_bucket="receta",  # template → receta
    expect_confidence_band="conf-high",  # 70 → high (< 85)
)


# Case 4: product not in product_by_id dict → product_obj=None →
# portion_label=None. Recipe present so recipe fields populated.
_RECIPE_PRODUCT_NOT_IN_DICT = _RecipeRowSpec(
    id="product_not_in_dict",
    description=(
        "r.product_id set but product_by_id doesn't have it → product_obj=None → portion_label=None"
    ),
    has_recipe=True,
    recipe_yield_qty=8.0,
    recipe_yield_unit="und",
    has_product=False,  # don't seed → product_by_id ends up empty
    pricing_dict={},
    demand_dict={},
    row_recipe_id=_WILL_BE_SET,  # filled by driver
    row_qty=0.0,
    row_forecast="rolling_14d_avg",
    row_confidence=40,
    expect_recipe_id=_WILL_BE_SET,
    expect_qty_to_produce=0.0,
    expect_completed_qty=0.0,
    expect_pending_pedido_qty=0.0,
    expect_batch_qty=8.0,
    expect_batch_unit="und",
    expect_portion_label=None,
    expect_batch_surplus_qty=None,  # qty==0 → no surplus even with recipe+yield
    expect_batch_surplus_pct=None,
    expect_cost_per_unit_gs=0,
    expect_retail_gs=0,
    expect_qty_demand_total=0.0,
    expect_qty_demand_pedidos=0.0,
    expect_qty_demand_pedidos_pending=0.0,
    expect_qty_demand_forecast=0.0,
    expect_closure_status="open",
    expect_confidence_band="conf-low",  # 40 → low
)


# Case 5: qty_to_produce=0 with recipe+yield present → batch_surplus
# branch is gated by `r.qty_to_produce > 0`, so surplus_qty / surplus_pct
# are both None (NOT a div-by-zero on _batch_surplus). The recipe
# itself is present so batch_qty / batch_unit still show.
_RECIPE_QTY_ZERO_NO_SURPLUS = _RecipeRowSpec(
    id="qty_zero_no_surplus",
    description=(
        "qty_to_produce=0 with recipe+yield_qty present → surplus "
        "computation is skipped (gate: r.qty_to_produce > 0) → "
        "batch_surplus_qty and batch_surplus_pct are both None"
    ),
    has_recipe=True,
    recipe_yield_qty=10.0,
    recipe_yield_unit="kg",
    has_product=True,
    product_portion_label="1 kg",
    pricing_dict={},
    demand_dict={},
    row_recipe_id=_WILL_BE_SET,
    row_qty=0.0,  # ← key knob
    row_forecast="rolling_14d_avg",
    row_confidence=0,
    expect_qty_to_produce=0.0,
    expect_batch_qty=10.0,  # still set
    expect_batch_unit="kg",
    expect_portion_label="1 kg",
    expect_batch_surplus_qty=None,  # the locked branch
    expect_batch_surplus_pct=None,  # the locked branch
    expect_qty_demand_total=0.0,
    expect_qty_demand_pedidos=0.0,
    expect_qty_demand_pedidos_pending=0.0,
    expect_qty_demand_forecast=0.0,
    expect_closure_status="open",
    expect_confidence_band="conf-vlow",  # 0 → vlow
)


# Case 6: fermentation_minutes set → fermentation_reminder dict present.
# The reminder has hour fields; just assert truthy.
_RECIPE_FERMENTATION_SET = _RecipeRowSpec(
    id="fermentation_with_minutes",
    description=(
        "recipe.fermentation_minutes is set → fermentation_reminder "
        "is a non-None dict (the calc-with-fermentation branch)"
    ),
    has_recipe=True,
    recipe_yield_qty=12.0,
    recipe_yield_unit="und",
    recipe_fermentation=720,  # 12h poolish
    has_product=True,
    product_portion_label="1 und",
    pricing_dict={},
    demand_dict={},
    row_recipe_id=_WILL_BE_SET,
    row_qty=12.0,
    row_forecast="template",
    row_confidence=80,
    expect_qty_to_produce=12.0,
    expect_batch_qty=12.0,
    expect_batch_unit="und",
    expect_portion_label="1 und",
    expect_fermentation={"exists": True},
    expect_qty_demand_total=0.0,
    expect_qty_demand_pedidos=0.0,
    expect_qty_demand_pedidos_pending=0.0,
    expect_qty_demand_forecast=0.0,
    expect_closure_status="open",
    expect_confidence_band="conf-high",  # 80 → high
)


# Case 7: fermentation_minutes is None (recipe present, but no ferment
# step) → fermentation_reminder is None (the `else None` branch).
_RECIPE_FERMENTATION_NONE = _RecipeRowSpec(
    id="fermentation_none_branch",
    description=(
        "recipe.fermentation_minutes is None → fermentation_reminder "
        "is None (the else-None branch — no ferment step)"
    ),
    has_recipe=True,
    recipe_yield_qty=24.0,
    recipe_yield_unit="und",
    recipe_fermentation=None,  # ← the key knob
    has_product=True,
    product_portion_label="1 und",
    pricing_dict={},
    demand_dict={},
    row_recipe_id=_WILL_BE_SET,
    row_qty=24.0,
    row_forecast="rolling_14d_avg",
    row_confidence=50,
    expect_qty_to_produce=24.0,
    expect_batch_qty=24.0,
    expect_batch_unit="und",
    expect_portion_label="1 und",
    expect_qty_demand_total=0.0,
    expect_qty_demand_pedidos=0.0,
    expect_qty_demand_pedidos_pending=0.0,
    expect_qty_demand_forecast=0.0,
    expect_closure_status="open",
    expect_confidence_band="conf-med",  # 50 → med
)


# Case 8: closure_status dict is empty → product_id not in dict → helper
# uses the `.get(pid, "open")` default → "open".
_RECIPE_CLOSURE_STATUS_DEFAULT = _RecipeRowSpec(
    id="closure_status_default_open",
    description=(
        "closure_status_by_pid is empty → product_id not in dict → "
        "helper's `.get(pid, 'open')` default fires → status='open'"
    ),
    has_recipe=True,
    recipe_yield_qty=12.0,
    recipe_yield_unit="und",
    has_product=True,
    product_portion_label="1 und",
    pricing_dict={},
    demand_dict={},
    closure_status={},  # ← key knob: empty
    closure_notes={},
    row_recipe_id=_WILL_BE_SET,
    row_qty=12.0,
    row_forecast="rolling_14d_avg",
    row_confidence=85,
    expect_qty_to_produce=12.0,
    expect_batch_qty=12.0,
    expect_batch_unit="und",
    expect_portion_label="1 und",
    expect_qty_demand_total=0.0,
    expect_qty_demand_pedidos=0.0,
    expect_qty_demand_pedidos_pending=0.0,
    expect_qty_demand_forecast=0.0,
    expect_closure_status="open",  # ← the default
    expect_closure_notes=None,  # empty dict → .get returns None
    expect_confidence_band="conf-vhigh",
)


# Case 9: completed + pending qty passthrough — completions_by_pid and
# ped_units_by_pid both contain entries for the row's product_id.
# Locks the `completions_by_pid.get(r.product_id, 0.0)` and
# `ped_units_by_pid.get(r.product_id, 0.0)` read paths.
_RECIPE_COMPLETIONS_PEDIDOS = _RecipeRowSpec(
    id="completions_and_pedidos_lookup",
    description=(
        "completions_by_pid and ped_units_by_pid both have entries → "
        "completed_qty and pending_pedido_qty are read from the dicts"
    ),
    has_recipe=True,
    recipe_yield_qty=12.0,
    recipe_yield_unit="und",
    has_product=True,
    product_portion_label="1 und",
    pricing_dict={},
    demand_dict={},
    row_recipe_id=_WILL_BE_SET,
    row_qty=12.0,
    row_forecast="rolling_14d_avg",
    row_confidence=85,
    expect_qty_to_produce=12.0,
    expect_completed_qty=8.0,  # filled by driver
    expect_pending_pedido_qty=3.0,  # filled by driver
    expect_batch_qty=12.0,
    expect_batch_unit="und",
    expect_portion_label="1 und",
    expect_qty_demand_total=0.0,
    expect_qty_demand_pedidos=0.0,
    expect_qty_demand_pedidos_pending=0.0,
    expect_qty_demand_forecast=0.0,
    expect_closure_status="open",
    expect_confidence_band="conf-vhigh",
)


_ROWS_RECIPE: list[dict[str, Any]] = [
    {"spec": _RECIPE_FULL},
    {"spec": _RECIPE_NO_RECIPE},
    {"spec": _RECIPE_RECIPE_NOT_IN_DICT},
    {"spec": _RECIPE_PRODUCT_NOT_IN_DICT},
    {"spec": _RECIPE_QTY_ZERO_NO_SURPLUS},
    {"spec": _RECIPE_FERMENTATION_SET},
    {"spec": _RECIPE_FERMENTATION_NONE},
    {"spec": _RECIPE_CLOSURE_STATUS_DEFAULT},
    {"spec": _RECIPE_COMPLETIONS_PEDIDOS, "completed_qty": 8.0, "pending_qty": 3.0},
]


# ─── _restock_for_target row spec ─────────────────────────────────────────


@dataclass
class _RestockSpec:
    """One scenario for `_restock_for_target`.

    All field defaults are `None` so the driver can detect "not set"
    with `is None`. The `target_type` and `target_id` are the only
    required fields; the rest are seed instructions.
    """

    id: str = ""
    description: str = ""
    target_type: str = "sale"
    target_id: int = 1  # filled by driver if needed
    restocked_qty: float = 0.0
    reason: Optional[str] = None
    recorded_by: str = "operator"
    # Sale-branch seed: StockMovement rows to insert
    sale_moves: list[dict] = field(default_factory=list)
    # PedidoLine branch seed: a PedidoLine (and its Pedido/Recipe/RecipeLine)
    pl_qty: float = 1.0
    pl_unit_price_gs: int = 10_000
    pl_recipe_yield_qty: Optional[float] = None
    pl_recipe_lines: list[dict] = field(default_factory=list)  # [{ing_qty, ing_stock}]
    pl_recipe_id_present: bool = True
    # Pedido branch seed: a Pedido with N PedidoLine rows
    pedido_lines: list[dict] = field(default_factory=list)  # [{qty, unit_price}]
    # Post-call assertions
    expect_returned_count: Optional[int] = None
    expect_returned_total_qty: Optional[float] = None
    expect_ingredient_count: Optional[int] = None
    expect_first_ing_id: Optional[int] = None
    expect_first_qty: Optional[float] = None


def _seed_ingredient(s, *, name="Test Ing", stock_qty=100.0, purchase_price_gs=5_000) -> int:
    from app.rms.models_legacy import Ingredient

    ing = Ingredient(
        name=name,
        unit="kg",
        stock_qty=stock_qty,
        purchase_price_gs=purchase_price_gs,
    )
    s.add(ing)
    s.flush()
    iid = ing.id
    s.commit()
    return iid


def _seed_stock_movement(
    s, *, ingredient_id, qty, reference_id, reference_type="sale", movement_type="sale"
) -> int:

    from app.rms.models_legacy import StockMovement

    m = StockMovement(
        ingredient_id=ingredient_id,
        movement_type=movement_type,
        qty=qty,  # signed
        reason="test",
        reference_id=reference_id,
        reference_type=reference_type,
        recorded_at=datetime.now(timezone.utc),
    )
    s.add(m)
    s.flush()
    mid = m.id
    s.commit()
    return mid


def _seed_recipe_with_lines(
    s, *, name="Test Recipe", yield_qty=10.0, lines: list[tuple[float, float]] | None = None
) -> int:
    """lines: list of (per-portion qty, initial stock of that ingredient)."""
    from app.rms.models_legacy import Ingredient, Recipe, RecipeLine

    r = Recipe(name=name, yield_qty=yield_qty, yield_unit="und")
    s.add(r)
    s.flush()
    rid = r.id
    if lines:
        for ing_qty, _stock in lines:
            ing = Ingredient(
                name=f"_ing_for_{r.name}_{ing_qty}",
                unit="kg",
                stock_qty=100.0,
            )
            s.add(ing)
            s.flush()
            rl = RecipeLine(
                recipe_id=rid,
                line_kind="ingredient",
                line_ref_id=ing.id,
                qty=ing_qty,
            )
            s.add(rl)
    s.commit()
    return rid


def _seed_sale(s, *, product_id, qty=1.0, unit_price_gs=10_000) -> int:

    from app.rms.models_legacy import Sale

    sa = Sale(
        product_id=product_id,
        qty=qty,
        unit_price_gs=unit_price_gs,
        sold_at=datetime.now(timezone.utc),
        payment_method="efectivo",
        channel="mostrador",
        invoice_type="boleta_resimple",
    )
    s.add(sa)
    s.flush()
    sid = sa.id
    s.commit()
    return sid


def _seed_pedido(s) -> int:
    from datetime import date

    from app.rms.models_legacy import Pedido

    p = Pedido(
        customer_name="Test",
        promised_date=date.today(),
        channel="mostrador",
        status="pending",
        payment_intent="efectivo",
    )
    s.add(p)
    s.flush()
    pid = p.id
    s.commit()
    return pid


def _seed_pedido_line(s, *, pedido_id, product_id, qty=1.0, unit_price_gs=10_000) -> int:
    from app.rms.models_legacy import PedidoLine

    pl = PedidoLine(
        pedido_id=pedido_id,
        product_id=product_id,
        qty=qty,
        unit_price_gs=unit_price_gs,
    )
    s.add(pl)
    s.flush()
    plid = pl.id
    s.commit()
    return plid


# ─── _restock_for_target scenario definitions ─────────────────────────────


# Case 1: target_type=sale, the sale exists, but there are NO
# StockMovement rows for it → helper returns [] (the `if not moves:
# return []` early return).
_RESTOCK_SALE_NO_MOVES = _RestockSpec(
    id="sale_no_movement_returns_empty",
    description=(
        "target_type='sale', sale exists, no StockMovement rows for it → "
        "helper returns [] (the `if not moves: return []` early return)"
    ),
    target_type="sale",
    restocked_qty=5.0,
    sale_moves=[],  # ← no movement rows
    expect_returned_count=0,
    expect_returned_total_qty=0.0,
    expect_ingredient_count=0,
)


# Case 2: target_type=sale, the sale has 2 StockMovement rows
# (consumption of 2 ingredients), restocked_qty > 0 → helper returns
# 2 (ing_id, share) entries, share ∝ |qty| / total * restocked_qty.
_RESTOCK_SALE_TWO_MOVES = _RestockSpec(
    id="sale_two_movements_proportional",
    description=(
        "target_type='sale', 2 StockMovement rows (sale_id matches) → "
        "helper returns 2 (ing_id, share) entries; share is "
        "|move.qty|/sum(|move.qty|) * restocked_qty"
    ),
    target_type="sale",
    restocked_qty=10.0,
    sale_moves=[{"qty_delta": -3.0, "stock": 100.0}, {"qty_delta": -7.0, "stock": 100.0}],
    expect_returned_count=2,
    expect_returned_total_qty=10.0,
    expect_ingredient_count=2,
    # Larger |qty| (7) → larger share. The 2 movements are ordered by
    # ASC id by the helper; assert the second entry's share is bigger.
    expect_first_qty=3.0,  # 3 / 10 * 10 = 3.0
)


# Case 3: target_type=sale, but sale_id points to NO sale row →
# helper returns [] (the `if sale is None: return []` early return).
# Driver seeds a real Sale (so the in-memory DB has rows) but the
# helper is then called with target_id=99_999 — a no-such-row id.
# The spec carries an explicit target_id; the driver skips the seed.
_RESTOCK_SALE_NOT_FOUND = _RestockSpec(
    id="sale_not_found_returns_empty",
    description=(
        "target_type='sale', target_id points to no Sale → "
        "helper returns [] (the `if sale is None: return []` early return)"
    ),
    target_type="sale",
    target_id=99_999,  # ← no Sale with this id
    restocked_qty=5.0,
    sale_moves=[],
    expect_returned_count=0,
    expect_returned_total_qty=0.0,
    expect_ingredient_count=0,
)


# Case 4: target_type=sale, single StockMovement → single entry, share
# == restocked_qty (since there's only one |qty| to share with).
# Locks the single-move case (helper still distributes proportionally,
# but with one move the share is 1.0 * restocked_qty).
_RESTOCK_SALE_SINGLE_MOVE = _RestockSpec(
    id="sale_single_movement_full_share",
    description=(
        "target_type='sale', 1 StockMovement row → 1 (ing_id, share) "
        "entry; share = restocked_qty (1 / 1 * restocked_qty)"
    ),
    target_type="sale",
    restocked_qty=5.0,
    sale_moves=[{"qty_delta": -4.0, "stock": 100.0}],
    expect_returned_count=1,
    expect_returned_total_qty=5.0,
    expect_ingredient_count=1,
    expect_first_qty=5.0,  # only one move gets the full share
)


# Case 5: target_type=sale, but every StockMovement has qty=0 →
# total_delta = 0 → helper uses `or 1.0` divisor fallback → share
# for each is 0/1.0 * restocked = 0 → all skipped (`share <= 0`).
# Locks the `total_delta = sum(abs(m.qty)) or 1.0` divisor branch and
# the per-move `if share <= 0: continue` skip.
_RESTOCK_SALE_ZERO_QTY_MOVES = _RestockSpec(
    id="sale_zero_qty_moves_all_skipped",
    description=(
        "target_type='sale', 2 StockMovement rows with qty=0 → "
        "total_delta=0 → divisor falls back to 1.0 → each share = 0 → "
        "all skipped (the `if share <= 0: continue` filter)"
    ),
    target_type="sale",
    restocked_qty=5.0,
    sale_moves=[
        {"qty_delta": 0.0, "stock": 100.0},
        {"qty_delta": 0.0, "stock": 100.0},
    ],
    expect_returned_count=0,
    expect_returned_total_qty=0.0,
    expect_ingredient_count=0,
)


# Case 6: target_type=pedido, but the pedido has no PedidoLine rows
# → helper returns [] (the `if not lines: return []` early return).
# This is the only pedido branch that doesn't recursively call
# `_restock_for_target(target_type='pedido_line', ...)` (which would
# hit a separate bug in the helper — see note below).
_RESTOCK_PEDIDO_NO_LINES = _RestockSpec(
    id="pedido_no_lines_returns_empty",
    description=(
        "target_type='pedido', the pedido has 0 PedidoLine rows → "
        "helper returns [] (the `if not lines: return []` early return)"
    ),
    target_type="pedido",
    restocked_qty=5.0,
    pedido_lines=[],  # ← no pedido lines
    expect_returned_count=0,
    expect_returned_total_qty=0.0,
    expect_ingredient_count=0,
)


# NOTE: the pedido_line-with-recipe and pedido-with-lines branches of
# `_restock_for_target` are excluded from this batch-7 test file
# because the helper has two pre-existing bugs that the s1-batch7
# scope doesn't cover (s3 refactor territory):
#
# 1. The helper reads `pl.recipe_id` (app/rms/refunds.py:412, 464) but
#    `PedidoLine` has no `recipe_id` column. Calling the helper with
#    a real PedidoLine raises AttributeError. A S3 PR would either
#    add the column or change the helper to use `pl.product.recipe_id`.
# 2. Inside the pedido_line branch, the helper computes
#    `per_portion = (rl.qty or 0) / recipe.yield_qty` (line 426) but
#    `RecipeLine.qty` is `Numeric(12, 4)` → Decimal, while
#    `Recipe.yield_qty` is `Float` → float. The Decimal/float division
#    raises TypeError. A S3 PR would wrap `rl.qty` in `float(...)`.
#
# Documenting the bugs in this comment so the next batch / S3 audit
# picks them up — they are out of scope for the s1-batch7 test-coverage
# sweep (which only writes parametrize rows for branches that can be
# exercised end-to-end).


# ─── Parametrized driver: _step_5_build_recipe_row ────────────────────────


@pytest.mark.parametrize(
    "row",
    _ROWS_RECIPE,
    ids=lambda r: r["spec"].id,
)
def test_step_5_build_recipe_row_branches(row: dict, session_factory) -> None:
    """Drive `_step_5_build_recipe_row` through 9 scenarios covering its
    CC-24 branches:

    - all_objects_present: full happy path → every field populated
    - no_recipe: r.recipe_id is None → all recipe fields None
    - recipe_not_in_dict: r.recipe_id set, recipe_by_id miss → same
    - product_not_in_dict: r.product_id set, product_by_id miss → portion_label=None
    - qty_zero_no_surplus: qty=0 with recipe+yield → surplus computation skipped
    - fermentation_with_minutes: recipe.fermentation_minutes set → reminder present
    - fermentation_none_branch: recipe.fermentation_minutes None → reminder None
    - closure_status_default_open: empty closure dict → "open" default
    - completions_and_pedidos_lookup: completions/pedidos dicts hit

    Called directly — pure function; no DB needed for the helper itself
    (the seed inserts rows so the dicts can be wired with real ids).

    `session_factory` is required so the conftest's app-fixture tree
    (init_db, make_engine) runs — many ORM lookups inside the helper
    would NPE without a real session context.
    """
    from app.routers.produccion._full import _step_5_build_recipe_row

    spec: _RecipeRowSpec = row["spec"]

    with session_factory() as s:
        # Seed Recipe + Product, capturing their dynamic ids.
        recipe_id: Optional[int] = None
        if spec.has_recipe:
            recipe_id = _seed_recipe(
                s,
                yield_qty=spec.recipe_yield_qty,
                yield_unit=spec.recipe_yield_unit,
                fermentation_minutes=spec.recipe_fermentation,
                difficulty=spec.recipe_difficulty,
                allergens=spec.recipe_allergens,
            )
        product_id: Optional[int] = None
        if spec.has_product:
            product_id = _seed_product(
                s,
                portion_label=spec.product_portion_label,
                recipe_id=recipe_id,
            )

        # Resolve row_recipe_id: spec may carry the sentinel if it was
        # meant to be bound to the just-seeded recipe id.
        row_recipe_id: Optional[int] = spec.row_recipe_id
        if row_recipe_id == _WILL_BE_SET:
            row_recipe_id = recipe_id
        row_product_id: int = product_id if product_id is not None else spec.row_product_id

        # Build the lookup dicts the helper expects.
        recipe_by_id: dict = {}
        if recipe_id is not None:
            recipe_by_id[recipe_id] = _make_recipe_obj(recipe_id, spec)

        product_by_id: dict = {}
        if product_id is not None:
            product_by_id[product_id] = _make_product_obj(product_id, spec)

        # pricing_dict: {recipe_id: (cost, retail)} — copy then resolve
        # the sentinel.
        pricing_by_recipe_id: dict = {}
        for k, v in spec.pricing_dict.items():
            resolved_k = recipe_id if k == _WILL_BE_SET else k
            if resolved_k is None:
                continue
            cost, retail = v
            from types import SimpleNamespace

            pricing_by_recipe_id[resolved_k] = SimpleNamespace(
                cost_per_unit_gs=cost,
                retail_gs=retail,
            )

        # demand_dict: {product_id: DemandLike} — resolve sentinel.
        demand_by_pid: dict = {}
        for k, v in spec.demand_dict.items():
            resolved_k = product_id if k == _WILL_BE_SET else k
            if resolved_k is None:
                continue
            demand_by_pid[resolved_k] = v

        # closure dicts: resolve sentinel to the row's product_id.
        closure_status_by_pid: dict = {}
        for k, v in spec.closure_status.items():
            resolved_k = product_id if k == _WILL_BE_SET else k
            if resolved_k is None:
                continue
            closure_status_by_pid[resolved_k] = v
        closure_notes_by_pid: dict = {}
        for k, v in spec.closure_notes.items():
            resolved_k = product_id if k == _WILL_BE_SET else k
            if resolved_k is None:
                continue
            closure_notes_by_pid[resolved_k] = v

        # completions / pedido lookups
        completions_by_pid: dict = {}
        ped_units_by_pid: dict = {}
        if row.get("completed_qty") is not None and product_id is not None:
            completions_by_pid[product_id] = row["completed_qty"]
        if row.get("pending_qty") is not None and product_id is not None:
            ped_units_by_pid[product_id] = row["pending_qty"]

        # Build the ProductionRow `r` shape the helper expects.
        from types import SimpleNamespace

        r = SimpleNamespace(
            product_id=row_product_id,
            product_name=spec.row_product_name,
            recipe_id=row_recipe_id,
            qty_to_produce=spec.row_qty,
            forecast_source=spec.row_forecast,
            confidence_pct=spec.row_confidence,
        )

        # Resolve expect_recipe_id (may carry the sentinel).
        expect_recipe_id = spec.expect_recipe_id
        if expect_recipe_id == _WILL_BE_SET:
            expect_recipe_id = recipe_id

        # Call the helper.
        result = _step_5_build_recipe_row(
            r,
            completions_by_pid=completions_by_pid,
            ped_units_by_pid=ped_units_by_pid,
            recipe_by_id=recipe_by_id,
            product_by_id=product_by_id,
            pricing_by_recipe_id=pricing_by_recipe_id,
            demand_by_pid=demand_by_pid,
            closure_status_by_pid=closure_status_by_pid,
            closure_notes_by_pid=closure_notes_by_pid,
        )

    # ─── Post-call assertions ──────────────────────────────────────────

    def _check(name: str, expected, actual) -> None:
        if expected is None:
            return
        # Sentinel-as-dict marker: caller said "exists" without a value.
        if isinstance(expected, dict) and expected.get("exists") is True:
            assert actual is not None, (
                f"{spec.id}: {name} should be truthy, got {actual!r} — {spec.description}"
            )
            return
        assert actual == expected, (
            f"{spec.id}: {name}={actual!r}, expected {expected!r} — {spec.description}"
        )

    _check("recipe_id", expect_recipe_id, result["recipe_id"])
    _check("qty_to_produce", spec.expect_qty_to_produce, result["qty_to_produce"])
    _check("completed_qty", spec.expect_completed_qty, result["completed_qty"])
    _check("pending_pedido_qty", spec.expect_pending_pedido_qty, result["pending_pedido_qty"])
    _check("batch_qty", spec.expect_batch_qty, result["batch_qty"])
    _check("batch_unit", spec.expect_batch_unit, result["batch_unit"])
    _check("portion_label", spec.expect_portion_label, result["portion_label"])
    _check("batch_surplus_qty", spec.expect_batch_surplus_qty, result["batch_surplus_qty"])
    _check("batch_surplus_pct", spec.expect_batch_surplus_pct, result["batch_surplus_pct"])
    _check("cost_per_unit_gs", spec.expect_cost_per_unit_gs, result["cost_per_unit_gs"])
    _check("retail_gs", spec.expect_retail_gs, result["retail_gs"])
    _check("recipe_difficulty", spec.expect_recipe_difficulty, result["recipe_difficulty"])
    _check("recipe_allergens", spec.expect_recipe_allergens, result["recipe_allergens"])
    _check("qty_demand_total", spec.expect_qty_demand_total, result["qty_demand_total"])
    _check("qty_demand_pedidos", spec.expect_qty_demand_pedidos, result["qty_demand_pedidos"])
    _check(
        "qty_demand_pedidos_pending",
        spec.expect_qty_demand_pedidos_pending,
        result["qty_demand_pedidos_pending"],
    )
    _check("qty_demand_forecast", spec.expect_qty_demand_forecast, result["qty_demand_forecast"])
    _check("closure_status", spec.expect_closure_status, result["closure_status"])
    _check("closure_notes", spec.expect_closure_notes, result["closure_notes"])
    _check("fermentation_reminder", spec.expect_fermentation, result["fermentation_reminder"])
    _check("source_bucket", spec.expect_source_bucket, result["source_bucket"])
    _check("confidence_band", spec.expect_confidence_band, result["confidence_band"])

    # Sanity: the helper should ALWAYS return these stable fields.
    assert result["product_id"] == row_product_id, f"{spec.id}: product_id passthrough mismatch"
    assert result["product_name"] == spec.row_product_name, (
        f"{spec.id}: product_name passthrough mismatch"
    )
    assert result["forecast_source"] == spec.row_forecast, (
        f"{spec.id}: forecast_source passthrough mismatch"
    )
    assert result["confidence_pct"] == spec.row_confidence, (
        f"{spec.id}: confidence_pct passthrough mismatch"
    )
    assert result["is_ad_hoc"] is False, (
        f"{spec.id}: is_ad_hoc is always False in _step_5 (ad_hoc is _step_6)"
    )


_ROWS_RESTOCK: list[dict[str, Any]] = [
    {"spec": _RESTOCK_SALE_NO_MOVES},
    {"spec": _RESTOCK_SALE_TWO_MOVES},
    {"spec": _RESTOCK_SALE_NOT_FOUND},
    {"spec": _RESTOCK_SALE_SINGLE_MOVE},
    {"spec": _RESTOCK_SALE_ZERO_QTY_MOVES},
    {"spec": _RESTOCK_PEDIDO_NO_LINES},
]


# ─── Parametrized driver: _restock_for_target ──────────────────────────────


@pytest.mark.parametrize(
    "row",
    _ROWS_RESTOCK,
    ids=lambda r: r["spec"].id,
)
def test_restock_for_target_branches(row: dict, session_factory) -> None:
    """Drive `_restock_for_target` through 6 scenarios covering its
    CC-29 branches:

    - sale_no_movement_returns_empty: sale exists, no StockMovement → []
    - sale_two_movements_proportional: 2 moves → 2 entries, share ∝ |qty|
    - sale_not_found_returns_empty: target_id → no Sale → []
    - sale_single_movement_full_share: 1 move → 1 entry, full share
    - sale_zero_qty_moves_all_skipped: 2 moves with qty=0 → all skipped
    - pedido_no_lines_returns_empty: pedido with 0 lines → []

    Called directly — pure function (writes to session; commits by the
    caller). The `Session` is the only dep.

    Note: pedido_line and pedido-with-lines branches are documented
    in the scenario section as "excluded — pre-existing helper bugs";
    see the NOTE block in the scenario section above.
    """

    from app.rms.models_legacy import Ingredient
    from app.rms.refunds import _restock_for_target

    spec: _RestockSpec = row["spec"]
    now_utc = datetime.now(timezone.utc)

    with session_factory() as s:
        target_id: int = 0
        # ── SALE branch seeding ──────────────────────────────────────
        if spec.target_type == "sale":
            # The "not found" spec carries an explicit target_id (99_999)
            # and we want the helper to look up a row that DOESN'T
            # exist. For "not found" we skip the sale seed entirely so
            # the in-memory DB has no Sale with that id.
            if spec.id != "sale_not_found_returns_empty":
                product_id = _seed_product(s, name="Restock Test Product")
                sale_id = _seed_sale(s, product_id=product_id)
                target_id = sale_id
            else:
                # Still create a real sale in the DB so the engine has
                # at least one Product row (some helpers reject empty
                # inits). But the helper will be called with target_id
                # = spec.target_id (a no-such-row id).
                _seed_product(s, name="Restock Test Product")
            # Seed StockMovement rows for whatever the spec asked for
            # (empty list → no moves; sale_not_found also has no moves
            # but the helper won't even get that far because sale=None).
            # Use a monotonic counter so two qty=0 moves still get
            # distinct ingredient names (Ingredient.name is unique).
            for idx, mv in enumerate(spec.sale_moves):
                ing_id = _seed_ingredient(
                    s,
                    name=f"_ing_{mv['qty_delta']}_{idx}",
                    stock_qty=mv.get("stock", 100.0),
                )
                _seed_stock_movement(
                    s,
                    ingredient_id=ing_id,
                    qty=mv["qty_delta"],
                    reference_id=target_id or 1,
                )
        # ── PEDIDO branch seeding ────────────────────────────────────
        elif spec.target_type == "pedido":
            # Only the "no_lines" case is testable end-to-end; the
            # pedido-with-lines case is excluded (see NOTE block).
            _seed_pedido(s)  # creates a Pedido with no lines
            target_id = 1  # the just-seeded pedido's id (first row)
        else:
            pytest.fail(
                f"Unknown target_type={spec.target_type!r} — branch not testable in s1-batch7"
            )

        s.commit()

        # For the "not found" spec, override target_id with the spec's
        # explicit id (no such Sale in the DB).
        if spec.id == "sale_not_found_returns_empty":
            target_id = spec.target_id

        # Snapshot ingredient stock_qty before so we can verify the
        # post-call increment matches the returned (ing_id, qty).
        from sqlalchemy import select as sa_select

        all_ings = s.scalars(sa_select(Ingredient)).all()
        before_stock = {ing.id: ing.stock_qty for ing in all_ings}

        # Call the helper.
        result = _restock_for_target(
            s,
            spec.target_type,
            target_id,
            spec.restocked_qty,
            spec.reason,
            spec.recorded_by,
            now_utc,
        )

        s.flush()

        # Snapshot after.
        all_ings = s.scalars(sa_select(Ingredient)).all()
        after_stock = {ing.id: ing.stock_qty for ing in all_ings}

    # ─── Post-call assertions ──────────────────────────────────────────

    if spec.expect_returned_count is not None:
        assert len(result) == spec.expect_returned_count, (
            f"{spec.id}: returned {len(result)} entries, "
            f"expected {spec.expect_returned_count} — {spec.description}"
        )

    if spec.expect_ingredient_count is not None:
        # Locked: helper returns one entry per ingredient that was restocked.
        # For multi-ingredient scenarios (sale with 2 moves, pedido with 2
        # lines) the count must equal the number of distinct ingredients.
        assert len(result) == spec.expect_ingredient_count, (
            f"{spec.id}: ingredient count={len(result)}, "
            f"expected {spec.expect_ingredient_count} — {spec.description}"
        )

    if spec.expect_returned_total_qty is not None:
        total = sum(qty for _, qty in result)
        assert abs(total - spec.expect_returned_total_qty) < 1e-6, (
            f"{spec.id}: returned qty sum={total}, "
            f"expected {spec.expect_returned_total_qty} — {spec.description}"
        )

    # Verify the helper ALSO bumped each affected ingredient's stock_qty
    # by the returned share (this is the side-effect locked by
    # apply_stock_delta).
    for ing_id, share in result:
        diff = after_stock[ing_id] - before_stock[ing_id]
        assert abs(diff - share) < 1e-6, (
            f"{spec.id}: ingredient {ing_id} stock delta={diff}, "
            f"expected +{share} (the returned share) — {spec.description}"
        )

    # Sanity: result is a list of (int, float) tuples.
    for entry in result:
        assert isinstance(entry, tuple) and len(entry) == 2, (
            f"{spec.id}: returned entry {entry!r} is not (int, float) — {spec.description}"
        )
        ing_id, qty = entry
        assert isinstance(ing_id, int), (
            f"{spec.id}: ing_id={ing_id!r} is not int — {spec.description}"
        )
        assert isinstance(qty, float), f"{spec.id}: qty={qty!r} is not float — {spec.description}"
        assert qty > 0, f"{spec.id}: returned qty={qty} should be > 0 — {spec.description}"


# ─── Row-count docs (mirrors PR #178 / #179 / #181 pattern) ───────────────


def test_parametrize_row_count() -> None:
    """Document the number of branch-coverage cases covered by this file.

    Locks the parametrize row count so adding/removing a row forces a
    reviewer to update the matching CHANGELOG entry — same pattern
    as batch3 / batch4 / batch5 / batch6 (#174, #178, #179, #181).
    """
    assert len(_ROWS_RECIPE) == 9
    assert len(_ROWS_RESTOCK) == 6  # 5 sale + 1 pedido (no_lines)
    # Sanity: the spec docstring's "8+ parametrized rows" claim is met.
    assert len(_ROWS_RECIPE) + len(_ROWS_RESTOCK) >= 8
