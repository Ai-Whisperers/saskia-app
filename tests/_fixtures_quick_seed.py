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
    PedidoLine,
    Product,
    Recipe,
    RecipeLine,
    Supplier,
    WasteLog,
)


def _make_quick_ingredient(
    s,
    name: str = "harina QA",
    unit: str = "kg",
    stock_qty: float = 10.0,
    min_stock_qty: float = 1.0,
    purchase_price_gs: int = 3000,
) -> Ingredient:
    """Idempotent — returns existing or creates new."""
    existing = s.query(Ingredient).filter_by(name=name).first()
    if existing:
        return existing
    ing = Ingredient(
        name=name,
        unit=unit,
        stock_qty=stock_qty,
        min_stock_qty=min_stock_qty,
        purchase_price_gs=purchase_price_gs,
    )
    s.add(ing)
    s.flush()
    return ing


def _make_quick_recipe(
    s, name: str, ing: Ingredient | None, yield_qty: float = 12.0, yield_unit: str = "und"
) -> Recipe:
    existing = s.query(Recipe).filter_by(name=name).first()
    if existing:
        return existing
    rec = Recipe(name=name, yield_qty=yield_qty, yield_unit=yield_unit)
    s.add(rec)
    s.flush()
    if ing is not None:
        s.add(
            RecipeLine(
                recipe_id=rec.id,
                line_kind="ingredient",
                line_ref_id=ing.id,
                qty=0.3,
                line_unit="kg",
            )
        )
    s.flush()
    return rec


def _make_quick_product(s, name: str, recipe: Recipe | None, sale_price_gs: int = 2500) -> Product:
    existing = s.query(Product).filter_by(name=name).first()
    if existing:
        return existing
    p = Product(
        name=name,
        sale_price_gs=sale_price_gs,
        recipe_id=recipe.id if recipe else None,
    )
    s.add(p)
    s.flush()
    return p


