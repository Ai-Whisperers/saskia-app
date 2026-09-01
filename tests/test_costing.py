"""tests/test_costing.py — formal tests for recipe/product costing engine.

Per dev plan Batch 3 (~3 hours). Lifts coverage of app/rms/costing.py from
the 5-scenario smoke test into proper pytest. Targets ~16 tests.

Covers:
- recipe_batch_cost_gs: simple, sub-recipe, cycle, missing price
- recipe_unit_cost_gs: normal + missing yield
- product_unit_cost_gs: normal + no recipe
- product_margin: normal + no cost + zero sale price
"""

from __future__ import annotations


def _seed_basic(session_factory):
    """3 ingredients + 1 recipe (Muffin, 12 und) with known prices."""
    from app.rms.models import Ingredient, Recipe, RecipeLine

    with session_factory() as s:
        flour = Ingredient(name="Harina", unit="kg", stock_qty=2.0, purchase_price_gs=5000)
        sugar = Ingredient(name="Azúcar", unit="kg", stock_qty=1.5, purchase_price_gs=4000)
        egg = Ingredient(name="Huevo", unit="und", stock_qty=20.0, purchase_price_gs=1500)
        s.add_all([flour, sugar, egg])
        s.flush()

        recipe = Recipe(name="Muffin", yield_qty=12.0, yield_unit="und")
        s.add(recipe)
        s.flush()

        s.add_all(
            [
                RecipeLine(
                    recipe_id=recipe.id,
                    line_kind="ingredient",
                    line_ref_id=flour.id,
                    qty=0.3,
                ),
                RecipeLine(
                    recipe_id=recipe.id,
                    line_kind="ingredient",
                    line_ref_id=sugar.id,
                    qty=0.2,
                ),
                RecipeLine(
                    recipe_id=recipe.id,
                    line_kind="ingredient",
                    line_ref_id=egg.id,
                    qty=2.0,
                ),
            ]
        )
        s.commit()
        return recipe.id


def _seed_sub_recipe(session_factory):
    """1 base (Masa) + 1 sub-recipe (Muffin uses Masa) + 1 product."""
    from app.rms.models import Ingredient, Product, Recipe, RecipeLine

    with session_factory() as s:
        flour = Ingredient(name="Harina", unit="kg", stock_qty=5.0, purchase_price_gs=5000)
        egg = Ingredient(name="Huevo", unit="und", stock_qty=30.0, purchase_price_gs=1500)
        s.add_all([flour, egg])
        s.flush()

        # Sub-recipe: Masa base (12 unidades)
        masa = Recipe(name="Masa base", yield_qty=12.0, yield_unit="und")
        s.add(masa)
        s.flush()
        s.add_all(
            [
                RecipeLine(
                    recipe_id=masa.id,
                    line_kind="ingredient",
                    line_ref_id=flour.id,
                    qty=0.5,
                ),
                RecipeLine(
                    recipe_id=masa.id,
                    line_kind="ingredient",
                    line_ref_id=egg.id,
                    qty=3.0,
                ),
            ]
        )
        s.flush()

        # Top recipe: Muffin uses 1 unidad of Masa
        muffin = Recipe(name="Muffin", yield_qty=12.0, yield_unit="und")
        s.add(muffin)
        s.flush()
        s.add(
            RecipeLine(
                recipe_id=muffin.id,
                line_kind="sub_recipe",
                line_ref_id=masa.id,
                qty=1.0,
            )
        )
        s.flush()

        # Product
        product = Product(
            name="Muffin Producto",
            portion_label="1 muffin",
            sale_price_gs=8000,
            recipe_id=muffin.id,
        )
        s.add(product)
        s.commit()
        return masa.id, muffin.id, product.id


# --- recipe_batch_cost_gs ---


def test_recipe_batch_cost_simple(session_factory):
    """3 ingredients, all priced: cost = 0.3*5000 + 0.2*4000 + 2.0*1500 = 5300 Gs."""
    from app.rms.costing import recipe_batch_cost_gs

    recipe_id = _seed_basic(session_factory)
    with session_factory() as s:
        result = recipe_batch_cost_gs(s, recipe_id)
    assert result.batch_cost_gs == 5300
    assert result.missing_ingredient_names == []
    assert result.cycle_detected is False
    assert result.has_missing is False


def test_recipe_batch_cost_sub_recipe(session_factory):
    """Muffin uses 1 of Masa (yield 12). Masa = 0.5*5000 + 3*1500 = 7000. Ratio = 1/12.

    Muffin batch cost = (1/12) * 7000 = 583 Gs (rounded half-up from 583.333...).
    """
    from app.rms.costing import recipe_batch_cost_gs

    _, muffin_id, _ = _seed_sub_recipe(session_factory)
    with session_factory() as s:
        result = recipe_batch_cost_gs(s, muffin_id)
    assert result.batch_cost_gs == 583  # 7000/12 = 583.333... → 583 (half-up)
    assert result.cycle_detected is False


