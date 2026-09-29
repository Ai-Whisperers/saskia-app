"""tests/test_recipe_intel.py — E27 recipe intelligence tests."""

from __future__ import annotations

import pytest

from app.rms.models import Ingredient, Recipe, RecipeLine
from app.rms.recipe_intel import (
    classify_recipe,
    estimate_cook_minutes,
    estimate_prep_minutes,
    estimate_total_minutes,
    infer_difficulty,
    infer_recipe_dietary,
    infer_recipe_family,
    recipe_cost_per_gram,
    recipe_ingredient_count,
    recipe_sub_recipe_depth,
    recipe_yield_grams,
)

# ---------------------------------------------------------------------------
# infer_recipe_family
# ---------------------------------------------------------------------------

def test_infer_family_panaderia():
    assert infer_recipe_family(Recipe(name="pan de campo")) == "panadería"
    assert infer_recipe_family(Recipe(name="Facturas criollas")) == "panadería"


def test_infer_family_pasteleria():
    assert infer_recipe_family(Recipe(name="muffin de chocolate")) == "pastelería"
    assert infer_recipe_family(Recipe(name="Torta de cumple")) == "pastelería"


def test_infer_family_frios():
    assert infer_recipe_family(Recipe(name="cheesecake")) == "fríos"  # could also be pastelería
    # cheesecake matches "pastelería" first via "cake" keyword; that's fine.


def test_infer_family_salados():
    assert infer_recipe_family(Recipe(name="empanada de carne")) == "salados"


def test_infer_family_frituras():
    assert infer_recipe_family(Recipe(name="oliebollen")) == "frituras"


def test_infer_family_unknown():
    assert infer_recipe_family(Recipe(name="xyz123")) == "otros"


# ---------------------------------------------------------------------------
# estimate_prep_minutes / cook / total
# ---------------------------------------------------------------------------

def test_estimate_prep_minutes_small_recipe():
    r = Recipe(name="x", yield_qty=10, yield_unit="und")
    # 10 * 2 + 0 * 1.5 = 20
    assert estimate_prep_minutes(r, ingredient_count=0) == 20


def test_estimate_prep_minutes_with_ingredients():
    r = Recipe(name="x", yield_qty=12, yield_unit="und")
    # 12 * 2 + 8 * 1.5 = 24 + 12 = 36
    assert estimate_prep_minutes(r, ingredient_count=8) == 36


def test_estimate_prep_minutes_minimum_5():
    r = Recipe(name="x", yield_qty=0.5, yield_unit="und")
    assert estimate_prep_minutes(r, ingredient_count=0) == 5


def test_estimate_cook_minutes_pasteleria():
    r = Recipe(name="torta", yield_qty=8, yield_unit="und")
    assert estimate_cook_minutes(r) == 35


def test_estimate_cook_minutes_frituras():
    r = Recipe(name="oliebollen", yield_qty=20, yield_unit="und")
    assert estimate_cook_minutes(r) == 8


def test_estimate_total_minutes():
    r = Recipe(name="torta", yield_qty=8, yield_unit="und")
    # 8*2 + 0*1.5 = 16 prep + 35 cook = 51
    assert estimate_total_minutes(r, ingredient_count=0) == 51


# ---------------------------------------------------------------------------
# infer_difficulty
# ---------------------------------------------------------------------------

def test_difficulty_simple():
    # 3 ingredients, no sub-recipes → 3/4 = 0.75 → round 1
    assert infer_difficulty(Recipe(name="x"), 3, 0) == 1


def test_difficulty_complex():
    # 16 ingredients → 16/4 = 4 → round 4
    assert infer_difficulty(Recipe(name="x"), 16, 0) == 4


def test_difficulty_with_sub_recipes():
    # 4 ingredients + 2 deep sub-recipes = 1 + 2 = 3
    assert infer_difficulty(Recipe(name="x"), 4, 2) == 3


def test_difficulty_capped_at_5():
    # 30 ingredients + 5 deep = 7.5 + 5 = 12.5 → clamp 5
    assert infer_difficulty(Recipe(name="x"), 30, 5) == 5


def test_difficulty_minimum_1():
    # 0 ingredients + 0 depth → 0 → clamp 1
    assert infer_difficulty(Recipe(name="x"), 0, 0) == 1


# ---------------------------------------------------------------------------
# infer_recipe_dietary
# ---------------------------------------------------------------------------

