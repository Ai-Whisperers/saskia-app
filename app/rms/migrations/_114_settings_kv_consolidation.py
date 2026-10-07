"""Migration 114 — Sprint 2.1: settings consolidation data copy (AppMeta → settings_kv).

Copies operator-customized values out of the legacy string-keyed
AppMeta table into the canonical JSON settings_kv table, then deletes
the copied AppMeta rows. Keys copied:

- The 42 registry keys from the old app/rms/settings.py (now
  app/rms/settings_registry.py) — e.g. production.demand_snapshot_ttl_seconds.
- The legacy router keys written by /settings (business_name,
  business_ruc, business_address, business_phone, business_email,
  theme, timbrado, punto_expedicion, invoice_sequence).

AppMeta rows NOT in this list (eod markers, last_backup_at, seed
flags, etc.) are left untouched — AppMeta remains the store for
non-settings operational state.

Idempotent: a key already present in settings_kv is NOT overwritten.
Rows with empty-string values are skipped (meaning "never customized").
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

# The 42 registry keys (settings_registry.SETTINGS) + legacy router keys.
REGISTRY_KEYS: list[str] = [
    "general.business_name",
    "general.currency_symbol",
    "general.decimal_places",
    "general.tax_mode",
    "general.locale",
    "general.timezone",
    "ui.theme",
    "branding.business_name",
    "branding.tagline",
    "branding.business_type",
    "branding.logo_filename",
    "branding.favicon_filename",
    "branding.hero_filename",
    "branding.primary_color",
    "branding.contact_email",
    "branding.contact_phone",
    "branding.address",
    "inventory.default_min_stock",
    "inventory.alert_lead_time_days",
    "inventory.stale_days",
    "inventory.default_unit",
    "inventory.auto_deduct_on_sale",
    "inventory.warn_negative_stock",
    "sales.default_payment_method",
    "sales.require_customer_for_evento",
    "sales.max_void_hours",
    "sales.print_receipt_on_post",
    "sales.low_stock_warning_threshold",
    "dashboard.default_period",
    "dashboard.chart_style",
    "dashboard.show_margins",
    "dashboard.daily_summary_optin",
    "dashboard.top_n_products",
    "backup.daily_backup_enabled",
    "backup.notification_email",
    "backup.retention_days",
    "session.session_lifetime_hours",
    "session.remember_me_days",
    "session.max_concurrent_per_user",
    "demo.banner_enabled",
    "demo.reset_seed_enabled",
    "production.demand_snapshot_ttl_seconds",
    # Legacy /settings router keys (AppMeta string rows)
    "business_name",
    "business_ruc",
    "business_address",
    "business_phone",
    "business_email",
    "theme",
    "timbrado",
    "punto_expedicion",
    "invoice_sequence",
]


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _migration_114_settings_kv_consolidation(conn: Any) -> None:
    """Copy settings-ish AppMeta rows → settings_kv, then delete them."""
    copied = 0
    for key in REGISTRY_KEYS:
        row = conn.execute(text("SELECT value FROM app_meta WHERE key = :k"), {"k": key}).fetchone()
        if row is None:
            continue
        value = row[0]
        if value is None or value == "":
            continue  # never customized
        existing = conn.execute(
            text("SELECT key FROM settings_kv WHERE key = :k"), {"k": key}
        ).fetchone()
        if existing is not None:
            continue  # idempotent: KV wins
        payload = (
            value if value.startswith(("{", "[", '"')) else json.dumps(value, ensure_ascii=False)
        )
        conn.execute(
            text("INSERT INTO settings_kv (key, value_json, updated_at) VALUES (:k, :v, :ts)"),
            {"k": key, "v": payload, "ts": _now_iso()},
        )
        conn.execute(text("DELETE FROM app_meta WHERE key = :k"), {"k": key})
        copied += 1

    # Bump INSIDE this function — each migration owns its own bump
    # (renumbering/automated replaces of these calls corrupt siblings).
    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 114)
