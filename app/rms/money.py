"""Money helpers — Decimal + Guaraní (Gs.) formatting.

Rules (per docs/operations/2026-09-fase-1-specs.md §A and the
04_foodbiz/AGENTS.md hard rules):

- All money columns in the DB are integer Gs. (no decimals).
- All money calculations should NOT round intermediate values.
- All money persistence rounds half-up to integer at the last step.
- Money display uses Paraguayan convention: "Gs. 1.234.567" with period
  as thousands separator.

Why we don't use py-moneyed or similar:
- Paraguayan formatting (period as thousands separator) is not built in.
- Storing in cents would not match our integer-Gs. policy.
- The 5 functions below cover all our needs; a library buys us nothing.

This module is dependency-free (stdlib only).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# Sentinel for "no value" — used by callers to mean "we don't know the price"
# Display returns "—" rather than "Gs. 0" so the dashboard alert
# ("falta precio de ingrediente") is honest.
MISSING_MONEY = None


def to_decimal(value) -> Decimal:
    """Coerce input to Decimal safely.

    Reject None, empty string, NaN, infinity, or non-numeric input.
    Accepts str, int, float, Decimal. Floats go through str() to avoid
    representation errors (e.g., Decimal(0.1) is exact, but
    Decimal(float('0.1')) is not).

    Examples:
        >>> to_decimal("100")
        Decimal('100')
        >>> to_decimal(100.5)
        Decimal('100.5')
        >>> to_decimal(Decimal("3.14"))
        Decimal('3.14')
        >>> to_decimal(None)
        Traceback (most recent exception being shown): ...
        ValueError: Cannot coerce None to Decimal
        >>> to_decimal("NaN")
        Traceback (most recent exception being shown): ...
        ValueError: Cannot coerce NaN or infinity
    """
    if value is None or value == "":
        raise ValueError(f"Cannot coerce {value!r} to Decimal")
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid money value: {value!r}") from exc
    if d.is_nan() or d.is_infinite():
        raise ValueError(f"Cannot coerce NaN or infinity: {value!r}")
    return d


def to_int_gs(value) -> int:
    """Round to nearest integer Gs., half up. Use at persistence sites only.

    NEVER use this in intermediate calculations. The pattern is:

        line_cost = to_decimal(qty) * to_decimal(price)   # Decimal, no rounding
        recipe_cost = sum(...)                            # Decimal, no rounding
        recipe_cost_gs = to_int_gs(recipe_cost)           # round ONCE at the end

    Examples:
        >>> to_int_gs(Decimal("0.5"))
        1
        >>> to_int_gs(Decimal("1.5"))
        2
        >>> to_int_gs(Decimal("2.5"))
        3   # NOT 2 (banker's rounding); we want half-up
        >>> to_int_gs(Decimal("0.1") + Decimal("0.2"))
        0   # Decimal precision; float would give 1
    """
    return int(to_decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def format_gs(value: int | None) -> str:
    """Format integer Gs. as 'Gs. 1.234.567' (Paraguayan convention).

    Period as thousands separator, no decimals. None -> "—".

    Examples:
        >>> format_gs(0)
        'Gs. 0'
        >>> format_gs(1234567)
        'Gs. 1.234.567'
        >>> format_gs(729167)
        'Gs. 729.167'
        >>> format_gs(None)
        '—'
        >>> format_gs(-500)
        '-Gs. 500'
    """
    if value is None:
        return "—"
    sign = "-" if value < 0 else ""
    abs_val = abs(value)
    # Format with Python's comma, then swap to period (Paraguayan)
    formatted = f"{abs_val:,}".replace(",", ".")
    return f"{sign}Gs. {formatted}" if sign else f"Gs. {formatted}"


def parse_gs(s: str) -> int:
    """Parse a user-entered Gs. string back to int.

    Accepts: "Gs." prefix (optional), digits, period or comma as thousands
    separator (NOT both — pick one). Rejects negatives, decimals, multi-period.

    Examples:
        >>> parse_gs("Gs. 729.167")
        729167
        >>> parse_gs("1.234.567")
        1234567
        >>> parse_gs("1,234,567")
        1234567
        >>> parse_gs("1234567")
        1234567
        >>> parse_gs("  Gs  500  ")
        500
        >>> parse_gs("abc")
        Traceback (most recent exception being shown): ...
        ValueError: not a valid Gs. amount: 'abc'
        >>> parse_gs("1.5.5")
        Traceback (most recent exception being shown): ...
        ValueError: not a valid Gs. amount: '1.5.5' (multi-separator or decimal)
        >>> parse_gs("Gs. -500")
        Traceback (most recent exception being shown): ...
        ValueError: not a valid Gs. amount: 'Gs. -500' (negatives not allowed)
        >>> parse_gs("1.5")
        Traceback (most recent exception being shown): ...
        ValueError: not a valid Gs. amount: '1.5' (decimals not allowed)
    """
    if s is None or not isinstance(s, str):
        raise ValueError(f"not a valid Gs. amount: {s!r}")
    if not s.strip():
        raise ValueError("empty string")
    if s.strip().startswith("-"):
        raise ValueError(f"not a valid Gs. amount: {s!r} (negatives not allowed)")
    # Strip prefix and whitespace
    cleaned = s.strip()
    for prefix in ("Gs.", "Gs", "gs.", "gs"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
            break
    # A valid Gs. amount is digits with optional periods or commas as
    # thousands separators (every 3 digits from the right). Patterns accepted:
    #   "1234567"      no separators
    #   "1.234.567"    period as thousands sep
    #   "1,234,567"    comma as thousands sep
    # Patterns rejected:
    #   "1.5"          decimal (fractional)
    #   "1.5.5"        malformed (5 is not a group of 3)
    #   "1.234,567"    mixed separators
    digits = cleaned
    # Normalize all separators to period for checking
    normalized = digits.replace(",", ".")
    # Count periods: each separator must be followed by exactly 3 digits until end
    parts = normalized.split(".")
    if len(parts) == 1:
        # No separators, all digits
        if not parts[0].isdigit() or not parts[0]:
            raise ValueError(f"not a valid Gs. amount: {s!r}")
    else:
        # First part must be 1-3 digits, all subsequent must be exactly 3 digits
        if not parts[0].isdigit() or not (1 <= len(parts[0]) <= 3):
            raise ValueError(f"not a valid Gs. amount: {s!r} (decimal)")
        for part in parts[1:]:
            if not part.isdigit() or len(part) != 3:
                raise ValueError(f"not a valid Gs. amount: {s!r} (decimal or malformed)")
    digits_only = digits.replace(".", "").replace(",", "")
    if not digits_only:
        raise ValueError(f"not a valid Gs. amount: {s!r}")
    return int(digits_only)


__all__ = [
    "MISSING_MONEY",
    "to_decimal",
    "to_int_gs",
    "format_gs",
    "parse_gs",
]