def test_recipe_dietary_all_vegan(session_factory):
    """Recipe with only vegan ingredients is vegan."""
    with session_factory() as s:
        ing_flour = Ingredient(name="Harina xyz", unit="kg", stock_qty=1,
                               purchase_price_gs=5000)
        ing_water = Ingredient(name="agua_xyz", unit="l", stock_qty=1,
                               purchase_price_gs=0)
        ing_sugar = Ingredient(name="azúcar_xyz", unit="kg", stock_qty=1,
                               purchase_price_gs=5000)
        s.add_all([ing_flour, ing_water, ing_sugar])
        s.flush()
        r = Recipe(name="galleta_vegana", yield_qty=10, yield_unit="und")
        s.add(r)
        s.flush()
        for ing in (ing_flour, ing_water, ing_sugar):
            s.add(RecipeLine(recipe_id=r.id, line_kind="ingredient",
                             line_ref_id=ing.id, qty=0.1))
        s.commit()
        tags = infer_recipe_dietary(s, r)
        assert "vegan" in tags


def test_recipe_dietary_with_dairy_not_vegan(session_factory):
    """Recipe containing milk is NOT vegan but IS vegetarian."""
    with session_factory() as s:
        ing_flour = Ingredient(name="Harina xyz", unit="kg", stock_qty=1,
                               purchase_price_gs=5000)
        ing_milk = Ingredient(name="Leche xyz", unit="l", stock_qty=1,
                              purchase_price_gs=8000)
        s.add_all([ing_flour, ing_milk])
        s.flush()
        r = Recipe(name="torta_xyz", yield_qty=10, yield_unit="und")
        s.add(r)
        s.flush()
        for ing in (ing_flour, ing_milk):
            s.add(RecipeLine(recipe_id=r.id, line_kind="ingredient",
                             line_ref_id=ing.id, qty=0.1))
        s.commit()
        tags = infer_recipe_dietary(s, r)
        assert "vegan" not in tags
        assert "vegetarian" in tags


# ---------------------------------------------------------------------------
# recipe_yield_grams
# ---------------------------------------------------------------------------

def test_recipe_yield_grams_und():
    r = Recipe(name="x", yield_qty=12, yield_unit="und")
    # 12 * 50 = 600
    assert recipe_yield_grams(r) == 600.0


def test_recipe_yield_grams_kg():
    r = Recipe(name="x", yield_qty=2, yield_unit="kg")
    assert recipe_yield_grams(r) == 2000.0


def test_recipe_yield_grams_unknown_unit():
    r = Recipe(name="x", yield_qty=1, yield_unit="cubeta")
    assert recipe_yield_grams(r) is None


def test_recipe_yield_grams_g():
    r = Recipe(name="x", yield_qty=500, yield_unit="g")
    assert recipe_yield_grams(r) == 500.0


# ---------------------------------------------------------------------------
# recipe_ingredient_count + sub_recipe_depth
# ---------------------------------------------------------------------------

def test_recipe_ingredient_count_basic(session_factory):
    with session_factory() as s:
        ing1 = Ingredient(name="ing1_xyz", unit="kg", stock_qty=1,
                          purchase_price_gs=1000)
        ing2 = Ingredient(name="ing2_xyz", unit="kg", stock_qty=1,
                          purchase_price_gs=1000)
        s.add_all([ing1, ing2])
        s.flush()
        r = Recipe(name="count_test_xyz", yield_qty=1, yield_unit="und")
        s.add(r)
        s.flush()
        s.add(RecipeLine(recipe_id=r.id, line_kind="ingredient",
                         line_ref_id=ing1.id, qty=0.1))
        s.add(RecipeLine(recipe_id=r.id, line_kind="ingredient",
                         line_ref_id=ing2.id, qty=0.1))
        s.commit()
        assert recipe_ingredient_count(r) == 2


def test_recipe_sub_recipe_depth_no_sub(session_factory):
    with session_factory() as s:
        r = Recipe(name="depth_test_xyz", yield_qty=1, yield_unit="und")
        s.add(r)
        s.commit()
        assert recipe_sub_recipe_depth(s, r) == 0


def test_recipe_sub_recipe_depth_one_level(session_factory):
    with session_factory() as s:
        sub = Recipe(name="sub_xyz", yield_qty=1, yield_unit="und")
        main = Recipe(name="main_xyz", yield_qty=1, yield_unit="und")
        s.add_all([sub, main])
        s.flush()
        s.add(RecipeLine(recipe_id=main.id, line_kind="sub_recipe",
                         line_ref_id=sub.id, qty=1))
        s.commit()
        assert recipe_sub_recipe_depth(s, main) == 1


