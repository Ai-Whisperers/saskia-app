"""tests/test_money_consolidation.py — Sprint 1.4 verification.

Sprint 1.4 of the 2026-10-02 backend overhaul: money & validation
consolidation.

This file locks the *already-shipped* consolidation between
``app.rms.money.parse_gs`` (the canonical, strict parser) and
``app.rms.validation.parse_money_gs`` (the HTTP-shaped wrapper).
The two-function split was the original P0 of the plan, and it was
fixed in P1-3 (commit a0b8a4e, 2026-09-25). This test is the
regression guard so the two functions never drift again.

The plan's 1.4.3 (Float → Numeric(12,4) on 19 quantity columns) was
deferred because:

  - It is an ALTER TABLE on 19 columns with existing float data.
  - Postgres and SQLite handle the migration differently.
  - The backfill of ``NaN`` / ``inf`` from float → ``DECIMAL`` is a
    window-of-need operation, not a code-only change.

The float arithmetic already runs through the Decimal-bounded ``parse``
chain (``parse_quantity`` returns ``float``, but every multiplication
that flows into a monetary value goes through ``MoneyCtx`` which
forces Decimal). So the production risk of the deferred work is
acceptable for now.

What we lock here:

  1. ``validation.parse_money_gs`` is a thin wrapper around
     ``money.parse_gs`` (no divergent grammar).
  2. ``parse_gs`` is the only strict parser (no second copy).
  3. ``parse_quantity`` exists in ``validation`` and behaves as
     documented.
  4. ``parse_money_gs`` rejects every input shape ``parse_gs``
     rejects, and accepts every shape ``parse_gs`` accepts.
  5. ``format_gs(N) → parse_gs(N) == N`` roundtrip property.
"""

from __future__ import annotations

import inspect

import pytest

from app.rms import money, validation
from app.rms.money import format_gs, parse_gs
from app.rms.validation import parse_money_gs, parse_quantity

# ─── Existence ─────────────────────────────────────────────────────────────


def test_parse_gs_exists_in_money():
    """``parse_gs`` lives in ``app.rms.money`` (single source of truth)."""
    assert hasattr(money, "parse_gs")
    assert callable(money.parse_gs)


def test_parse_money_gs_lives_in_validation():
    """``parse_money_gs`` lives in ``app.rms.validation`` (HTTP wrapper)."""
    assert hasattr(validation, "parse_money_gs")
    assert callable(parse_money_gs)


def test_parse_quantity_lives_in_validation():
    """``parse_quantity`` is exposed by ``validation``."""
    assert hasattr(validation, "parse_quantity")
    sig = inspect.signature(parse_quantity)
    # Required kwargs we documented: field, allow_zero
    assert "field" in sig.parameters
    assert "allow_zero" in sig.parameters


# ─── Wrapper contract ──────────────────────────────────────────────────────


def test_parse_money_gs_delegates_to_parse_gs():
    """The wrapper's body should call parse_gs — not re-implement grammar."""
    src = inspect.getsource(parse_money_gs)
    assert "parse_gs(" in src, (
        "parse_money_gs must delegate to parse_gs. Re-implementing the\n"
        "grammar locally is the bug we're trying to prevent.\n"
        f"Source:\n{src}"
    )


def test_parse_money_gs_accepts_canonical_grammar():
    """parse_money_gs accepts the same inputs as parse_gs."""
    assert parse_money_gs("12500") == 12500
    assert parse_money_gs("12.500") == 12500
    assert parse_money_gs("12,500") == 12500
    assert parse_money_gs("Gs. 6.500") == 6500
    assert parse_money_gs("₲12500") == 12500


def test_parse_money_gs_rejects_negatives():
    """parse_money_gs raises HTTPException(400, ...) on negative input."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        parse_money_gs("-100")
    assert exc.value.status_code == 400
    assert "negativo" in str(exc.value.detail).lower()


def test_parse_money_gs_rejects_decimal():
    """parse_money_gs rejects fractional Gs. amounts (money is integer-only)."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        parse_money_gs("1.5")
    assert exc.value.status_code == 400


