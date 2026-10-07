"""tests/test_pre_sale_check.py — pre-billing checklist tests.

Companion to app/rms/sales/pre_sale_check.py (ported from
ury-erp/ury posClosing.js validation pattern).
"""
from __future__ import annotations

from datetime import date

from app.rms.sales.pre_sale_check import (
    MAX_QTY_PER_SALE,
    PreSaleIntent,
    validate_sale_intent,
)

# ---- Helpers ------------------------------------------------------------


def _make_product_with_recipe(session_factory, *, with_recipe=True, name="Torta", price=10000):
    """Create a Product (and Recipe with one ingredient) for tests."""
    from app.rms.models import Ingredient, Product, Recipe, RecipeLine
    with session_factory() as session:
        with session.begin():
            ing = Ingredient(
                name=f"Harina-{name}",
                stock_qty=5000.0,
                unit="g",
            )
            session.add(ing)
            session.flush()
            ing_id = ing.id
            p = Product(name=name, sku=f"SKU-{name}", sale_price_gs=price)
            if with_recipe:
                r = Recipe(name=f"Receta {name}", yield_qty=10.0, yield_unit="g")
                session.add(r)
                session.flush()
                line = RecipeLine(
                    recipe_id=r.id, line_kind="ingredient",
                    line_ref_id=ing_id, qty=200.0, line_unit="g",
                )
                session.add(line)
                session.flush()
                p.recipe_id = r.id
            session.add(p)
            session.flush()
            return p.id


def _make_customer_with_allergen(session_factory, allergen_text: str = "alérgica al maní"):
    """Create a Customer with an allergen declared in free-text notes.

    Sazon parses customer.notes for "alérgica al X" / "alérgico al X" patterns.
    See app/rms/derived_intel.py:parse_customer_allergies.
    """
    from app.rms.models import Customer
    with session_factory() as session:
        with session.begin():
            c = Customer(
                name="Cliente Alérgico", phone="0981111111",
                notes=allergen_text,
            )
            session.add(c)
            session.flush()
            return c.id


def _make_clean_customer(session_factory):
    from app.rms.models import Customer
    with session_factory() as session:
        with session.begin():
            c = Customer(name="Cliente Limpio", phone="0981222222")
            session.add(c)
            session.flush()
            return c.id


# ---- 1. Clean sale ------------------------------------------------------


def test_clean_sale_returns_no_warnings(session_factory):
    product_id = _make_product_with_recipe(session_factory, with_recipe=True, name="Clean")
    customer_id = _make_clean_customer(session_factory)
    with session_factory() as session:
        intent = PreSaleIntent(
            product_id=product_id, sku="", qty=1.0,
            discount_gs=0, customer_id=customer_id,
            payment_method="efectivo", channel="mostrador",
            sold_at=date(2026, 10, 7),
        )
        result = validate_sale_intent(session, intent, today=date(2026, 10, 7))
    assert result.is_clean, (
        f"Expected clean, got: {result.warning_messages + result.blocking_messages}"
    )
    assert result.is_ready


# ---- 2. Quantity floor --------------------------------------------------


def test_negative_qty_is_blocker(session_factory):
    with session_factory() as session:
        intent = PreSaleIntent(product_id=1, sku="", qty=-1.0, sold_at=date(2026, 10, 7))
        result = validate_sale_intent(session, intent, today=date(2026, 10, 7))
    assert not result.is_ready
    assert any(w.code == "QTY_NOT_POSITIVE" for w in result.blockers)


def test_zero_qty_is_blocker(session_factory):
    with session_factory() as session:
        intent = PreSaleIntent(product_id=1, sku="", qty=0, sold_at=date(2026, 10, 7))
        result = validate_sale_intent(session, intent, today=date(2026, 10, 7))
    assert any(w.code == "QTY_NOT_POSITIVE" for w in result.blockers)


def test_excessive_qty_is_blocker(session_factory):
    with session_factory() as session:
        intent = PreSaleIntent(
            product_id=1, sku="", qty=MAX_QTY_PER_SALE + 1, sold_at=date(2026, 10, 7)
        )
        result = validate_sale_intent(session, intent, today=date(2026, 10, 7))
    assert any(w.code == "QTY_TOO_LARGE" for w in result.blockers)


