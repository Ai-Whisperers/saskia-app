"""app/rms/tag_algebra.py — derived dietary tags & allergens for recipes/products.

Two propagation families (see docs: derived-intelligence engines):

  ALLERGENS  ("contains X")   → UNION: any line carrying an allergen means
                               the recipe contains it. Recursive through
                               sub-recipes.
  DIETARY    ("sin X / vegano") → INTERSECTION: a recipe qualifies for tag T
                               only if EVERY non-packaging line's target
                               qualifies for T. One gram of harina cancels
                               "sin gluten" for the whole recipe. Sub-recipes
                               contribute their own DERIVED set (not raw
                               ingredients), with cycle protection.

Also provides the shared recipe-tree walker used by other derivation engines
(costing, nutrition, demand): walk_recipe_tree() with cycle guard.

Design notes:
- Pure functions over a Session; no schema writes. Caching is the caller's
  concern (recipes.py refreshes Recipe.derived_dietary_tags on save).
- Packaging ingredients (is_packaging) are EXCLUDED from dietary derivation
  and allergen rollup — boxes/ribbons are not food claims.
- "Sin TACC" requires may_contain_gluten=False on every line (SINACLA
  cross-contamination), stricter than plain sin_gluten.
- Traceability: every cancelled tag returns the blocking lines so the UI can
  show "why isn't my pan sin gluten?" (blocked_by list).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

# NOTE: no module-level model imports here. tests/test_review_quick_wins.py
# purges sys.modules of all app.* modules mid-suite and re-imports; holding
# Ingredient/Recipe class references at import time would leave stale
# identity (queries silently return nothing). Import models inside the
# functions on every call instead.

# Tags where sub-recipe contribution is intersection-based (all of them —
# dietary tags are "suit" claims). If a new union-style dietary tag is ever
# added, list it here.
_UNION_TAGS: frozenset[str] = frozenset()

# Neutral ingredients never block a dietary tag (they carry every suit by
# definition). Keeping this explicit (rather than inferring) so operators
# can audit it.
_NEUTRAL_KEYWORDS: tuple[str, ...] = (
    # Water / salt / ice
    "agua", "sal", "sal fina", "sal gruesa", "hielo",
    # Common spices — never disqualify a recipe from any dietary tag
    "canela", "jengibre", "nuez moscada", "vainilla", "esencia",
    # Leaveners / acids / chemical inputs
    "bicarbonato", "polvo de hornear", "levadura", "vinagre",
    # Fats / oils — oil is universally vegan/keto/sugar-free
    "aceite",
    # Sugars and flours are NOT neutral — they're the actual blockers.
    # Operator must declare their allergens (e.g. Harina de trigo → gluten).
)


@dataclass
class TagDerivation:
    """Result of deriving tags for one recipe.

    Attributes:
      allergens:        union of all line allergens (sorted).
      dietary:          intersection-derived dietary tags (sorted).
      blocked:          tag → [line labels that cancelled it]. For UI
                        "why not sin gluten?" tooltips. Empty dict when
                        nothing was cancelled.
      undeclared:       ingredient names with allergens=None — NOT the same
                        as allergen-free; the UI must show "sin declarar".
      cycles:           sub-recipe reference cycles detected (should be
                        empty; the walker guards, the route blocks).
    """

    allergens: list[str] = field(default_factory=list)
    dietary: list[str] = field(default_factory=list)
    blocked: dict[str, list[str]] = field(default_factory=dict)
    undeclared: list[str] = field(default_factory=list)
    cycles: list[str] = field(default_factory=list)


def _split_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


# EN→ES normalization for dietary tags.  Some code paths
# (ingredient_intel, recipe_intel, older seeds, xlsx imports) emit English
# or snake_case labels; tag_algebra compares against the Spanish canonical
# set in app/rms/constants.py:CANONICAL_DIETARY_TAGS, so we normalize at the
# read boundary.  Keys are lowercase to match the case the data already has.
_TAG_NORMALIZE: dict[str, str] = {
    "vegan": "vegano",
    "vegetarian": "vegetariano",
    "gluten_free": "sin gluten",
    "gluten-free": "sin gluten",
    "sugar_free": "sin azúcar",
    "sugar-free": "sin azúcar",
    "keto_friendly": "keto",
    "keto-friendly": "keto",
    "lactose_free": "sin lactosa",
    "dairy_free": "sin lactosa",
    "egg_free": "sin huevo",
    "nut_free": "sin frutos secos",
    "whole_grain": "integral",
    "organic": "orgánico",
    # Spanish variants — pass through:
    "vegano": "vegano",
    "vegetariano": "vegetariano",
    "sin gluten": "sin gluten",
    "sin-gluten": "sin gluten",
    "sin tacc": "sin tacc",
    "sin-tacc": "sin tacc",
    "sin lactosa": "sin lactosa",
    "sin-lactosa": "sin lactosa",
    "sin huevo": "sin huevo",
    "sin-huevo": "sin huevo",
    "sin frutos secos": "sin frutos secos",
    "sin-frutos-secos": "sin frutos secos",
    "sin azúcar": "sin azúcar",
    "sin-azucar": "sin azúcar",
    "integral": "integral",
    "orgánico": "orgánico",
    "organico": "orgánico",
    "keto": "keto",
}


def _normalize_tag(raw: str) -> str | None:
    """Map any common label form to the canonical Spanish tag.  Returns
    None for unrecognized / empty input so the caller can drop it.
    """
    if not raw:
        return None
    key = raw.strip().lower()
    if not key:
        return None
    if key in _TAG_NORMALIZE:
        return _TAG_NORMALIZE[key]
    return None


def _is_neutral(name: str) -> bool:
    n = name.strip().lower()
    return any(n == kw or n.startswith(kw + " ") for kw in _NEUTRAL_KEYWORDS)


# ---------------------------------------------------------------------------
# Shared recipe-tree walker (used by tag algebra; reusable by nutrition,
# demand, and any future per-line derivation engine).
# ---------------------------------------------------------------------------

@dataclass
class LineTarget:
    """One resolved line of a recipe tree walk."""

    line: object  # RecipeLine (lazy-typed: see module header)
    target: object  # Ingredient | Recipe
    depth: int  # 0 = direct line of the requested recipe


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

    include_packaging=False skips is_packaging ingredients entirely (tag
    and nutrition semantics). Costing callers pass True.
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
            lines = session.scalars(
                select(RecipeLine)
                .where(RecipeLine.recipe_id == rid)
                .order_by(RecipeLine.id)
            ).all()
            for line in lines:
                if depth > 0 and line.line_kind == "sub_recipe":
                    # sub-recipe at depth>0 means nested sub-recipe
                    if line.line_ref_id in seen or depth >= max_depth:
                        continue
                    seen.add(line.line_ref_id)
                    _walk(line.line_ref_id, depth + 1)
                    continue
                target = _resolve(session, line)
                if target is None:
                    continue
                if (
                    isinstance(target, Ingredient)
                    and target.is_packaging
                    and not include_packaging
                ):
                    continue
                targets.append(LineTarget(line=line, target=target, depth=depth))
                if line.line_kind == "sub_recipe" and depth < max_depth:
                    # Direct sub-recipe lines: walk children after recording.
                    if line.line_ref_id not in seen:
                        seen.add(line.line_ref_id)
                        _walk(line.line_ref_id, depth + 1)
        finally:
            path.pop()

    _walk(recipe_id, 0)
    return targets, cycles


def _resolve(session: Session, line: object) -> object | None:
    from app.rms.costing import resolve_line_target

    try:
        return resolve_line_target(session, line)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Ingredient-level tag sets
# ---------------------------------------------------------------------------

def ingredient_dietary_set(ing: object) -> frozenset[str]:
    """(takes Ingredient lazily — see module header note)"""
    """Dietary tags an ingredient qualifies for (normalized to canonical Spanish).

    Tags from older seeds / ingredient_intel / xlsx imports may be English
    or snake_case ("vegan", "gluten_free", "keto_friendly"); we map those
    to the canonical Spanish vocabulary via _normalize_tag so downstream
    intersection against CANONICAL_DIETARY_TAGS works as intended.
    """
    raw = _split_tags(ing.dietary_tags)
    out: set[str] = set()
    for tag in raw:
        norm = _normalize_tag(tag)
        if norm:
            out.add(norm)
    return frozenset(out)


# Map of dietary tag → allergen keywords that block it.
# An ingredient blocks "sin X" if any of its allergens match the keywords
# for X.  This makes ingredient.allergens the source of truth for blocking,
# and dietary_tags becomes a redundant cross-check / claim.
# Order matters only for readability; .intersection() handles membership.
_TAG_ALLERGEN_BLOCKERS: dict[str, tuple[str, ...]] = {
    "sin gluten":   ("gluten",),
    "sin tacc":     ("gluten",),       # sin tacc ≡ sin gluten (Argentina/Py)
    "sin lactosa":  ("dairy",),
    "sin huevo":    ("eggs",),
    "sin frutos secos": ("nuts",),
    "vegano":       ("dairy", "eggs", "honey"),  # vegan excludes animal products
    "vegetariano":  (),                # vegetarian only excludes meat; dairy/eggs OK
    "sin azúcar":   ("sugar", "azúcar"),  # explicit sugar ingredient (rare)
    "keto":         ("sugar", "azúcar", "gluten"),  # keto = low-carb, no flour
    "integral":     (),                # integral = whole-grain — derived, not blocked
    "orgánico":     (),                # orgánico = ingredient-level certification
}


def ingredient_blocks(ing: object, tag: str) -> bool:
    """True if this ingredient DISQUALIFIES the recipe from `tag`.

    Blocking rules — hierarchical, allergen-driven, dietary_tags is a claim:

    1. **Neutral keywords** — `agua`, `sal`, `hielo`, common spices, leaveners
       never block any tag (they're pantry staples that don't disqualify).

    2. **Allergens column populated** → use it as source of truth.
       An ingredient blocks `sin X` if its `allergens` column contains any
       keyword that disqualifies X (per `_TAG_ALLERGEN_BLOCKERS`).
       Example: Harina de trigo has allergens='gluten' → blocks sin_gluten
       and sin_tacc; manteca has allergens='dairy' → blocks sin_lactosa.

    3. **Allergens column empty/null** → fall back to `infer_allergens(name)`
       heuristic.  This handles operators who haven't yet populated the
       allergens column (the UI shows these as "sin declarar").  Zanahoria
       has no allergens and no name-keyword matches → does NOT block sin_x.
       Harina de trigo (no allergens, but name matches `trigo`) → blocks
       sin_gluten.

    4. **sin tacc cross-contamination** — even with empty allergens,
       `may_contain_gluten=True` still blocks `sin tacc` (SINACLA rule for
       shared equipment).

    5. **dietary_tags cross-check** — if the ingredient CLAIMS the tag T
       (e.g. `vegano`, `sin gluten`) in its declared dietary set, that claim
       overrides a heuristic match.  e.g. `Harina de almendras` matches the
       `almendra` nut keyword for infer_allergens, but if it declares
       `sin frutos secos`, trust the claim and don't block sin_frutos_secos.

    6. **Default: don't block.**  If neither allergens nor name-heuristic
       yields a disqualifier, the ingredient is treated as not blocking.
       The UI shows it as "sin declarar" so the operator can fill inventory.
       This prevents the broken legacy behavior where carrots blocked
       sin_gluten because their allergens column was simply unpopulated.
    """
    if _is_neutral(ing.name or ""):
        return False

    allergens_raw = getattr(ing, "allergens", None)
    may_contain_gluten = getattr(ing, "may_contain_gluten", False)

    # (4) sin tacc cross-contamination takes priority (operator-set flag)
    if tag == "sin tacc" and may_contain_gluten:
        return True

    # Resolve which allergens disqualify this tag, from most-trusted to least.
    blockers = _TAG_ALLERGEN_BLOCKERS.get(tag, ())
    if not blockers:
        # No allergen → tag rule defined; tags like 'integral', 'orgánico'
        # aren't blocked by allergens (they're derived/cert claims).
        return False

    # (2) allergens column is the preferred source of truth.
    if allergens_raw:
        allergens = {a.strip().lower() for a in allergens_raw.split(",") if a.strip()}
        if any(b in allergens for b in blockers):
            return True
        # Allergens declared and don't include any blocker → don't block.
        return False

    # (3) Allergens column unpopulated → heuristic from ingredient name.
    #     Lazily import to avoid circular module-load (ingredient_intel
    #     imports models from here indirectly).
    from app.rms.ingredient_intel import infer_allergens

    inferred = set(infer_allergens(getattr(ing, "name", "") or ""))
    if any(b in inferred for b in blockers):
        # (5) dietary_tags claim can override a heuristic match
        declared = ingredient_dietary_set(ing)
        if tag in declared:
            return False
        return True

    # (6) No allergens + no name-heuristic match → don't block.
    #     UI marks the ingredient "sin declarar alérgenos" so the operator
    #     knows to fill inventory.
    return False


# ---------------------------------------------------------------------------
# The derivation
# ---------------------------------------------------------------------------

_ALLERGEN_ORDER = [
    "gluten", "dairy", "eggs", "nuts", "soy", "sesame", "sulfites",
]


def _allergen_sort_key(a: str) -> tuple[int, int, str]:
    """Canonical allergens first (in _ALLERGEN_ORDER), unknown ones after,
    alphabetically. Ingredients carry free-text Spanish allergens (e.g.
    'lacteos', 'mani') — .index() raised ValueError on any unknown string,
    which crashed derive_recipe_tags; routes swallowed it as a warning, so
    product derived tags silently NEVER updated. Found by tests/e2e/."""
    try:
        return (0, _ALLERGEN_ORDER.index(a), a)
    except ValueError:
        return (1, 0, a)


def derive_recipe_tags(
    session: Session,
    recipe_id: int,
    *,
    candidate_tags: list[str] | None = None,
) -> TagDerivation:
    """Derive allergens + dietary tags for a recipe.

    candidate_tags: the tag vocabulary to test intersection against. When
    None, uses the union of tags declared across the tree's ingredients —
    i.e. "every tag any ingredient claims" — plus the canonical Paraguayan
    bakery set. Pass the DB tag list (kind='recipe') from routes for
    consistency with the operator's vocabulary.
    """
    from app.rms.models import Ingredient, Recipe

    result = TagDerivation()

    # Union allergens across the whole tree (including sub-recipes' own
    # cached allergen columns, which already union their ingredients).
    targets, cycles = walk_recipe_tree(session, recipe_id, include_packaging=False)
    result.cycles = cycles

    allergen_set: set[str] = set()

    # Dietary candidates: canonical set ∪ declared tags across tree.
    declared_union: set[str] = set()
    for t in targets:
        if isinstance(t.target, Ingredient):
            if t.target.allergens is None:
                result.undeclared.append(t.target.name)
            else:
                allergen_set.update(_split_tags(t.target.allergens))
            declared_union.update(ingredient_dietary_set(t.target))
        elif isinstance(t.target, Recipe):
            allergen_set.update(_split_tags(t.target.allergens))
            # Sub-recipe dietary_tags may be English; normalize to Spanish
            # canonical so the sub-recipe's own claim is comparable.
            sub_declared = {
                norm for raw in _split_tags(t.target.dietary_tags)
                if (norm := _normalize_tag(raw)) is not None
            }
            declared_union.update(sub_declared)

    if candidate_tags is None:
        from app.rms.constants import CANONICAL_DIETARY_TAGS

        candidate_tags = sorted(set(CANONICAL_DIETARY_TAGS) | declared_union)

    # Intersect: a candidate survives only if no non-sub-recipe ingredient
    # blocks it. Sub-recipes block via their own derived set (cached
    # dietary_tags column, which routes refresh on save).
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
                # Sub-recipe blocks tag T if T is not in its declared set.
                # Normalize so English-named sub-recipes block correctly.
                sub_tags_lc = {
                    _normalize_tag(x)
                    for x in _split_tags(t.target.dietary_tags)
                }
                if tag_l not in {x for x in sub_tags_lc if x}:
                    blockers.append(f"{t.target.name} (sub-receta)")
        if blockers:
            result.blocked[tag] = blockers
        else:
            kept.append(tag)

    result.allergens = sorted(allergen_set, key=_allergen_sort_key)
    result.dietary = kept
    return result


def refresh_recipe_tag_cache(session: Session, recipe_id: int) -> None:
    """Recompute + persist Recipe.allergens / derived tag cache.

    Call on: recipe save (line changes), ingredient tag edits affecting this
    recipe, sub-recipe cache refresh (cascade handled by caller walking
    parents).
    """
    from app.rms.models import Recipe

    r = session.get(Recipe, recipe_id)
    if r is None:
        return
    d = derive_recipe_tags(session, recipe_id)
    r.allergens = ",".join(d.allergens) if d.allergens else None
    # Cache derived dietary into the existing column format; manual tags are
    # reconciled by the route (they live in tag_link), so here we only store
    # the derived portion for downstream product inheritance.
    r.derived_dietary_tags = ",".join(d.dietary) if d.dietary else None


def recipes_using_ingredient(session: Session, ingredient_id: int) -> list[int]:
    """Recipe IDs with a DIRECT line to this ingredient (for cascade)."""
    from app.rms.models import RecipeLine
    rows = session.execute(
        select(RecipeLine.recipe_id).where(
            RecipeLine.line_kind == "ingredient",
            RecipeLine.line_ref_id == ingredient_id,
        )
    ).scalars().all()
    return sorted(set(rows))


def recipes_using_recipe(session: Session, sub_recipe_id: int) -> list[int]:
    """Recipe IDs with a DIRECT sub-recipe line to this one (for cascade)."""
    from app.rms.models import RecipeLine
    rows = session.execute(
        select(RecipeLine.recipe_id).where(
            RecipeLine.line_kind == "sub_recipe",
            RecipeLine.line_ref_id == sub_recipe_id,
        )
    ).scalars().all()
    return sorted(set(rows))


def cascade_refresh(session: Session, ingredient_id: int | None = None,
                    recipe_id: int | None = None) -> list[int]:
    """Refresh tag caches for a recipe and every transitive parent.

    Returns the recipe IDs refreshed. Guarded against cycles by the walker;
    the loop terminates because parent chains form a DAG in practice and we
    track visited sets.
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




def _product_inherit_sync(session: Session, recipe_id: int) -> list[int]:
    """Push a recipe's derived tags + allergens into linked products' caches.

    Returns product IDs updated. Called after cascade_refresh so products
    (POS cards, receipts, label printing) never show stale claims.
    """
    from app.rms.models import Product, Recipe

    r = session.get(Recipe, recipe_id)
    if r is None:
        return []
    inherited = sorted(set(_split_tags(r.derived_dietary_tags)))
    # Allergens ride along so the POS guard can check them cheaply.
    allergens = _split_tags(r.allergens)
    value = ",".join(inherited + [f"al:{a}" for a in allergens]) or None
    products = session.scalars(
        select(Product).where(Product.recipe_id == recipe_id)
    ).all()
    for p_ in products:
        p_.inherited_tags = value
    return [p_.id for p_ in products]


__all__ = [
    "LineTarget",
    "TagDerivation",
    "_product_inherit_sync",
    "cascade_refresh",
    "derive_recipe_tags",
    "ingredient_blocks",
    "ingredient_dietary_set",
    "recipes_using_ingredient",
    "recipes_using_recipe",
    "refresh_recipe_tag_cache",
    "walk_recipe_tree",
]
