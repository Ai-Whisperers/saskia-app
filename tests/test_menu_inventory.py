"""tests/test_menu_inventory.py — per-product stock ceilings.

Ports the FloCafe addon-inventory.ts pattern: expose a stock
ceiling so the POS qty input can't exceed what we can actually make.
"""

from __future__ import annotations

from app.rms.menu_inventory import (
    product_is_sold_out,
    product_low_stock_threshold,
    product_stock_ceiling,
)
from app.rms.models import Ingredient, Product, Recipe, RecipeLine


def _make_product(
    session_factory,
    *,
    name="Torta",
    ing_stock=1000.0,
    recipe_yield=10.0,
    line_qty=100.0,
    no_recipe=False,
):
    """Build a Product with one Ingredient.

    Per-unit demand: line_qty / recipe_yield = 100/10 = 10 units of
    ingredient per 1 product. With ing_stock=1000, we can make 100
    units of product.
    """
    with session_factory() as session:
        with session.begin():
            ing = Ingredient(name=f"Ing-{name}", stock_qty=ing_stock, unit="g")
            session.add(ing)
            session.flush()
            ing_id = ing.id
            if no_recipe:
                p = Product(name=name, sku=f"SKU-{name}", sale_price_gs=5000)
                session.add(p)
                session.flush()
                return p.id
            r = Recipe(name=f"Receta-{name}", yield_qty=recipe_yield, yield_unit="g")
            session.add(r)
            session.flush()
            line = RecipeLine(
                recipe_id=r.id,
                line_kind="ingredient",
                line_ref_id=ing_id,
                qty=line_qty,
                line_unit="g",
            )
            session.add(line)
            session.flush()
            p = Product(name=name, sku=f"SKU-{name}", sale_price_gs=5000, recipe_id=r.id)
            session.add(p)
            session.flush()
            return p.id


# ---- product_stock_ceiling --------------------------------------------


def test_no_recipe_returns_none(session_factory):
    """A product with no recipe has no ceiling (sale-time check decides)."""
    pid = _make_product(session_factory, no_recipe=True)
    with session_factory() as session:
        assert product_stock_ceiling(session, pid) is None


def test_simple_ceiling(session_factory):
    """100g/10g_yield × 1000g_stock = 100 units ceiling."""
    pid = _make_product(session_factory, recipe_yield=10.0, line_qty=100.0, ing_stock=1000.0)
    with session_factory() as session:
        ceiling = product_stock_ceiling(session, pid)
    assert ceiling == 100.0


def test_zero_stock_is_zero(session_factory):
    """Out of ingredient = ceiling 0 (sold out)."""
    pid = _make_product(session_factory, ing_stock=0.0)
    with session_factory() as session:
        ceiling = product_stock_ceiling(session, pid)
    assert ceiling == 0.0


def test_nonexistent_product_returns_none(session_factory):
    with session_factory() as session:
        assert product_stock_ceiling(session, 999999) is None


def test_uncatchable_recipe_returns_none(session_factory):
    """yield_qty=NULL is an uncatchable recipe (pre-flight blocks it).

    Sazon has a CHECK constraint: yield_qty must be > 0 OR NULL.
    A NULL yield_qty is the "draft" state (RecipeWithoutYield error).
    """
    with session_factory() as session:
        with session.begin():
            ing = Ingredient(name="Ing-NullYield", stock_qty=1000.0, unit="g")
            session.add(ing)
            session.flush()
            r = Recipe(name="Receta-NullYield", yield_qty=None, yield_unit="g")
            session.add(r)
            session.flush()
            line = RecipeLine(
                recipe_id=r.id,
                line_kind="ingredient",
                line_ref_id=ing.id,
                qty=100.0,
                line_unit="g",
            )
            session.add(line)
            session.flush()
            p = Product(name="P-NullYield", sku="NULLY", sale_price_gs=5000, recipe_id=r.id)
            session.add(p)
            session.flush()
            pid = p.id
    with session_factory() as session:
        assert product_stock_ceiling(session, pid) is None