# ---- 3. Product resolution ---------------------------------------------


def test_missing_product_is_blocker(session_factory):
    with session_factory() as session:
        intent = PreSaleIntent(product_id=None, sku="", qty=1.0, sold_at=date(2026, 10, 7))
        result = validate_sale_intent(session, intent, today=date(2026, 10, 7))
    assert any(w.code == "PRODUCT_NOT_FOUND" for w in result.blockers)


def test_unknown_sku_is_blocker(session_factory):
    with session_factory() as session:
        intent = PreSaleIntent(
            product_id=None, sku="NOSUCHSKU", qty=1.0, sold_at=date(2026, 10, 7)
        )
        result = validate_sale_intent(session, intent, today=date(2026, 10, 7))
    assert any(w.code == "PRODUCT_NOT_FOUND" for w in result.blockers)


def test_sku_resolves_to_product(session_factory):
    """When only sku is given, the checklist should resolve it to a product."""
    from app.rms.models import Product
    product_id = _make_product_with_recipe(session_factory, with_recipe=True, name="BySku")
    # Use a clean alphanumeric SKU that passes barcode validation
    with session_factory() as session:
        # Set a known good SKU (overwrite the default)
        p = session.get(Product, product_id)
        p.sku = "TOR-001"
        session.commit()
        # Now use that SKU
        intent = PreSaleIntent(
            product_id=None, sku="TOR-001", qty=1.0,
            payment_method="efectivo", sold_at=date(2026, 10, 7),
        )
        result = validate_sale_intent(session, intent, today=date(2026, 10, 7))
    assert not any(w.code == "PRODUCT_NOT_FOUND" for w in result.blockers), (
        f"Expected SKU resolution, got blockers: {result.blocking_messages}"
    )


# ---- 4. Customer allergen ------------------------------------------------


def test_customer_allergen_is_blocker(session_factory):
    """A customer with notes 'alérgica al maní' (parsed → "nuts") and
    a product whose recipe.allergens contains "nuts" should block the sale.
    """
    from app.rms.models import Ingredient, Product, Recipe, RecipeLine
    with session_factory() as session:
        with session.begin():
            ing = Ingredient(name="Maní", stock_qty=1000, unit="g")
            session.add(ing)
            session.flush()
            ing_id = ing.id
            r = Recipe(
                name="Maní Recipe", yield_qty=1, yield_unit="und",
                allergens="nuts",  # tells the system the recipe has nuts
            )
            session.add(r)
            session.flush()
            line = RecipeLine(
                recipe_id=r.id, line_kind="ingredient",
                line_ref_id=ing_id, qty=10, line_unit="g",
            )
            session.add(line)
            session.flush()
            p = Product(name="Maní Sale", sku="MANI", sale_price_gs=5000, recipe_id=r.id)
            session.add(p)
            session.flush()
            product_id = p.id

    customer_id = _make_customer_with_allergen(session_factory, "alérgica al maní")
    with session_factory() as session:
        intent = PreSaleIntent(
            product_id=product_id, sku="", qty=1.0,
            customer_id=customer_id, payment_method="efectivo",
            sold_at=date(2026, 10, 7),
        )
        result = validate_sale_intent(session, intent, today=date(2026, 10, 7))
    assert any(w.code == "CUSTOMER_ALLERGEN" for w in result.blockers)


def test_no_allergen_no_blocker(session_factory):
    product_id = _make_product_with_recipe(session_factory, with_recipe=True, name="NoAllergy")
    customer_id = _make_clean_customer(session_factory)
    with session_factory() as session:
        intent = PreSaleIntent(
            product_id=product_id, sku="", qty=1.0,
            customer_id=customer_id, payment_method="efectivo",
            sold_at=date(2026, 10, 7),
        )
        result = validate_sale_intent(session, intent, today=date(2026, 10, 7))
    assert not any(w.code == "CUSTOMER_ALLERGEN" for w in result.all_items)


# ---- 5. Discount --------------------------------------------------------


