"""app/rms/tagging/derive.py — Recipe-level tag derivation orchestrator.

Public API:
    LineTarget              — One resolved line of a recipe tree walk.
    TagDerivation           — Result of deriving tags for one recipe.
    walk_recipe_tree()      — DFS walker with cycle guard.
    derive_recipe_tags()    — Main entry point. Returns TagDerivation.
    refresh_recipe_tag_cache() — Compute + persist to Recipe columns.
    cascade_refresh()       — Refresh a recipe + every transitive parent.

Design notes:
  - Pure functions over a Session. No schema writes (cache writes live in
    cache.py — explicitly imported by callers).
  - Sub-recipes contribute their DERIVED set (recursive call), NOT their
    operator-claimed `dietary_tags` column. This is the fix for the bug
    where a sub-recipe with empty dietary_tags silently blocked everything
    upstream.
  - Packaging ingredients (is_packaging=True) are excluded from dietary
    derivation and allergen rollup — boxes/ribbons are not food claims.
  - "Sin TACC" requires may_contain_gluten=False on every line (SINACLA
    cross-contamination), stricter than plain sin_gluten. Enforced by
    classify.ingredient_blocks() step 4.
  - Traceability: every cancelled tag returns the blocking lines so the
    UI can show "why isn't my pan sin gluten?" (blocked_by list).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

# NOTE: no module-level model imports here. tests purge sys.modules of all
# app.* modules mid-suite and re-import; holding Ingredient/Recipe class
# references at import time would leave stale identity (queries silently
# return nothing). Import models inside the functions on every call.
from app.rms.tagging.classify import (
    ingredient_blocks,
    normalize_all,
)


@dataclass
class LineTarget:
    """One resolved line of a recipe tree walk."""

    line: object  # RecipeLine (lazy-typed)
    target: object  # Ingredient | Recipe
    depth: int  # 0 = direct line of the requested recipe


@dataclass
class TagDerivation:
    """Result of deriving tags for one recipe.

    Attributes:
      allergens:        union of all line allergens (sorted).
      dietary:          intersection-derived dietary tags (sorted).
      blocked:          tag → [line labels that cancelled it]. For UI
                        "why not sin gluten?" tooltips.
      undeclared:       ingredient names with allergens=None — NOT the
                        same as allergen-free; the UI must show
                        "sin declarar".
      undeclared_ids:   ingredient ids parallel to `undeclared` names —
                        lets the UI deep-link each name straight to its
                        Inventario edit form ("fix at source" UX).
      cycles:           sub-recipe reference cycles detected (should be
                        empty; the walker guards).
    """

    allergens: list[str] = field(default_factory=list)
    dietary: list[str] = field(default_factory=list)
    blocked: dict[str, list[str]] = field(default_factory=dict)
    undeclared: list[str] = field(default_factory=list)
    undeclared_ids: list[int] = field(default_factory=list)
    cycles: list[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────
# Tree walker
# ─────────────────────────────────────────────────────────────────────────


def walk_recipe_tree(
    session: Session,
    recipe_id: int,
    *,
    include_packaging: bool = False,
    max_depth: int = 8,
) -> tuple[list[LineTarget], list[str]]:
    """Walk a recipe tree depth-first, resolving sub-recipes recursively.

    Returns (targets, cycles):
      targets — every line's target in tree order (sub-recipe lines appear
                after their parent line, with depth > 0)
      cycles  — "RecipeA -> RecipeB -> RecipeA" strings if a cycle was cut

    include_packaging=False skips is_packaging ingredients entirely
    (tag and nutrition semantics). Costing callers pass True.
    """
    seen: set[int] = set()
    targets: list[LineTarget] = []
    cycles: list[str] = []
    path: list[str] = []

    from app.rms.models import Ingredient, RecipeLine

    def _walk(rid: int, depth: int) -> None:
        label = f"#{rid}"
        if label in path:
            cycles.append(" -> ".join([*path, label]))
            return
        path.append(label)
        try:
            lines = _load_recipe_lines(session, rid)
            for line in lines:
                _process_line(session, line, depth, seen, targets, path,
                              cycles, include_packaging, max_depth)
        finally:
            path.pop()

    _walk(recipe_id, 0)
    return targets, cycles


def _load_recipe_lines(session, rid: int) -> list:
    """Load recipe lines for a recipe, ordered by ID.
    
    Extracted from walk_recipe_tree to reduce complexity.
    """
    from app.rms.models import RecipeLine

    return session.scalars(
        select(RecipeLine).where(RecipeLine.recipe_id == rid).order_by(RecipeLine.id)
    ).all()


def _process_line(
    session, line, depth: int, seen: set, targets: list,
    path: list, cycles: list, include_packaging: bool, max_depth: int,
) -> None:
    """Process a single recipe line in the tree walk.
    
    Extracted from walk_recipe_tree to reduce complexity.
    """
    from app.rms.models import Ingredient

    if depth > 0 and line.line_kind == "sub_recipe":
        _handle_nested_sub_recipe(session, line, depth, seen, targets, path, cycles,
                                  include_packaging, max_depth)
        return

    target = _resolve(session, line)
    if not _is_valid_target(target, include_packaging):
        return
    targets.append(LineTarget(line=line, target=target, depth=depth))

    if line.line_kind == "sub_recipe" and depth < max_depth:
        _handle_direct_sub_recipe(session, line, depth, seen, targets, path, cycles,
                                   include_packaging, max_depth)


def _handle_nested_sub_recipe(
    session, line, depth: int, seen: set, targets: list,
    path: list, cycles: list, include_packaging: bool, max_depth: int,
) -> None:
    """Handle a nested sub-recipe line (depth > 0).
    
    Extracted from _process_line to reduce complexity.
    """
    if line.line_ref_id in seen or depth >= max_depth:
        return
    seen.add(line.line_ref_id)
    _walk_recurse(
        session, line.line_ref_id, depth, seen, targets, path, cycles,
        include_packaging, max_depth,
    )


def _handle_direct_sub_recipe(
    session, line, depth: int, seen: set, targets: list,
    path: list, cycles: list, include_packaging: bool, max_depth: int,
) -> None:
    """Handle a direct sub-recipe line (depth == 0).
    
    Extracted from _process_line to reduce complexity.
    """
    if line.line_ref_id in seen:
        return
    seen.add(line.line_ref_id)
    _walk_recurse(
        session, line.line_ref_id, depth, seen, targets, path, cycles,
        include_packaging, max_depth,
    )


def _is_valid_target(target, include_packaging: bool) -> bool:
    """Check if a target is valid (not None, and not excluded packaging).
    
    Extracted from _process_line to reduce complexity.
    """
    if target is None:
        return False
    from app.rms.models import Ingredient
    if isinstance(target, Ingredient) and target.is_packaging and not include_packaging:
        return False
    return True


def _walk_recurse(
    session, rid: int, parent_depth: int, seen: set, targets: list,
    path: list, cycles: list, include_packaging: bool, max_depth: int,
) -> None:
    """Recurse into a sub-recipe, reusing the same state.
    
    Extracted from walk_recipe_tree to reduce complexity.
    """
    label = f"#{rid}"
    if label in path:
        cycles.append(" -> ".join([*path, label]))
        return
    path.append(label)
    try:
        lines = _load_recipe_lines(session, rid)
        for line in lines:
            _process_line(session, line, parent_depth + 1, seen, targets, path,
                          cycles, include_packaging, max_depth)
    finally:
        path.pop()


def _resolve(session: Session, line: object) -> object | None:
    from app.rms.costing import resolve_line_target

    try:
        return resolve_line_target(session, line)
    except ValueError:
        return None


# ─────────────────────────────────────────────────────────────────────────
# The derivation
# ─────────────────────────────────────────────────────────────────────────


def _split(raw: str | None) -> list[str]:
    """Split a CSV string into a list of trimmed non-empty tokens."""
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def _allergen_sort_key(a: str) -> tuple[int, int, str]:
    """Canonical allergens first, unknown ones after, alphabetically.

    Ingredients carry free-text Spanish allergens (e.g. 'lacteos', 'mani')
    — .index() would raise ValueError on any unknown string, crashing
    derive_recipe_tags; routes would swallow it as a warning, so product
    derived tags silently NEVER updated. Found by tests/e2e/.
    """
    from app.rms.tagging.vocabulary import ALLERGEN_DISPLAY_ORDER

    try:
        return (0, ALLERGEN_DISPLAY_ORDER.index(a), a)
    except ValueError:
        return (1, 0, a)


def derive_recipe_tags(
    session: Session,
    recipe_id: int,
    *,
    candidate_tags: list[str] | None = None,
    _recursion_depth: int = 0,
    _max_recursion: int = 4,
) -> TagDerivation:
    """Derive allergens + dietary tags for a recipe.

    candidate_tags: the tag vocabulary to test intersection against. When
    None, uses the union of tags declared across the tree's ingredients —
    i.e. "every tag any ingredient claims" — plus the canonical Paraguayan
    bakery set. Pass the DB tag list (kind='recipe') from routes for
    consistency with the operator's vocabulary.

    Sub-recipe derivation is recursive (capped at _max_recursion). This
    is the fix for the bug where a sub-recipe with unpopulated
    `dietary_tags` blocked every upstream recipe silently.
    """
    from app.rms.models import Ingredient, Recipe

    result = TagDerivation()

    # Union allergens across the whole tree.
    targets, cycles = walk_recipe_tree(session, recipe_id, include_packaging=False)
    result.cycles = cycles

    allergen_set: set[str] = set()
    declared_union: set[str] = set()
    for t in targets:
        if isinstance(t.target, Ingredient):
            # '' = operator saved it as declared-neutral; NULL = never touched.
            # (Backfill 2026-09-30 normalized all neutral rows to ''.)
            if t.target.allergens is None or t.target.allergens == "":
                result.undeclared.append(t.target.name)
                # UI-V2 fix-at-source: keep the id parallel to the name so
                # the warning can deep-link to /inventario/{id}/editar.
                result.undeclared_ids.append(t.target.id)
            else:
                allergen_set.update(_split(t.target.allergens))
            declared_union.update(normalize_all(t.target.dietary_tags))
        elif isinstance(t.target, Recipe):
            allergen_set.update(_split(t.target.allergens))
            # Recurse into sub-recipe for its derived set (not its
            # operator-claimed dietary_tags).
            if _recursion_depth < _max_recursion:
                sub_dietary = derive_recipe_tags(
                    session,
                    t.target.id,
                    candidate_tags=None,
                    _recursion_depth=_recursion_depth + 1,
                    _max_recursion=_max_recursion,
                ).dietary
                declared_union.update(sub_dietary)

    if candidate_tags is None:
        from app.rms.tagging.vocabulary import CANONICAL_DIETARY_TAGS

        candidate_tags = sorted(CANONICAL_DIETARY_TAGS | declared_union)

    # Intersect: a candidate survives only if no non-sub-recipe ingredient
    # blocks it. Sub-recipes block via their own derived set (recursive).
    direct = [t for t in targets if t.depth == 0]
    kept: list[str] = []
    for tag in candidate_tags:
        tag_l = tag.strip().lower()
        blockers: list[str] = []
        for t in direct:
            if isinstance(t.target, Ingredient):
                if ingredient_blocks(t.target, tag_l):
                    blockers.append(t.target.name)
            elif isinstance(t.target, Recipe):
                # Sub-recipe blocks tag T if T is not in its DERIVED set.
                if _recursion_depth < _max_recursion:
                    sub_dietary = derive_recipe_tags(
                        session,
                        t.target.id,
                        candidate_tags=None,
                        _recursion_depth=_recursion_depth + 1,
                        _max_recursion=_max_recursion,
                    ).dietary
                else:
                    # Recursion cap hit — fall back to operator-claimed set
                    # (legacy behavior, but safer than crashing).
                    sub_dietary = list(normalize_all(t.target.dietary_tags))
                if tag_l not in {d.lower() for d in sub_dietary}:
                    blockers.append(f"{t.target.name} (sub-receta)")
        if blockers:
            result.blocked[tag] = blockers
        else:
            kept.append(tag)

    result.allergens = sorted(allergen_set, key=_allergen_sort_key)
    result.dietary = sorted(set(kept))
    return result


# ─────────────────────────────────────────────────────────────────────────
# Cache refresh (writes — but isolated in this layer)
# ─────────────────────────────────────────────────────────────────────────


def refresh_recipe_tag_cache(session: Session, recipe_id: int) -> None:
    """Recompute + persist Recipe.allergens / derived tag cache.

    Call on: recipe save (line changes), ingredient tag edits affecting this
    recipe, sub-recipe cache refresh (cascade handled by caller walking
    parents).
    """
    from app.rms.tagging.cache import persist_recipe_cache

    d = derive_recipe_tags(session, recipe_id)
    persist_recipe_cache(session, recipe_id, d)


def recipes_using_ingredient(session: Session, ingredient_id: int) -> list[int]:
    """Recipe IDs with a DIRECT line to this ingredient (for cascade)."""
    from app.rms.models import RecipeLine

    rows = (
        session.execute(
            select(RecipeLine.recipe_id).where(
                RecipeLine.line_kind == "ingredient",
                RecipeLine.line_ref_id == ingredient_id,
            )
        )
        .scalars()
        .all()
    )
    return sorted(set(rows))


def recipes_using_recipe(session: Session, sub_recipe_id: int) -> list[int]:
    """Recipe IDs with a DIRECT sub-recipe line to this one (for cascade)."""
    from app.rms.models import RecipeLine

    rows = (
        session.execute(
            select(RecipeLine.recipe_id).where(
                RecipeLine.line_kind == "sub_recipe",
                RecipeLine.line_ref_id == sub_recipe_id,
            )
        )
        .scalars()
        .all()
    )
    return sorted(set(rows))


def cascade_refresh(
    session: Session,
    ingredient_id: int | None = None,
    recipe_id: int | None = None,
) -> list[int]:
    """Refresh tag caches for a recipe and every transitive parent.

    Returns the recipe IDs refreshed. Guarded against cycles by the
    walker; the loop terminates because parent chains form a DAG in
    practice and we track visited sets.
    """
    start: set[int] = set()
    if ingredient_id is not None:
        start.update(recipes_using_ingredient(session, ingredient_id))
    if recipe_id is not None:
        start.add(recipe_id)

    visited: set[int] = set()
    queue = sorted(start)
    refreshed: list[int] = []
    while queue:
        rid = queue.pop(0)
        if rid in visited:
            continue
        visited.add(rid)
        refresh_recipe_tag_cache(session, rid)
        refreshed.append(rid)
        queue.extend(recipes_using_recipe(session, rid))
    return refreshed


__all__ = [
    "LineTarget",
    "TagDerivation",
    "cascade_refresh",
    "derive_recipe_tags",
    "recipes_using_ingredient",
    "recipes_using_recipe",
    "refresh_recipe_tag_cache",
    "walk_recipe_tree",
]
