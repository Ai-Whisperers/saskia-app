"""Migration 089: Add Ingredient.avg_cost_gs for moving-average cost tracking.

Sprint 4.4 / BACKLOG #13 (2026-10-02): Waste (merma) deducts stock but
does not update the per-ingredient average cost. The latest supplier
price (purchase_price_gs) is used for cost math in analytics, which
silently hides cost drift when supplier prices change mid-batch.

Adds one nullable column:
- ingredient.avg_cost_gs INTEGER — moving-average cost per unit in Gs.

NULL means "not yet computed". Analytics fall back to purchase_price_gs
when this is NULL, so behaviour is unchanged for legacy data.

Backfill: copy purchase_price_gs into avg_cost_gs for existing rows.
This is conservative — it uses the latest supplier price as the
initial "average" rather than leaving everything NULL. From this point
on, waste events keep the column up to date.

Postgres-side: ALTER COLUMN TYPE is not needed (Integer maps to INTEGER
on both dialects).
"""

from typing import Any

from sqlalchemy import text


def _migration_097_ingredient_avg_cost(conn: Any) -> None:
    """Add avg_cost_gs column to ingredient table (idempotent).

    Also backfills from purchase_price_gs where avg_cost_gs is NULL and
    purchase_price_gs is not NULL — conservative initial value.
    """
    from app.rms.db import atomic_ddl_block

    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"

    # Detect existing columns
    if dialect == "postgresql":
        existing_cols = conn.execute(
            text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'ingredient'
            """)
        ).fetchall()
        existing = {row[0] for row in existing_cols}
    else:
        existing_cols = conn.execute(text("PRAGMA table_info(ingredient)")).fetchall()
        # PRAGMA table_info: cid, name, type, notnull, dflt_value, pk
        existing = {row[1] for row in existing_cols}

    # BACKLOG #4 (2026-10-02): wrap DDL in atomic_ddl_block so each
    # ADD COLUMN/UPDATE is its own SAVEPOINT on Postgres (DDL auto-commits
    # there). On SQLite, the helper just runs the SQL directly.
    if "avg_cost_gs" not in existing:
        atomic_ddl_block(conn, ["ALTER TABLE ingredient ADD COLUMN avg_cost_gs INTEGER"])

    # Backfill from purchase_price_gs (conservative initial value).
    # Idempotent: WHERE avg_cost_gs IS NULL skips already-filled rows.
    atomic_ddl_block(
        conn,
        [
            "UPDATE ingredient "
            "SET avg_cost_gs = purchase_price_gs "
            "WHERE avg_cost_gs IS NULL AND purchase_price_gs IS NOT NULL"
        ],
    )

    # BACKLOG #4 (2026-10-02): migrations 085+ shipped without bumping
    # schema_version, silently breaking fresh installs. Sprint 4.5 fixed.
    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 97)
