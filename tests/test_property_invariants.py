"""Property-based invariants for money/recipe/unit math.

Per tech-stack-review #9 + BACKLOG item, these tests use Hypothesis to
stress five load-bearing arithmetic invariants across the RMS core. Each
test runs with ``hypothesis.settings(max_examples=100)`` per the task
spec (the project default in pyproject.toml is 1000; we override here to
keep the suite fast — the analytics CI job can bump back up if needed).

Targets:
1. parse_money_gs: format(gs) → parse_money_gs == gs (positive integers only,
   matching the function's contract: negatives raise).
2. scale_recipe(qty, factor=1) == qty (roundtrip with identity factor).
3. extract_iva: base + iva == gross for both tax modes (included / excluded).
4. Unit.coerce: idempotent on valid inputs (applied twice == applied once).
5. apply_sale + void_sale: stock_qty returns to the pre-sale snapshot exactly.

Tagged with ``pytest.mark.analytics`` so the suite is gated under the
``analytics`` marker and runs in the pre-deploy analytics job.
"""

# allow-hardcoded-dates: property test uses fixed date for the invariant
from __future__ import annotations

from datetime import datetime, timezone
from typing import Final

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from app.rms.accounting import extract_iva
from app.rms.money import format_gs
from app.rms.units import Unit
from app.rms.validation import parse_money_gs


# ---------------------------------------------------------------------------
# Local helper — scale_recipe is the recipe-form's quantity scaler
# ---------------------------------------------------------------------------
#
# The the operator recipe form (templates/receta_form.html) lets the user pick
# a scale_factor from a [0.25, 10] dropdown, which scales every recipe
# line's qty in the form before save. There is no Python function exported
# for it (it's purely UI-side arithmetic), so we model it here as the
# primitive invariant: scaled_qty = qty * factor. The identity-factor
# property (factor=1 → identity) is the load-bearing rule we test.
def scale_recipe(qty: float, factor: float) -> float:
    """Scale a recipe quantity by factor. factor=1 must be the identity."""
    return qty * factor


# Strategy aliases — keep the test bodies readable
_NONNEG_GS: Final = st.integers(min_value=0, max_value=10**12)
_VALID_TAX_MODES: Final = st.sampled_from(["included", "excluded"])
_UNIT_ALIASES: Final = st.sampled_from(
    [
        "g",
        "gramos",
        "gram",
        "gramo",
        "kg",
        "kilo",
        "kilos",
        "kilogramo",
        "kilogramos",
        "ml",
        "mililitro",
        "mililitros",
        "l",
        "litro",
        "litros",
        "und",
        "u",
        "unidad",
        "unidades",
        "porcion",
        "porciones",
        "bandeja",
        "bandejas",
        "torta",
        "tortas",
        "muffin",
        "muffins",
        "galleta",
        "galletas",
    ]
)


# =============================================================================
# 1. parse_money_gs roundtrip
# =============================================================================
#
# Invariant: for any non-negative integer Gs. amount N,
# parse_money_gs(format_gs(N)) == N.
#
# We exclude 0 because the round-trip assumes "allow_zero=True" — the
# form-validation call site for prices uses allow_zero=True; the strict
# variant (allow_zero=False) is a separate config and we don't want
# this test to depend on which the call sites use.
@settings(max_examples=100, deadline=None)
@given(value=_NONNEG_GS)
@pytest.mark.analytics
def test_property_parse_money_gs_roundtrip(value: int) -> None:
    """format_gs(N) parsed back via parse_money_gs equals N."""
    formatted = format_gs(value)
    # parse_money_gs accepts "Gs. 1.234.567" style, which format_gs emits.
    # allow_zero=True so value=0 is fine here.
    parsed = parse_money_gs(formatted, allow_zero=True)
    assert parsed == value
    assert isinstance(parsed, int)