def quick_seed(session_factory, scenario: str = "basic", seed: int = 42) -> dict:
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
            # Anchor "today" to UTC midnight so the bucketed local-date
            # matches `_asuncion_today()` regardless of runner TZ.
            # Previously this used `now - 1h` which bucketed into
            # yesterday on CI runners in UTC, since Asunción is UTC-3/-4
            # and a UTC sale at 02:00 lands at 23:00 the previous
            # Asunción-day. Anchoring at midnight UTC puts the sale at
            # 21:00/20:00 the previous Asunción-day in the worst case
            # — wait, that's still yesterday. We want the sale to fall
            # in *today's* bucket, so anchor at noon UTC, which is
            # always 08:00-09:00 in Asunción, well within "today".
            today_noon_utc = datetime.now(timezone.utc).replace(
                hour=12, minute=0, second=0, microsecond=0
            )
            sale = apply_sale(
                s,
                product_id=p.id,
                qty=2.0,
                sold_at=today_noon_utc,
                notes=None,
                customer_id=None,
                payment_method="efectivo",
                discount_gs=0,
                channel="mostrador",
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
            s.add(ped)
            s.flush()
            out["pedido"] = ped

        elif scenario == "with_manana_pedidos":
            """basic + 2 pedidos para mañana con líneas + 14d sales history
            so the forecast actually returns rows for the "Qué producir"
            table. (para tests de /produccion/manana — exercise del nuevo
            display per-cliente).
            """
            import secrets as _secrets

            from app.rms.config import ASUNCION_TZ

            # Match the route's "tomorrow" computation exactly so the
            # seeded Pedido.promised_date hits the SELECT filter.
            _today_asu = datetime.now(ASUNCION_TZ).date()
            _tomorrow_asu = _today_asu + timedelta(days=1)

            # Add 14 days of sales history to make the product appear
            # in the forecast (rolling 14d). One sale per day at noon
            # Asunción (= 16:00 UTC during standard time).
            for d in range(14):
                _sold_at = datetime.now(timezone.utc).replace(
                    hour=16, minute=0, second=0, microsecond=0
                ) - timedelta(days=d)
                apply_sale(
                    s,
                    product_id=p.id,
                    qty=2.0,
                    sold_at=_sold_at,
                    notes=None,
                    customer_id=None,
                    payment_method="efectivo",
                    discount_gs=0,
                    channel="mostrador",
                )

            c1 = _make_or_get_customer(s, "María Rodríguez")
            c2 = _make_or_get_customer(s, "Carlos Pereira")
            ped1 = Pedido(
                customer_id=c1.id,
                customer_name=c1.name,
                customer_phone="0981222333",
                status="confirmed",
                promised_date=_tomorrow_asu,
                promised_time="10:00",
                channel="whatsapp",
                public_token=_secrets.token_hex(4),
            )
            ped2 = Pedido(
                customer_id=c2.id,
                customer_name=c2.name,
                customer_phone="0981444555",
                status="pending",
                promised_date=_tomorrow_asu,
                promised_time="16:30",
                channel="mostrador",
                public_token=_secrets.token_hex(4),
            )
            s.add_all([ped1, ped2])
            s.flush()
            # Pedido 1: 6 unidades del producto QA + 1 unidad de un
            # segundo producto (lo creamos ad-hoc).
            p2 = _make_quick_product(s, "Empanada QA", rec)
            s.add(PedidoLine(pedido_id=ped1.id, product_id=p.id, qty=6.0, unit_price_gs=12000))
            s.add(PedidoLine(pedido_id=ped1.id, product_id=p2.id, qty=12.0, unit_price_gs=5000))
            # Pedido 2: 3 unidades del producto QA.
            s.add(PedidoLine(pedido_id=ped2.id, product_id=p.id, qty=3.0, unit_price_gs=12000))
            s.flush()
            out.update({"pedidos": [ped1, ped2], "product": p, "p2": p2})

        elif scenario == "with_voided_sale":
            sale_result = apply_sale(
                s,
                product_id=p.id,
                qty=1.0,
                sold_at=now - timedelta(hours=2),
                notes=None,
                customer_id=None,
                payment_method="efectivo",
                discount_gs=0,
                channel="mostrador",
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
                s.add(
                    RecipeLine(
                        recipe_id=rec2.id,
                        line_kind="ingredient",
                        line_ref_id=ing_extra.id,
                        qty=0.1,
                        line_unit="kg",
                    )
                )
            s.flush()
            out["complex_recipe"] = rec2

        elif scenario == "with_kyrian_full":
            # Phase 1 — Kyrian demo dataset (idempotent). See app/seed/kyrian.py.
            # Calls the full seed function which clears prior Kyrian data first.
            from app.seed.kyrian import seed_kyrian

            result = seed_kyrian(s)
            out["kyrian"] = result

        elif scenario == "with_many_products":
            # 25 active products + 25 sales for pagination fixtures.
            for i in range(25):
                ing = _make_quick_ingredient(s, name=f"ing_many_{i}")
                rec = _make_quick_recipe(s, f"Receta Many {i}", ing, yield_qty=12.0)
                p = _make_quick_product(s, f"Producto Many {i:02d}", rec)
                sale = apply_sale(
                    s,
                    product_id=p.id,
                    qty=2.0,
                    sold_at=today_noon_utc if False else now - timedelta(hours=i),
                    notes=None,
                    customer_id=None,
                    payment_method="efectivo",
                    discount_gs=0,
                    channel="mostrador",
                )
            out["n_products"] = 25

        elif scenario == "with_plan_shortages":
            """3 products with recipes + 1 product without recipe + 14d
            sales so plan_production() has rows that REQUIRE ingredients
            the operator has insufficient stock for. Used by the
            prep-recipes vs shopping-list cross-check test.
            """

            for i in range(3):
                ing = _make_quick_ingredient(
                    s, name=f"PlanShort Ing {i}", unit="kg" if i % 2 == 0 else "und"
                )
                # 10 kg starting stock; 14 sales of 3 und consume
                # ~420 kg → stock clamps at 0 (CHECK constraint) and
                # every plan line is a real shortage. The actual unit
                # numbers aren't what we care about — we only need
                # both views to agree on them.
                ing.stock_qty = 10.0
                s.flush()
                rec = _make_quick_recipe(s, f"PlanShort Rec {i}", ing, yield_qty=10.0)
                # Replace the default 0.3 kg line with 1 kg/batch so
                # 1 unit sold → 0.1 kg consumed × 3 × 14 = 4.2 kg
                # (fits under the 10 kg starting stock; no sale-side
                # constraint violation).
                rl = s.query(RecipeLine).filter_by(recipe_id=rec.id).first()
                if rl is not None:
                    rl.qty = 1.0
                p = _make_quick_product(s, f"PlanShort Prod {i:02d}", rec)
                # 14 days of sales so the rolling forecast produces rows
                for d in range(14):
                    apply_sale(
                        s,
                        product_id=p.id,
                        qty=3.0,
                        sold_at=now - timedelta(days=d, hours=1),
                        notes=None,
                        customer_id=None,
                        payment_method="efectivo",
                        discount_gs=0,
                        channel="mostrador",
                    )
            s.commit()

        s.commit()
    return out


def _make_or_get_customer(s, name: str) -> Customer:
    c = s.query(Customer).filter_by(name=name).first()
    if c:
        return c
    c = Customer(name=name, phone="0980000000")
    s.add(c)
    s.flush()
    return c


def _make_or_get_supplier(s, name: str) -> Supplier:
    sup = s.query(Supplier).filter_by(name=name).first()
    if sup:
        return sup
    sup = Supplier(name=name, phone="021000000")
    s.add(sup)
    s.flush()
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
