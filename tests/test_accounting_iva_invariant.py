"""PR A2 — IVA round-trip invariant.

Moved from app/rms/accounting.py:41 to app/rms/constants.py on 2026-10-07.
This test pins the contract: for any non-negative gross amount divisible
by 100, the extracted base + IVA must sum back to the original gross.
Both `tax_mode` values are covered.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from app.rms.accounting import extract_iva
from app.rms.constants import IVA_DIVISOR, PARAGUAY_IVA_RATE

# ─── Sanity: the constants exist where they should ─────────────────

def test_constants_live_in_constants_module() -> None:
    """The single source of truth is app/rms/constants.py."""
    from app.rms import accounting, constants

    assert accounting.PARAGUAY_IVA_RATE is constants.PARAGUAY_IVA_RATE
    assert accounting.IVA_DIVISOR is constants.IVA_DIVISOR
    assert accounting.PARAGUAY_IVA_RATE == Decimal("0.10")
    assert accounting.IVA_DIVISOR == Decimal("1.10")


# ─── Property: round-trip invariant ───────────────────────────────

# Gross amounts in the realistic Sazón range: 1k Gs. (a chipita) to
# 100M Gs. (a busy day). Divided by 100 so Decimal division by 1.10
# doesn't lose the cents.
POSITIVE_GROSS = st.integers(min_value=1_000, max_value=100_000_000).filter(
    lambda x: x % 100 == 0
)


@given(gross=POSITIVE_GROSS)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_extract_iva_included_round_trip(gross: int) -> None:
    """tax_mode='included': base + iva == gross (within integer rounding)."""
    assume(gross > 0)
    result = extract_iva(gross, tax_mode="included")
    # Integer-rounding tolerance: each side is rounded to int separately.
    # Total drift is at most 1 Gs. either direction.
    assert abs((result.base_gs + result.iva_gs) - result.gross_gs) <= 1, (
        f"gross={gross} base={result.base_gs} iva={result.iva_gs} "
        f"sum={result.base_gs + result.iva_gs}"
    )


@given(gross=POSITIVE_GROSS)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_extract_iva_excluded_round_trip(gross: int) -> None:
    """tax_mode='excluded': base == gross, iva == round(gross * 0.10)."""
    assume(gross > 0)
    result = extract_iva(gross, tax_mode="excluded")
    assert result.base_gs == gross, f"gross={gross} expected base={gross}, got {result.base_gs}"
    # iva is exact (gross * 0.10 in Decimal then int-truncated). Allow ±1
    # for the int() cast.
    expected_iva = int(Decimal(gross) * PARAGUAY_IVA_RATE)
    assert abs(result.iva_gs - expected_iva) <= 1, (
        f"gross={gross} expected iva≈{expected_iva}, got {result.iva_gs}"
    )


# ─── Concrete examples that match the accounting math docs ────────


def test_extract_iva_included_examples() -> None:
    """The 3 worked examples from the docstring of extract_iva()."""
    r = extract_iva(110_000, tax_mode="included")
    assert r.gross_gs == 110_000
    assert r.base_gs == 100_000
    assert r.iva_gs == 10_000

    r = extract_iva(55_000, tax_mode="included")
    assert r.gross_gs == 55_000
    assert r.base_gs == 50_000
    assert r.iva_gs == 5_000

    r = extract_iva(0, tax_mode="included")
    assert r.gross_gs == 0
    assert r.base_gs == 0
    assert r.iva_gs == 0


def test_extract_iva_excluded_examples() -> None:
    """excluded mode: iva = 10% of gross, base = gross unchanged."""
    r = extract_iva(100_000, tax_mode="excluded")
    assert r.gross_gs == 100_000
    assert r.base_gs == 100_000
    assert r.iva_gs == 10_000

    r = extract_iva(50_000, tax_mode="excluded")
    assert r.gross_gs == 50_000
    assert r.base_gs == 50_000
    assert r.iva_gs == 5_000


def test_extract_iva_rejects_unknown_tax_mode() -> None:
    """Future-proofing: bad tax_mode must raise, not silently miscompute."""
    with pytest.raises(ValueError, match="Unknown tax_mode"):
        extract_iva(100_000, tax_mode="banana")


def test_included_uses_divisor_one_point_one() -> None:
    """The included-mode divisor is the documented 1.10 (Decimal)."""
    # If someone "simplifies" the divisor to 10/9 or 1.1 (float), this test
    # will catch it because the exact Decimal division matters for tax math.
    r = extract_iva(110_000, tax_mode="included")
    expected_base = int(Decimal(110_000) / IVA_DIVISOR)
    assert r.base_gs == expected_base