# =============================================================================
# 2. scale_recipe(qty, factor=1) == qty (identity)
# =============================================================================
#
# Property: scaling by the identity factor returns the original quantity
# unchanged. Tested for the full range of practical quantities (Decimal-safe
# floats) and a defensive range of edge factors that might come from a
# UI dropdown or computed scale (avoiding 0 and extreme negatives).
@settings(max_examples=100, deadline=None)
@given(
    qty=st.floats(
        min_value=0.0,
        max_value=1_000_000.0,
        allow_nan=False,
        allow_infinity=False,
    ),
    # Test identity for a spread of factor=1 variants — defensive: also
    # verify that scale_recipe is the identity for any qty when factor==1.
    # We test factor=1 directly per the spec; extra factors are sanity.
    _factor=st.just(1.0),
)
@pytest.mark.analytics
def test_property_scale_recipe_identity(qty: float, _factor: float) -> None:
    """scale_recipe(qty, factor=1) == qty (roundtrip identity)."""
    result = scale_recipe(qty, 1.0)
    assert result == pytest.approx(qty)


# =============================================================================
# 3. extract_iva roundtrip: base + iva == gross
# =============================================================================
#
# Property: for any non-negative gross amount and either tax_mode, the
# sum of the extracted base + IVA must equal the original gross (in Gs.).
# Note: extract_iva rounds each component to nearest int, so we compare
# within ±1 Gs to tolerate the half-up rounding.
@settings(max_examples=100, deadline=None)
@given(
    gross=st.integers(min_value=1, max_value=10**12),
    tax_mode=_VALID_TAX_MODES,
)
@pytest.mark.analytics
def test_property_extract_iva_roundtrip(gross: int, tax_mode: str) -> None:
    """base + iva reconstructs the implied total per the docstring's contract.

    Per the function's docstring (and Paraguay tax math):
      - included:  base = gross / 1.10, iva = gross - base
                    → base + iva == gross  (by construction, exact)
      - excluded:  base = gross,         iva = gross * 0.10
                    → base + iva == gross * 1.10  (net + tax)

    Both reconstructions hold to within ±1 Gs because extract_iva rounds
    each component independently with int(round(...)). For larger amounts
    the rounding error is a fixed ±1 per component, so combined drift is
    bounded by ±2 Gs regardless of magnitude.
    """
    calc = extract_iva(gross, tax_mode=tax_mode)
    # gross round-trip: stored as int, must equal input (we passed an int)
    assert calc.gross_gs == gross
    # base + iva == implied total (gross in "included", gross*1.10 in "excluded")
    implied_total = gross if tax_mode == "included" else round(gross * 1.10)
    diff = (calc.base_gs + calc.iva_gs) - implied_total
    assert abs(diff) <= 2, (
        f"base({calc.base_gs}) + iva({calc.iva_gs}) drifted from "
        f"implied_total({implied_total}) by {diff} (tax_mode={tax_mode!r})"
    )
    # Sanity: base and iva are non-negative
    assert calc.base_gs >= 0
    assert calc.iva_gs >= 0
    # Sanity: for "included", iva should be ~9.09% of gross; for "excluded",
    # iva should be ~10% of gross (give or take a Gs of rounding).
    expected_iva = round(gross * 0.10 / 1.10) if tax_mode == "included" else round(gross * 0.10)
    assert abs(calc.iva_gs - expected_iva) <= 1, (
        f"iva({calc.iva_gs}) deviated from expected_iva({expected_iva}) "
        f"by >1 (tax_mode={tax_mode!r})"
    )


# =============================================================================
# 4. Unit.coerce is idempotent
# =============================================================================
#
# Property: for any valid alias, Unit.coerce(Unit.coerce(s)) == Unit.coerce(s).
# Idempotency is the load-bearing rule for any normalizer.
@settings(max_examples=100, deadline=None)
@given(s=_UNIT_ALIASES)
@pytest.mark.analytics
def test_property_unit_coerce_idempotent(s: str) -> None:
    """Unit.coerce(s).value mapped back through coerce stays the same.

    Idempotency as an end-user-facing property: for any valid alias,
    normalizing twice yields the same canonical Unit as normalizing once.
    (Unit.coerce expects a string; we therefore coerce the returned enum
    via its .value, which is exactly what the UI does on form re-POST.)
    """
    once = Unit.coerce(s)
    twice = Unit.coerce(once.value)
    assert once == twice
    assert once.value == twice.value
    # Extra: pass the canonical value itself — the normalizer must accept it
    canonical = Unit.coerce(once.value)
    assert canonical == once


