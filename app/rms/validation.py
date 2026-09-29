"""Centralized form-validation helpers for Saskia RMS CRUD endpoints.

All errors are returned as Spanish HTTPExceptions so BUG-00 is consistent.
Helpers return cleaned values (or raise on bad input) so the calling route
can use them directly when constructing model instances.

Usage:
    from app.rms.validation import require_text, parse_money_gs, parse_unit, validate_phone

    name = require_text(request_form.name, field="nombre", max_len=120)
    price = parse_money_gs(sale_price_gs, allow_zero=False)
    unit_enum = parse_unit("kg")
"""
from __future__ import annotations

import re
import unicodedata
from typing import Final

from fastapi import HTTPException

from app.rms.units import Unit

# Paraguay phone formats we accept:
#   - Mobile: 098X XXX XXX or 098XXXXXXX (10 digits starting with 09)
#   - Landline: 0XX XXXXXX (8-10 digits with city code)
#   - International: +595 9XX XXX XXX
PHONE_RE: Final = re.compile(r"^\+?\d{6,15}$")

# Basic email regex — pragmatic, not exhaustive.
EMAIL_RE: Final = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# Paraguay RUC formats (DNIT/RUC):
#   - Persona física: X.XXX.XXX
#   - Persona jurídica: XXXXXXX-X (7 digits + dash + 1 digit)
#   - Simplified: just digits
RUC_RE: Final = re.compile(r"^[\d.\-]{5,20}$")

# Paraguay cédula: X.XXX.XXX or just digits (5-8 digits typical)
CEDULA_RE: Final = re.compile(r"^[\d.]{5,12}$")


def require_text(value: str | None, *, field: str, max_len: int) -> str:
    """Return the value stripped, or raise a Spanish 400 if blank/too long."""
    cleaned = (value or "").strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail=f"{field} es obligatorio")
    if len(cleaned) > max_len:
        raise HTTPException(
            status_code=400,
            detail=f"{field} es demasiado largo (máx {max_len} caracteres)",
        )
    return cleaned


def optional_text(value: str | None, *, max_len: int) -> str | None:
    """Return the value stripped (or None if blank), enforcing max length."""
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    if len(cleaned) > max_len:
        raise HTTPException(
            status_code=400,
            detail=f"Texto demasiado largo (máx {max_len} caracteres)",
        )
    return cleaned


def optional_int(value: str | int | None, *, default: int | None = None) -> int | None:
    """Parse as an int. Accepts str (form input), int (already parsed), or None.

    Empty / invalid → default (None or caller value).
    """
    if value is None:
        return default
    if isinstance(value, int):
        return value
    s = str(value).strip()
    if not s:
        return default
    try:
        return int(s)
    except (ValueError, TypeError):
        return default


def parse_money_gs(value: str | int | float | None, *, allow_zero: bool = True) -> int:
    """Parse a money string into integer Gs.

    Rejects negative unless allow_zero=False. Accepts:
      - "12.500" → 12500 (dot-separated thousands, Paraguay style)
      - "12,500" → 12500 (US style)
      - "Gs. 6.500" → 6500 (with currency prefix)
      - "12500" → 12500 (plain integer)
    Negative numbers and zero (when allow_zero=False) raise Spanish 400.
    """
    if value is None or value == "":
        raise HTTPException(status_code=400, detail="Precio es obligatorio")
    if isinstance(value, (int, float)):
        amount = int(value)
    else:
        # Strip currency prefix/suffix and grouping separators.
        s = str(value).strip()
        # Remove "Gs.", "G$", "$", "₲" prefixes (with optional whitespace)
        import re as _re
        s = _re.sub(r"^\s*(?:Gs\.?|G\$|₲|\$)\s*", "", s, flags=_re.IGNORECASE)
        s = s.replace(".", "").replace(",", "").strip()
        if not s or not s.lstrip("-").isdigit():
            raise HTTPException(
                status_code=400, detail=f"Precio inválido: {value!r}"
            )
        amount = int(s)
    if amount < 0:
        raise HTTPException(status_code=400, detail="Precio no puede ser negativo")
    if amount == 0 and not allow_zero:
        raise HTTPException(status_code=400, detail="Precio no puede ser cero")
    return amount


def parse_quantity(value: str | float | int | None, *, field: str = "cantidad", allow_zero: bool = False) -> float:
    """Parse a numeric quantity. Rejects negative, optionally rejects zero."""
    if value is None or value == "":
        raise HTTPException(status_code=400, detail=f"{field} es obligatorio")
    try:
        amount = float(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"{field} inválida: {value!r}") from None
    if amount < 0:
        raise HTTPException(status_code=400, detail=f"{field} no puede ser negativa")
    if amount == 0 and not allow_zero:
        raise HTTPException(status_code=400, detail=f"{field} debe ser mayor a 0")
    return amount