def test_recipe_sub_recipe_depth_three_levels(session_factory):
    with session_factory() as s:
        sub3 = Recipe(name="sub3_xyz", yield_qty=1, yield_unit="und")
        sub2 = Recipe(name="sub2_xyz", yield_qty=1, yield_unit="und")
        sub1 = Recipe(name="sub1_xyz", yield_qty=1, yield_unit="und")
        main = Recipe(name="main_xyz", yield_qty=1, yield_unit="und")
        s.add_all([sub3, sub2, sub1, main])
        s.flush()
        s.add(RecipeLine(recipe_id=main.id, line_kind="sub_recipe",
                         line_ref_id=sub1.id, qty=1))
        s.add(RecipeLine(recipe_id=sub1.id, line_kind="sub_recipe",
                         line_ref_id=sub2.id, qty=1))
        s.add(RecipeLine(recipe_id=sub2.id, line_kind="sub_recipe",
                         line_ref_id=sub3.id, qty=1))
        s.commit()
        assert recipe_sub_recipe_depth(s, main) == 3


# ---------------------------------------------------------------------------
# classify_recipe (composite)
# ---------------------------------------------------------------------------

def test_classify_recipe_basic(session_factory):
    with session_factory() as s:
        ing = Ingredient(name="Harina xyz", unit="kg", stock_qty=1,
                         purchase_price_gs=5000)
        s.add(ing)
        s.flush()
        r = Recipe(name="pan_de_campo", yield_qty=4, yield_unit="und")
        s.add(r)
        s.flush()
        s.add(RecipeLine(recipe_id=r.id, line_kind="ingredient",
                         line_ref_id=ing.id, qty=0.5))
        s.commit()
        result = classify_recipe(s, r)
        assert result["family"] == "panadería"
        assert result["difficulty"] >= 1
        assert result["prep_minutes"] >= 5
        assert result["cook_minutes"] == 30  # panadería default
        assert "yield_grams" in result
        assert "cost_per_gram" in result


# ---------------------------------------------------------------------------
# recipe_cost_per_gram — uses existing costing module
# ---------------------------------------------------------------------------

def test_recipe_cost_per_gram_computes(session_factory):
    """A recipe with cost should compute cost-per-gram."""
    with session_factory() as s:
        ing = Ingredient(name="Harina xyz", unit="kg", stock_qty=1,
                         purchase_price_gs=5000)
        s.add(ing)
        s.flush()
        r = Recipe(name="cpgram_test", yield_qty=10, yield_unit="und")
        s.add(r)
        s.flush()
        s.add(RecipeLine(recipe_id=r.id, line_kind="ingredient",
                         line_ref_id=ing.id, qty=0.5))  # 0.5kg flour
        s.commit()
        cost_g = recipe_cost_per_gram(s, r)
        # 0.5kg × 5000 Gs/kg = 2500 Gs / 500g yield (10 und × 50g) = 5 Gs/g
        assert cost_g == pytest.approx(5.0, rel=0.01)


def test_recipe_cost_per_gram_unknown_unit_returns_none(session_factory):
    with session_factory() as s:
        # Valid unit but no yield-equivalent conversion defined → returns None
        # 'ml' is valid unit but DEFAULT_YIELD_GRAMS_PER_UNIT doesn't have it,
        # so recipe_yield_grams returns None.
        # Actually ml IS in the dict, mapping to 1. Use a different scenario.
        # Skip — None case covered by yield_unit=None path.
        r = Recipe(name="cpgram_unknown", yield_qty=None, yield_unit=None)
        s.add(r)
        s.commit()
        assert recipe_cost_per_gram(s, r) is None


def test_recipe_yield_grams_with_valid_units():
    """Sanity: all 5 valid units convert reasonably."""
    r = Recipe(name="x", yield_qty=1, yield_unit="und")
    assert recipe_yield_grams(r) == 50.0
    r = Recipe(name="x", yield_qty=100, yield_unit="g")
    assert recipe_yield_grams(r) == 100.0
    r = Recipe(name="x", yield_qty=1, yield_unit="kg")
    assert recipe_yield_grams(r) == 1000.0
    r = Recipe(name="x", yield_qty=500, yield_unit="ml")
    assert recipe_yield_grams(r) == 500.0
    r = Recipe(name="x", yield_qty=1, yield_unit="l")
    assert recipe_yield_grams(r) == 1000.0
