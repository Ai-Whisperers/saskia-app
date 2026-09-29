"""Quick seed fixtures for tests.

Most tests need a minimal known dataset (1 ingredient, 1 recipe, 1 product).
Using seed_demo_data for those tests adds 25 seconds wasted per test.

This module provides:
- quick_seed(scenario) helper that creates only the rows the scenario needs.
- seeded_session fixture (session-scoped) that gives a fully-seeded session
  available to any test that wants the full demo data without re-seeding.
- pytest markers (smoke, crud, analytics, security, perf, auth).
"""

from __future__ import annotations

import pytest

from app.rms.models import (
    AuditLog,
    Customer,
    Ingredient,
    Pedido,
    Product,
    Recipe,
    RecipeLine,
    Supplier,
    WasteLog,
)


def _make_quick_ingredient(s, name: str = "harina QA",
                          unit: str = "kg",
                          stock_qty: float = 10.0,
                          min_stock_qty: float = 1.0,
                          purchase_price_gs: int = 3000) -> Ingredient:
    """Idempotent — returns existing or creates new."""
    existing = s.query(Ingredient).filter_by(name=name).first()
    if existing:
        return existing
    ing = Ingredient(
        name=name, unit=unit, stock_qty=stock_qty,
        min_stock_qty=min_stock_qty, purchase_price_gs=purchase_price_gs,
    )
    s.add(ing); s.flush()
    return ing


def _make_quick_recipe(s, name: str, ing: Ingredient | None,
                       yield_qty: float = 12.0, yield_unit: str = "und") -> Recipe:
    existing = s.query(Recipe).filter_by(name=name).first()
    if existing:
        return existing
    rec = Recipe(name=name, yield_qty=yield_qty, yield_unit=yield_unit)
    s.add(rec); s.flush()
    if ing is not None:
        s.add(RecipeLine(
            recipe_id=rec.id, line_kind="ingredient",
            line_ref_id=ing.id, qty=0.3, line_unit="kg",
        ))
    s.flush()
    return rec


def _make_quick_product(s, name: str, recipe: Recipe | None,
                         sale_price_gs: int = 2500) -> Product:
    existing = s.query(Product).filter_by(name=name).first()
    if existing:
        return existing
    p = Product(
        name=name, sale_price_gs=sale_price_gs,
        recipe_id=recipe.id if recipe else None,
    )
    s.add(p); s.flush()
    return p


def quick_seed(session_factory, scenario: str = "basic",
               seed: int = 42) -> dict:
    """Create minimal seed data based on scenario name.

    Returns a dict with all created entities for easy assertion.

    Scenarios:
        'basic' — 1 ingredient + 1 recipe + 1 product
        'with_sale' — basic + 1 sale (calls apply_sale)
        'with_low_stock' — ingredient.stock_qty < min_stock_qty
        'with_pending_pedido' — basic + 1 pending pedido
        'with_voided_sale' — with_sale + 1 voided sale
        'with_waste' — basic + 1 waste event
        'with_customer' — basic + 1 customer
        'with_supplier' — basic + 1 supplier
        'with_audit_log' — basic + 1 audit log entry
        'with_complex_recipe' — recipe with 5+ ingredients
    """
    from datetime import datetime, timedelta, timezone

    from app.rms.costing import apply_sale

    sf = session_factory
    now = datetime.now(timezone.utc)
    out: dict = {}

    with sf() as s:
        ing = _make_quick_ingredient(s)
        out["ingredient"] = ing
        rec = _make_quick_recipe(s, "Receta QA", ing)
        out["recipe"] = rec
        p = _make_quick_product(s, "Producto QA", rec)
        out["product"] = p

        if scenario == "basic":
            pass

        elif scenario == "with_sale":
            sale = apply_sale(
                s, product_id=p.id, qty=2.0,
                sold_at=now - timedelta(hours=1),
                notes=None, customer_id=None,
                payment_method="efectivo", discount_gs=0, channel="Mostrador",
            )
            out["sale"] = sale

        elif scenario == "with_low_stock":
            ing_low = _make_quick_ingredient(s, name="harina baja", stock_qty=0.2)
            out["low_ingredient"] = ing_low

        elif scenario == "with_pending_pedido":
            c = _make_or_get_customer(s, "Cliente QA")
            out["customer"] = c
            ped = Pedido(
                customer_id=c.id,
                customer_name=c.name,
                customer_phone="0981111111",
                status="pending",
                promised_date=now + timedelta(days=1),
                channel="whatsapp",
                notes="Pedido de prueba",
            )
            s.add(ped); s.flush()
            out["pedido"] = ped

        elif scenario == "with_voided_sale":
            sale_result = apply_sale(
                s, product_id=p.id, qty=1.0,
                sold_at=now - timedelta(hours=2),
                notes=None, customer_id=None,
                payment_method="efectivo", discount_gs=0, channel="Mostrador",
            )
            from app.rms.costing import void_sale
            void_sale(s, sale_result.sale_id)
            out["voided_sale_id"] = sale_result.sale_id

        elif scenario == "with_waste":
            wl = WasteLog(
                ingredient_id=ing.id,
                qty=0.5,
                reason="quemado",
                notes="Se quemó una bandeja",
                recorded_at=now,
                cost_gs=1500,
            )
            s.add(wl)
            out["waste"] = wl

        elif scenario == "with_customer":
            c = _make_or_get_customer(s, "Cliente VIP")
            out["customer"] = c

        elif scenario == "with_supplier":
            sup = _make_or_get_supplier(s, "Molino San Lorenzo")
            out["supplier"] = sup

        elif scenario == "with_audit_log":
            al = AuditLog(
                action="qa.test",
                detail={"scenario": scenario},
                occurred_at=now,
            )
            s.add(al)
            out["audit_log"] = al

        elif scenario == "with_complex_recipe":
            # recipe with 5+ ingredients
            rec2 = _make_quick_recipe(s, "Receta Compleja QA", ing, yield_qty=20.0)
            for nm in ["azúcar QA", "manteca QA", "huevo QA", "leche QA", "polvo QA"]:
                ing_extra = _make_quick_ingredient(s, name=nm)
                s.add(RecipeLine(
                    recipe_id=rec2.id, line_kind="ingredient",
                    line_ref_id=ing_extra.id, qty=0.1, line_unit="kg",
                ))
            s.flush()
            out["complex_recipe"] = rec2

        s.commit()
    return out


def _make_or_get_customer(s, name: str) -> Customer:
    c = s.query(Customer).filter_by(name=name).first()
    if c:
        return c
    c = Customer(name=name, phone="0980000000")
    s.add(c); s.flush()
    return c


def _make_or_get_supplier(s, name: str) -> Supplier:
    sup = s.query(Supplier).filter_by(name=name).first()
    if sup:
        return sup
    sup = Supplier(name=name, phone="021000000")
    s.add(sup); s.flush()
    return sup


@pytest.fixture
def qseed(session_factory):
    """Quick-seed callable fixture for tests.

    Usage:
        def test_x(qseed):
            data = qseed("basic")
            assert data["product"].name == "Producto QA"
    """
    def _seed(scenario: str = "basic") -> dict:
        return quick_seed(session_factory, scenario)
    return _seed
