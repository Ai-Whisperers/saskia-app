"""Migration 117: Add Ingredient.image_url column.

Saskia product images (cherry-picked via 7d18b05a..d6d5045b in the
2026-10-09 image deploy) and recipe images are already wired:
- Product.image_url exists from migration 090
- Recipe.image_url exists from the HEREBUS integration
- Ingredient.image_url was the only one missing

This migration adds the column so future ingredient image generation
(documented in data/ingredient_visuals.py as a prompt generator, not
yet a real image pipeline) has a place to land. The column is nullable
so existing 94 seeded ingredients are not affected; no backfill is
performed because there are no ingredient images yet to reference
(app/static/ingredients/ is empty).

Patterned after _097_ingredient_avg_cost.py which added avg_cost_gs
to the same table. Uses atomic_ddl_block so the ADD COLUMN is its
own SAVEPOINT on Postgres (DDL auto-commits there) and a no-op
SQL statement on SQLite.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text


def _migration_117_ingredient_image_url(conn: Any) -> None:
    """Add image_url column to ingredient table (idempotent)."""
    from app.rms.db import _bump_schema_version, atomic_ddl_block

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

    if "image_url" not in existing:
        # Match the existing Product/Recipe image_url width: VARCHAR(255) on
        # product (migration 090) and VARCHAR(255) on recipe (HEREBUS).
        # SQLite is loosely typed, so VARCHAR is just a hint; on Postgres
        # this is the actual column type.
        if dialect == "postgresql":
            atomic_ddl_block(
                conn,
                ["ALTER TABLE ingredient ADD COLUMN image_url VARCHAR(255)"],
            )
        else:
            atomic_ddl_block(
                conn,
                ["ALTER TABLE ingredient ADD COLUMN image_url VARCHAR(255)"],
            )

    _bump_schema_version(conn, 117)
