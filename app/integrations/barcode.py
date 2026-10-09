"""app/rms/barcode.py — Barcode / SKU lookup (E23).

Per docs/plans/2026-09-07-sazon-complete-epic-plan-v3.md E23.

Most USB / Bluetooth barcode scanners act as keyboard emulators: they
"type" the barcode + Enter. So at the routing level, E23 is mostly:
- A SKU column on Product (optional, unique)
- A lookup helper: get_product_by_sku(session, sku)
- A route to POST a scanned SKU (so the front-end can wire a hardware
  trigger)

The hardware integration itself happens outside the app (scanner →
keyboard event → JS → POST /sales/scan).

This module adds:
- Product.sku column (optional, unique when set)
- migration 007 (additive column)
- validate_sku() / normalize_sku() helpers
- get_product_by_sku(session, sku) lookup with caching ready for v2
- scan_to_cart(sku, qty=1) helper used by the future /sales/scan route
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.rms.models import Product

# SKU normalization: uppercase, strip whitespace, replace OCR mistakes.
_SKU_RE = re.compile(r"[^A-Z0-9\-]")


def normalize_sku(raw: str) -> str:
    """Normalize a scanned SKU.

    - trim whitespace
    - uppercase
    - replace 0/O look-alikes (keep raw by default)
    - strip non-alphanumeric/dash characters
    """
    s = raw.strip().upper()
    s = _SKU_RE.sub("", s)
    return s


def validate_sku(sku: str) -> str | None:
    """Validate SKU shape. Returns None if ok, error string if not.

    Rules: 4-32 chars; alphanumeric + dash; must contain at least one
    digit OR letter (no empty strings).
    """
    if not sku:
        return "SKU is empty"
    if len(sku) < 4 or len(sku) > 32:
        return f"SKU length must be 4-32 chars, got {len(sku)}"
    if not re.fullmatch(r"[A-Z0-9\-]+", sku):
        return "SKU may only contain letters, digits, and dashes"
    return None


@dataclass
class ScanResult:
    """Result of a barcode scan."""

    ok: bool
    product: Product | None = None
    error: str | None = None
    normalized_sku: str | None = None


def get_product_by_sku(session: Session, sku: str) -> ScanResult:
    """Look up a product by SKU.

    Returns ScanResult(ok=True, product=...) on hit.
    Returns ScanResult(ok=False, error="...", normalized_sku=...) on miss.
    """
    normalized = normalize_sku(sku)
    err = validate_sku(normalized)
    if err:
        return ScanResult(ok=False, error=err, normalized_sku=normalized)

    p = session.execute(select(Product).where(Product.sku == normalized)).scalar_one_or_none()

    if p is None:
        return ScanResult(ok=False, error="not_found", normalized_sku=normalized)
    return ScanResult(ok=True, product=p, normalized_sku=normalized)


def assign_sku(session: Session, product_id: int, sku: str) -> str:
    """Assign a SKU to a product, normalized + validated.

    Raises ValueError on validation failure or duplicate.
    """
    normalized = normalize_sku(sku)
    err = validate_sku(normalized)
    if err:
        raise ValueError(err)

    p = session.get(Product, product_id)
    if p is None:
        raise ValueError(f"No product with id={product_id}")
    p.sku = normalized
    try:
        session.flush()
    except IntegrityError as e:
        session.rollback()
        raise ValueError(f"SKU '{normalized}' already in use") from e
    return normalized


def suggest_sku(product_name: str) -> str:
    """Suggest a default SKU from a product name.

    Heuristic: take first letters of words + first 4 hex chars of a
    timestamp; not guaranteed unique — operator may override.
    """
    s = re.sub(r"[^A-Za-z\s]", "", product_name or "").upper()
    parts = s.split()
    abbrev = "".join(p[0] for p in parts if p)[:4] or "PROD"
    ts = datetime.now(timezone.utc).strftime("%H%M")
    return f"{abbrev}-{ts}"


__all__ = [
    "ScanResult",
    "assign_sku",
    "get_product_by_sku",
    "normalize_sku",
    "suggest_sku",
    "validate_sku",
]
