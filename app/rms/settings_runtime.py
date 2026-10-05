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

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import SettingsKV

# Pricing defaults (legacy hardcoded values)
DEFAULT_PRICING_MARKUP = {"multiplier": 3.0, "round_to_gs": 1000}


def settings_get(session: Session, key: str, default: Any = None) -> Any:
    """Read one key from settings_kv (parsed JSON). Returns default if missing."""
    row = session.execute(select(SettingsKV).where(SettingsKV.key == key)).scalar_one_or_none()
    if row is None:
        return default
    try:
        return json.loads(row.value_json)
    except (TypeError, ValueError):
        return default


def settings_set(session: Session, key: str, value: Any) -> None:
    """Upsert one key into settings_kv (serialized as JSON)."""
    import json as _json

    payload = _json.dumps(value)
    row = session.execute(select(SettingsKV).where(SettingsKV.key == key)).scalar_one_or_none()
    if row is None:
        row = SettingsKV(key=key, value_json=payload)
        session.add(row)
    else:
        row.value_json = payload
    session.flush()


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


__all__ = [
    "DEFAULT_BRANDING",
    "DEFAULT_PRICING_MARKUP",
    "compute_suggested_price",
    "get_branding",
    "get_pricing_markup",
    "set_branding",
    "set_pricing_markup",
    "settings_get",
    "settings_set",
]
