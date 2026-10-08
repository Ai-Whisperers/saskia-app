"""tests/test_waste_roi_per_ingredient.py — BACKLOG #34 waste ROI per ingredient test."""

from __future__ import annotations

from datetime import datetime


def test_waste_roi_per_ingredient_no_data(testdb):
    """When no waste data, return empty list."""
    from app.rms.analytics import waste_roi_per_ingredient

    result = waste_roi_per_ingredient(testdb)
    assert result == []


def test_waste_roi_per_ingredient_with_merma(testdb):
    """When some waste, calculate cost/batch."""
    from app.rms.analytics import waste_roi_per_ingredient
    from app.rms.models import Ingredient, Recipe, RecipeLine, StockMovement

    ing = Ingredient(name="Azúcar", cost_per_kg_gs=5000)
    testdb.add(ing)
    recipe = Recipe(name="Torta", yield_qty=4.0)
    testdb.add(recipe)
    RecipeLine(ingredient=ing, recipe=recipe, qty_kg=0.5)
    testdb.flush()

    # Create batch with waste
    batch_id = 1
    testdb.add(
        StockMovement(
            batch_id=batch_id,
            recipe_id=recipe.id,
            movement_type="merma",
            created_at=datetime.now(),
            qty_gs=1000,  # wasted 1000 Gs worth
        )
    )
    testdb.commit()

    result = waste_roi_per_ingredient(testdb, since_days=1)
    assert len(result) == 1
    r = result[0]
    assert r["ingredient_name"] == "Azúcar"
    assert r["waste_gs"] == 1000.0
    assert r["total_batches"] == 1
    assert r["waste_per_batch"] == 1000.0
    assert r["recipe_usage"] == 1
    assert r["waste_pct"] == 0.0  # no sales, so waste_pct undefined


def test_waste_roi_per_ingredient_with_usage(testdb):
    """With both waste and usage, calculate % waste."""
    from app.rms.analytics import waste_roi_per_ingredient
    from app.rms.models import Ingredient, Recipe, RecipeLine, StockMovement

    ing = Ingredient(name="Harina", cost_per_kg_gs=3000)
    testdb.add(ing)
    recipe = Recipe(name="Pan", yield_qty=10.0)
    testdb.add(recipe)
    RecipeLine(ingredient=ing, recipe=recipe, qty_kg=1.0)
    testdb.flush()

    batch_id = 1
    # First sale: 5000 Gs used
    testdb.add(
        StockMovement(
            batch_id=batch_id,
            recipe_id=recipe.id,
            movement_type="sale",
            created_at=datetime.now(),
            qty_gs=5000,
        )
    )
    # Then waste: 1000 Gs wasted
    testdb.add(
        StockMovement(
            batch_id=batch_id,
            recipe_id=recipe.id,
            movement_type="merma",
            created_at=datetime.now(),
            qty_gs=1000,
        )
    )
    testdb.commit()

    result = waste_roi_per_ingredient(testdb, since_days=1)
    r = result[0]
    assert r["waste_gs"] == 1000.0
    assert r["total_batches"] == 1
    assert r["waste_per_batch"] == 1000.0
    assert r["waste_pct"] == 20.0  # 1000 waste / 5000 used * 100


def test_waste_roi_per_ingredient_multiple_batches(testdb):
    """Sum waste across multiple batches."""
    from app.rms.analytics import waste_roi_per_ingredient
    from app.rms.models import Ingredient, Recipe, RecipeLine, StockMovement

    ing = Ingredient(name="Leche", cost_per_kg_gs=2000)
    testdb.add(ing)
    recipe = Recipe(name="Flan", yield_qty=6.0)
    testdb.add(recipe)
    RecipeLine(ingredient=ing, recipe=recipe, qty_kg=0.5)
    testdb.flush()

    # Batch 1: 500 waste
    testdb.add(
        StockMovement(
            batch_id=1,
            recipe_id=recipe.id,
            movement_type="merma",
            created_at=datetime.now(),
            qty_gs=500,
        )
    )
    # Batch 2: 1500 waste
    testdb.add(
        StockMovement(
            batch_id=2,
            recipe_id=recipe.id,
            movement_type="merma",
            created_at=datetime.now(),
            qty_gs=1500,
        )
    )
    testdb.commit()

    result = waste_roi_per_ingredient(testdb, since_days=1)
    r = result[0]
    assert r["waste_gs"] == 2000.0
    assert r["total_batches"] == 2
    assert r["waste_per_batch"] == 1000.0  # (500+1500)/2


def test_waste_roi_per_ingredient_filter_ingredient(testdb):
    """Filter to a single ingredient by ID."""
    from app.rms.analytics import waste_roi_per_ingredient
    from app.rms.models import Ingredient, Recipe, RecipeLine, StockMovement

    ing1 = Ingredient(name="Chocolate", cost_per_kg_gs=10000)
    ing2 = Ingredient(name="Vainilla", cost_per_kg_gs=4000)
    testdb.add_all([ing1, ing2])
    recipe1 = Recipe(name="Torta Chocolate", yield_qty=4.0)
    recipe2 = Recipe(name="Torta Vainilla", yield_qty=4.0)
    testdb.add_all([recipe1, recipe2])
    RecipeLine(ingredient=ing1, recipe=recipe1, qty_kg=0.2)
    RecipeLine(ingredient=ing2, recipe=recipe2, qty_kg=0.5)
    testdb.flush()

    # Only chocolate wasted
    testdb.add(
        StockMovement(
            batch_id=1,
            recipe_id=recipe1.id,
            movement_type="merma",
            created_at=datetime.now(),
            qty_gs=2000,
        )
    )
    testdb.commit()

    # All ingredients
    result_all = waste_roi_per_ingredient(testdb)
    assert len(result_all) == 1  # only chocolate has waste
    assert result_all[0]["ingredient_name"] == "Chocolate"

    # Filter to chocolate (same result)
    result_choc = waste_roi_per_ingredient(testdb, ingredient_id=ing1.id)
    assert len(result_choc) == 1
    assert result_choc[0]["ingredient_name"] == "Chocolate"

    # Filter to vainilla (empty)
    result_vain = waste_roi_per_ingredient(testdb, ingredient_id=ing2.id)
    assert result_vain == []
