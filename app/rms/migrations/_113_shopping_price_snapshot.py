"""Migration 113 — SASKIA-206: unit price snapshot on shopping_list_item.

Adds `unit_price_snapshot_gs` (nullable INTEGER) to shopping_list_item.
When a list row is created, the ingredient's current purchase_price_gs
is frozen onto the row, so re-opening an old list shows the price that
was quoted when the row was written — not today's (possibly changed)
catalog price.

Nullable on purpose: rows created before this migration have no
snapshot; the UI falls back to the live ingredient price for them.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text


def _migration_113_shopping_price_snapshot(conn: Any) -> None:
    """Add unit_price_snapshot_gs to shopping_list_item (idempotent)."""
    cols = conn.execute(text("PRAGMA table_info(shopping_list_item)")).fetchall()
    have = {row[1] for row in cols}
    if "unit_price_snapshot_gs" not in have:
        conn.execute(
            text("ALTER TABLE shopping_list_item ADD COLUMN unit_price_snapshot_gs INTEGER")
        )
    # Bump INSIDE this function — each migration owns its own bump
    # (renumbering/automated replaces of these calls corrupt siblings).
    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 113)
