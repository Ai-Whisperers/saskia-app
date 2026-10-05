"""Migration 101: add recipe.fermentation_minutes column.

T-2026-10-05 (B.3): recipes for masa madre / poolish / preferments need
many hours of fermentation before baking. The operator currently has to
mentally compute "if tomorrow's pan starts at 06:00 and pan masa madre
takes 14h, I need to start it at 16:00 today". The new column makes
that an explicit field, so /produccion can show a per-row reminder
("Fermentar 14h — empezar 16:00 hoy, listo 06:00 mañana").

Schema:
  - ADD COLUMN recipe.fermentation_minutes INTEGER NULL
    - NULL = no fermentation step (e.g., quick breads)
    - > 0 = the recipe needs N hours of bulk fermentation before bake
    - Suggested values: 4-8h for poolish, 12-16h for masa madre, 24-72h
      for levain builds

Idempotent: try/except on every ALTER TABLE.
"""

from typing import Any

from sqlalchemy import text


def _migration_101_recipe_fermentation_minutes(conn: Any) -> None:
    """Add recipe.fermentation_minutes column."""
    try:
        dialect_name = conn.dialect.name
    except Exception:
        dialect_name = "sqlite"

    try:
        if dialect_name == "sqlite":
            conn.execute(text("ALTER TABLE recipe ADD COLUMN fermentation_minutes INTEGER"))
        else:
            conn.execute(text("ALTER TABLE recipe ADD COLUMN fermentation_minutes INTEGER"))
    except Exception:  # noqa: S110 — column may already exist
        pass

    # BACKLOG #4 (2026-10-02): always bump schema_version at the end.
    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 101)
