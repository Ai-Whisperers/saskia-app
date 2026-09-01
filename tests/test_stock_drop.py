"""tests/test_stock_drop.py — apply_sale + stock decrement.

Per dev plan Batch 3. Targets ~6 tests.

Covers:
- apply_sale simple: stock drops correctly
- apply_sale sub-recipe: walks tree, drops sub-recipe ingredients
- apply_sale no recipe: sale is saved, has_recipe=False, no stock moves
- apply_sale NULL yield: raises RecipeWithoutYield
- apply_sale zero/negative qty: raises ValueError
- stock decrement is persisted (re-read after commit)
"""

from __future__ import annotations

from datetime import datetime


def _seed_simple(session_factory):
    """1 product with recipe, 2 ingredients priced."""
    from app.rms.models import Ingredient, Product, Recipe, RecipeLine

    with session_factory() as s:
        flour = Ingredient(name="Harina", unit="kg", stock_qty=2.0, purchase_price_gs=5000)
        egg = Ingredient(name="Huevo", unit="und", stock_qty=20.0, purchase_price_gs=1500)
        s.add_all([flour, egg])
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
                    line_ref_id=egg.id,
                    qty=2.0,
                ),
            ]
        )
        s.flush()

        product = Product(
            name="Muffin",
            portion_label="1 muffin",
            sale_price_gs=8000,
            recipe_id=recipe.id,
        )
        s.add(product)
        s.commit()
        return flour.id, egg.id, product.id


def _seed_sub_recipe(session_factory):
    """Product → Recipe → sub-recipe → ingredient."""
    from app.rms.models import Ingredient, Product, Recipe, RecipeLine

    with session_factory() as s:
        flour = Ingredient(name="Harina", unit="kg", stock_qty=10.0, purchase_price_gs=5000)
        s.add(flour)
        s.flush()

        masa = Recipe(name="Masa base", yield_qty=12.0, yield_unit="und")
        s.add(masa)
        s.flush()
        s.add(
            RecipeLine(
                recipe_id=masa.id,
                line_kind="ingredient",
                line_ref_id=flour.id,
                qty=0.5,
            )
        )
        s.flush()

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

        product = Product(
            name="Muffin",
            portion_label="1 muffin",
            sale_price_gs=8000,
            recipe_id=muffin.id,
        )
        s.add(product)
        s.commit()
        return flour.id, product.id


def test_apply_sale_simple_drops_stock(session_factory):
    """Sale of 1 muffin → flour -0.025 (0.3/12*1), egg -0.166... (2/12*1).

    Per-sale qty = (line.qty / recipe.yield_qty) * sale.qty
    = (0.3 / 12) * 1 = 0.025 for flour
    = (2 / 12) * 1 = 0.1666... for egg
    """
    from app.rms.costing import apply_sale
    from app.rms.models import Ingredient

    flour_id, egg_id, product_id = _seed_simple(session_factory)

    with session_factory() as s:
        result = apply_sale(s, product_id, qty=1.0, sold_at=datetime(2026, 8, 31, 14, 30))

    assert result.has_recipe is True
    assert result.cycle_warning is False
    assert len(result.stock_moves) == 2

    # Verify stock decremented
    with session_factory() as s:
        flour = s.get(Ingredient, flour_id)
        egg = s.get(Ingredient, egg_id)
        # 2.0 - 0.025 = 1.975; 20.0 - 0.1666... = 19.8333...
        assert abs(flour.stock_qty - 1.975) < 1e-6
        assert abs(egg.stock_qty - 19.8333) < 1e-3


def test_apply_sale_sub_recipe_walks_tree(session_factory):
    """Sub-recipe: 1 muffin → 1 masa → 0.5kg flour per masa.

    Per-sale: (line.qty / muffin.yield_qty) * sale.qty = (1/12) * 1 = 0.0833 masa
    Masa contributes: (0.5/12) * 0.0833 = 0.00347 kg flour
    Stock drop: 10 - 0.00347 = 9.9965
    """
    from app.rms.costing import apply_sale
    from app.rms.models import Ingredient

    flour_id, product_id = _seed_sub_recipe(session_factory)

    with session_factory() as s:
        result = apply_sale(s, product_id, qty=1.0, sold_at=datetime.now())

    assert result.has_recipe is True
    assert len(result.stock_moves) == 1
    # The move is for the sub-recipe's ingredient (flour)
    assert result.stock_moves[0][0] == flour_id

    with session_factory() as s:
        flour = s.get(Ingredient, flour_id)
        # 10 - (0.5/12) * (1/12) * 1 = 10 - 0.003472 = 9.9965
        assert flour.stock_qty < 10.0
        assert flour.stock_qty > 9.99


def test_apply_sale_no_recipe_saves_without_stock_moves(session_factory):
    """Product with recipe_id=None: sale saved, no stock moves, has_recipe=False."""
    from app.rms.costing import apply_sale
    from app.rms.models import Product, Sale

    with session_factory() as s:
        s.add(Product(name="Mystery", portion_label="1", sale_price_gs=5000, recipe_id=None))
        s.commit()

    with session_factory() as s:
        product_id = 1
        result = apply_sale(s, product_id, qty=1.0, sold_at=datetime.now())

    assert result.has_recipe is False
    assert result.stock_moves == []

    # Sale row was saved
    with session_factory() as s:
        sale = s.get(Sale, 1)
        assert sale is not None
        assert sale.product_id == 1


def test_apply_sale_null_yield_raises(session_factory):
    """Recipe with yield_qty=NULL → apply_sale raises RecipeWithoutYield."""
    import pytest

    from app.rms.costing import RecipeWithoutYield, apply_sale
    from app.rms.models import Product, Recipe

    with session_factory() as s:
        rec = Recipe(name="Sin rendimiento", yield_qty=None, yield_unit="und")
        s.add(rec)
        s.flush()
        s.add(Product(name="Test", portion_label="1", sale_price_gs=5000, recipe_id=rec.id))
        s.commit()

    with pytest.raises(RecipeWithoutYield):
        with session_factory() as s:
            apply_sale(s, 1, qty=1.0, sold_at=datetime.now())


def test_apply_sale_zero_qty_raises(session_factory):
    """qty=0 → raises ValueError."""
    import pytest

    from app.rms.costing import apply_sale

    _seed_simple(session_factory)

    with pytest.raises(ValueError, match="qty must be > 0"):
        with session_factory() as s:
            apply_sale(s, 1, qty=0, sold_at=datetime.now())


def test_apply_sale_negative_qty_raises(session_factory):
    """qty=-1 → raises ValueError."""
    import pytest

    from app.rms.costing import apply_sale

    _seed_simple(session_factory)

    with pytest.raises(ValueError, match="qty must be > 0"):
        with session_factory() as s:
            apply_sale(s, 1, qty=-1.0, sold_at=datetime.now())


def test_apply_sale_unknown_product_raises(session_factory):
    """Unknown product_id → raises ValueError."""
    import pytest

    from app.rms.costing import apply_sale

    with pytest.raises(ValueError, match="Product .* not found"):
        with session_factory() as s:
            apply_sale(s, 99999, qty=1.0, sold_at=datetime.now())