def test_small_discount_no_warning(session_factory):
    product_id = _make_product_with_recipe(session_factory, with_recipe=True, name="SmallDisc")
    with session_factory() as session:
        intent = PreSaleIntent(
            product_id=product_id, sku="", qty=10.0,
            discount_gs=5000,  # 5% of 100000
            payment_method="efectivo", sold_at=date(2026, 10, 7),
        )
        result = validate_sale_intent(session, intent, today=date(2026, 10, 7))
    assert not any(w.code == "LARGE_DISCOUNT" for w in result.all_items)


def test_large_discount_warns(session_factory):
    product_id = _make_product_with_recipe(session_factory, with_recipe=True, name="BigDisc")
    with session_factory() as session:
        intent = PreSaleIntent(
            product_id=product_id, sku="", qty=10.0,  # 100000 total
            discount_gs=int(0.25 * 100000),  # 25%
            payment_method="efectivo", sold_at=date(2026, 10, 7),
        )
        result = validate_sale_intent(session, intent, today=date(2026, 10, 7))
    large = [w for w in result.warnings if w.code == "LARGE_DISCOUNT"]
    assert len(large) == 1
    assert large[0].severity == "warning"
    assert result.is_ready


def test_zero_discount_no_warning(session_factory):
    product_id = _make_product_with_recipe(session_factory, with_recipe=True, name="ZeroDisc")
    with session_factory() as session:
        intent = PreSaleIntent(
            product_id=product_id, sku="", qty=1.0, discount_gs=0,
            payment_method="efectivo", sold_at=date(2026, 10, 7),
        )
        result = validate_sale_intent(session, intent, today=date(2026, 10, 7))
    assert not any(w.code == "LARGE_DISCOUNT" for w in result.all_items)


# ---- 6. Recipe / stock shortage -----------------------------------------


def test_no_recipe_is_warning(session_factory):
    product_id = _make_product_with_recipe(session_factory, with_recipe=False, name="NoRecipe")
    with session_factory() as session:
        intent = PreSaleIntent(
            product_id=product_id, sku="", qty=1.0,
            payment_method="efectivo", sold_at=date(2026, 10, 7),
        )
        result = validate_sale_intent(session, intent, today=date(2026, 10, 7))
    no_recipe = [w for w in result.warnings if w.code == "NO_RECIPE"]
    assert len(no_recipe) == 1
    assert result.is_ready


def test_recipe_no_yield_is_blocker(session_factory):
    from app.rms.models import Product, Recipe
    with session_factory() as session:
        with session.begin():
            r = Recipe(name="NoYield", yield_qty=None, yield_unit="g")
            session.add(r)
            session.flush()
            p = Product(name="NY", sku="NY", sale_price_gs=1000, recipe_id=r.id)
            session.add(p)
            session.flush()
            product_id = p.id

    with session_factory() as session:
        intent = PreSaleIntent(
            product_id=product_id, sku="", qty=1.0,
            payment_method="efectivo", sold_at=date(2026, 10, 7),
        )
        result = validate_sale_intent(session, intent, today=date(2026, 10, 7))
    assert any(w.code == "RECIPE_NO_YIELD" for w in result.blockers)


def test_single_ingredient_shortage_is_warning(session_factory):
    from app.rms.models import Ingredient, Product, Recipe, RecipeLine
    with session_factory() as session:
        with session.begin():
            ing = Ingredient(name="Low Stock Ing", stock_qty=5.0, unit="g")
            session.add(ing)
            session.flush()
            ing_id = ing.id
            r = Recipe(name="Uses Low Ing", yield_qty=1.0, yield_unit="g")
            session.add(r)
            session.flush()
            line = RecipeLine(
                recipe_id=r.id, line_kind="ingredient",
                line_ref_id=ing_id, qty=100.0, line_unit="g",
            )
            session.add(line)
            session.flush()
            p = Product(name="Big Sale", sku="BIG", sale_price_gs=1000, recipe_id=r.id)
            session.add(p)
            session.flush()
            product_id = p.id

    with session_factory() as session:
        intent = PreSaleIntent(
            product_id=product_id, sku="", qty=1.0,
            payment_method="efectivo", sold_at=date(2026, 10, 7),
        )
        result = validate_sale_intent(session, intent, today=date(2026, 10, 7))
    stock = [w for w in result.warnings if w.code == "STOCK_SHORTAGE"]
    assert len(stock) == 1
    assert stock[0].severity == "warning"


# ---- 7. Packaging consistency -------------------------------------------


