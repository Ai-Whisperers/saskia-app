"""tests/test_rollup_cross_unit.py — verify cross-unit rollups (bug fix 2026-10-01).

Decision A1 follow-up: ``rollup_ingredient_stock()`` had a latent bug
where ``stock_qty`` (a count of packages) was being converted as if it
were a quantity in ``package_unit``. The bug was invisible for
same-unit variants (e.g. all kg) because ``convert_qty(x, kg, kg) = x``,
but it produced wildly inflated numbers for cross-unit cases
(e.g. base=kg + variants in g). This file covers the cross-unit cases
that the original test in test_saskia_r2_data_models.py didn't.

Covers:
- Base=kg, variants in g → correct kg total
- Base=g, variants in kg → correct g total
- Base=l, variants in ml → correct l total
- Base=ml, variants in l → correct ml total
- Per-variant stock_in_base and size_in_base fields are computed right
- Mixed g + kg on the same ingredient (the real B1 use case: harina
  comes in 1kg bags and 250g packets)
- days_until_short() uses the corrected rollup (no NaN, no inflation)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.crud


def _make_ingredient(session_factory, name, unit, **kwargs):
    """Helper: create an Ingredient with the given base unit."""
    from app.rms.db import safe_commit
    from app.rms.models import Ingredient

    with session_factory() as s:
        ing = Ingredient(name=name, unit=unit, **kwargs)
        s.add(ing); s.flush()
        ing_id = ing.id
        safe_commit(s)
    return ing_id


def _add_variant(session_factory, ingredient_id, package_size, package_unit, stock_qty, **kwargs):
    from app.rms.db import safe_commit
    from app.rms.models import IngredientVariant

    with session_factory() as s:
        s.add(IngredientVariant(
            ingredient_id=ingredient_id,
            package_size=package_size,
            package_unit=package_unit,
            stock_qty=stock_qty,
            **kwargs,
        ))
        safe_commit(s)


# ---------------------------------------------------------------------------
# Cross-unit rollup: the bug-fix tests
# ---------------------------------------------------------------------------


def test_rollup_kg_base_with_g_variants(session_factory):
    """Base=kg, variants in g → correct total in kg.

    Real-world case: harina ingredient tracked in kg, but variants
    are 1kg bag (1000g) and 250g packet. The bug was inflating
    these by 1,000,000x.
    """
    from app.rms.variants import rollup_ingredient_stock

    ing_id = _make_ingredient(session_factory, "harina test", "kg")
    _add_variant(session_factory, ing_id, 1000, "g", 3, preferred=True)  # 3 × 1kg = 3 kg
    _add_variant(session_factory, ing_id, 250, "g", 12)                  # 12 × 250g = 3 kg

    with session_factory() as s:
        r = rollup_ingredient_stock(s, ing_id)

    assert r is not None
    assert r.base_unit == "kg"
    # 3 kg + 3 kg = 6 kg (the bug would have given 3,006,000 kg)
    assert abs(r.base_qty - 6.0) < 1e-9, f"expected 6.0 kg, got {r.base_qty}"


def test_rollup_g_base_with_kg_variants(session_factory):
    """Base=g, variants in kg → correct total in g.

    Inverse of the above: an ingredient tracked in grams with
    2 kg packages (2000g each).
    """
    from app.rms.variants import rollup_ingredient_stock

    ing_id = _make_ingredient(session_factory, "azúcar test", "g")
    _add_variant(session_factory, ing_id, 2.0, "kg", 5, preferred=True)  # 5 × 2kg = 10 kg = 10_000 g
    _add_variant(session_factory, ing_id, 500, "g", 4)                   # 4 × 500g = 2000 g

    with session_factory() as s:
        r = rollup_ingredient_stock(s, ing_id)

    assert r is not None
    assert r.base_unit == "g"
    # 10_000 g + 2_000 g = 12_000 g (the bug would have given 12_004_000_000 g)
    assert abs(r.base_qty - 12_000.0) < 1e-6, f"expected 12000 g, got {r.base_qty}"


def test_rollup_l_base_with_ml_variants(session_factory):
    """Base=l, variants in ml → correct total in l."""
    from app.rms.variants import rollup_ingredient_stock

    ing_id = _make_ingredient(session_factory, "leche test", "l")
    _add_variant(session_factory, ing_id, 1000, "ml", 4, preferred=True)  # 4 × 1l = 4 l
    _add_variant(session_factory, ing_id, 250, "ml", 8)                    # 8 × 250ml = 2 l

    with session_factory() as s:
        r = rollup_ingredient_stock(s, ing_id)

    assert r is not None
    assert r.base_unit == "l"
    assert abs(r.base_qty - 6.0) < 1e-9, f"expected 6.0 l, got {r.base_qty}"


def test_rollup_ml_base_with_l_variants(session_factory):
    """Base=ml, variants in l → correct total in ml."""
    from app.rms.variants import rollup_ingredient_stock

    ing_id = _make_ingredient(session_factory, "aceite test", "ml")
    _add_variant(session_factory, ing_id, 1.5, "l", 3, preferred=True)  # 3 × 1.5l = 4.5l = 4500 ml
    _add_variant(session_factory, ing_id, 500, "ml", 2)                 # 2 × 500ml = 1000 ml

    with session_factory() as s:
        r = rollup_ingredient_stock(s, ing_id)

    assert r is not None
    assert r.base_unit == "ml"
    assert abs(r.base_qty - 5500.0) < 1e-6, f"expected 5500 ml, got {r.base_qty}"


def test_rollup_mixed_g_and_kg_harina_use_case(session_factory):
    """The actual B1 use case: flour bought in 1kg bags and 250g packets,
    ingredient base unit is kg. Saskia's most common purchase."""
    from app.rms.variants import rollup_ingredient_stock

    ing_id = _make_ingredient(session_factory, "Harina 000", "kg", min_stock_qty=10.0)
    _add_variant(session_factory, ing_id, 1.0, "kg", 3, preferred=True,
                 purchase_price_gs=8500, supplier_id=None)
    _add_variant(session_factory, ing_id, 0.25, "kg", 12,  # also have 250g packets
                 purchase_price_gs=2400, supplier_id=None)

    with session_factory() as s:
        r = rollup_ingredient_stock(s, ing_id)

    assert r is not None
    assert r.variant_count == 2
    # 3 × 1kg + 12 × 0.25kg = 3 + 3 = 6 kg
    assert abs(r.base_qty - 6.0) < 1e-9, f"expected 6.0 kg, got {r.base_qty}"
    # Per-variant breakdown
    v_by_size = {v["package_size"]: v for v in r.variants}
    assert abs(v_by_size[1.0]["stock_in_base"] - 3.0) < 1e-9
    assert abs(v_by_size[0.25]["stock_in_base"] - 3.0) < 1e-9
    # size_in_base fields document the package conversion
    assert v_by_size[1.0]["size_in_base"] == 1.0   # 1 kg = 1 kg in kg-base
    assert v_by_size[0.25]["size_in_base"] == 0.25  # 0.25 kg = 0.25 kg in kg-base


