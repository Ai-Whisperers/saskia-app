"""app/rms/tagging/ — Centralized dietary tag intelligence.

Refactored 2026-09-29 from three scattered implementations:
- tag_algebra.py (recipe-level intersection, mixed concerns)
- ingredient_intel.py (per-ingredient English/Spanish keyword tables)
- recipe_intel.py (per-recipe keyword heuristic, divergent semantics)

Sub-modules:
  vocabulary.py   — single source of truth for tag strings:
                    CANONICAL_DIETARY_TAGS, ALLERGEN_KEYWORDS,
                    TAG_ALIASES, TAG_ALLERGEN_BLOCKERS,
                    NEUTRAL_INGREDIENT_KEYWORDS, CUSTOMER_ALLERGEN_WORDS.
  classify.py     — pure functions:
                    normalize, normalize_all, infer_allergens,
                    infer_dietary_tags, ingredient_blocks,
                    validate_ingredient.
  derive.py       — recipe-tree walker + derive_recipe_tags + cascade_refresh.
  cache.py        — schema-write helpers: persist_recipe_cache,
                    sync_product_inheritance.
  audit.py        — audit_all_ingredients, audit_recipe_tags,
                    backfill_validation_issues.

Public API (re-exported here for convenience):
    CANONICAL_DIETARY_TAGS, CANONICAL_ALLERGENS, ALLERGEN_KEYWORDS,
    TAG_ALIASES, TAG_ALLERGEN_BLOCKERS, NEUTRAL_INGREDIENT_KEYWORDS,
    CUSTOMER_ALLERGEN_WORDS,
    normalize, normalize_all, infer_allergens, infer_dietary_tags,
    ingredient_blocks, validate_ingredient,
    LineTarget, TagDerivation, walk_recipe_tree, derive_recipe_tags,
    refresh_recipe_tag_cache, cascade_refresh,
    audit_all_ingredients, audit_recipe_tags, backfill_validation_issues.

Migration: 061 adds ingredient.tag_validation_issues and backfills via
backfill_validation_issues. Subsequent inventory saves call
validate_ingredient() to keep the column current.
"""

from __future__ import annotations

from app.rms.tagging.audit import (
    audit_all_ingredients,
    audit_recipe_tags,
    backfill_validation_issues,
)
from app.rms.tagging.classify import (
    infer_allergens,
    infer_dietary_tags,
    ingredient_blocks,
    ingredient_dietary_set,
    normalize,
    normalize_all,
    validate_ingredient,
)
from app.rms.tagging.derive import (
    LineTarget,
    TagDerivation,
    cascade_refresh,
    derive_recipe_tags,
    refresh_recipe_tag_cache,
    walk_recipe_tree,
)
from app.rms.tagging.ensure import (
    STARTER_TAGS,
    ensure_starter_tags,
    ensure_tag,
    list_tags_for_kind,
    tag_target,
    tags_for_target,
    targets_with_tag,
    untag_target,
)
from app.rms.tagging.filters import (
    InventoryFilter,
    ProductFilter,
    RecipeFilter,
    SalesFilter,
    filter_inventory,
    filter_products,
    filter_recipes,
    filter_sales,
)
from app.rms.tagging.model import TagKind
from app.rms.tagging.vocabulary import (
    ALLERGEN_DISPLAY_ORDER,
    ALLERGEN_KEYWORDS,
    CANONICAL_ALLERGENS,
    CANONICAL_DIETARY_TAGS,
    CUSTOMER_ALLERGEN_WORDS,
    NEUTRAL_INGREDIENT_KEYWORDS,
    TAG_ALIASES,
    TAG_ALLERGEN_BLOCKERS,
)
from app.rms.tagging.ensure import STARTER_TAGS  # re-export for db.py

__all__ = [
    "ALLERGEN_DISPLAY_ORDER",
    "ALLERGEN_KEYWORDS",
    "CANONICAL_ALLERGENS",
    "CANONICAL_DIETARY_TAGS",
    "CUSTOMER_ALLERGEN_WORDS",
    "NEUTRAL_INGREDIENT_KEYWORDS",
    "STARTER_TAGS",
    "TAG_ALIASES",
    "TAG_ALLERGEN_BLOCKERS",
    "LineTarget",
    "TagDerivation",
    "audit_all_ingredients",
    "audit_recipe_tags",
    "backfill_validation_issues",
    "cascade_refresh",
    "derive_recipe_tags",
    "infer_allergens",
    "infer_dietary_tags",
    "ingredient_blocks",
    "ingredient_dietary_set",
    "normalize",
    "normalize_all",
    "refresh_recipe_tag_cache",
    "validate_ingredient",
    "walk_recipe_tree",
]
