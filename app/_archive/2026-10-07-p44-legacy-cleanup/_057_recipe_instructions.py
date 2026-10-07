"""Migration: Add recipe.instructions column.

Stores the preparation sequence as a JSON array of phases. Each phase has:
  {phase, title, steps}
where steps is a list of free-form voseo Spanish strings (commands to the baker).

This column was added to the ORM (Recipe.instructions) during the receta_detalle
UX work (branch fix/receta-detalle-ux). The DB was missing the column, which
caused every Recipe SELECT to raise `OperationalError: no such column:
recipe.instructions` in production — the route's exception handler rendered a
200 with empty context, so every /recetas/<id> page looked broken.

This migration closes the ORM↔DB gap. Idempotent via try/except.
"""

from typing import Any

from sqlalchemy import text

from app.rms.db import _bump_schema_version


def _migration_057_recipe_instructions(conn: Any) -> None:
    """Add recipe.instructions (TEXT, nullable) for JSON phase storage."""
    # Idempotent: create_all may have already added the column via the
    # ORM model before migrations run; ALTER would then fail.
    try:
        conn.execute(text("ALTER TABLE recipe ADD COLUMN instructions TEXT"))
    except Exception:
        pass  # column already exists

    _bump_schema_version(conn, 57)
