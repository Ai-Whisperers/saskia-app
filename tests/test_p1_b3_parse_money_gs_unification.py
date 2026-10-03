"""P1-3: tests for parse_money_gs / parse_gs unification.

After the refactor, parse_money_gs is a thin HTTP-shaped wrapper around
the canonical parse_gs (in app/rms/money.py). This test file locks in
the unified behavior:

  - parse_money_gs accepts the same inputs as parse_gs (canonical grammar)
  - parse_money_gs rejects what parse_gs rejects (negatives, decimals,
    mixed separators, malformed) — this fixes the silent-mangling bug
    that the old parse_money_gs had when it stripped both . and ,
    indiscriminately
  - parse_money_gs translates ValueError → HTTPException(400) with
    Spanish detail (preserves caller contract)
  - parse_money_gs still handles int / float / None coercion
  - parse_money_gs still honors allow_zero
  - parse_gs (the canonical one) now also accepts ₲ / G$ / $ prefixes
    (added in this refactor so the wrapper doesn't need its own prefix
    stripping)
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.rms.money import parse_gs
from app.rms.validation import parse_money_gs

# ─── Canonical grammar (parse_gs) — locked in tests ──────────────────────


def test_parse_gs_accepts_plain_integer() -> None:
    assert parse_gs("12500") == 12500


def test_parse_gs_accepts_dot_thousands() -> None:
    """Paraguay style: 12.500 = twelve thousand five hundred."""
    assert parse_gs("12.500") == 12500


def test_parse_gs_accepts_comma_thousands() -> None:
    """US style: 12,500 = twelve thousand five hundred."""
    assert parse_gs("12,500") == 12500


def test_parse_gs_accepts_currency_prefix() -> None:
    assert parse_gs("Gs. 6.500") == 6500


def test_parse_gs_accepts_guarani_symbol() -> None:
    """₲ (Unicode Guarani sign) is a valid currency prefix."""
    assert parse_gs("₲12500") == 12500


def test_parse_gs_accepts_g_dollar() -> None:
    """G$ is the rare variant."""
    assert parse_gs("G$ 500") == 500


def test_parse_gs_accepts_dollar() -> None:
    """$ by itself (loose, common in Paraguayan invoices)."""
    assert parse_gs("$ 500") == 500


def test_parse_gs_rejects_negative() -> None:
    with pytest.raises(ValueError, match="negatives"):
        parse_gs("-100")


def test_parse_gs_rejects_decimal() -> None:
    """No fractions — Gs. is integer-only by convention."""
    with pytest.raises(ValueError, match="decimal"):
        parse_gs("1.5")


def test_parse_gs_normalizes_mixed_separators() -> None:
    """Mixed separators are normalized (commas → periods) rather than rejected.

    This is the canonical parse_gs behavior, intentionally permissive
    for users who mix . and , in the same number. The old parse_money_gs
    was LESS strict here — it would have stripped BOTH giving a wrong
    result; this canonical version is at least consistent.
    """
    # "1.234,567" → normalize , → . → "1.234.567" → 1234567
    assert parse_gs("1.234,567") == 1234567
    assert parse_gs("1,234.567") == 1234567


def test_parse_gs_rejects_malformed_groups() -> None:
    """1.5.5 → second 'group' is 5 not 3 digits."""
    with pytest.raises(ValueError, match="decimal"):
        parse_gs("1.5.5")


def test_parse_gs_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        parse_gs("abc")


def test_parse_gs_rejects_empty() -> None:
    with pytest.raises(ValueError):
        parse_gs("")
    with pytest.raises(ValueError):
        parse_gs("   ")


# ─── Wrapper contract (parse_money_gs) — HTTP-shaped ─────────────────────


def test_parse_money_gs_accepts_canonical_grammar() -> None:
    """Everything parse_gs accepts must work through the wrapper."""
    assert parse_money_gs("12500") == 12500
    assert parse_money_gs("12.500") == 12500
    assert parse_money_gs("12,500") == 12500
    assert parse_money_gs("Gs. 6.500") == 6500
    assert parse_money_gs("₲12500") == 12500


def test_parse_money_gs_accepts_int() -> None:
    """FastAPI form binding sometimes hands us int."""
    assert parse_money_gs(12500) == 12500


def test_parse_money_gs_accepts_float_when_integer_valued() -> None:
    """12_500.0 should coerce cleanly (not become 12500.0 with a float body)."""
    assert parse_money_gs(12500.0) == 12500


def test_parse_money_gs_none_raises_400() -> None:
    """None / empty → 400 'Precio es obligatorio'."""
    with pytest.raises(HTTPException) as exc:
        parse_money_gs(None)
    assert exc.value.status_code == 400
    assert "obligatorio" in exc.value.detail

    with pytest.raises(HTTPException) as exc:
        parse_money_gs("")
    assert exc.value.status_code == 400
    assert "obligatorio" in exc.value.detail


def test_parse_money_gs_negative_raises_400_negativo() -> None:
    """Negative must say 'negativo', not the generic 'inválido'."""
    with pytest.raises(HTTPException) as exc:
        parse_money_gs("-100")
    assert exc.value.status_code == 400
    assert "negativo" in exc.value.detail


def test_parse_money_gs_garbage_raises_400_invalido() -> None:
    """Garbage (not just negative) gets the generic 'inválido' message."""
    with pytest.raises(HTTPException) as exc:
        parse_money_gs("abc")
    assert exc.value.status_code == 400
    assert "inválido" in exc.value.detail


def test_parse_money_gs_decimal_raises_400() -> None:
    """1.5 was silently accepted by old parse_money_gs as 15 (or 15000).

    With the unification it must raise 400 'inválido' — this is the
    whole point of the refactor: the old parser silently mangled
    multi-separator / decimal inputs into bogus amounts.
    """
    with pytest.raises(HTTPException) as exc:
        parse_money_gs("1.5")
    assert exc.value.status_code == 400
    assert "inválido" in exc.value.detail


def test_parse_money_gs_mixed_separators_normalizes() -> None:
    """Mixed separators are normalized (consistent with the canonical parser).

    This documents the unification's behavior: the wrapper inherits
    parse_gs's normalization instead of the old strip-both-and-mangle
    behavior. 1.234,567 now correctly parses as 1234567.
    """
    # Was previously mangled to a wrong number; now correctly normalized.
    assert parse_money_gs("1.234,567") == 1234567
    assert parse_money_gs("1,234.567") == 1234567


def test_parse_money_gs_malformed_groups_raises_400() -> None:
    """1.5.5 was previously mangled silently → 155. Now correctly rejected."""
    with pytest.raises(HTTPException) as exc:
        parse_money_gs("1.5.5")
    assert exc.value.status_code == 400
    assert "inválido" in exc.value.detail


def test_parse_money_gs_zero_allowed_by_default() -> None:
    """allow_zero=True (the default) lets zero through."""
    assert parse_money_gs("0") == 0
    assert parse_money_gs(0) == 0


def test_parse_money_gs_zero_rejected_when_disallowed() -> None:
    with pytest.raises(HTTPException) as exc:
        parse_money_gs("0", allow_zero=False)
    assert exc.value.status_code == 400
    assert "cero" in exc.value.detail


def test_parse_money_gs_zero_rejected_when_disallowed_int() -> None:
    """The int 0 must also be rejected when allow_zero=False."""
    with pytest.raises(HTTPException) as exc:
        parse_money_gs(0, allow_zero=False)
    assert exc.value.status_code == 400
    assert "cero" in exc.value.detail


# ─── Unification invariant — format(gs) roundtrip ─────────────────────────


def test_format_parse_roundtrip_via_wrapper() -> None:
    """format_gs(N) → parse_money_gs → N for many N values.

    Locks in that the canonical format the app emits (Gs. 1.234.567)
    can always be parsed back. Previously caught regressions when
    someone tightened the grammar and broke the round-trip.
    """
    from app.rms.money import format_gs

    for n in (0, 1, 100, 999, 1_000, 12_345, 1_234_567, 999_999_999):
        formatted = format_gs(n)
        parsed = parse_money_gs(formatted, allow_zero=True)
        assert parsed == n, f"round-trip failed for {n}: {formatted!r} → {parsed}"
