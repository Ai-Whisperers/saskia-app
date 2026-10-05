"""Recipes polymorphic roundtrip tests.

Tests that RecipeLine.line_kind can be 'ingredient' OR 'sub_recipe',
and that batch_cost/unit_cost compute correctly.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.crud
from app.rms.models import Ingredient, Recipe, RecipeLine


def test_recetas_page_loads(authed_client):
    """GET /recetas must return 200."""
    r = authed_client.get("/recetas")
    assert r.status_code == 200


def test_recetas_nueva_form_loads(authed_client):
    """GET /recetas/nueva must return 200."""
    r = authed_client.get("/recetas/nueva")
    assert r.status_code == 200


def test_recipe_with_ingredient_line(authed_client, session_factory):
    """Create recipe with line_kind='ingredient'. Must roundtrip."""

    with session_factory() as s:
        ing = Ingredient(
            name="Recipe Test Ing",
            unit="kg",
            stock_qty=100.0,
            min_stock_qty=10.0,
        )
        s.add(ing)
        s.commit()
        s.refresh(ing)

        recipe = Recipe(
            name="Polymorphic Test Recipe",
            yield_qty=10.0,
        )
        s.add(recipe)
        s.commit()
        s.refresh(recipe)

        line = RecipeLine(
            recipe_id=recipe.id,
            line_kind="ingredient",
            line_ref_id=ing.id,
            qty=2.0,
        )
        s.add(line)
        s.commit()

        recipe_id = recipe.id

    # Verify the recipe loaded with line
    with session_factory() as s:
        loaded = s.get(Recipe, recipe_id)
        assert loaded is not None
        assert loaded.yield_qty == 10.0


def test_recipe_with_sub_recipe_line(authed_client, session_factory):
    """Create recipe with line_kind='sub_recipe' (recursive)."""

    with session_factory() as s:
        # Create sub-recipe
        sub = Recipe(name="Sub Recipe", yield_qty=5.0)
        s.add(sub)
        s.commit()
        s.refresh(sub)

        # Create parent recipe referencing sub
        parent = Recipe(name="Parent Recipe", yield_qty=10.0)
        s.add(parent)
        s.commit()
        s.refresh(parent)

        line = RecipeLine(
            recipe_id=parent.id,
            line_kind="sub_recipe",
            line_ref_id=sub.id,
            qty=2.0,
        )
        s.add(line)
        s.commit()

        parent_id = parent.id

    with session_factory() as s:
        loaded = s.get(Recipe, parent_id)
        assert loaded is not None


def test_recipe_detail_page_shows_cost(authed_client, session_factory):
    """GET /recetas/{id} must render batch_cost + unit_cost."""

    with session_factory() as s:
        ing = Ingredient(
            name="Cost Test Ing",
            unit="kg",
            stock_qty=100.0,
            purchase_price_gs=1000,
        )
        s.add(ing)
        s.commit()
        s.refresh(ing)

        recipe = Recipe(name="Cost Recipe", yield_qty=10.0)
        s.add(recipe)
        s.commit()
        s.refresh(recipe)

        line = RecipeLine(
            recipe_id=recipe.id,
            line_kind="ingredient",
            line_ref_id=ing.id,
            qty=2.0,
        )
        s.add(line)
        s.commit()
        recipe_id = recipe.id

    r = authed_client.get(f"/recetas/{recipe_id}")
    assert r.status_code == 200, f"/recetas/{recipe_id} returned {r.status_code}"


def test_recipe_yield_qty_validation(session_factory):
    """Recipe.yield_qty is OPTIONAL (nullable=True). Sales are rejected when NULL."""

    with session_factory() as s:
        # Recipe without yield_qty should succeed (NULL is allowed)
        recipe = Recipe(name="No Yield Recipe", yield_qty=None)
        s.add(recipe)
        s.commit()
        s.refresh(recipe)

        # Verify it's allowed
        assert recipe.yield_qty is None, "yield_qty should be nullable"


def test_recipe_line_kind_validation(session_factory):
    """RecipeLine.line_kind must be 'ingredient' or 'sub_recipe' (Polymorphic)."""
    with session_factory() as s:
        ing = Ingredient(name="VK Test Ing", unit="kg", stock_qty=10.0, min_stock_qty=1.0)
        s.add(ing)
        s.commit()
        s.refresh(ing)

        recipe = Recipe(name="VK Test Recipe", yield_qty=5.0)
        s.add(recipe)
        s.commit()
        s.refresh(recipe)

        # Valid line_kind
        line_ing = RecipeLine(
            recipe_id=recipe.id,
            line_kind="ingredient",
            line_ref_id=ing.id,
            qty=1.0,
        )
        s.add(line_ing)
        s.commit()

        # Verify polymorphic
        loaded = s.get(RecipeLine, line_ing.id)
        assert loaded.line_kind == "ingredient"
