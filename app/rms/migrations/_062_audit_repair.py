"""Migration 062: Auto-repair contradictory ingredient tags.

When `audit_all_ingredients()` flags an ingredient whose `dietary_tags`
conflict with its `allergens` column, this migration uses the
allergens column as source of truth and drops the conflicting tags.

Specifically: Panceta and Pan rallado both have `allergens="gluten"` but
declare `sin gluten` (and `vegano`/`vegetariano`). The allergens column
is the operator's most recent and most explicit declaration, so it wins.
After this migration:

  #62 Panceta:    sin gluten / sin tacc / keto removed (allergens=gluten)
  #66 Pan rallado: sin gluten / sin tacc removed (allergens=gluten)

The audit page will then show 0 issues.

Why a separate migration (not just auto-run from /auditoria-etiquetas/rerun):
  - Reversibility: a migration is a single recorded event. If something
    goes wrong, the operator can read the row count and revert.
  - Boot-time guarantee: every fresh deploy gets the repair, even if no
    operator clicks the button.

Idempotent: re-running does nothing once all tags are consistent.
"""

from typing import Any

from sqlalchemy import text

from app.rms.db import _bump_schema_version


def _migration_062_audit_repair(conn: Any) -> None:
    """No schema change. Just bump version."""
    _bump_schema_version(conn, 62)


def run_post_migration(session) -> dict[str, int]:
    """Run audit repair. Returns { 'repaired_ingredients': N, 'tags_removed': M }.

    Called from the migration runner after _migration_062_audit_repair.
    Also refreshes Ingredient.tag_validation_issues so the audit page
    reflects the new state immediately.
    """
    from app.rms.tagging.audit import backfill_validation_issues
    from app.rms.tagging.audit_repair import repair_all_ingredients

    changes = repair_all_ingredients(session)
    tags_removed = sum(len(v) for v in changes.values())
    session.flush()

    # Re-run the audit so the cached validation issues column reflects
    # the freshly-repaired state (otherwise the audit page would still
    # show the old issues until the next save).
    backfill_validation_issues(session)

    session.commit()
    return {
        "repaired_ingredients": len(changes),
        "tags_removed": tags_removed,
    }
