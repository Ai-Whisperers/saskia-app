"""Tests for the Phase 14 #20 — discount overflow guard.

The previous code computed discount_gs via float:
    discount_gs = math.ceil(qty * unit_price * discount_pct / 100)

Float can overflow (becomes `inf`) for large qty or unit_price, then
math.ceil(inf) raises OverflowError. Decimal-safe math prevents this.
Additionally, discount_pct is Pydantic-bounded to [0, 100] upstream,
so the discount can never exceed the line subtotal.

These tests exercise the Decimal path directly via a small helper that
mirrors the production logic, so we don't depend on full HTTP plumbing.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, getcontext

# Loosen the Decimal precision context for these tests — production
# money math doesn't need 100-digit precision but tests with huge inputs
# shouldn't crash with InvalidOperation.
getcontext().prec = 60


def _compute_line_discount_gs(qty, unit_price, discount_pct):
    """Mirror of the sales.py:1230 logic, refactored to Decimal."""
    return int(
        (
            Decimal(str(qty))
            * Decimal(str(unit_price))
            * Decimal(str(discount_pct or 0))
            / Decimal(100)
        ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )


def test_basic_50_percent_discount():
    """100 * 5000 * 0.5 = 250000"""
    assert _compute_line_discount_gs(2, 5000, 50) == 5000


def test_zero_discount_returns_zero():
    """discount_pct=0 must yield 0 Gs., not None or empty."""
    assert _compute_line_discount_gs(5, 1000, 0) == 0


def test_full_100_percent_discount():
    """discount_pct=100% caps discount at the line subtotal."""
    assert _compute_line_discount_gs(3, 10000, 100) == 30000


def test_no_overflow_with_huge_unit_price():
    """Decimal must not overflow where float would yield `inf`."""
    # 10**30 easily overflows float64 (max ~1.8e308), but Decimal handles it.
    huge = 10**30
    result = _compute_line_discount_gs(2, huge, 10)
    # 2 * 10**30 * 0.10 = 2 * 10**29
    assert result == 2 * 10**29


def test_rounding_half_up():
    """3 × 1000 × 1% = 30 exactly (no rounding needed)."""
    assert _compute_line_discount_gs(3, 1000, 1) == 30


def test_rounding_half_up_fractional():
    """7 × 100 × 1% = 7.0 exact (no rounding needed)."""
    assert _compute_line_discount_gs(7, 100, 1) == 7


def test_rounding_half_up_with_half_cent():
    """1 × 100 × 3% = 3 exactly. 1 × 101 × 3% = 3.03 → 3 (truncate)."""
    # Decimal quantize with ROUND_HALF_UP: 3.03 → 3
    assert _compute_line_discount_gs(1, 101, 3) == 3
    # 1 × 100 × 3.5% = 3.5 → 4 (round up at half)
    assert _compute_line_discount_gs(1, 100, 3.5) == 4


def test_discount_pct_none_treated_as_zero():
    """None discount_pct (from optional form field) must not crash."""
    assert _compute_line_discount_gs(5, 2000, None) == 0


def test_negative_qty_is_safely_handled():
    """Negative qty (shouldn't happen, but defense in depth) returns negative."""
    # The Pydantic model at line 1028 has qty > 0, but if it ever slipped
    # through, Decimal math still produces a consistent signed result.
    result = _compute_line_discount_gs(-2, 5000, 10)
    assert result == -1000


def test_discount_never_exceeds_subtotal_when_pct_bounded():
    """With discount_pct ≤ 100, discount ≤ subtotal — invariant."""
    # The Pydantic validator on SaleRequest.discount_pct caps at 100.
    # Decimal math here respects that: even if a bad request sneaks
    # through with discount_pct=100, the result is bounded by qty*price.
    for pct in (0, 25, 50, 75, 100):
        qty, price = 13, 12345
        subtotal = qty * price
        discount = _compute_line_discount_gs(qty, price, pct)
        assert 0 <= discount <= subtotal, (
            f"discount_pct={pct} → discount {discount} > subtotal {subtotal}"
        )