def test_recipe_batch_cost_cycle(session_factory):
    """A uses B uses A → cycle detected, batch_cost_gs=None, cycle_detected=True."""
    from app.rms.costing import recipe_batch_cost_gs
    from app.rms.models import Ingredient, Recipe, RecipeLine

    with session_factory() as s:
        ing = Ingredient(name="Harina", unit="kg", stock_qty=2.0, purchase_price_gs=5000)
        s.add(ing)
        s.flush()

        rec_a = Recipe(name="A", yield_qty=10.0, yield_unit="und")
        rec_b = Recipe(name="B", yield_qty=10.0, yield_unit="und")
        s.add_all([rec_a, rec_b])
        s.flush()

        s.add_all(
            [
                RecipeLine(
                    recipe_id=rec_a.id, line_kind="sub_recipe", line_ref_id=rec_b.id, qty=1.0
                ),
                RecipeLine(
                    recipe_id=rec_b.id, line_kind="sub_recipe", line_ref_id=rec_a.id, qty=1.0
                ),
            ]
        )
        s.commit()
        a_id = rec_a.id

    with session_factory() as s:
        result = recipe_batch_cost_gs(s, a_id)
    assert result.batch_cost_gs is None
    assert result.cycle_detected is True
    assert result.has_missing is False


def test_recipe_batch_cost_missing_price(session_factory):
    """One ingredient has purchase_price_gs=None → batch_cost_gs=None, has_missing=True."""
    from app.rms.costing import recipe_batch_cost_gs
    from app.rms.models import Ingredient, Recipe, RecipeLine

    with session_factory() as s:
        flour = Ingredient(name="Harina", unit="kg", stock_qty=2.0, purchase_price_gs=5000)
        # Sugar has no price yet
        sugar = Ingredient(name="Azúcar", unit="kg", stock_qty=1.5, purchase_price_gs=None)
        s.add_all([flour, sugar])
        s.flush()

        recipe = Recipe(name="Bizcocho", yield_qty=12.0, yield_unit="und")
        s.add(recipe)
        s.flush()
        s.add_all(
            [
                RecipeLine(
                    recipe_id=recipe.id,
                    line_kind="ingredient",
                    line_ref_id=flour.id,
                    qty=0.3,
                ),
                RecipeLine(
                    recipe_id=recipe.id,
                    line_kind="ingredient",
                    line_ref_id=sugar.id,
                    qty=0.2,
                ),
            ]
        )
        s.commit()
        recipe_id = recipe.id

    with session_factory() as s:
        result = recipe_batch_cost_gs(s, recipe_id)
    assert result.batch_cost_gs is None
    assert result.cycle_detected is False
    assert result.has_missing is True
    # Missing list mentions sugar
    assert any("Azúcar" in name for name in result.missing_ingredient_names)


def test_recipe_batch_cost_missing_recipe(session_factory):
    """Unknown recipe_id → returns CostResult with placeholder name in missing list."""
    from app.rms.costing import recipe_batch_cost_gs

    with session_factory() as s:
        result = recipe_batch_cost_gs(s, 99999)
    assert result.batch_cost_gs is None
    assert "99999" in result.missing_ingredient_names[0]


def test_recipe_batch_cost_no_yield(session_factory):
    """Recipe with yield_qty=NULL → batch_cost_gs=None, has_missing=True."""
    from app.rms.costing import recipe_batch_cost_gs
    from app.rms.models import Ingredient, Recipe, RecipeLine

    with session_factory() as s:
        flour = Ingredient(name="Harina", unit="kg", stock_qty=2.0, purchase_price_gs=5000)
        s.add(flour)
        s.flush()

        recipe = Recipe(name="Sin rendimiento", yield_qty=None, yield_unit="und")
        s.add(recipe)
        s.flush()
        s.add(
            RecipeLine(
                recipe_id=recipe.id,
                line_kind="ingredient",
                line_ref_id=flour.id,
                qty=0.3,
            )
        )
        s.commit()
        recipe_id = recipe.id

    with session_factory() as s:
        result = recipe_batch_cost_gs(s, recipe_id)
    assert result.batch_cost_gs is None
    assert result.cycle_detected is False
    assert result.has_missing is True


# --- recipe_unit_cost_gs ---


def test_recipe_unit_cost_normal(session_factory):
    """unit_cost = batch_cost / yield_qty. 5300 / 12 = 442 (half-up from 441.666)."""
    from app.rms.costing import recipe_unit_cost_gs

    recipe_id = _seed_basic(session_factory)
    with session_factory() as s:
        result = recipe_unit_cost_gs(s, recipe_id)
    assert result.batch_cost_gs == 442
    assert result.missing_ingredient_names == []


def test_recipe_unit_cost_no_yield(session_factory):
    """yield_qty NULL → walker reports 'sin rendimiento', unit_cost is None."""
    from app.rms.costing import recipe_unit_cost_gs
    from app.rms.models import Recipe

    with session_factory() as s:
        s.add(Recipe(name="Empty", yield_qty=None, yield_unit="und"))
        s.commit()

    with session_factory() as s:
        result = recipe_unit_cost_gs(s, 1)
    assert result.batch_cost_gs is None
    # Walker reports the recipe is missing yield first; that error message wins.
    assert "sin rendimiento" in str(result.missing_ingredient_names)


