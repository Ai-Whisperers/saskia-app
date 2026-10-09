"""app/rms/settings.py — SettingsKV-backed runtime config helpers.

Phase 2 of the static-content audit. Replaces hardcoded values like the
pricing.suggested_markup multiplier (was hardcoded as 3.0 in three places).

API:
- get_pricing_markup(session) → dict {multiplier, round_to_gs}
- set_pricing_markup(session, multiplier, round_to_gs=1000)

The default fallback when the SettingsKV row is missing matches the legacy
hardcoded behavior, so the migration to settings-based config is invisible
to operators.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

# settings_get / settings_set are now defined in app.rms.settings_registry
# (the SettingsKV layer). Re-import here so legacy callers of
# `from app.rms.settings_runtime import settings_get, settings_set`
# still work, and the historical bidirectional cycle is broken.
from app.rms.settings_registry import settings_get, settings_set

# Pricing defaults (legacy hardcoded values)
DEFAULT_PRICING_MARKUP = {"multiplier": 3.0, "round_to_gs": 1000}


def get_pricing_markup(session: Session) -> dict:
    """Return the suggested-pricing markup config.

    Returns dict with keys: multiplier (float), round_to_gs (int).
    Defaults to {multiplier: 3.0, round_to_gs: 1000} when missing.
    """
    cfg = settings_get(session, "pricing.suggested_markup", DEFAULT_PRICING_MARKUP)
    # Defensive: coerce types and fill missing keys with defaults.
    out = dict(DEFAULT_PRICING_MARKUP)
    if isinstance(cfg, dict):
        if "multiplier" in cfg:
            try:
                out["multiplier"] = float(cfg["multiplier"])
            except (TypeError, ValueError):
                pass
        if "round_to_gs" in cfg:
            try:
                out["round_to_gs"] = int(cfg["round_to_gs"])
            except (TypeError, ValueError):
                pass
    return out


def set_pricing_markup(session: Session, multiplier: float, round_to_gs: int = 1000) -> dict:
    """Update the pricing markup config. Returns the new value."""
    if multiplier <= 0:
        raise ValueError("multiplier must be > 0")
    if round_to_gs <= 0:
        raise ValueError("round_to_gs must be > 0")
    cfg = {"multiplier": float(multiplier), "round_to_gs": int(round_to_gs)}
    settings_set(session, "pricing.suggested_markup", cfg)
    return cfg


def compute_suggested_price(cost_gs: int, markup_cfg: dict | None = None) -> int:
    """Pure helper: compute the suggested retail price from a cost.

    Used by both Python (recipes.py, costing.py) and exposed for the JS
    front-end via /api/settings/pricing-markup which returns the same
    formula.

    Args:
        cost_gs: batch or unit cost in integer Gs.
        markup_cfg: dict with 'multiplier' and 'round_to_gs'. Defaults to
            DEFAULT_PRICING_MARKUP when None.

    Returns:
        Rounded suggested retail price in integer Gs.
    """
    if markup_cfg is None:
        markup_cfg = DEFAULT_PRICING_MARKUP
    mult = float(markup_cfg.get("multiplier", 3.0))
    rnd = int(markup_cfg.get("round_to_gs", 1000))
    if rnd <= 0:
        return round(cost_gs * mult)
    # Round up to the nearest round_to_gs step (mirrors Math.ceil behavior in JS)
    import math

    return int(math.ceil(cost_gs * mult / rnd) * rnd)


# ─── Branding (Phase 5) ────────────────────────────────────────────────
# All branding assets are loaded by get_branding() and exposed in templates
# via {{ branding.* }}. Defaults match the Sazón starter; operators change
# values via /admin/branding (settings_ui.py). File uploads (logo, favicon,
# hero) land in app/static/branding/<id>/<filename>, served by /static/.

DEFAULT_BRANDING = {
    # Identity (shown on login, sidebar, tickets, PDF)
    "business_name": "Sazón",
    "tagline": "Panadería / Bakery — Sistema de gestión",
    "footer": "Sistema local",
    "business_type": "restaurant",  # restaurant, panaderia, cafeteria, bar, etc.
    # Visual assets (filenames inside app/static/branding/)
    "accent_color": "#f97316",  # primary color hex (#RRGGBB)
    "logo_filename": "",  # main logo (PNG/JPG/SVG, square ideal)
    "favicon_filename": "",  # browser tab icon (ICO/PNG 32x32 or 192x192)
    "hero_filename": "",  # login page background (1200x600 ideal)
    # Contact info (tickets, PDF)
    "contact_email": "",
    "contact_phone": "",
    "address": "",
    # Paraguay tax ID — printed on receipts (recibo.html) when set
    "ruc": "",
}


def get_branding(session: object) -> dict:
    """Return the branding dict with defaults for missing keys.

    The footer gets a trailing year (e.g. "· 2026") stripped at read time:
    base.html always appends the CURRENT year via now_year(), so a stored
    footer carrying its own year rendered as "2026 · 2026" (60-page
    critique G-4). Normalizing here fixes legacy DBs without a migration.
    """
    import re

    cfg = settings_get(session, "branding", {})
    out = dict(DEFAULT_BRANDING)
    if isinstance(cfg, dict):
        for k in DEFAULT_BRANDING:
            if k in cfg and isinstance(cfg[k], str):
                out[k] = cfg[k]
    out["footer"] = re.sub(r"\s*[·•\-–]\s*\d{4}\s*$", "", out["footer"]).strip()
    return out


def set_branding(session: object, **fields: object) -> dict:
    """Update branding fields. Returns the new full dict.

    Allowed keys: business_name, tagline, footer, business_type,
    accent_color, logo_filename, favicon_filename, hero_filename,
    contact_email, contact_phone, address.
    Each is validated to be a string and within reasonable length.
    """
    current = get_branding(session)
    for k, v in fields.items():
        if k not in DEFAULT_BRANDING:
            raise ValueError(f"Unknown branding key: {k!r}")
        if not isinstance(v, str):
            raise ValueError(f"branding.{k} must be a string")
        if len(v) > 500:
            raise ValueError(f"branding.{k} too long (max 500 chars)")
        current[k] = v
    settings_set(session, "branding", current)
    return current


# ─── Batch B: per-domain config helpers (2026-10-07) ─────────────────────
# Each domain has:
#   - DEFAULT_<DOMAIN>_CONFIG  module-level dict (frozen defaults)
#   - get_<domain>_config(session)  fetches from SettingsKV via SETTINGS
#     registry, returning a dict with all keys validated + coerced
#
# Consumer modules (loyalty/suggestions.py, services/eod_anomaly.py,
# observability/alerts.py, services/auto_backup.py) accept an optional
# <domain>_cfg dict kwarg. When None, they fall back to the module-level
# DEFAULT_<DOMAIN>_CONFIG. This keeps the pure-function contract while
# letting the operator override via /admin/settings.
# ────────────────────────────────────────────────────────────────────────


# ── Loyalty (B1) ──────────────────────────────────────────────────────────
DEFAULT_LOYALTY_CONFIG: dict[str, int] = {
    # LAPSED thresholds (days without a visit, by tier)
    "lapsed_days_bronze": 21,
    "lapsed_days_silver": 30,
    "lapsed_days_gold": 45,
    # LAPSED discount percent by tier (int 0–100)
    "lapsed_discount_pct_bronze": 10,
    "lapsed_discount_pct_silver": 7,
    "lapsed_discount_pct_gold": 5,
    # BIRTHDAY window + discount
    "birthday_window_days": 7,
    "birthday_discount_pct": 15,
    # POINTS-DORMANT
    "points_dormant_threshold": 50,
    # CROSS-SELL (reserved, not yet wired into a rule)
    "cross_sell_min_sales": 3,
    # Cap on returned suggestions
    "max_suggestions": 3,
}


def get_loyalty_config(session: Session) -> dict[str, int]:
    """Read the loyalty config dict from SettingsKV (one DB query).

    Returns a fresh dict every call (callers may mutate freely). Keys
    missing from the DB fall back to DEFAULT_LOYALTY_CONFIG values.
    """
    from app.rms.settings_registry import get_setting_value

    out = dict(DEFAULT_LOYALTY_CONFIG)
    for key in DEFAULT_LOYALTY_CONFIG:
        try:
            v = get_setting_value(session, f"loyalty.{key}")
            if v is not None:
                out[key] = int(v)
        except (ValueError, TypeError):
            # Stale or corrupt DB row — fall back to default silently.
            pass
    return out


# ── EOD anomaly detector (B2) ─────────────────────────────────────────────
DEFAULT_EOD_CONFIG: dict[str, int | float] = {
    "voided_rate_threshold": 0.10,  # fraction; > this → "tasa alta" anomaly
    "voided_rate_min_sales": 3,  # day with fewer sales skips the check
    "max_uninvoiced_ids_displayed": 10,  # email body slice cap
}


def get_eod_config(session: Session) -> dict[str, int | float]:
    """Read the EOD anomaly detector config from SettingsKV."""
    from app.rms.settings_registry import get_setting_value

    out = dict(DEFAULT_EOD_CONFIG)
    type_coerce = {
        "voided_rate_threshold": float,
        "voided_rate_min_sales": int,
        "max_uninvoiced_ids_displayed": int,
    }
    for key in DEFAULT_EOD_CONFIG:
        try:
            v = get_setting_value(session, f"eod.{key}")
            if v is not None:
                out[key] = type_coerce[key](v)
        except (ValueError, TypeError):
            pass
    return out


# ── Alert dispatch (B3) ───────────────────────────────────────────────────
DEFAULT_ALERTS_CONFIG: dict[str, int] = {
    "max_per_day": 50,  # rate limit on dispatch_anomalies()
}


def get_alerts_config(session: Session) -> dict[str, int]:
    """Read the alerts dispatch config from SettingsKV."""
    from app.rms.settings_registry import get_setting_value

    out = dict(DEFAULT_ALERTS_CONFIG)
    for key in DEFAULT_ALERTS_CONFIG:
        try:
            v = get_setting_value(session, f"alerts.{key}")
            if v is not None:
                out[key] = int(v)
        except (ValueError, TypeError):
            pass
    return out


# ── Auto-backup (B4) ──────────────────────────────────────────────────────
DEFAULT_BACKUP_CONFIG: dict[str, int] = {
    "auto_threshold_hours": 24,  # run auto-backup if last > N hours
    "warn_threshold_days": 7,  # show warning if last > N days
    "keep_last_n": 30,  # prune backups beyond this count
}


def get_backup_config(session: Session) -> dict[str, int]:
    """Read the backup config from SettingsKV."""
    from app.rms.settings_registry import get_setting_value

    out = dict(DEFAULT_BACKUP_CONFIG)
    for key in DEFAULT_BACKUP_CONFIG:
        try:
            v = get_setting_value(session, f"backup.{key}")
            if v is not None:
                out[key] = int(v)
        except (ValueError, TypeError):
            pass
    return out


# ── Rate limit (B5) ───────────────────────────────────────────────────────
DEFAULT_RATE_LIMIT_CONFIG: dict[str, int] = {
    "login_max_failures": 5,
    "login_window_minutes": 5,
    "write_max_per_minute": 10,
    "read_max_per_minute": 60,
    "read_window_seconds": 60,
}


def get_rate_limit_config(session: Session) -> dict[str, int]:
    """Read the rate-limit config from SettingsKV."""
    from app.rms.settings_registry import get_setting_value

    out = dict(DEFAULT_RATE_LIMIT_CONFIG)
    for key in DEFAULT_RATE_LIMIT_CONFIG:
        try:
            v = get_setting_value(session, f"rate_limit.{key}")
            if v is not None:
                out[key] = int(v)
        except (ValueError, TypeError):
            pass
    return out


# ── Pre-sale (B6) ────────────────────────────────────────────────────────
DEFAULT_PRE_SALE_CONFIG: dict[str, int] = {
    "max_qty_per_sale": 999,
    "max_discount_pct": 15,
    "low_stock_warn_pct": 25,
}


def get_pre_sale_config(session: Session) -> dict[str, int]:
    """Read the pre-sale config from SettingsKV.

    Used by app/rms/sales/pre_sale_check.py to make the pre-billing
    checklist (qty cap, discount %, low-stock warning) operator-tunable
    without code changes.
    """
    from app.rms.settings_registry import get_setting_value

    out = dict(DEFAULT_PRE_SALE_CONFIG)
    for key in DEFAULT_PRE_SALE_CONFIG:
        try:
            v = get_setting_value(session, f"pre_sale.{key}")
            if v is not None:
                out[key] = int(v)
        except (ValueError, TypeError):
            pass
    return out


__all__ = [
    "DEFAULT_ALERTS_CONFIG",
    "DEFAULT_BACKUP_CONFIG",
    "DEFAULT_BRANDING",
    "DEFAULT_EOD_CONFIG",
    "DEFAULT_LOYALTY_CONFIG",
    "DEFAULT_PRE_SALE_CONFIG",
    "DEFAULT_PRICING_MARKUP",
    "DEFAULT_RATE_LIMIT_CONFIG",
    "compute_suggested_price",
    "get_alerts_config",
    "get_backup_config",
    "get_branding",
    "get_eod_config",
    "get_loyalty_config",
    "get_pre_sale_config",
    "get_pricing_markup",
    "get_rate_limit_config",
    "set_branding",
    "set_pricing_markup",
    "settings_get",
    "settings_set",
]
