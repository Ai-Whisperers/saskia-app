"""app/rms/tag_algebra.py — Backwards-compat re-export from tagging/.

Restored 2026-10-05 after the Sprint 2.2 merge deleted this file but
several call sites still import from it. Re-exports the same public
surface as before, sourced from app/rms/tagging/.

NEW CODE SHOULD IMPORT DIRECTLY FROM app.rms.tagging.

Public surface (unchanged from before Sprint 2.2):
  - LineTarget, TagDerivation (dataclasses)
  - walk_recipe_tree, derive_recipe_tags, refresh_recipe_tag_cache
  - cascade_refresh
  - infer_allergens, ingredient_blocks
  - normalize, normalize_all
  - persist_recipe_cache
  - recipes_using_ingredient, recipes_using_recipe
  - ingredient_dietary_set (back-compat wrapper around normalize_all)
  - sync_product_inheritance (was _product_inherit_sync)
"""

from __future__ import annotations

from app.rms.tagging.cache import (
    persist_recipe_cache,
    sync_product_inheritance,
)
from app.rms.tagging.classify import (
    infer_allergens,
    ingredient_blocks,
    normalize,
    normalize_all,
)
from app.rms.tagging.derive import (
    LineTarget,
    TagDerivation,
    cascade_refresh,
    derive_recipe_tags,
    recipes_using_ingredient,
    recipes_using_recipe,
    refresh_recipe_tag_cache,
    walk_recipe_tree,
)


def ingredient_dietary_set(ing: object) -> frozenset[str]:
    """Backwards-compat wrapper for the original ingredient_dietary_set.

    Original implementation lived in tag_algebra.py. Now delegates to
    normalize_all() from the public tagging/classify surface.
    """
    return normalize_all(getattr(ing, "dietary_tags", None))


# Legacy private alias kept for any module still using the old name.
_product_inherit_sync = sync_product_inheritance

__all__ = [
    "LineTarget",
    "TagDerivation",
    "cascade_refresh",
    "derive_recipe_tags",
    "infer_allergens",
    "ingredient_blocks",
    "ingredient_dietary_set",
    "normalize",
    "normalize_all",
    "persist_recipe_cache",
    "recipes_using_ingredient",
    "recipes_using_recipe",
    "refresh_recipe_tag_cache",
    "sync_product_inheritance",
    "walk_recipe_tree",
]
