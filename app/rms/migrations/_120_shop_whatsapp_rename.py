"""Migration 120 — SASKIA-215: rename SettingsKV key 'shop_whatsapp'
to 'sales.shop_whatsapp' (registry-backed namespacing).

Why: the new settings_registry (SASKIA-215, 2026-10-12) adds
sales.shop_whatsapp to the canonical settings. The legacy
un-namespaced 'shop_whatsapp' key (written by /api/settings/shop-whatsapp
and read by /menu) is no longer touched. To preserve operator-
configured values across this rename, we copy the legacy row to
the new key (idempotent — KV-wins if both already exist), then
delete the legacy row.

Idempotent: the copy step is a no-op if 'sales.shop_whatsapp'
already exists. The delete step is a no-op if the legacy key
doesn't exist. Re-running the migration on the same DB is safe.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

LEGACY_KEY = "shop_whatsapp"
NEW_KEY = "sales.shop_whatsapp"


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _migration_120_shop_whatsapp_rename(conn: Any) -> None:
    """Copy the legacy 'shop_whatsapp' row to 'sales.shop_whatsapp',
    then delete the legacy row.

    - Skip if no legacy row exists (fresh install — no copy needed).
    - Skip the copy if 'sales.shop_whatsapp' already exists (KV-wins;
      this could happen if the seeder ran in the same window).
    - Always delete the legacy row when it exists, even if we
      didn't copy (the legacy key is now read by no route, so it
      is dead state and should not accumulate).
    """
    legacy = conn.execute(
        text("SELECT value_json FROM settings_kv WHERE key = :k"),
        {"k": LEGACY_KEY},
    ).fetchone()

    if legacy is not None:
        # Check if new key already exists (KV-wins)
        existing = conn.execute(
            text("SELECT key FROM settings_kv WHERE key = :k"),
            {"k": NEW_KEY},
        ).fetchone()
        if existing is None:
            conn.execute(
                text(
                    "INSERT INTO settings_kv (key, value_json, updated_at) "
                    "VALUES (:k, :v, :ts)"
                ),
                {"k": NEW_KEY, "v": legacy[0], "ts": _now_iso()},
            )
        # Delete the legacy row regardless (the route no longer reads it)
        conn.execute(
            text("DELETE FROM settings_kv WHERE key = :k"),
            {"k": LEGACY_KEY},
        )

    # Bump INSIDE this function — each migration owns its own bump
    # (renumbering/automated replaces of these calls corrupt siblings).
    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 120)
