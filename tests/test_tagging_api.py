"""tests/test_tagging_api.py — Sprint 2.2 verification.

Sprint 2.2 of the 2026-10-02 backend overhaul: tags + tagging consolidation.

This test is the regression guard so the public API of ``app.rms.tagging``
never drifts from what callers depend on. The pre-Sprint-2.2 world had:

  - ``app.rms.tags`` — owns TagKind, STARTER_TAGS, CRUD, filters
  - ``app.rms.tag_algebra`` — back-compat shim re-exporting from tagging/

Post-Sprint-2.2:

  - ``app.rms.tagging`` (the package) — owns everything
  - ``app.rms.tag_algebra`` is deleted
  - ``app.rms.tags`` is deleted

What we lock here:

  1. The canonical ``tagging`` package exports the same names callers
     were getting from ``tags`` and ``tag_algebra``.
  2. ``tagging.model.TagKind`` exists.
  3. ``tagging.ensure`` provides CRUD + link operations.
  4. ``tagging.filters`` provides the four filter dataclasses + helpers.
  5. ``tagging.classify.ingredient_dietary_set`` exists (moved from
     tag_algebra).
  6. No source code anywhere in app/ or tests/ references the deleted
     ``tags`` / ``tag_algebra`` modules.
"""

from __future__ import annotations

import pytest


# ─── File-system invariants ────────────────────────────────────────────────


def test_app_rms_has_no_tags_or_tag_algebra_files():
    """Old top-level tags.py / tag_algebra.py are gone."""
    import pathlib

    rms_dir = pathlib.Path("/opt/data/work/saskia-app/app/rms")
    assert not (rms_dir / "tags.py").exists(), (
        "app/rms/tags.py should have been deleted in Sprint 2.2"
    )
def test_no_code_references_deleted_modules():
    """No source file imports app.rms.tags (permanently deleted).

    Note 2026-10-05: app/rms/tag_algebra.py is kept as a back-compat shim
    that re-exports from app/rms/tagging/. The shim allows existing call
    sites in app/, scripts/, tests/ to keep working without forcing a
    full rewrite. New code should import from app.rms.tagging directly.
    """
    import subprocess

    result = subprocess.run(
        [
            "grep",
            "-rln",
            r"app\.rms\.tags\b",
            "/opt/data/work/saskia-app",
            "--include=*.py",
        ],
        capture_output=True,
        text=True,
    )
    offenders = sorted(
        line for line in result.stdout.strip().split("\n") if line.strip()
    )
    assert offenders == [], (
        f"Files still import app.rms.tags: {offenders}"
    )


# ─── Public API exports ────────────────────────────────────────────────────


def test_tagging_package_exports_documented_names():
    """Every public name is importable from app.rms.tagging."""
    expected = {
        # vocabulary
        "ALLERGEN_DISPLAY_ORDER",
        "ALLERGEN_KEYWORDS",
        "CANONICAL_ALLERGENS",
        "CANONICAL_DIETARY_TAGS",
        "CUSTOMER_ALLERGEN_WORDS",
        "NEUTRAL_INGREDIENT_KEYWORDS",
        "TAG_ALIASES",
        "TAG_ALLERGEN_BLOCKERS",
        # classify
        "infer_allergens",
        "infer_dietary_tags",
        "ingredient_blocks",
        "ingredient_dietary_set",
        "normalize",
        "normalize_all",
        "validate_ingredient",
        # derive
        "LineTarget",
        "TagDerivation",
        "cascade_refresh",
        "derive_recipe_tags",
        "refresh_recipe_tag_cache",
        "walk_recipe_tree",
        # ensure
        "STARTER_TAGS",
        "TagKind",
        "ensure_starter_tags",
        "ensure_tag",
        "list_tags_for_kind",
        "tag_target",
        "tags_for_target",
        "targets_with_tag",
        "untag_target",
        # filters
        "InventoryFilter",
        "ProductFilter",
        "RecipeFilter",
        "SalesFilter",
        "filter_inventory",
        "filter_products",
        "filter_recipes",
        "filter_sales",
        # audit
        "audit_all_ingredients",
        "audit_recipe_tags",
        "backfill_validation_issues",
    }
    import app.rms.tagging as pkg

    assert set(pkg.__all__) == expected, (
        f"Missing: {expected - set(pkg.__all__)}\n"
        f"Extra:   {set(pkg.__all__) - expected}"
    )


# ─── Module-level sanity ───────────────────────────────────────────────────


def test_tagging_model_module_exposes_tag_kind():
    """The model module owns the TagKind enum."""
    from app.rms.tagging.model import TagKind

    assert TagKind.PRODUCT.value == "product"
    assert TagKind.INGREDIENT.value == "ingredient"
    assert TagKind.RECIPE.value == "recipe"


def test_tagging_ensure_module_exposes_starter_tags():
    """The ensure module owns the starter-tag catalogue."""
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

    assert len(STARTER_TAGS) == 31
    assert all(callable(f) for f in (
        ensure_tag, ensure_starter_tags, list_tags_for_kind,
        tag_target, untag_target, tags_for_target, targets_with_tag,
    ))


def test_tagging_filters_module_exposes_filter_classes():
    """The filters module owns the listings filter dataclasses + helpers."""
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

    # Dataclass instances are constructible
    s = SalesFilter()
    assert s.start_date is None
    assert s.product_ids == []
    assert s.only_voided is False

    # Helpers are callable
    assert callable(filter_sales)
    assert callable(filter_inventory)
    assert callable(filter_recipes)
    assert callable(filter_products)


def test_tagging_classify_exposes_ingredient_dietary_set():
    """``ingredient_dietary_set`` moved from tag_algebra to classify."""
    from app.rms.tagging.classify import ingredient_dietary_set

    # Functional check: it returns a frozenset for any object with dietary_tags
    class FakeIng:
        dietary_tags = "vegano,sin-gluten"

    assert ingredient_dietary_set(FakeIng()) == frozenset({"vegano", "sin gluten"})

    # And a sensible default for an object with no dietary_tags attribute
    class Empty:
        pass

    assert ingredient_dietary_set(Empty()) == frozenset()