"""Migration 092: drop sale_stock_move (BACKLOG #1 complete).

Final step of the sale_stock_move → stock_movement consolidation.

Prerequisites (already shipped in this session):
  - Migration 090: added `stock_movement.affected_recipe_id` column
  - Migration 091: backfilled existing stock_movement rows from
    sale_stock_move.affected_recipe_id
  - costing.py: writes ONLY stock_movement on each sale (no more
    dual-write). Both legacy and new code paths now populate the
    stock_movement row with affected_recipe_id.
  - All read paths (food_cost, inventory_intel, forecast, routers)
    migrated to stock_movement.
  - demo_reset, export_csv, sales router detail page: migrated.

This migration drops the sale_stock_move table. The SaleStockMove
ORM class is kept as a no-table stub so any test fixture that
imports the symbol still resolves (it cannot be used to insert).

SQLite + Postgres: DROP TABLE IF EXISTS sale_stock_move.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text


def _migration_092_drop_sale_stock_move(conn: Any) -> None:
    """Drop the legacy sale_stock_move table."""
    # CASCADE handles any straggler FKs. SQLite supports CASCADE in
    # DROP TABLE since 3.35 (we're on 3.4x+).
    conn.execute(text("DROP TABLE IF EXISTS sale_stock_move"))

    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 92)