def test_rollup_cross_unit_size_in_base_field_is_correct(session_factory):
    """The new `size_in_base` field on each variant must reflect the
    unit conversion (e.g. 1000g package in a kg-base ingredient = 1.0)."""
    from app.rms.variants import rollup_ingredient_stock

    ing_id = _make_ingredient(session_factory, "sal test", "kg")
    _add_variant(session_factory, ing_id, 1000, "g", 2, preferred=True)

    with session_factory() as s:
        r = rollup_ingredient_stock(s, ing_id)

    v = r.variants[0]
    assert v["size_in_base"] == 1.0, "1000 g package should size to 1.0 kg in kg-base"
    assert v["stock_in_base"] == 2.0, "2 packages × 1.0 kg = 2.0 kg"


# ---------------------------------------------------------------------------
# Regression: same-unit cases must still work (the original tests).
# ---------------------------------------------------------------------------


def test_rollup_same_unit_still_works(session_factory):
    """All kg variants → unchanged from the original test in
    test_saskia_r2_data_models.py."""
    from app.rms.variants import rollup_ingredient_stock

    ing_id = _make_ingredient(session_factory, "azúcar kg", "kg")
    _add_variant(session_factory, ing_id, 1.0, "kg", 3, preferred=True)
    _add_variant(session_factory, ing_id, 0.250, "kg", 12)
    _add_variant(session_factory, ing_id, 5.0, "kg", 1)

    with session_factory() as s:
        r = rollup_ingredient_stock(s, ing_id)

    assert r is not None
    # 3 + 12*0.25 + 1*5 = 11.0 kg
    assert abs(r.base_qty - 11.0) < 1e-9


def test_rollup_no_variants_uses_legacy_column(session_factory):
    """Pre-migration ingredients (no variants) get the legacy stock_qty."""
    from app.rms.variants import rollup_ingredient_stock

    ing_id = _make_ingredient(session_factory, "legacy test", "kg", stock_qty=42.0)

    with session_factory() as s:
        r = rollup_ingredient_stock(s, ing_id)

    assert r is not None
    assert r.base_qty == 42.0
    assert r.variant_count == 0


def test_rollup_returns_none_for_missing_ingredient(session_factory):
    """rollup_ingredient_stock returns None if the ingredient doesn't exist."""
    from app.rms.variants import rollup_ingredient_stock

    with session_factory() as s:
        r = rollup_ingredient_stock(s, 999999)
    assert r is None


# ---------------------------------------------------------------------------
# Integration: days_until_short() must use the corrected rollup.
# ---------------------------------------------------------------------------


def test_days_until_short_with_cross_unit_variants(session_factory):
    """days_until_short reads rollup.base_qty — verify it gets sensible
    numbers when variants are in a different unit than the base."""
    from app.rms.variants import days_until_short

    ing_id = _make_ingredient(session_factory, "harina forecast", "kg")
    # 5 kg in stock (1kg packages, 5 of them)
    _add_variant(session_factory, ing_id, 1.0, "kg", 5, preferred=True)

    result = days_until_short(session_factory(), ing_id, default_horizon=14)

    assert result is not None
    # current_stock_base = 5.0 (kg). With no consumption, status='dead'.
    assert result.current_stock_base == pytest.approx(5.0, abs=1e-9)
    assert result.base_unit == "kg"
    # With zero consumption days_remaining is None.
    assert result.days_remaining is None
    assert result.status == "dead"
