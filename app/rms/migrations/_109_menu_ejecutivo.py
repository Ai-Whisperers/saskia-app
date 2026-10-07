"""Migration 109 (WP-4.2 menú ejecutivo, 2026-10-07): menu + menu_item.

Combo/menú ejecutivo: precio propio (no sumatoria); al vender se
expande a sus productos (stock y receta por producto). Nombres de
tabla `menu`/`menu_item` para evitar la colisión semántica con
combo-rows.js (labels de ui-combo) y target_combo (refund).
Idempotente + self-bump 109 (house idiom _104.._108).
"""

from __future__ import annotations

from typing import Any


def _migration_109_menu_ejecutivo(conn: Any) -> None:
    """Create menu + menu_item (menús ejecutivos)."""
    if conn.dialect.name == "postgresql":
        try:
            conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        except Exception:  # noqa: S110
            pass

    def _tables_missing() -> bool:
        if conn.dialect.name == "sqlite":
            row = conn.exec_driver_sql(
                "SELECT COUNT(*) FROM sqlite_master "
                "WHERE type='table' AND name IN ('menu','menu_item')"
            ).scalar()
            return int(row or 0) < 2
        row = conn.exec_driver_sql(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name IN ('menu','menu_item')"
        ).scalar()
        return int(row or 0) < 2

    if _tables_missing():
        try:
            conn.exec_driver_sql(
                """
                CREATE TABLE menu (
                    id {PK},
                    tenant_id INTEGER NOT NULL DEFAULT 1,
                    name VARCHAR(120) NOT NULL,
                    price_gs INTEGER NOT NULL,
                    active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at {TS}
                )
                """.replace("{PK}", "SERIAL PRIMARY KEY" if conn.dialect.name == "postgresql" else "INTEGER PRIMARY KEY AUTOINCREMENT")
                .replace("{TS}", "TIMESTAMPTZ DEFAULT now()" if conn.dialect.name == "postgresql" else "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            )
            conn.exec_driver_sql(
                """
                CREATE TABLE menu_item (
                    id {PK},
                    menu_id INTEGER NOT NULL REFERENCES menu(id) ON DELETE CASCADE,
                    product_id INTEGER NOT NULL REFERENCES product(id) ON DELETE CASCADE,
                    qty FLOAT NOT NULL DEFAULT 1
                )
                """.replace("{PK}", "SERIAL PRIMARY KEY" if conn.dialect.name == "postgresql" else "INTEGER PRIMARY KEY AUTOINCREMENT")
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_menu_tenant_id ON menu (tenant_id)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_menu_item_menu_id ON menu_item (menu_id)"
            )
        except Exception:  # noqa: S110 — concurrent migration
            pass

    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 109)
