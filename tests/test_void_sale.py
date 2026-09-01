"""tests/test_void_sale.py — void_sale behavior.

Per dev plan Batch 3. Targets ~4 tests.

Covers:
- void_sale simple: stock restored, voided_at set
- void_sale sub-recipe: stock restored across the tree
- void_sale double-void: raises ValueError ("ya anulada")
- void_sale unknown: raises ValueError
"""

from __future__ import annotations

from datetime import datetime


def _seed(session_factory):
    """Same as test_stock_drop._seed_simple — 1 product, 2 ingredients."""
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


def test_void_sale_restores_stock(session_factory):
    """Apply a sale, then void: stock restored to original."""
    from app.rms.costing import apply_sale, void_sale
    from app.rms.models import Ingredient

    flour_id, egg_id, product_id = _seed(session_factory)

    # Apply sale
    with session_factory() as s:
        result = apply_sale(s, product_id, qty=2.0, sold_at=datetime(2026, 8, 31, 14, 30))
        sale_id = result.sale_id

    # Stock should be lower
    with session_factory() as s:
        flour = s.get(Ingredient, flour_id)
        egg = s.get(Ingredient, egg_id)
        stock_after_sale_flour = flour.stock_qty
        stock_after_sale_egg = egg.stock_qty

    # Void
    with session_factory() as s:
        void_result = void_sale(s, sale_id)
    assert void_result.sale_id == sale_id
    assert len(void_result.restored_moves) == 2

    # Stock restored to original
    with session_factory() as s:
        flour = s.get(Ingredient, flour_id)
        egg = s.get(Ingredient, egg_id)
        assert flour.stock_qty == 2.0
        assert egg.stock_qty == 20.0
        # Sanity: stock was actually lower before void
        assert stock_after_sale_flour < 2.0
        assert stock_after_sale_egg < 20.0


def test_void_sale_sets_voided_at(session_factory):
    """After void, Sale.voided_at is set (not None)."""
    from app.rms.costing import apply_sale, void_sale
    from app.rms.models import Sale

    _, _, product_id = _seed(session_factory)
    with session_factory() as s:
        result = apply_sale(s, product_id, qty=1.0, sold_at=datetime.now())
        sale_id = result.sale_id

    with session_factory() as s:
        sale = s.get(Sale, sale_id)
        assert sale.voided_at is None

    with session_factory() as s:
        void_sale(s, sale_id)

    with session_factory() as s:
        sale = s.get(Sale, sale_id)
        assert sale.voided_at is not None


def test_void_sale_double_void_raises(session_factory):
    """Voiding an already-voided sale → raises ValueError('ya anulada')."""
    import pytest

    from app.rms.costing import apply_sale, void_sale

    _, _, product_id = _seed(session_factory)
    with session_factory() as s:
        result = apply_sale(s, product_id, qty=1.0, sold_at=datetime.now())
        sale_id = result.sale_id

    with session_factory() as s:
        void_sale(s, sale_id)

    with pytest.raises(ValueError, match="ya anulada"):
        with session_factory() as s:
            void_sale(s, sale_id)


def test_void_sale_unknown_raises(session_factory):
    """Unknown sale_id → raises ValueError('Sale ... not found')."""
    import pytest

    from app.rms.costing import void_sale

    with pytest.raises(ValueError, match="Sale .* not found"):
        with session_factory() as s:
            void_sale(s, 99999)


def test_void_sale_sub_recipe_restores(session_factory):
    """Apply + void on sub-recipe sale: stock restored across the tree."""
    from app.rms.costing import apply_sale, void_sale
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
        flour_id, product_id = flour.id, product.id

    # Apply sale
    with session_factory() as s:
        result = apply_sale(s, product_id, qty=1.0, sold_at=datetime.now())
        sale_id = result.sale_id

    # Stock dropped
    with session_factory() as s:
        flour = s.get(Ingredient, flour_id)
        assert flour.stock_qty < 10.0

    # Void
    with session_factory() as s:
        void_sale(s, sale_id)

    # Restored
    with session_factory() as s:
        flour = s.get(Ingredient, flour_id)
        assert flour.stock_qty == 10.0