def test_packaging_item_without_qty_is_blocker(session_factory):
    product_id = _make_product_with_recipe(session_factory, with_recipe=True, name="PckErr1")
    with session_factory() as session:
        intent = PreSaleIntent(
            product_id=product_id, sku="", qty=1.0, packaging_item_id=42,
            packaging_qty=None, sold_at=date(2026, 10, 7),
        )
        result = validate_sale_intent(session, intent, today=date(2026, 10, 7))
    assert any(w.code == "PACKAGING_QTY_MISSING" for w in result.blockers)


def test_packaging_qty_without_item_is_blocker(session_factory):
    product_id = _make_product_with_recipe(session_factory, with_recipe=True, name="PckErr2")
    with session_factory() as session:
        intent = PreSaleIntent(
            product_id=product_id, sku="", qty=1.0, packaging_item_id=None,
            packaging_qty=1.0, sold_at=date(2026, 10, 7),
        )
        result = validate_sale_intent(session, intent, today=date(2026, 10, 7))
    assert any(w.code == "PACKAGING_ITEM_MISSING" for w in result.blockers)


def test_consistent_packaging_no_blocker(session_factory):
    product_id = _make_product_with_recipe(session_factory, with_recipe=True, name="PckOK")
    with session_factory() as session:
        intent = PreSaleIntent(
            product_id=product_id, sku="", qty=1.0,
            packaging_item_id=None, packaging_qty=None,
            payment_method="efectivo", sold_at=date(2026, 10, 7),
        )
        result = validate_sale_intent(session, intent, today=date(2026, 10, 7))
    assert not any(
        w.code in ("PACKAGING_QTY_MISSING", "PACKAGING_ITEM_MISSING")
        for w in result.all_items
    )


# ---- 8. Closed day ------------------------------------------------------


def test_closed_day_is_blocker(session_factory, monkeypatch):
    from app.rms import eod_closed
    monkeypatch.setattr(eod_closed, "eod_is_day_closed", lambda *a, **kw: True)
    product_id = _make_product_with_recipe(session_factory, with_recipe=True, name="ClosedDay")
    with session_factory() as session:
        intent = PreSaleIntent(
            product_id=product_id, sku="", qty=1.0,
            payment_method="efectivo", sold_at=date(2026, 10, 7),
        )
        result = validate_sale_intent(session, intent, today=date(2026, 10, 7))
    assert any(w.code == "DAY_CLOSED" for w in result.blockers)


# ---- 9. Payment method missing (info only) ------------------------------


def test_missing_payment_method_is_info_not_blocker(session_factory):
    product_id = _make_product_with_recipe(session_factory, with_recipe=True, name="NoPay")
    with session_factory() as session:
        intent = PreSaleIntent(
            product_id=product_id, sku="", qty=1.0,
            payment_method="", sold_at=date(2026, 10, 7),
        )
        result = validate_sale_intent(session, intent, today=date(2026, 10, 7))
    payment = [w for w in result.warnings if w.code == "PAYMENT_METHOD_MISSING"]
    assert len(payment) == 1
    assert payment[0].severity == "info"
    assert result.is_ready


# ---- 10. Checklist structure --------------------------------------------


def test_checklist_blockers_warnings_ordering(session_factory):
    product_id = _make_product_with_recipe(session_factory, with_recipe=True, name="Order")
    with session_factory() as session:
        intent = PreSaleIntent(
            product_id=product_id, sku="", qty=1.0,
            payment_method="", sold_at=date(2026, 10, 7),
        )
        result = validate_sale_intent(session, intent, today=date(2026, 10, 7))
    items = result.all_items
    blocker_idxs = [i for i, w in enumerate(items) if w.is_blocker()]
    warning_idxs = [i for i, w in enumerate(items) if not w.is_blocker()]
    if blocker_idxs and warning_idxs:
        assert max(blocker_idxs) < min(warning_idxs)