def test_two_ingredients_min_wins(session_factory):
    """When two ingredients are needed, ceiling = min over both."""
    with session_factory() as session:
        with session.begin():
            ing1 = Ingredient(name="Harina-2ing", stock_qty=1000.0, unit="g")
            ing2 = Ingredient(name="Azúcar-2ing", stock_qty=100.0, unit="g")
            session.add_all([ing1, ing2])
            session.flush()
            r = Recipe(name="Receta-2ing", yield_qty=10.0, yield_unit="g")
            session.add(r)
            session.flush()
            # 100g flour + 50g sugar per unit, yield=10 → per_unit = 10g flour + 5g sugar
            session.add_all(
                [
                    RecipeLine(
                        recipe_id=r.id,
                        line_kind="ingredient",
                        line_ref_id=ing1.id,
                        qty=100.0,
                        line_unit="g",
                    ),
                    RecipeLine(
                        recipe_id=r.id,
                        line_kind="ingredient",
                        line_ref_id=ing2.id,
                        qty=50.0,
                        line_unit="g",
                    ),
                ]
            )
            session.flush()
            p = Product(name="Bizcocho-2ing", sku="BIZ2", sale_price_gs=5000, recipe_id=r.id)
            session.add(p)
            session.flush()
            pid = p.id
    with session_factory() as session:
        ceiling = product_stock_ceiling(session, pid)
    # Flour: 1000/10 = 100 units
    # Sugar: 100/5 = 20 units  ← limits the city
    assert ceiling == 20.0


# ---- product_low_stock_threshold -------------------------------------


def test_low_stock_threshold_default_units(session_factory):
    """Default threshold is 5 units (env-overridable)."""
    pid = _make_product(session_factory, recipe_yield=10.0, line_qty=100.0, ing_stock=1000.0)
    with session_factory() as session:
        threshold = product_low_stock_threshold(session, pid)
    assert threshold == 5.0  # default from SAZON_MENU_LOW_STOCK_UNITS


def test_low_stock_threshold_custom_units(session_factory):
    pid = _make_product(session_factory, recipe_yield=10.0, line_qty=100.0, ing_stock=1000.0)
    with session_factory() as session:
        threshold = product_low_stock_threshold(session, pid, units=10.0)
    assert threshold == 10.0


def test_low_stock_threshold_env_override(monkeypatch, session_factory):
    """SAZON_MENU_LOW_STOCK_UNITS env var changes the default."""
    monkeypatch.setenv("SAZON_MENU_LOW_STOCK_UNITS", "12")
    import importlib

    import app.rms.config as cfg

    importlib.reload(cfg)
    import app.rms.menu_inventory as mi

    importlib.reload(mi)
    pid = _make_product(session_factory, recipe_yield=10.0, line_qty=100.0, ing_stock=1000.0)
    with session_factory() as session:
        threshold = mi.product_low_stock_threshold(session, pid)
    assert threshold == 12.0


def test_low_stock_threshold_no_recipe_returns_zero(session_factory):
    """Products with no recipe return 0.0 (template should hide badge)."""
    pid = _make_product(session_factory, no_recipe=True)
    with session_factory() as session:
        assert product_low_stock_threshold(session, pid) == 0.0


# ---- product_is_sold_out ---------------------------------------------


def test_sold_out_when_stock_zero(session_factory):
    pid = _make_product(session_factory, ing_stock=0.0)
    with session_factory() as session:
        assert product_is_sold_out(session, pid) is True


def test_not_sold_out_with_stock(session_factory):
    pid = _make_product(session_factory, ing_stock=1000.0)
    with session_factory() as session:
        assert product_is_sold_out(session, pid) is False


def test_sold_out_no_recipe_returns_false(session_factory):
    """No recipe = no sold-out concept (sale-time check decides)."""
    pid = _make_product(session_factory, no_recipe=True)
    with session_factory() as session:
        assert product_is_sold_out(session, pid) is False


def test_sold_out_nonexistent_product(session_factory):
    with session_factory() as session:
        assert product_is_sold_out(session, 999999) is False