def test_recipe_unit_cost_propagates_missing(session_factory):
    """Missing price propagates: unit cost is also None."""
    from app.rms.costing import recipe_unit_cost_gs
    from app.rms.models import Ingredient, Recipe, RecipeLine

    with session_factory() as s:
        ing = Ingredient(name="X", unit="kg", stock_qty=1.0, purchase_price_gs=None)
        s.add(ing)
        s.flush()
        rec = Recipe(name="R", yield_qty=10.0, yield_unit="und")
        s.add(rec)
        s.flush()
        s.add(RecipeLine(recipe_id=rec.id, line_kind="ingredient", line_ref_id=ing.id, qty=1.0))
        s.commit()
        rec_id = rec.id

    with session_factory() as s:
        result = recipe_unit_cost_gs(s, rec_id)
    assert result.batch_cost_gs is None


# --- product_unit_cost_gs ---


def test_product_unit_cost_normal(session_factory):
    """product has recipe → returns recipe_unit_cost."""
    from app.rms.costing import product_unit_cost_gs

    _, _, product_id = _seed_sub_recipe(session_factory)
    with session_factory() as s:
        result = product_unit_cost_gs(s, product_id)
    # Muffin batch = 583 (from sub_recipe test); unit = 583/12 = 49 (half-up from 48.58)
    assert result.batch_cost_gs == 49


def test_product_unit_cost_no_recipe(session_factory):
    """Product with recipe_id=NULL → batch_cost_gs=None, 'product sin receta' in missing."""
    from app.rms.costing import product_unit_cost_gs
    from app.rms.models import Product

    with session_factory() as s:
        s.add(Product(name="Mystery", portion_label="1", sale_price_gs=5000, recipe_id=None))
        s.commit()

    with session_factory() as s:
        result = product_unit_cost_gs(s, 1)
    assert result.batch_cost_gs is None
    assert "product sin receta" in result.missing_ingredient_names


def test_product_unit_cost_missing_product(session_factory):
    """Unknown product_id → batch_cost_gs=None, product_id in missing."""
    from app.rms.costing import product_unit_cost_gs

    with session_factory() as s:
        result = product_unit_cost_gs(s, 99999)
    assert result.batch_cost_gs is None
    assert "99999" in result.missing_ingredient_names[0]


# --- product_margin ---


def test_product_margin_normal(session_factory):
    """sale_price=8000, cost=49 (from product_unit_cost_normal). margin=7951, ratio≈0.994."""
    from app.rms.costing import product_margin

    _, _, product_id = _seed_sub_recipe(session_factory)
    with session_factory() as s:
        margin_gs, ratio = product_margin(s, product_id)
    # margin_gs = 8000 - 49 = 7951; ratio = 7951/8000 ≈ 0.994
    assert margin_gs == 7951
    assert ratio is not None
    assert 0.99 < ratio < 1.0


def test_product_margin_no_cost(session_factory):
    """Product without recipe → margin None, ratio None."""
    from app.rms.costing import product_margin
    from app.rms.models import Product

    with session_factory() as s:
        s.add(Product(name="Mystery", portion_label="1", sale_price_gs=5000, recipe_id=None))
        s.commit()

    with session_factory() as s:
        margin_gs, ratio = product_margin(s, 1)
    assert margin_gs is None
    assert ratio is None


def test_product_margin_zero_sale_price(session_factory):
    """sale_price_gs=0 with valid cost → ratio is None (division-by-zero guard)."""
    from app.rms.costing import product_margin
    from app.rms.models import Ingredient, Product, Recipe, RecipeLine

    with session_factory() as s:
        ing = Ingredient(name="X", unit="kg", stock_qty=1.0, purchase_price_gs=100)
        rec = Recipe(name="R", yield_qty=10.0, yield_unit="und")
        s.add_all([ing, rec])
        s.flush()
        s.add(RecipeLine(recipe_id=rec.id, line_kind="ingredient", line_ref_id=ing.id, qty=0.1))
        s.flush()
        s.add(
            Product(
                name="Zero",
                portion_label="1",
                sale_price_gs=0,
                recipe_id=rec.id,
            )
        )
        s.commit()

    with session_factory() as s:
        margin_gs, ratio = product_margin(s, 1)
    # recipe batch cost = 0.1 * 100 = 10; unit cost = 10 / 10 = 1; margin = 0 - 1 = -1
    assert margin_gs == -1
    assert ratio is None  # sale_price_gs <= 0 branch


def test_product_margin_missing_product(session_factory):
    """Unknown product_id → (None, None)."""
    from app.rms.costing import product_margin

    with session_factory() as s:
        margin_gs, ratio = product_margin(s, 99999)
    assert margin_gs is None
    assert ratio is None
