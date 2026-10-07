"""tests/test_pre_sale_check_cart.py — multi-line pre-billing checklist.

Companion to app/rms/sales/pre_sale_check_cart.py and the
/ventas/nueva/preflight/multi route.
"""
from __future__ import annotations

from datetime import date

from app.rms.sales.pre_sale_check_cart import (
    CartIntent,
    CartLine,
    validate_cart_intent,
)


def _make_product_with_recipe(session_factory, *, name="Torta", price=10000,
                              ingredient_stock=5000.0, recipe_qty=200.0):
    from app.rms.models import Ingredient, Product, Recipe, RecipeLine
    with session_factory() as session:
        with session.begin():
            ing = Ingredient(
                name=f"Harina-{name}",
                stock_qty=ingredient_stock,
                unit="g",
            )
            session.add(ing)
            session.flush()
            ing_id = ing.id
            r = Recipe(name=f"Receta {name}", yield_qty=10.0, yield_unit="g")
            session.add(r)
            session.flush()
            line = RecipeLine(
                recipe_id=r.id, line_kind="ingredient",
                line_ref_id=ing_id, qty=recipe_qty, line_unit="g",
            )
            session.add(line)
            session.flush()
            p = Product(name=name, sku=f"SKU-{name}", sale_price_gs=price, recipe_id=r.id)
            session.add(p)
            session.flush()
            return p.id


# ---- Empty cart ---------------------------------------------------------


def test_empty_cart_is_blocker(session_factory):
    cart = CartIntent(lines=())
    with session_factory() as session:
        result = validate_cart_intent(session, cart, today=date(2026, 10, 7))
    assert any(w.code == "CART_EMPTY" for w in result.blockers)


# ---- Per-line checks ----------------------------------------------------


def test_negative_qty_line_suffixed(session_factory):
    p1 = _make_product_with_recipe(session_factory, name="Bad")
    cart = CartIntent(lines=(CartLine(line_index=0, product_id=p1, qty=-1),))
    with session_factory() as session:
        result = validate_cart_intent(session, cart, today=date(2026, 10, 7))
    # QTY_NOT_POSITIVE@0
    codes = {w.code for w in result.all_items}
    assert "QTY_NOT_POSITIVE@0" in codes


def test_excessive_qty_line_suffixed(session_factory):
    p1 = _make_product_with_recipe(session_factory, name="X")
    cart = CartIntent(lines=(CartLine(line_index=0, product_id=p1, qty=99999),))
    with session_factory() as session:
        result = validate_cart_intent(session, cart, today=date(2026, 10, 7))
    codes = {w.code for w in result.all_items}
    assert any(c.startswith("QTY_TOO_LARGE@0") for c in codes)


# ---- Cart-level stock aggregation ---------------------------------------


def test_aggregated_stock_check_two_lines_same_ingredient(session_factory):
    """Two lines using the same ingredient should aggregate demand.

    Both products point to the SAME recipe/ingredient. Demand: 200g
    each × 2 lines = 400g. Stock: 100g. Shortage!
    """
    from app.rms.models import Ingredient, Product, Recipe, RecipeLine
    with session_factory() as session:
        with session.begin():
            ing = Ingredient(name="Harina-Agg", stock_qty=50.0, unit="g")
            session.add(ing)
            session.flush()
            ing_id = ing.id
            r = Recipe(name="Receta-Agg", yield_qty=1.0, yield_unit="und")
            session.add(r)
            session.flush()
            # Per-sale demand: 200/1 × 1 = 200g per unit sold
            line = RecipeLine(
                recipe_id=r.id, line_kind="ingredient",
                line_ref_id=ing_id, qty=200.0, line_unit="g",
            )
            session.add(line)
            session.flush()
            p1 = Product(name="Agg1", sku="AGG1", sale_price_gs=10000, recipe_id=r.id)
            p2 = Product(name="Agg2", sku="AGG2", sale_price_gs=10000, recipe_id=r.id)
            session.add_all([p1, p2])
            session.flush()
            p1_id, p2_id = p1.id, p2.id

    cart = CartIntent(lines=(
        CartLine(line_index=0, product_id=p1_id, qty=1),
        CartLine(line_index=1, product_id=p2_id, qty=1),
    ))
    with session_factory() as session:
        result = validate_cart_intent(session, cart, today=date(2026, 10, 7))
    cart_shortage = [w for w in result.warnings if w.code == "CART_STOCK_SHORTAGE"]
    assert len(cart_shortage) == 1, (
        f"Expected 1 aggregated shortage, got {len(cart_shortage)}. "
        f"All warnings: {[(w.code, w.message) for w in result.warnings]}"
    )


