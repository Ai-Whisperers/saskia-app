"""app/rms/cost_freshness.py — Product cost freshness (UI-V2).

Answers "is this sale price computed on stale costs?" — the productos
table shows a 'Costo actualizado' column: the most recent
IngredientPriceEvent across the product's recipe tree, or None when the
product has no priced ingredients at all (never costed).

Batch API: product_cost_freshness(session, [products]) → {product_id:
datetime | None} in ~3 queries (products → recipes → lines+events), so
the list route stays N+1-free.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def _walk_recipe_ids(session: Session, recipe_ids: list[int]) -> set[int]:
    """All recipe ids in the trees rooted at recipe_ids (sub-recipes incl.)."""
    from app.rms.models import RecipeLine

    out: set[int] = set()
    frontier = list(recipe_ids)
    while frontier:
        batch = [r for r in frontier if r not in out]
        if not batch:
            break
        out.update(batch)
        # Children: sub_recipe lines FROM these recipes point at their children.
        rows = (
            session.execute(
                select(RecipeLine.line_ref_id).where(
                    RecipeLine.line_kind == "sub_recipe",
                    RecipeLine.recipe_id.in_(batch),
                )
            )
            .scalars()
            .all()
        )
        frontier = list(set(rows))
    return out


def product_cost_freshness(session: Session, products: list) -> dict[int, datetime | None]:
    """Map product_id → latest ingredient-price timestamp (or None).

    None means: no recipe, or the recipe tree has zero priced events —
    the cost shown is effectively 'never computed'.
    """

    recipe_ids = sorted({p.recipe_id for p in products if p.recipe_id})
    if not recipe_ids:
        return {p.id: None for p in products}

    all_recipe_ids = _walk_recipe_ids(session, recipe_ids)
    if not all_recipe_ids:
        return {p.id: None for p in products}

    # Load ingredient IDs and latest price events
    ingredient_ids = _load_ingredient_ids(session, all_recipe_ids)
    if not ingredient_ids:
        return {p.id: None for p in products}

    latest_by_ingredient = _load_latest_price_events(session, ingredient_ids)
    recipe_ings = _load_recipe_to_ingredients(session, all_recipe_ids)

    # Build result: product → freshness = max event over its recipe tree
    return _build_freshness_map(session, products, latest_by_ingredient, recipe_ings)


def _load_ingredient_ids(session: Session, recipe_ids: list[int]) -> set[int]:
    """Load set of ingredient IDs referenced by the given recipes.

    Extracted from product_cost_freshness to reduce complexity.
    """
    from app.rms.models import RecipeLine

    return set(
        session.execute(
            select(RecipeLine.line_ref_id).where(
                RecipeLine.recipe_id.in_(recipe_ids),
                RecipeLine.line_kind == "ingredient",
            )
        )
        .scalars()
        .all()
    )


def _load_latest_price_events(session: Session, ingredient_ids: set[int]) -> dict[int, datetime]:
    """Load latest IngredientPriceEvent timestamp per ingredient.

    Extracted from product_cost_freshness to reduce complexity.
    """
    from app.rms.models import IngredientPriceEvent

    return {
        ing_id: recorded_at
        for ing_id, recorded_at in session.execute(
            select(
                IngredientPriceEvent.ingredient_id,
                func_max_recorded_at(),
            )
            .where(IngredientPriceEvent.ingredient_id.in_(ingredient_ids))
            .group_by(IngredientPriceEvent.ingredient_id)
        ).all()
    }


def _load_recipe_to_ingredients(session: Session, recipe_ids: list[int]) -> dict[int, set[int]]:
    """Load mapping of recipe_id → set of ingredient IDs.

    Extracted from product_cost_freshness to reduce complexity.
    """
    from app.rms.models import RecipeLine

    recipe_ings: dict[int, set[int]] = {}
    for recipe_id, ing_id in session.execute(
        select(RecipeLine.recipe_id, RecipeLine.line_ref_id).where(
            RecipeLine.recipe_id.in_(recipe_ids),
            RecipeLine.line_kind == "ingredient",
        )
    ).all():
        recipe_ings.setdefault(recipe_id, set()).add(ing_id)
    return recipe_ings


def _build_freshness_map(
    session: Session,
    products: list,
    latest_by_ingredient: dict[int, datetime],
    recipe_ings: dict[int, set[int]],
) -> dict[int, datetime | None]:
    """Build the product_id → freshness timestamp map.

    For each product, walks the recipe tree top-down (cycle-safe) and
    computes the max price event timestamp across all ingredients.

    Extracted from product_cost_freshness to reduce complexity.
    """
    result: dict[int, datetime | None] = {}
    for p in products:
        if not p.recipe_id:
            result[p.id] = None
            continue
        tree_ids = _walk_recipe_tree(session, p.recipe_id)
        ings: set[int] = set()
        for rid in tree_ids:
            ings |= recipe_ings.get(rid, set())
        stamps = [latest_by_ingredient[i] for i in ings if i in latest_by_ingredient]
        result[p.id] = max(stamps) if stamps else None
    return result


def _walk_recipe_tree(session: Session, root_recipe_id: int) -> set[int]:
    """Walk recipe tree top-down from root, cycle-safe.

    Returns set of all recipe IDs in the tree (including root).
    Extracted from product_cost_freshness to reduce complexity.
    """
    from app.rms.models import RecipeLine

    seen: set[int] = set()
    frontier = [root_recipe_id]
    while frontier:
        batch = [r for r in frontier if r not in seen]
        if not batch:
            break
        seen.update(batch)
        children = (
            session.execute(
                select(RecipeLine.line_ref_id).where(
                    RecipeLine.line_kind == "sub_recipe",
                    RecipeLine.recipe_id.in_(batch),
                )
            )
            .scalars()
            .all()
        )
        frontier = list(set(children))
    return seen


def func_max_recorded_at() -> "func":
    """max(IngredientPriceEvent.recorded_at) — small helper for readability."""
    from app.rms.models import IngredientPriceEvent

    return func.max(IngredientPriceEvent.recorded_at)
