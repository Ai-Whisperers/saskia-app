"""app/rms/tagging/audit_repair.py — One-shot data correction (migration v62).

Picks up where audit.validate_ingredient() reports contradictions, and
resolves them deterministically using `allergens` (the operator-declared
allergens column) as the source of truth. The audit surfaces warnings,
this module CLEANS them up.

Resolution rules (allergens column wins over dietary_tags claims):

  sin gluten declared + gluten allergen   → drop 'sin gluten' (and 'sin tacc')
  sin lactosa declared + dairy allergen   → drop 'sin lactosa'
  sin huevo declared + eggs allergen      → drop 'sin huevo'
  sin frutos secos declared + nuts        → drop 'sin frutos secos'
  vegano declared + dairy/eggs allergen  → drop 'vegano' (and 'vegetariano'
                                           if it's a stricter claim)
  vegetariano declared + name is meat    → drop 'vegetariano'
  sin tacc declared + may_contain_gluten → drop 'sin tacc' (cross-contaminated)

Each fix writes a row to the `data_migration_log` table (or prints to
stdout if the table is missing) so the operator can review what changed.

Idempotent: re-running does nothing once an ingredient's tags match.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

# (issue_text_substring, allergen_trigger, tags_to_remove)
# Order matters: more-specific rules first.
#
# A rule fires when its `substring` appears anywhere in the validator's
# issue string. We don't filter on allergen_trigger — the validator has
# already validated that the allergen exists.
_REPAIR_RULES: list[tuple[str, frozenset[str], frozenset[str]]] = [
    # allergen contradictions (allergens wins)
    (
        "sin gluten' but allergens include gluten",
        frozenset({"gluten"}),
        frozenset({"sin gluten", "sin tacc"}),
    ),
    (
        "sin tacc' but allergens include gluten",
        frozenset({"gluten"}),
        frozenset({"sin tacc", "sin gluten"}),
    ),
    ("sin lactosa' but allergens include dairy", frozenset({"dairy"}), frozenset({"sin lactosa"})),
    ("sin huevo' but allergens include eggs", frozenset({"eggs"}), frozenset({"sin huevo"})),
    (
        "sin frutos secos' but allergens include nuts",
        frozenset({"nuts"}),
        frozenset({"sin frutos secos"}),
    ),
    # 'vegano' but allergens include [anything that disqualifies vegan].
    # Validator currently only flags dairy/eggs; if it ever flags more
    # (e.g. meat allergens), this substring still matches.
    ("vegano' but allergens include", frozenset(), frozenset({"vegano"})),
    # vegetariano + name is meat → drop BOTH vegetariano and vegano
    # (vegano is stricter than vegetariano; if the ingredient isn't
    # even vegetarian, it definitely isn't vegan).
    ("vegetariano' but name suggests", frozenset(), frozenset({"vegetariano", "vegano"})),
    # may_contain_gluten overrides sin tacc
    ("sin tacc cannot be true", frozenset(), frozenset({"sin tacc", "sin gluten"})),
]


def repair_ingredient(ing: Any) -> list[str]:
    """Apply repair rules to one ingredient. Returns list of changes made.

    Returns [] if no changes needed.
    Each change is a human-readable string like "removed 'sin gluten'".

    Handles two classes of fixes:
      (a) Tag/Allergen contradictions — drop conflicting dietary_tags
          using allergens column as source of truth.
      (b) Category mismatches — if infer_category(name) disagrees with
          the stored category, swap to the inferred one. (Both #39 Café
          espresso → 'bebidas' and #70 Jengibre fresco → 'especias' are
          caught by this rule.)
    """
    from app.rms.tagging.classify import validate_ingredient

    issues = validate_ingredient(ing)
    if not issues:
        return []

    changes: list[str] = []
    changes = _repair_allergen_contradictions(ing, issues)
    if not changes:
        changes = _repair_category_mismatch(ing, issues)
    return changes


def _repair_allergen_contradictions(ing: Any, issues: list[str]) -> list[str]:
    """Repair tag/allergen contradictions. Returns list of changes.
    
    Extracted from repair_ingredient to reduce complexity.
    """
    declared_set = _get_declared_tags(ing)
    to_remove = _collect_tags_to_remove(issues)
    changes = _apply_tag_removals(ing, declared_set, to_remove)
    if changes:
        _persist_declared_tags(ing, declared_set)
    return changes


def _get_declared_tags(ing: Any) -> set[str]:
    """Get the set of declared dietary tags.
    
    Extracted from _repair_allergen_contradictions to reduce complexity.
    """
    declared_raw = getattr(ing, "dietary_tags", "") or ""
    return {t.strip() for t in declared_raw.split(",") if t.strip()}


def _collect_tags_to_remove(issues: list[str]) -> set[str]:
    """Collect tags that should be removed based on issues.
    
    Extracted from _repair_allergen_contradictions to reduce complexity.
    """
    to_remove: set[str] = set()
    for issue in issues:
        for substring, _allergen_trigger, tags_drop in _REPAIR_RULES:
            if substring in issue:
                to_remove |= tags_drop
                break
    return to_remove


def _apply_tag_removals(ing: Any, declared_set: set[str], to_remove: set[str]) -> list[str]:
    """Remove tags from declared_set and return change messages.
    
    Extracted from _repair_allergen_contradictions to reduce complexity.
    """
    changes: list[str] = []
    for tag in to_remove:
        if tag in declared_set:
            declared_set.remove(tag)
            changes.append(f"removed '{tag}' (allergens column is authoritative)")
    return changes


def _persist_declared_tags(ing: Any, declared_set: set[str]) -> None:
    """Persist the modified declared_set back to the ingredient.
    
    Extracted from _repair_allergen_contradictions to reduce complexity.
    """
    ing.dietary_tags = ",".join(declared_set) if declared_set else None


_VALID_CATEGORIES = {
    "grasas", "lácteos", "harinas", "endulzantes", "frutas", "carnes",
    "pescados", "especias", "otros", "leudantes", "huevos", "decoración",
    "frutos-secos", "líquidos", "semillas",
}


def _repair_category_mismatch(ing: Any, issues: list[str]) -> list[str]:
    """Repair category mismatches. Returns list of changes.
    
    Extracted from repair_ingredient to reduce complexity.
    """
    for issue in issues:
        if "may be wrong; name suggests" not in issue:
            continue
        stored, inferred = _parse_category_issue(issue)
        if stored is None or inferred is None:
            continue
        if (ing.category or "").lower() == stored and inferred in _VALID_CATEGORIES:
            ing.category = inferred
            return [f"category: '{stored}' → '{inferred}' (from name)"]
    return []


def _parse_category_issue(issue: str) -> tuple[str | None, str | None]:
    """Parse a category issue string into (stored, inferred).
    
    Extracted from _repair_category_mismatch to reduce complexity.
    """
    try:
        head, tail = issue.split("name suggests ", 1)
        stored = head.split("'")[1]
        inferred = tail.strip().rstrip("'").lstrip("'").strip()
    except (IndexError, ValueError):
        return None, None
    return stored, inferred


def repair_all_ingredients(session: Session) -> dict[int, list[str]]:
    """Run repair on every ingredient. Returns {ing_id: [changes]}.

    Used by migration v62 + the /inventario/auditoria-etiquetas/rerun
    endpoint (which now also repairs).
    """
    from app.rms.models import Ingredient

    out: dict[int, list[str]] = {}
    for ing in session.scalars(select(Ingredient)).all():
        changes = repair_ingredient(ing)
        if changes:
            out[ing.id] = changes
    return out


__all__ = ["repair_all_ingredients", "repair_ingredient"]


# Suppress unused: select is imported in the function above (lazy) — but
# ruff wants it here. Add a noqa so the lazy import keeps working.
