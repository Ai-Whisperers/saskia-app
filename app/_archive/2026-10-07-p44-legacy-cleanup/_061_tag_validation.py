"""Migration 061: Add ingredient.tag_validation_issues column.

Background: With the new allergen-driven tag derivation (tagging/ module,
2026-09-29), we can detect logical contradictions in an ingredient's tags:

  - declares 'vegano' but contains dairy/eggs allergens
  - declares 'sin gluten' but allergens include gluten
  - declares 'vegetariano' but name suggests meat/fish
  - sin tacc declared while may_contain_gluten is set

audit.backfill_validation_issues() runs after this migration and
populates the column for every existing ingredient. The UI reads this
column to surface warnings in the inventory page (zero round-trips on
the read path; recomputed only when allergens/dietary_tags change).

Idempotent: try/except around the ALTER.
"""

from typing import Any

from sqlalchemy import text

from app.rms.db import _bump_schema_version


def _migration_061_tag_validation(conn: Any) -> None:
    """Add ingredient.tag_validation_issues (TEXT, nullable)."""
    try:
        conn.execute(text("ALTER TABLE ingredient ADD COLUMN tag_validation_issues TEXT"))
    except Exception:  # noqa: BLE001, S110 — column may already exist
        pass

    _bump_schema_version(conn, 61)


def run_post_migration(session: Any) -> int:
    """Backfill tag_validation_issues for every ingredient.

    Called from the migration runner after _migration_061_tag_validation.
    Returns the count of ingredients updated.
    """
    from app.rms.tagging.audit import backfill_validation_issues

    return backfill_validation_issues(session)