def test_parse_money_gs_none_raises_400_obligatorio():
    """parse_money_gs rejects None with the Spanish 'obligatorio' message."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        parse_money_gs(None)
    assert exc.value.status_code == 400
    assert "obligatorio" in str(exc.value.detail).lower()


def test_parse_money_gs_zero_rejected_when_disallowed():
    """parse_money_gs(0, allow_zero=False) raises 400."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        parse_money_gs(0, allow_zero=False)


def test_parse_money_gs_zero_allowed_by_default():
    """parse_money_gs('0') returns 0 by default."""
    assert parse_money_gs("0") == 0
    assert parse_money_gs(0) == 0


def test_parse_money_gs_accepts_int_and_float_inputs():
    """FastAPI sometimes hands us int/float — wrapper coerces."""
    assert parse_money_gs(12500) == 12500
    assert parse_money_gs(12500.0) == 12500


# ─── Grammar parity: parse_gs and parse_money_gs agree ─────────────────────


ACCEPT_CASES = [
    "0",
    "1",
    "100",
    "12500",
    "12.500",
    "12,500",
    "1.234.567",
    "1,234,567",
    "Gs. 6.500",
    "Gs 6.500",
    "₲12500",
    "₲ 12.500",
    "  12.500  ",
]
REJECT_CASES = [
    "-100",
    "-1",
    "1.5",
    "abc",
    "",
    "1.5.5",
    "1,5",
]


@pytest.mark.parametrize("value", ACCEPT_CASES)
def test_parse_money_gs_and_parse_gs_both_accept(value):
    """Inputs that parse_gs accepts, parse_money_gs also accepts."""
    gs_result = parse_gs(value)
    wrapper_result = parse_money_gs(value, allow_zero=True)
    assert gs_result == wrapper_result, (
        f"parse_gs({value!r})={gs_result} but parse_money_gs({value!r})={wrapper_result}"
    )


@pytest.mark.parametrize("value", REJECT_CASES)
def test_parse_money_gs_rejects_what_parse_gs_rejects(value):
    """Inputs that parse_gs rejects, parse_money_gs also rejects."""
    from fastapi import HTTPException

    with pytest.raises((ValueError, HTTPException)):
        parse_gs(value)
    with pytest.raises(HTTPException):
        parse_money_gs(value, allow_zero=True)


# ─── parse_quantity contract ──────────────────────────────────────────────────


def test_parse_quantity_basic():
    """parse_quantity('1.5', field='x') returns 1.5."""
    assert parse_quantity("1.5", field="x") == 1.5
    assert parse_quantity(2, field="x") == 2.0


def test_parse_quantity_rejects_negative():
    """parse_quantity rejects negatives (quantities must be ≥ 0)."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        parse_quantity("-1", field="x")
    assert exc.value.status_code == 400


def test_parse_quantity_zero_default_rejected():
    """parse_quantity defaults to allow_zero=False."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        parse_quantity("0", field="x")
    assert exc.value.status_code == 400


def test_parse_quantity_zero_allowed_with_flag():
    """parse_quantity('0', allow_zero=True) returns 0.0."""
    assert parse_quantity("0", field="x", allow_zero=True) == 0.0


def test_parse_quantity_none_rejected():
    """parse_quantity rejects None."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        parse_quantity(None, field="x")
    assert exc.value.status_code == 400


# ─── Roundtrip property ────────────────────────────────────────────────────


@pytest.mark.parametrize("value", [1, 100, 12500, 1_000_000, 999_999_999])
def test_format_parse_roundtrip(value):
    """format_gs(N) → parse_gs → N for normal positive integers."""
    formatted = format_gs(value)
    assert parse_gs(formatted) == value
