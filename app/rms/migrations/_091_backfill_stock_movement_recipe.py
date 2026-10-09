"""Migration 091: backfill stock_movement.affected_recipe_id from sale_stock_move.

Backlog #1 (partial): the cost record in `stock_movement` is now the
authoritative read path for sale-driven consumption, but only new
sales (written after migration 090) carry `affected_recipe_id`. To
make historical reporting complete, copy `sale_stock_move.affected_recipe_id`
over to matching `stock_movement` rows where:
  - stock_movement.reference_type = 'sale'
  - stock_movement.reference_id   = sale_stock_move.sale_id
  - stock_movement.ingredient_id  = sale_stock_move.ingredient_id
  - stock_movement.affected_recipe_id IS NULL

We match on (sale_id, ingredient_id) because the dual-write in
costing.py emits one SaleStockMove row per (recipe, ingredient) pair
in the recipe tree, and one StockMovement row per the same pair.

The migration is idempotent: it only fills NULLs. Running it twice
will not overwrite values populated by new sales after migration 090.

Following migrations: 092 drops the sale_stock_move table itself.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text


def _migration_091_backfill_stock_movement_recipe(conn: Any) -> None:
    """Backfill stock_movement.affected_recipe_id from sale_stock_move.

    SQLite + Postgres both support this UPDATE...FROM syntax. We use
    a CTE so the matching keys stay readable.

    Fresh-DB safety: if the sale_stock_move table does not exist
    yet (this happens on a brand-new DB where migration 090 ran but
    no earlier migration created the table), skip the UPDATE — there
    is nothing to backfill. Production databases that had
    sale_stock_move before migration 090 will have the table and
    the backfill runs as designed.
    """
    # Probe table existence (SQLite uses sqlite_schema; Postgres uses
    # information_schema.tables).
    dialect = conn.dialect.name if hasattr(conn, "dialect") else None
    if dialect == "sqlite":
        present = conn.execute(
            text("SELECT 1 FROM sqlite_schema WHERE type='table' AND name='sale_stock_move'")
        ).first()
    else:
        present = conn.execute(
            text("SELECT 1 FROM information_schema.tables WHERE table_name='sale_stock_move'")
        ).first()
    if present is not None:
        conn.execute(
            text(
                """
                UPDATE stock_movement
                   SET affected_recipe_id = (
                     SELECT ssm.affected_recipe_id
                       FROM sale_stock_move ssm
                      WHERE ssm.sale_id = stock_movement.reference_id
                        AND ssm.ingredient_id = stock_movement.ingredient_id
                   )
                 WHERE stock_movement.reference_type = 'sale'
                   AND stock_movement.affected_recipe_id IS NULL
                """
            )
        )

    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 91)
