"""app/rms/tagging/cache.py — Cache write helpers.

The derivation engine (derive.py) is pure: it computes TagDerivation
without touching the database beyond read queries. This module owns all
schema writes for tag caches:

  persist_recipe_cache()    — writes Recipe.allergens and
                              Recipe.derived_dietary_tags from a
                              TagDerivation result.
  sync_product_inheritance() — pushes a recipe's derived tags + allergens
                              into every linked Product.inherited_tags.

Cache invalidation rules:
  - Recipe save (line changes) → refresh_recipe_tag_cache()
  - Ingredient tag/allergen edit → cascade_refresh(ingredient_id=...)
  - Sub-recipe derivation change → cascade_refresh(recipe_id=...)

Routes call refresh_recipe_tag_cache() / cascade_refresh() directly;
those are in derive.py.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session


def persist_recipe_cache(
    session: Session,
    recipe_id: int,
    derivation,
) -> None:
    """Write Recipe.allergens and Recipe.derived_dietary_tags from a
    TagDerivation result. Operator-claimed dietary_tags is preserved
    (lives in tag_link); this only stores the derived portion.
    """
    from app.rms.models import Recipe

    r = session.get(Recipe, recipe_id)
    if r is None:
        return
    r.allergens = ",".join(derivation.allergens) if derivation.allergens else None
    r.derived_dietary_tags = ",".join(derivation.dietary) if derivation.dietary else None


def sync_product_inheritance(session: Session, recipe_id: int) -> list[int]:
    """Push a recipe's derived tags + allergens into linked products' caches.

    Returns product IDs updated. Called after persist_recipe_cache so
    products (POS cards, receipts, label printing) never show stale
    claims. The cache field is `Product.inherited_tags` and stores
    a CSV like `"vegano,vegetariano,al:gluten,al:dairy"`.
    """
    from app.rms.models import Product, Recipe

    r = session.get(Recipe, recipe_id)
    if r is None:
        return []

    inherited = _split(r.derived_dietary_tags or "")
    allergens = _split(r.allergens or "")
    value = ",".join(inherited + [f"al:{a}" for a in allergens]) or None

    products = session.scalars(
        select(Product).where(Product.recipe_id == recipe_id)
    ).all()
    for p_ in products:
        p_.inherited_tags = value
    return [p_.id for p_ in products]


def _split(raw: str | None) -> list[str]:
    """Split a CSV string into trimmed non-empty tokens."""
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


# Backwards-compat alias: previously named `_split_tags` in tag_algebra.py.
# Exposed because app.rms.derived_intel imports it.
_split_tags = _split


__all__ = [
    "persist_recipe_cache",
    "sync_product_inheritance",
]