def test_checklist_messages_are_spanish(session_factory):
    product_id = _make_product_with_recipe(session_factory, with_recipe=True, name="Es")
    customer_id = _make_clean_customer(session_factory)
    with session_factory() as session:
        intent = PreSaleIntent(
            product_id=product_id, sku="", qty=1.0,
            customer_id=customer_id, payment_method="",
            sold_at=date(2026, 10, 7),
        )
        result = validate_sale_intent(session, intent, today=date(2026, 10, 7))
    for w in result.all_items:
        spanish_signals = ["ñ", "á", "é", "í", "ó", "ú", "ü", "El ", "La ", "Los "]
        assert any(s in w.message for s in spanish_signals), (
            f"Warning message not in Spanish: '{w.message}'"
        )


# ---- 11. Module API surface --------------------------------------------


def test_pre_sale_intent_required_fields():
    """PreSaleIntent dataclass exposes all fields used by /ventas/nueva."""
    intent = PreSaleIntent(product_id=1, sku="", qty=1.0)
    assert intent.product_id == 1
    assert intent.sku == ""
    assert intent.qty == 1.0
    assert intent.discount_gs == 0
    assert intent.customer_id is None
    assert intent.payment_method == ""
    assert intent.channel == "mostrador"
    assert intent.sold_at is None
    assert intent.unit_price_gs_override is None
    assert intent.packaging_item_id is None
    assert intent.packaging_qty is None
    assert intent.points_to_redeem == 0


def test_pre_sale_warning_severity_helper():
    from app.rms.sales.pre_sale_check import PreSaleWarning
    blocker = PreSaleWarning(code="X", severity="blocker", message="X")
    warning = PreSaleWarning(code="X", severity="warning", message="X")
    info = PreSaleWarning(code="X", severity="info", message="X")
    assert blocker.is_blocker()
    assert not warning.is_blocker()
    assert not info.is_blocker()


def test_checklist_helper_properties():
    from app.rms.sales.pre_sale_check import PreSaleChecklist, PreSaleWarning
    cl = PreSaleChecklist()
    cl.warnings.append(PreSaleWarning(code="W", severity="warning", message="warning msg"))
    cl.blockers.append(PreSaleWarning(code="B", severity="blocker", message="blocker msg"))
    assert not cl.is_clean
    assert not cl.is_ready
    assert cl.blocking_messages == ["blocker msg"]
    assert cl.warning_messages == ["warning msg"]
    # all_items: blockers first
    assert cl.all_items[0].code == "B"
    assert cl.all_items[1].code == "W"


# ---- Env-var override (operator-tunable thresholds) ---------------------


def test_env_override_changes_max_qty(monkeypatch):
    """SAZON_PREFLIGHT_MAX_QTY_PER_SALE=10 lowers the threshold to 10."""
    monkeypatch.setenv("SAZON_PREFLIGHT_MAX_QTY_PER_SALE", "10")
    # Reload config first, then the module that imports from config
    import importlib

    import app.rms.config as cfg
    importlib.reload(cfg)
    import app.rms.sales.pre_sale_check as mod
    importlib.reload(mod)
    # Now the constant is 10, not the default 999
    assert mod.MAX_QTY_PER_SALE == 10
    # 50 is now > max (was < max under default)
    assert mod.MAX_QTY_PER_SALE < 50


def test_env_override_changes_max_discount_pct(monkeypatch):
    """SAZON_PREFLIGHT_MAX_DISCOUNT_PCT=5 lowers discount ceiling to 5%."""
    monkeypatch.setenv("SAZON_PREFLIGHT_MAX_DISCOUNT_PCT", "5")
    import importlib

    import app.rms.config as cfg
    importlib.reload(cfg)
    import app.rms.sales.pre_sale_check as mod
    importlib.reload(mod)
    assert mod.MAX_DISCOUNT_PCT_WITHOUT_OVERRIDE == 5


def test_env_override_default_when_unset(monkeypatch):
    """With no env vars, defaults are 999 and 20."""
    monkeypatch.delenv("SAZON_PREFLIGHT_MAX_QTY_PER_SALE", raising=False)
    monkeypatch.delenv("SAZON_PREFLIGHT_MAX_DISCOUNT_PCT", raising=False)
    import importlib

    import app.rms.config as cfg
    importlib.reload(cfg)
    import app.rms.sales.pre_sale_check as mod
    importlib.reload(mod)
    assert mod.MAX_QTY_PER_SALE == 999
    assert mod.MAX_DISCOUNT_PCT_WITHOUT_OVERRIDE == 20
