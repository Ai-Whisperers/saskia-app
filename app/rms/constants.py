"""app/rms/constants.py — Business constants for Sazón.

Single source of truth for small, operator-relevant constants that don't
need their own DB table or settings UI:

  - Currency formatting (Gs., thousands separator)
  - Tax defaults (Paraguayan IVA, tax regime)
  - Invoice types (boleta_resimple, factura, none)
  - Stock status thresholds (overridable via /api/stock-status-config)
  - Costing defaults (labor, overhead, yield percentage)
  - Pagination defaults
  - Margin tier filter thresholds (now backed by `margin_tier` table)
  - Date range presets (now backed by `date_range_preset` table)

Per the static-content audit:
  - Phase 1-6: catalog tables (categories, channels, payment methods, tags,
    pricing, branding, message templates)
  - Phase 7: this module + margin_tier / stock_status_config tables

When to use this module:
  ✓ Reading a default that's overridable via DB
  ✗ Reading config that has its own table (use the table's helper module)
  ✗ Reading config that varies per request (use the request context)

When to add a constant here:
  - It's used in 2+ places
  - It might change in the future
  - It documents the business rule being enforced
"""

from __future__ import annotations

from decimal import Decimal

# ─── Currency ────────────────────────────────────────────────────────
CURRENCY_CODE = "PYG"
CURRENCY_SYMBOL = "Gs."
THOUSANDS_SEPARATOR = "."  # Paraguayan convention: 8.696.000


# ─── Tax (Paraguay) ────────────────────────────────────────────────
# Per Ley 125/91 Art. 91 inc. e — general IVA rate. Some products are
# exempt (medicines, books) at "exento" or reduced to "5".
DEFAULT_IVA_RATE = "10"
VALID_IVA_RATES = frozenset({"5", "10", "exento"})

DEFAULT_TAX_REGIME = "resimple"  # Most small businesses in Paraguay
VALID_TAX_REGIMES = frozenset({"resimple", "general"})

INVOICE_TYPES = frozenset({"boleta_resimple", "factura", "none"})
DEFAULT_INVOICE_TYPE = "boleta_resimple"


# ─── Stock status thresholds ──────────────────────────────────────
# These are DEFAULTS — operators can override via the stock_status_config
# table (migration 046) or via /api/stock-status-config. The DB values win
# when present.
DEFAULT_STOCK_RATIO_CRITICO = Decimal("0.5")  # stock_qty / min_stock_qty
DEFAULT_STOCK_RATIO_SOBRESTOCK = Decimal("5.0")  # stock_qty / min_stock_qty
DEFAULT_DEAD_STOCK_DAYS = 30  # no consumption in N days

# Status codes (used as keys in stock_status_config table)
STOCK_STATUS_BAJO_MIN = "bajo_min"
STOCK_STATUS_CRITICO = "critico"
STOCK_STATUS_SOBRESTOCK = "sobrestock"
STOCK_STATUS_MUERTO = "muerto"
ALL_STOCK_STATUSES = (
    STOCK_STATUS_BAJO_MIN,
    STOCK_STATUS_CRITICO,
    STOCK_STATUS_SOBRESTOCK,
    STOCK_STATUS_MUERTO,
)


# ─── Costing (overridable via ComplianceInfo) ─────────────────────
# These are FALLBACK defaults when ComplianceInfo doesn't have a row yet.
DEFAULT_LABOR_COST_PER_HOUR_GS = 25_000
DEFAULT_OVERHEAD_MULTIPLIER_PCT = 15
DEFAULT_YIELD_PERCENTAGE = Decimal("0.85")  # 15% moisture loss for breads


# ─── Pagination ───────────────────────────────────────────────────
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500