def test_no_stock_shortage_when_enough_stock(session_factory):
    """With plenty of stock, no shortage warning."""
    p1 = _make_product_with_recipe(session_factory, name="Plenty", recipe_qty=200.0, ingredient_stock=10000.0)
    cart = CartIntent(lines=(CartLine(line_index=0, product_id=p1, qty=2),))
    with session_factory() as session:
        result = validate_cart_intent(session, cart, today=date(2026, 10, 7))
    assert not any(w.code == "CART_STOCK_SHORTAGE" for w in result.all_items)


# ---- Cart-level checks --------------------------------------------------


def test_closed_day_is_cart_blocker(session_factory, monkeypatch):
    from app.rms import eod_closed
    monkeypatch.setattr(eod_closed, "eod_is_day_closed", lambda *a, **kw: True)
    p1 = _make_product_with_recipe(session_factory, name="Closed")
    cart = CartIntent(
        lines=(CartLine(line_index=0, product_id=p1, qty=1),),
        sold_at=date(2026, 10, 7),
    )
    with session_factory() as session:
        result = validate_cart_intent(session, cart, today=date(2026, 10, 7))
    assert any(w.code == "CART_DAY_CLOSED" for w in result.blockers)


def test_missing_payment_is_info(session_factory):
    p1 = _make_product_with_recipe(session_factory, name="NoPay")
    cart = CartIntent(
        lines=(CartLine(line_index=0, product_id=p1, qty=1),),
        payment_method="",
    )
    with session_factory() as session:
        result = validate_cart_intent(session, cart, today=date(2026, 10, 7))
    payment = [w for w in result.warnings if w.code == "CART_PAYMENT_METHOD_MISSING"]
    assert len(payment) == 1
    assert payment[0].severity == "info"
    assert result.is_ready


# ---- Customer allergen on a line ---------------------------------------


def test_customer_allergen_blocks_cart(session_factory):
    """An allergen match on ANY line blocks the whole cart."""
    from app.rms.models import Ingredient, Product, Recipe, RecipeLine
    from app.rms.models import Customer
    p1 = _make_product_with_recipe(session_factory, name="Ok")
    # Create a product with a "nuts" allergen
    with session_factory() as session:
        with session.begin():
            ing = Ingredient(name="Maní-Cart", stock_qty=1000, unit="g")
            session.add(ing)
            session.flush()
            ing_id = ing.id
            r = Recipe(name="Maní-Cart-Recipe", yield_qty=1, yield_unit="und", allergens="nuts")
            session.add(r)
            session.flush()
            line = RecipeLine(recipe_id=r.id, line_kind="ingredient", line_ref_id=ing_id, qty=10, line_unit="g")
            session.add(line)
            session.flush()
            p2 = Product(name="Maní-Cart-Sale", sku="MANI-CART", sale_price_gs=5000, recipe_id=r.id)
            session.add(p2)
            session.flush()
            p2_id = p2.id
            # Customer with allergen
            c = Customer(name="Alerg", phone="0981", notes="alérgica al maní")
            session.add(c)
            session.flush()
            customer_id = c.id

    cart = CartIntent(
        lines=(
            CartLine(line_index=0, product_id=p1, qty=1),
            CartLine(line_index=1, product_id=p2_id, qty=1),
        ),
        customer_id=customer_id,
        payment_method="efectivo",
    )
    with session_factory() as session:
        result = validate_cart_intent(session, cart, today=date(2026, 10, 7))
    # Block on the offending line; the clean line should pass
    cart_allergen = [w for w in result.blockers if w.code.startswith("CART_CUSTOMER_ALLERGEN")]
    assert len(cart_allergen) == 1
    assert "@1" in cart_allergen[0].code  # the second line


# ---- Helper properties --------------------------------------------------


def test_cart_intent_total_qty():
    cart = CartIntent(lines=(
        CartLine(line_index=0, product_id=1, qty=2),
        CartLine(line_index=1, product_id=2, qty=3),
    ))
    assert cart.total_qty == 5


def test_cart_intent_is_empty():
    assert CartIntent(lines=()).is_empty
    assert not CartIntent(lines=(CartLine(line_index=0, product_id=1, qty=1),)).is_empty


def test_cart_intent_fields():
    cart = CartIntent(
        lines=(CartLine(line_index=0, product_id=1, qty=1),),
        customer_id=42,
        payment_method="efectivo",
        channel="mostrador",
        sold_at=date(2026, 10, 7),
    )
    assert cart.customer_id == 42
    assert cart.payment_method == "efectivo"
    assert cart.channel == "mostrador"
    assert cart.sold_at == date(2026, 10, 7)
