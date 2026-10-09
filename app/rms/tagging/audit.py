"""app/rms/tagging/audit.py — Batch consistency checks.

Used by:
  - CLI: `python -m app.rms.tagging.audit` for one-off data audits.
  - Inventory page: shows audit results in a "tag validation" panel.
  - Migration v61 (run after the migration that adds the
    tag_validation_issues column to Ingredient).

Public API:
  audit_all_ingredients(session) -> dict[int, list[str]]
  audit_recipe_tags(session, recipe_id) -> dict[str, list[str]]
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session


def audit_all_ingredients(session: Session) -> dict[int, list[str]]:
    """Returns {ingredient_id: [validation issues]} for every ingredient
    with at least one issue.  Empty dict = nothing to fix.

    Used by the inventory page warning banner and the audit CLI.
    Persisted to Ingredient.tag_validation_issues by migration v61 +
    a post-migration backfill.
    """
    # Lazy import to avoid circular at module load.
    from app.rms.models import Ingredient
    from app.rms.tagging.classify import validate_ingredient

    issues_by_id: dict[int, list[str]] = {}
    for ing in session.scalars(select(Ingredient)).all():
        inv = validate_ingredient(ing)
        if inv:
            issues_by_id[ing.id] = inv
    return issues_by_id


def audit_recipe_tags(
    session: Session,
    recipe_id: int,
) -> dict[str, object]:
    """Returns a structured report of derivation results.

    Used by the receta detail page to surface:
      - which dietary tags are kept (intersection)
      - which dietary tags are blocked (and by which lines)
      - which ingredients have undeclared allergens
      - any cycles detected in the recipe tree
    """
    from app.rms.tagging.derive import derive_recipe_tags

    d = derive_recipe_tags(session, recipe_id)
    return {
        "kept_tags": d.dietary,
        "blocked_tags": list(d.blocked.keys()),
        "blocked_detail": d.blocked,
        "undeclared_allergens": d.undeclared,
        "cycles": d.cycles,
    }


def backfill_validation_issues(session: Session) -> int:
    """Compute tag_validation_issues for every ingredient and persist.

    Called from migration v61 after the column is added. Returns count
    of ingredients updated.
    """
    from app.rms.models import Ingredient

    issues_by_id = audit_all_ingredients(session)
    for ing_id, issues in issues_by_id.items():
        ing = session.get(Ingredient, ing_id)
        if ing is not None:
            ing.tag_validation_issues = "\n".join(issues)
    session.flush()
    return len(issues_by_id)


__all__ = [
    "audit_all_ingredients",
    "audit_recipe_tags",
    "backfill_validation_issues",
]