# ─── Margin tier filter thresholds ─────────────────────────────────
# Legacy hardcoded tiers (will move to `margin_tier` table in Phase 7).
# Kept here so older callers continue to work; new code should use the
# `margin_tier` table via app/rms/margin_tier.py:list_margin_tiers().
MARGIN_TIER_DEFAULTS = {
    "top_10": {"max_cost_gs": 10_000, "label": "Top 10% (≤ 10.000 Gs)"},
    "top_25": {"max_cost_gs": 5_000, "label": "Top 25% (≤ 5.000 Gs)"},
    "bottom_25": {"min_cost_gs": 1_000, "label": "Bottom 25% (≥ 1.000 Gs)"},
}


# ─── Date range presets ───────────────────────────────────────────
# Legacy hardcoded ranges; will move to `date_range_preset` table.
DATE_RANGE_PRESETS_DAYS = {
    "today": 1,
    "week": 7,
    "month": 30,
    "quarter": 90,
    "year": 365,
}


# ─── HACCP storage codes ──────────────────────────────────────────
# Free-text values used in ingredient.storage column. Could move to a table
# later but currently fine as a documented constant.
STORAGE_AMBIENT = "ambient"
STORAGE_REFRIGERATED = "refrigerated"
STORAGE_FROZEN = "frozen"
STORAGE_DRY = "dry"
ALL_STORAGE_TYPES = (
    STORAGE_AMBIENT,
    STORAGE_REFRIGERATED,
    STORAGE_FROZEN,
    STORAGE_DRY,
)


# ─── Pagination presets for date filter chips ────────────────────
DATE_FILTER_CHIPS = (
    ("Hoy", "today", 1),
    ("7 días", "week", 7),
    ("30 días", "month", 30),
    ("90 días", "quarter", 90),
)


__all__ = [
    "ALL_STOCK_STATUSES",
    "ALL_STORAGE_TYPES",
    # Currency
    "CURRENCY_CODE",
    "CURRENCY_SYMBOL",
    "DATE_FILTER_CHIPS",
    # Date range presets (legacy)
    "DATE_RANGE_PRESETS_DAYS",
    "DEFAULT_DEAD_STOCK_DAYS",
    "DEFAULT_INVOICE_TYPE",
    # Tax
    "DEFAULT_IVA_RATE",
    # Costing
    "DEFAULT_LABOR_COST_PER_HOUR_GS",
    "DEFAULT_OVERHEAD_MULTIPLIER_PCT",
    # Pagination
    "DEFAULT_PAGE_SIZE",
    # Stock status
    "DEFAULT_STOCK_RATIO_CRITICO",
    "DEFAULT_STOCK_RATIO_SOBRESTOCK",
    "DEFAULT_TAX_REGIME",
    "DEFAULT_YIELD_PERCENTAGE",
    "INVOICE_TYPES",
    # Margin tiers (legacy)
    "MARGIN_TIER_DEFAULTS",
    "MAX_PAGE_SIZE",
    "STOCK_STATUS_BAJO_MIN",
    "STOCK_STATUS_CRITICO",
    "STOCK_STATUS_MUERTO",
    "STOCK_STATUS_SOBRESTOCK",
    # Storage
    "STORAGE_AMBIENT",
    "STORAGE_DRY",
    "STORAGE_FROZEN",
    "STORAGE_REFRIGERATED",
    "THOUSANDS_SEPARATOR",
    "VALID_IVA_RATES",
    "VALID_TAX_REGIMES",
]

# ── Tag algebra (2026-09-24, refactored 2026-09-29) ──────────────────────
# Canonical Paraguayan bakery dietary-tag vocabulary. Single source of
# truth lives in app/rms/tagging/vocabulary.py — this re-export preserves
# backwards compatibility for code paths that still import from constants.
# New code should import from app.rms.tagging.vocabulary (or the
# app.rms.tagging package's __init__).
from app.rms.tagging.vocabulary import (
    CANONICAL_DIETARY_TAGS as _CANONICAL_DIETARY_TAGS_FROZENSET,
)

# Backwards-compat tuple (legacy code expects mutable indexable tuple).
CANONICAL_DIETARY_TAGS: tuple[str, ...] = tuple(_CANONICAL_DIETARY_TAGS_FROZENSET)
