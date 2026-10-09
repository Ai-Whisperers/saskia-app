"""Tests for app/rms/money.py (per spec §9 — 5+ tests).

Tests cover:
- Half-up rounding (not banker's rounding)
- No float drift
- Paraguayan formatting
- parse_gs input flexibility
- to_decimal rejection of invalid input

Uses property-based tests via hypothesis in addition to hand-written cases.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.rms.money import format_gs, parse_gs, to_decimal, to_int_gs

# --- Half-up rounding (NOT banker's rounding) ---


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        (Decimal("0.4"), 0),
        (Decimal("0.5"), 1),  # NOT banker's (0)
        (Decimal("0.6"), 1),
        (Decimal("1.5"), 2),  # NOT banker's (2)
        (Decimal("2.5"), 3),  # NOT banker's (2)
        (Decimal("3.5"), 4),  # NOT banker's (4)
    ],
)
def test_to_int_gs_rounds_half_up(input_value, expected):
    """Half-up rounding: .5 rounds away from zero, not to even."""
    assert to_int_gs(input_value) == expected


def test_to_int_gs_handles_zero():
    assert to_int_gs(Decimal("0")) == 0
    assert to_int_gs(Decimal("0.0")) == 0
    assert to_int_gs(Decimal("-0.0")) == 0


# --- No float drift ---


def test_to_int_gs_no_float_drift():
    """Classic float bug: 0.1 + 0.2 = 0.30000000000000004.

    With Decimal, 0.1 + 0.2 is exactly 0.3 → rounds to 0.
    With float, it would round to 1.
    """
    assert to_int_gs(Decimal("0.1") + Decimal("0.2")) == 0
    # Sanity: 0.6 also rounds to 1, not 0
    assert to_int_gs(Decimal("0.6")) == 1


def test_to_int_gs_large_values():
    """No overflow at Guaraní-scale numbers (millions are normal)."""
    assert to_int_gs(Decimal("17500000")) == 17500000
    assert to_int_gs(Decimal("999999999999.5")) == 1000000000000  # half-up rounds up


# --- Paraguayan formatting ---


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        (0, "Gs. 0"),
        (1, "Gs. 1"),
        (1000, "Gs. 1.000"),
        (729167, "Gs. 729.167"),
        (1234567, "Gs. 1.234.567"),
        (17500000, "Gs. 17.500.000"),
        (-500, "-Gs. 500"),
        (None, "—"),
    ],
)
def test_format_gs_uses_period_thousands(input_value, expected):
    """Period as thousands separator (Paraguayan), no decimals."""
    assert format_gs(input_value) == expected


# --- parse_gs input flexibility ---


@pytest.mark.parametrize(
    ("input_str", "expected"),
    [
        ("Gs. 729.167", 729167),
        ("1.234.567", 1234567),
        ("1,234,567", 1234567),
        ("1234567", 1234567),
        ("  Gs  500  ", 500),
        ("gs. 1", 1),
        ("Gs 1", 1),
    ],
)
def test_parse_gs_handles_various_inputs(input_str, expected):
    """User input is messy; parse_gs should accept common variants."""
    assert parse_gs(input_str) == expected


@pytest.mark.parametrize(
    "bad_input",
    ["abc", "1.5.5", "Gs. -500", "1.5x"],
)
def test_parse_gs_rejects_invalid(bad_input):
    with pytest.raises(ValueError):
        parse_gs(bad_input)


# --- to_decimal rejection of invalid input ---


@pytest.mark.parametrize(
    "bad_input",
    [None, "", "abc", "1.5x", "NaN"],
)
def test_to_decimal_rejects_invalid_input(bad_input):
    with pytest.raises(ValueError):
        to_decimal(bad_input)


# --- Property-based tests (per tech-stack-review #9: hypothesis) ---


@given(st.integers(min_value=0, max_value=10**12))
def test_property_format_parse_roundtrip_positive(value):
    """For any non-negative integer Gs., format-then-parse is the identity.

    (We exclude negatives because parse_gs is intentionally non-negative —
    a future PR can add a parse_gs_signed() if the app ever handles
    refunds or reversals; today, voids are recorded as separate rows.)
    """
    formatted = format_gs(value)
    parsed = parse_gs(formatted)
    assert parsed == value


@given(st.integers(min_value=0, max_value=10**12))
def test_property_format_structure(value):
    """format_gs output has 'Gs. ' prefix and digits + period-only body."""
    out = format_gs(value)
    assert out.startswith("Gs. "), f"missing 'Gs. ' prefix: {out!r}"
    body = out[len("Gs. ") :]
    # Body is digits with optional period separators (every 3 from right)
    parts = body.split(".")
    assert all(p.isdigit() for p in parts), f"non-digit in body: {body!r}"
    # After the first part, all parts must be exactly 3 digits (thousands groups)
    for p in parts[1:]:
        assert len(p) == 3, f"thousands group wrong size: {p!r} in {body!r}"
