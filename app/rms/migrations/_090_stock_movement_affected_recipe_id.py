"""Migration 090: stock_movement.affected_recipe_id (BACKLOG #1 prep).

The full sale_stock_move → stock_movement consolidation (#1) requires
every column SaleStockMove has to also exist on StockMovement so the
two tables can be merged. SaleStockMove carries `affected_recipe_id`
to record WHICH recipe each ingredient came from (sub-recipe
traceability — StockMovement had no equivalent).

This migration adds `affected_recipe_id` to stock_movement, nullable
(only populated for sale movements). Future work will:
  1. Backfill stock_movement.affected_recipe_id from sale_stock_move
  2. Drop sale_stock_move
  3. Update callers

Doing the column-add now means callers can start writing both the
recipe-id and the audit row in one transaction, which keeps the
backfill cheap when #1 lands.
"""
from typing import Any


def _migration_090_stock_movement_affected_recipe_id(conn: Any) -> None:
    """Add stock_movement.affected_recipe_id nullable FK.

    SQLite quirk: `ALTER TABLE ... ADD COLUMN` doesn't support
    `IF NOT EXISTS`. We probe sqlite_schema (SQLite-only; Postgres
    uses information_schema) before adding so the migration is
    idempotent on both engines.
    """
    from sqlalchemy import text as _text

    # Probe: does the column already exist? SQLite keeps schema in
    # sqlite_schema; Postgres in information_schema.columns.
    dialect = conn.dialect.name if hasattr(conn, "dialect") else None
    if dialect == "sqlite":
        rows = conn.execute(_text("PRAGMA table_info(stock_movement)")).all()
        col_names = {row[1] for row in rows}
        if "affected_recipe_id" not in col_names:
            conn.execute(
                _text("ALTER TABLE stock_movement ADD COLUMN affected_recipe_id INTEGER")
            )
    else:
        # Postgres: information_schema.columns is portable.
        present = conn.execute(
            _text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name='stock_movement' AND column_name='affected_recipe_id'"
            )
        ).first()
        if present is None:
            conn.execute(
                _text(
                    "ALTER TABLE stock_movement "
                    "ADD COLUMN affected_recipe_id INTEGER"
                )
            )

    conn.execute(
        _text(
            "CREATE INDEX IF NOT EXISTS ix_stock_movement_affected_recipe_id "
            "ON stock_movement (affected_recipe_id)"
        )
    )

    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 90)
