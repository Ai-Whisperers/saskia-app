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

from sqlalchemy import select
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
        rows = session.execute(
            select(RecipeLine.line_ref_id).where(
                RecipeLine.line_kind == "sub_recipe",
                RecipeLine.recipe_id.in_(batch),
            )
        ).scalars().all()
        frontier = list(set(rows))
    return out


def product_cost_freshness(
    session: Session, products: list
) -> dict[int, datetime | None]:
    """Map product_id → latest ingredient-price timestamp (or None).

    None means: no recipe, or the recipe tree has zero priced events —
    the cost shown is effectively 'never computed'.
    """
    from app.rms.models import IngredientPriceEvent, RecipeLine

    recipe_ids = sorted({p.recipe_id for p in products if p.recipe_id})
    if not recipe_ids:
        return {p.id: None for p in products}

    all_recipe_ids = _walk_recipe_ids(session, recipe_ids)
    if not all_recipe_ids:
        return {p.id: None for p in products}

    # ingredient ids referenced by any of those recipes
    ingredient_ids = set(
        session.execute(
            select(RecipeLine.line_ref_id).where(
                RecipeLine.recipe_id.in_(all_recipe_ids),
                RecipeLine.line_kind == "ingredient",
            )
        ).scalars().all()
    )
    if not ingredient_ids:
        return {p.id: None for p in products}

    # latest event per ingredient, then we walk product→recipe→ingredients
    # in Python using the identity maps (still O(1) queries).
    latest_by_ingredient: dict[int, datetime] = {}
    for ing_id, recorded_at in session.execute(
        select(
            IngredientPriceEvent.ingredient_id,
            func_max_recorded_at(),
        )
        .where(IngredientPriceEvent.ingredient_id.in_(ingredient_ids))
        .group_by(IngredientPriceEvent.ingredient_id)
    ).all():
        latest_by_ingredient[ing_id] = recorded_at

    # recipe → ingredient ids
    recipe_ings: dict[int, set[int]] = {}
    for recipe_id, ing_id in session.execute(
        select(RecipeLine.recipe_id, RecipeLine.line_ref_id).where(
            RecipeLine.recipe_id.in_(all_recipe_ids),
            RecipeLine.line_kind == "ingredient",
        )
    ).all():
        recipe_ings.setdefault(recipe_id, set()).add(ing_id)

    # product → freshness = max event over its whole recipe tree.
    # Walk children top-down from the product's root recipe (cycle-safe).
    def _tree_from(rid: int) -> set[int]:
        seen: set[int] = set()
        frontier = [rid]
        while frontier:
            batch = [r for r in frontier if r not in seen]
            if not batch:
                break
            seen.update(batch)
            children = session.execute(
                select(RecipeLine.line_ref_id).where(
                    RecipeLine.line_kind == "sub_recipe",
                    RecipeLine.recipe_id.in_(batch),
                )
            ).scalars().all()
            frontier = list(set(children))
        return seen

    result: dict[int, datetime | None] = {}
    for p in products:
        if not p.recipe_id:
            result[p.id] = None
            continue
        tree_ids = _tree_from(p.recipe_id)
        ings: set[int] = set()
        for rid in tree_ids:
            ings |= recipe_ings.get(rid, set())
        stamps = [
            latest_by_ingredient[i] for i in ings if i in latest_by_ingredient
        ]
        result[p.id] = max(stamps) if stamps else None
    return result


def func_max_recorded_at():
    """max(IngredientPriceEvent.recorded_at) — small helper for readability."""
    from sqlalchemy import func

    from app.rms.models import IngredientPriceEvent

    return func.max(IngredientPriceEvent.recorded_at)
