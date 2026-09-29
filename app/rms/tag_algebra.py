"""app/rms/tag_algebra.py — Backwards-compat re-export from tagging/.

The tag-algebra logic was refactored into the `app/rms/tagging/` package
on 2026-09-29. This module now exists only to keep the public surface
(`from app.rms.tag_algebra import ingredient_blocks, derive_recipe_tags,
cascade_refresh, ...`) intact for any code or scripts that haven't been
updated yet.

NEW CODE SHOULD IMPORT DIRECTLY FROM app.rms.tagging.

Pre-refactor, this module owned:
  - TagDerivation / LineTarget dataclasses
  - walk_recipe_tree
  - derive_recipe_tags
  - refresh_recipe_tag_cache
  - cascade_refresh
  - ingredient_blocks
  - _TAG_NORMALIZE / _TAG_ALLERGEN_BLOCKERS / _NEUTRAL_KEYWORDS constants
  - _product_inherit_sync

The new package splits these across:
  - app/rms/tagging/vocabulary.py   — constants
  - app/rms/tagging/classify.py     — ingredient_blocks / normalize
  - app/rms/tagging/derive.py       — walk / derive / cascade_refresh
  - app/rms/tagging/cache.py        — persist_recipe_cache +
                                      sync_product_inheritance (was
                                      _product_inherit_sync)

Migration steps for callers:
  - `from app.rms.tag_algebra import X`  →  `from app.rms.tagging import X`
  - `_product_inherit_sync`             →  `sync_product_inheritance`
  - `_TAG_NORMALIZE` / `_TAG_ALLERGEN_BLOCKERS` / `_NEUTRAL_KEYWORDS`
                                       →  see `app.rms.tagging.vocabulary`
"""

from __future__ import annotations

# Public surface re-exported verbatim.
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


def _legacy_ingredient_dietary_set(ing: object) -> frozenset[str]:
    """Backwards-compat wrapper for ingredient_dietary_set().

    Original implementation lived in tag_algebra.py and was used by
    external scripts. Now delegated to the public normalize_all().
    """
    from app.rms.tagging.classify import normalize_all as _impl
    return _impl(getattr(ing, "dietary_tags", None))


# Keep the legacy module-level name for backwards compat.
ingredient_dietary_set = _legacy_ingredient_dietary_set


# Legacy private names kept as aliases.
_normalize_tag = normalize
_product_inherit_sync = sync_product_inheritance
from app.rms.tagging.cache import _split_tags  # noqa: F401

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
