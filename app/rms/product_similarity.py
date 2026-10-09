"""app/rms/product_similarity.py — Jaccard ingredient overlap between products.

Two products are "similar" if they share many of the same ingredients.
Useful for:
- Substitution ("what else can I sell?")
- Menu rationalization (which products are clones?)
- Cross-sell (recommend similar items)

Jaccard similarity:
    |A ∩ B| / |A ∪ B|

Returns 0.0 for disjoint sets, 1.0 for identical sets.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import Product, RecipeLine

# ---------------------------------------------------------------------------
# Set extraction
# ---------------------------------------------------------------------------


def product_ingredient_set(session: Session, product: Product) -> set[int]:
    """Return the set of ingredient IDs used in a product's recipe.

    Walks sub-recipes recursively to flatten the ingredient set.
    """
    return _flatten_ingredients(session, product.recipe_id, seen_recipes=None)


def _flatten_ingredients(
    session: Session, recipe_id: int | None, seen_recipes: set[int] | None
) -> set[int]:
    """Recursively gather ingredients from a recipe + its sub-recipes."""
    if recipe_id is None:
        return set()
    if seen_recipes is None:
        seen_recipes = set()
    if recipe_id in seen_recipes:
        return set()  # cycle protection
    seen_recipes = seen_recipes | {recipe_id}

    ingredients: set[int] = set()
    sub_recipe_ids: list[int] = []

    for line in session.scalars(select(RecipeLine).where(RecipeLine.recipe_id == recipe_id)).all():
        if line.line_kind == "ingredient":
            ingredients.add(line.line_ref_id)
        elif line.line_kind == "sub_recipe":
            sub_recipe_ids.append(line.line_ref_id)

    for sub_id in sub_recipe_ids:
        ingredients |= _flatten_ingredients(session, sub_id, seen_recipes)
    return ingredients


# ---------------------------------------------------------------------------
# Jaccard
# ---------------------------------------------------------------------------


def jaccard_similarity(set_a: set[int], set_b: set[int]) -> float:
    """Jaccard index: |A ∩ B| / |A ∪ B|.

    Returns 0.0 when both sets are empty (degenerate case).
    """
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    if union == 0:
        return 0.0
    return intersection / union


def ingredient_overlap_count(set_a: set[int], set_b: set[int]) -> int:
    """Count of shared ingredients."""
    return len(set_a & set_b)


# ---------------------------------------------------------------------------
# Most similar products
# ---------------------------------------------------------------------------


def most_similar_products(
    session: Session, product_id: int, top_n: int = 5
) -> list[tuple[Product, float]]:
    """Top N products by Jaccard similarity to product_id, excluding self."""
    target = session.get(Product, product_id)
    if target is None:
        return []

    target_set = product_ingredient_set(session, target)
    if not target_set:
        return []

    all_products = list(session.scalars(select(Product)).all())
    scored = []
    for p in all_products:
        if p.id == product_id:
            continue
        p_set = product_ingredient_set(session, p)
        sim = jaccard_similarity(target_set, p_set)
        if sim > 0:
            scored.append((p, sim))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_n]


# ---------------------------------------------------------------------------
# Substitution suggestions
# ---------------------------------------------------------------------------


def suggest_substitute(
    session: Session,
    product_id: int,
    similarity_threshold: float = 0.7,
    price_band_pct: float = 0.20,
    top_n: int = 5,
) -> list[Product]:
    """Products that could substitute for this one.

    Criteria:
    - Jaccard similarity > similarity_threshold
    - Sale price within ±price_band_pct of target
    """
    target = session.get(Product, product_id)
    if target is None:
        return []

    target_set = product_ingredient_set(session, target)
    if not target_set:
        return []

    target_price = float(target.sale_price_gs or 0)
    if target_price <= 0:
        return []

    candidates = []
    for p in session.scalars(select(Product)).all():
        if p.id == product_id:
            continue
        p_set = product_ingredient_set(session, p)
        sim = jaccard_similarity(target_set, p_set)
        if sim < similarity_threshold:
            continue
        p_price = float(p.sale_price_gs or 0)
        if p_price <= 0:
            continue
        # Price band check.
        deviation = abs(p_price - target_price) / target_price
        if deviation > price_band_pct:
            continue
        candidates.append(p)
    return candidates[:top_n]


# ---------------------------------------------------------------------------
# Cross-product overlap matrix (for menu rationalization dashboard)
# ---------------------------------------------------------------------------


def similarity_matrix(
    session: Session, products: list[Product] | None = None
) -> dict[tuple[int, int], float]:
    """Pairwise Jaccard similarity between all products.

    Returns dict keyed by (smaller_id, larger_id) → similarity.
    """
    if products is None:
        products = list(session.scalars(select(Product)).all())

    sets: dict[int, set[int]] = {}
    for p in products:
        sets[p.id] = product_ingredient_set(session, p)

    out: dict[tuple[int, int], float] = {}
    for i, a in enumerate(products):
        for b in products[i + 1 :]:
            sim = jaccard_similarity(sets[a.id], sets[b.id])
            if sim > 0:
                key = (min(a.id, b.id), max(a.id, b.id))
                out[key] = sim
    return out


def find_clones(session: Session, threshold: float = 0.7) -> list[tuple[Product, Product, float]]:
    """Pairs of products with similarity > threshold (potential menu clones)."""
    products = list(session.scalars(select(Product)).all())
    mat = similarity_matrix(session, products)
    out = []
    for (a_id, b_id), sim in mat.items():
        if sim >= threshold:
            pa = session.get(Product, a_id)
            pb = session.get(Product, b_id)
            if pa and pb:
                out.append((pa, pb, sim))
    out.sort(key=lambda x: x[2], reverse=True)
    return out


__all__ = [
    "find_clones",
    "ingredient_overlap_count",
    "jaccard_similarity",
    "most_similar_products",
    "product_ingredient_set",
    "similarity_matrix",
    "suggest_substitute",
]