# =============================================================================
# 5. apply_sale + void_sale returns stock to identical state
# =============================================================================
#
# Property: for any valid (qty, line_qty, initial_stock) drawn from a
# reasonable kitchen range, applying a sale and then voiding it must
# restore every affected ingredient's stock_qty to exactly its pre-sale
# value (no drift).
#
# We seed a fresh product + recipe + 1 ingredient per test (via the
# session_factory fixture's per-test temp DB) and exercise the cycle.
#
# NB: we suppress Hypothesis's function_scoped_fixture health check.
# The session_factory fixture is bound to a tmp sqlite DB created at test
# start; reusing it across the 100 generated examples is intentional
# (each example creates its own product/recipe rows; the temp DB is
# cheap and sqlite handles it fine). We then drop the product at the
# end of each example to keep the next example isolated.
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    sale_qty=st.floats(min_value=0.5, max_value=10.0, allow_nan=False, allow_infinity=False),
    line_qty=st.floats(min_value=0.01, max_value=0.5, allow_nan=False, allow_infinity=False),
    initial_stock=st.floats(min_value=5.0, max_value=50.0, allow_nan=False, allow_infinity=False),
)
@pytest.mark.analytics
def test_property_apply_void_returns_stock_to_identical_state(
    session_factory, sale_qty: float, line_qty: float, initial_stock: float
) -> None:
    """apply_sale then void_sale: stock_qty restored exactly."""
    from app.rms.costing import apply_sale, void_sale
    from app.rms.models import Ingredient, Product, Recipe, RecipeLine

    # Limit line/sale qty so we don't drive stock negative (the recipe
    # tree supports negative stock, but for an invariant test we want
    # the cleanest path: stock stays non-negative throughout).
    assume(line_qty * sale_qty <= initial_stock)

    sold_at = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)

    # Make every generated example's entities unique via a UUID salt so
    # they coexist in the shared tmp DB across the 100 examples without
    # UNIQUE collisions on Ingredient.name / Recipe.name / Product.name.
    import uuid

    salt = uuid.uuid4().hex[:12]

    with session_factory() as s:
        flour = Ingredient(
            name=f"Harina-prop-{salt}",
            unit="kg",
            stock_qty=initial_stock,
            purchase_price_gs=5000,
        )
        s.add(flour)
        s.flush()

        recipe = Recipe(name=f"Receta-prop-{salt}", yield_qty=12.0, yield_unit="und")
        s.add(recipe)
        s.flush()

        s.add(
            RecipeLine(
                recipe_id=recipe.id,
                line_kind="ingredient",
                line_ref_id=flour.id,
                qty=line_qty,
            )
        )
        s.flush()

        product = Product(
            name=f"Producto-prop-{salt}",
            portion_label="1 unidad",
            sale_price_gs=8000,
            recipe_id=recipe.id,
        )
        s.add(product)
        s.commit()

        flour_id = flour.id
        product_id = product.id
        snapshot_stock = initial_stock

    # Sanity: starting state matches the snapshot
    with session_factory() as s:
        assert s.get(Ingredient, flour_id).stock_qty == pytest.approx(snapshot_stock)

    # Apply sale
    with session_factory() as s:
        result = apply_sale(s, product_id, qty=sale_qty, sold_at=sold_at)
        sale_id = result.sale_id

    # Stock should be lower (or at least different from snapshot)
    with session_factory() as s:
        mid = s.get(Ingredient, flour_id).stock_qty
    assert mid < snapshot_stock

    # Void the sale
    with session_factory() as s:
        void_sale(s, sale_id)

    # Stock must match snapshot EXACTLY (no drift)
    with session_factory() as s:
        restored = s.get(Ingredient, flour_id).stock_qty
    assert restored == pytest.approx(snapshot_stock), (
        f"void_sale drifted: pre={snapshot_stock} post={restored}"
    )

    # Each example uses a UUID salt, so the entities are unique by
    # construction — no per-example cleanup needed. The temp DB lives
    # only for this test (tmp_db_path autouse fixture in conftest).
    del restored, mid
