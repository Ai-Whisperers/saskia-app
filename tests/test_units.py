"""Tests for app/rms/units.py (per spec §9 — 5+ tests)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.rms.units import Unit, can_convert, convert_qty, normalize_recipe_line_qty

# --- Coercion of common aliases ---


@pytest.mark.parametrize(
    ("input_str", "expected_unit"),
    [
        ("g", Unit.G),
        ("gramo", Unit.G),
        ("gramos", Unit.G),
        ("gram", Unit.G),
        ("kg", Unit.KG),
        ("kilo", Unit.KG),
        ("kilos", Unit.KG),
        ("kilogramo", Unit.KG),
        ("ml", Unit.ML),
        ("mililitro", Unit.ML),
        ("mililitros", Unit.ML),
        ("l", Unit.L),
        ("litro", Unit.L),
        ("litros", Unit.L),
        ("und", Unit.UNIT),
        ("unidad", Unit.UNIT),
        ("unidades", Unit.UNIT),
        ("u", Unit.UNIT),
        ("porcion", Unit.UNIT),
        ("porciones", Unit.UNIT),
        ("bandeja", Unit.UNIT),
        ("torta", Unit.UNIT),
        ("muffin", Unit.UNIT),
        ("galleta", Unit.UNIT),
        # Canonical values pass through
        ("g", Unit.G),
        ("kg", Unit.KG),
        ("ml", Unit.ML),
        ("l", Unit.L),
        ("und", Unit.UNIT),
    ],
)
def test_unit_coerce_aliases(input_str, expected_unit):
    assert Unit.coerce(input_str) == expected_unit


@pytest.mark.parametrize(
    "bad_input",
    ["stones", "fahrenheit", "kg2", None, "", "litros_extra"],
)
def test_unit_coerce_rejects_unknown(bad_input):
    with pytest.raises(ValueError, match=r"(unknown unit|empty unit)"):
        Unit.coerce(bad_input)


# --- Conversion: same-family allowed, cross-family forbidden ---


@pytest.mark.parametrize(
    ("qty", "from_unit", "to_unit", "expected"),
    [
        (Decimal("1500"), Unit.G, Unit.KG, Decimal("1.5")),
        (Decimal("1.5"), Unit.KG, Unit.G, Decimal("1500")),
        (Decimal("2000"), Unit.ML, Unit.L, Decimal("2")),
        (Decimal("0.5"), Unit.L, Unit.ML, Decimal("500")),
        # Identity
        (Decimal("100"), Unit.G, Unit.G, Decimal("100")),
        (Decimal("100"), Unit.UNIT, Unit.UNIT, Decimal("100")),
    ],
)
def test_convert_intra_family(qty, from_unit, to_unit, expected):
    """g↔kg and ml↔l conversions work; identity is a no-op."""
    assert convert_qty(qty, from_unit, to_unit) == expected


@pytest.mark.parametrize(
    ("from_unit", "to_unit"),
    [
        (Unit.G, Unit.L),
        (Unit.G, Unit.ML),
        (Unit.L, Unit.G),
        (Unit.L, Unit.KG),
        (Unit.ML, Unit.KG),
        (Unit.UNIT, Unit.G),  # countable to mass is forbidden
        (Unit.UNIT, Unit.KG),
        (Unit.G, Unit.UNIT),
    ],
)
def test_convert_cross_family_forbidden(from_unit, to_unit):
    """Cross-family conversions are forbidden (need ingredient-specific density)."""
    with pytest.raises(ValueError, match="cross-family"):
        convert_qty(Decimal("100"), from_unit, to_unit)


def test_can_convert_returns_true_for_compatible():
    """Same-family units are convertible."""
    assert can_convert(Unit.G, Unit.G)
    assert can_convert(Unit.G, Unit.KG)
    assert can_convert(Unit.KG, Unit.G)
    assert can_convert(Unit.ML, Unit.L)
    assert can_convert(Unit.L, Unit.ML)


def test_can_convert_returns_false_for_incompatible():
    """Cross-family units are not convertible."""
    assert not can_convert(Unit.G, Unit.L)
    assert not can_convert(Unit.G, Unit.ML)
    assert not can_convert(Unit.UNIT, Unit.G)
    assert not can_convert(Unit.UNIT, Unit.KG)


# --- Display and allowed_values ---


def test_unit_display():
    assert Unit.G.display == "g"
    assert Unit.KG.display == "kg"
    assert Unit.ML.display == "ml"
    assert Unit.L.display == "l"
    assert Unit.UNIT.display == "und"


def test_unit_allowed_values_for_docs():
    """Used in error messages and API responses."""
    assert Unit.allowed_values() == ["g", "kg", "ml", "l", "und"]


# --- normalize_recipe_line_qty (Phase B — T1 recipe line unit selector) ---


@pytest.mark.parametrize(
    ("line_qty", "line_unit", "ingredient_unit", "expected"),
    [
        # Same-unit identity (no conversion)
        (Decimal("250"), "g", "g", Decimal("250")),
        (Decimal("0.25"), "kg", "kg", Decimal("0.25")),
        (Decimal("500"), "ml", "ml", Decimal("500")),
        (Decimal("1.5"), "l", "l", Decimal("1.5")),
        (Decimal("12"), "und", "und", Decimal("12")),
        # g ↔ kg
        (Decimal("250"), "g", "kg", Decimal("0.25")),
        (Decimal("0.25"), "kg", "g", Decimal("250")),
        (Decimal("1500"), "g", "kg", Decimal("1.5")),
        # ml ↔ l
        (Decimal("500"), "ml", "l", Decimal("0.5")),
        (Decimal("0.5"), "l", "ml", Decimal("500")),
        (Decimal("2000"), "ml", "l", Decimal("2")),
    ],
)
def test_normalize_recipe_line_qty_same_family(line_qty, line_unit, ingredient_unit, expected):
    """Same-family conversions: 250 g into a kg ingredient → 0.25 kg."""
    actual = normalize_recipe_line_qty(line_qty, line_unit, ingredient_unit)
    assert actual == expected
    assert isinstance(actual, Decimal)


def test_normalize_recipe_line_qty_accepts_floats():
    """Inputs may be float (SQLite Float column). Coerced to Decimal internally."""
    actual = normalize_recipe_line_qty(250.0, "g", "kg")
    assert actual == Decimal("0.25")
    assert isinstance(actual, Decimal)


def test_normalize_recipe_line_qty_accepts_strings():
    """Inputs may be string (form POST). Coerced to Decimal internally."""
    actual = normalize_recipe_line_qty("250", "g", "kg")
    assert actual == Decimal("0.25")


@pytest.mark.parametrize(
    ("line_qty", "line_unit", "ingredient_unit"),
    [
        # Mass ↔ volume is forbidden (would need density)
        (Decimal("250"), "g", "l"),
        (Decimal("250"), "g", "ml"),
        (Decimal("1"), "kg", "l"),
        (Decimal("1"), "kg", "ml"),
        # Mass/volume ↔ countable is forbidden
        (Decimal("12"), "und", "g"),
        (Decimal("12"), "und", "kg"),
        (Decimal("12"), "und", "ml"),
        (Decimal("12"), "und", "l"),
        (Decimal("100"), "g", "und"),
        (Decimal("100"), "kg", "und"),
        (Decimal("100"), "ml", "und"),
        (Decimal("100"), "l", "und"),
    ],
)
def test_normalize_recipe_line_qty_cross_family_forbidden(line_qty, line_unit, ingredient_unit):
    """Cross-family conversion raises ValueError (no density lookup)."""
    with pytest.raises(ValueError, match="cross-family"):
        normalize_recipe_line_qty(line_qty, line_unit, ingredient_unit)


def test_normalize_recipe_line_qty_bad_unit_string():
    """An unknown unit string raises ValueError (coerce fails first)."""
    with pytest.raises(ValueError, match="unknown unit"):
        normalize_recipe_line_qty(Decimal("100"), "stones", "kg")


def test_normalize_recipe_line_qty_zero_qty_allowed():
    """Zero qty is not rejected by the converter — CHECK constraint catches negatives."""
    # Note: normalize_recipe_line_qty itself only does conversion; 0 is a no-op.
    assert normalize_recipe_line_qty(Decimal("0"), "g", "kg") == Decimal("0")