def parse_unit(value: str | None) -> Unit:
    """Coerce to Unit enum, raising Spanish 400 on invalid."""
    try:
        return Unit.coerce(value or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Unidad inválida: {e}") from e


def validate_email(value: str | None) -> str | None:
    """Return email or None if blank. Raise 400 if non-blank but malformed."""
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    if not EMAIL_RE.match(cleaned):
        raise HTTPException(
            status_code=400,
            detail=f"Email inválido: {cleaned!r}. Ejemplo válido: usuario@dominio.com",
        )
    if len(cleaned) > 120:
        raise HTTPException(status_code=400, detail="Email demasiado largo (máx 120 caracteres)")
    return cleaned.lower()


def validate_phone(value: str | None) -> str | None:
    """Return phone or None. Raise 400 if non-blank but not all digits.

    Accepts Paraguay formats with optional + prefix.
    """
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    # Strip spaces, dashes, parentheses before checking
    digits_only = re.sub(r"[\s\-\(\)]", "", cleaned)
    if not PHONE_RE.match(digits_only):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Teléfono inválido: {cleaned!r}. "
                "Usá solo dígitos (ej. 0981234567 o +595981234567)"
            ),
        )
    if len(cleaned) > 32:
        raise HTTPException(status_code=400, detail="Teléfono demasiado largo")
    return cleaned


def validate_ruc(value: str | None) -> str | None:
    """Return RUC or None. Paraguay RUC: X.XXX.XXX or XXXXXXX-X."""
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    if not RUC_RE.match(cleaned):
        raise HTTPException(
            status_code=400,
            detail=f"RUC inválido: {cleaned!r}. Formato: X.XXX.XXX o XXXXXXX-X",
        )
    if len(cleaned) > 20:
        raise HTTPException(status_code=400, detail="RUC demasiado largo")
    return cleaned


def validate_cedula(value: str | None) -> str | None:
    """Return cédula or None. Paraguay CI: X.XXX.XXX or just digits."""
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    if not CEDULA_RE.match(cleaned):
        raise HTTPException(
            status_code=400,
            detail=f"Cédula inválida: {cleaned!r}. Formato: X.XXX.XXX",
        )
    if len(cleaned) > 12:
        raise HTTPException(status_code=400, detail="Cédula demasiado larga")
    return cleaned


def validate_url(value: str | None) -> str | None:
    """Return URL or None. Reject if non-blank and not http(s)."""
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    if not (cleaned.startswith(("http://", "https://"))):
        raise HTTPException(
            status_code=400,
            detail=f"URL inválida: {cleaned!r}. Debe empezar con http:// o https://",
        )
    if len(cleaned) > 256:
        raise HTTPException(status_code=400, detail="URL demasiado larga (máx 256)")
    return cleaned


def parse_date_iso(value: str | None, *, field: str = "fecha") -> str | None:
    """Validate YYYY-MM-DD format. Returns the cleaned string or None if blank."""
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", cleaned):
        raise HTTPException(
            status_code=400,
            detail=f"{field} inválida: {cleaned!r}. Formato: YYYY-MM-DD",
        )
    return cleaned


# C2: URL-safe slug normalization.
# Used by /m/{slug} tablet-menu URLs and the product-form auto-suggest.
_SLUG_RE = re.compile(r"[^a-z0-9-]+")
_SLUG_DASH_RE = re.compile(r"-{2,}")


def slugify(value: str | None, *, fallback: str = "item", max_len: int = 60) -> str:
    """Normalize a free-text string into a URL-safe slug.

    Strips accents (NFD decomposition), lowercases, replaces every
    non-``[a-z0-9-]`` run with a single dash, and trims leading/trailing
    dashes. Returns ``fallback`` when the cleaned value is empty (e.g.,
    user typed only punctuation).

    ``max_len`` is enforced after cleanup; the function never raises on
    long input — it just truncates. Use ``validate_slug`` to enforce
    strict bounds and raise HTTP 400 on invalid input.
    """
    cleaned = (value or "").strip().lower()
    # Strip accents: NFD + remove combining marks.
    cleaned = unicodedata.normalize("NFKD", cleaned).encode("ascii", "ignore").decode("ascii")
    # Replace non-alphanumeric runs with a single dash.
    cleaned = _SLUG_RE.sub("-", cleaned)
    cleaned = _SLUG_DASH_RE.sub("-", cleaned).strip("-")
    if not cleaned:
        return fallback
    return cleaned[:max_len]


def validate_slug(
    value: str | None,
    *,
    field: str = "slug",
    max_len: int = 60,
    required: bool = False,
) -> str | None:
    """Validate a user-supplied slug and return the cleaned string.

    Rules:
      - blank + ``required=False`` → ``None``
      - blank + ``required=True`` → 400
      - non-lowercase / non-alphanumeric / non-dash chars are rejected
        (we don't auto-fix on input — silently changing what the user
        typed is worse than asking them to retype)
      - length > ``max_len`` → 400
      - leading/trailing dash rejected
    """
    raw = (value or "").strip()
    if not raw:
        if required:
            raise HTTPException(status_code=400, detail=f"{field} es obligatorio")
        return None
    if len(raw) > max_len:
        raise HTTPException(
            status_code=400,
            detail=f"{field} demasiado largo (máx {max_len} caracteres)",
        )
    if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", raw):
        raise HTTPException(
            status_code=400,
            detail=(
                f"{field} inválido: {raw!r}. "
                "Usá solo letras minúsculas, números y guiones medios, "
                "sin espacios ni acentos."
            ),
        )
    return raw


__all__ = [
    "optional_text",
    "parse_date_iso",
    "parse_money_gs",
    "parse_quantity",
    "parse_unit",
    "require_text",
    "slugify",
    "validate_cedula",
    "validate_email",
    "validate_phone",
    "validate_ruc",
    "validate_slug",
    "validate_url",
]
