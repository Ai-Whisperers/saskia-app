"""Sprint shopping-list: production plan → shopping list flow.

Covers the three pieces added this sprint:
1. plan_production() explodes SUB-RECIPES (via explode_recipe) — a product
   whose recipe includes a sub-recipe (glaze, filling) must show the
   sub-recipe's ingredients in plan.lines, not just direct lines.
2. POST /shopping-list/from-production-plan — one click sends all
   qty_to_buy > 0 rows of a day's plan to the shopping list, deduped
   against open items (top-up, never duplicate).
3. GET /shopping-list — supplier grouping context (named suppliers
   first, Sin proveedor last).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest


def _mk_ing(s, name, unit="g", stock=0.0, min_stock=0.0, supplier=None):
    from app.rms.models import Ingredient

    ing = Ingredient(
        name=name,
        unit=unit,
        stock_qty=stock,
        min_stock_qty=min_stock,
        purchase_price_gs=1000,
        supplier_id=supplier.id if supplier else None,
    )
    s.add(ing)
    s.flush()
    return ing


def _mk_recipe(s, name, yield_qty, lines):
    """lines: list of (line_kind, ref_id, qty, unit)."""
    from app.rms.models import Recipe, RecipeLine

    r = Recipe(name=name, yield_qty=yield_qty, yield_unit="und")
    s.add(r)
    s.flush()
    for kind, ref, qty, unit in lines:
        s.add(
            RecipeLine(
                recipe_id=r.id,
                line_kind=kind,
                line_ref_id=ref,
                qty=qty,
                line_unit=unit,
            )
        )
    s.flush()
    return r


def _mk_product(s, name, recipe_id, price=10000, visible=True):
    from app.rms.models import Product

    p = Product(
        name=name,
        recipe_id=recipe_id,
        sale_price_gs=price,
        is_available=True,
        tablet_visible=visible,
    )
    s.add(p)
    s.flush()
    return p


@pytest.fixture()
def subrecipe_world(session_factory):
    """Product → recipe with a sub-recipe (masa + glaseado sharing azúcar)."""
    from app.rms.models import RecipeLine

    with session_factory() as session:
        yield _build_subrecipe_world(session)


def _build_subrecipe_world(session):
    from app.rms.models import RecipeLine

    azucar = _mk_ing(session, "Azúcar", unit="g", stock=100.0)
    harina = _mk_ing(session, "Harina", unit="g", stock=500.0)
    queso = _mk_ing(session, "Quego crema", unit="g", stock=0.0)

    # Sub-recipe: glaseado — yield 500g, uses 200g azúcar + 300g queso
    glaseado = _mk_recipe(
        session,
        "Glaseado",
        yield_qty=500,
        lines=[("ingredient", azucar.id, 200, "g"), ("ingredient", queso.id, 300, "g")],
    )
    # Base: carrot cake — yield 10 porciones, 1kg harina + 100g azúcar + glaseado
    masa = _mk_recipe(
        session,
        "Carrot Cake",
        yield_qty=10,
        lines=[
            ("ingredient", harina.id, 1000, "g"),
            ("ingredient", azucar.id, 100, "g"),
        ],
    )
    session.add(
        RecipeLine(
            recipe_id=masa.id,
            line_kind="sub_recipe",
            line_ref_id=glaseado.id,
            qty=500,  # one full glaze batch per cake batch
            line_unit="g",
        )
    )
    session.flush()

    prod = _mk_product(session, "Carrot Cake entera", masa.id)

    # Seed tomorrow's override (10 units) so the day plan has real qty —
    # otherwise forecast=0 and the route flow finds no shortages.
    from app.rms.models import ProductionPlanOverride
    from datetime import datetime as _dt

    session.add(
        ProductionPlanOverride(
            product_id=prod.id,
            for_date=date.today() + timedelta(days=1),
            qty=10.0,
            updated_at=_dt.utcnow(),
        )
    )
    session.commit()
    return {"product": prod, "azucar": azucar, "harina": harina, "queso": queso}


def test_plan_includes_subrecipe_ingredients(session_factory, subrecipe_world):
    """The glaze's azúcar + queso MUST appear in the day plan lines."""
    from app.rms.production import plan_production

    with session_factory() as session:
        _assert_plan(session, subrecipe_world)


def _assert_plan(session, subrecipe_world):
    from app.rms.production import plan_production

    tomorrow = date.today() + timedelta(days=1)
    plan = plan_production(session, for_date=tomorrow, manual_forecast={subrecipe_world["product"].id: 10})
    by_ing = {ln.ingredient_id: ln for ln in plan.lines}

    # Azúcar: 100g (masa) + 200g (glaseado) = 300g required — summed, not duplicated
    assert by_ing[subrecipe_world["azucar"].id].qty_required == pytest.approx(300.0)
    # Queso crema ONLY exists in the glaze — the old code dropped it entirely
    assert by_ing[subrecipe_world["queso"].id].qty_required == pytest.approx(300.0)
    # Harina from the base
    assert by_ing[subrecipe_world["harina"].id].qty_required == pytest.approx(1000.0)


def test_from_production_plan_creates_shortage_items(session_factory, subrecipe_world, client):
    from app.rms.models import ShoppingListItem

    tomorrow = date.today() + timedelta(days=1)
    resp = client.post(
        "/shopping-list/from-production-plan",
        data={"for_date": tomorrow.isoformat()},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    print("REDIRECT:", resp.headers["location"])
    assert "/shopping-list?from_plan=" in resp.headers["location"]

    with session_factory() as session:
        items = session.query(ShoppingListItem).filter(
            ShoppingListItem.purchased.is_(False)
        ).all()
        by_ing = {i.ingredient_id: i for i in items}
        # queso: stock 0 → full 300g shortage
        assert by_ing[subrecipe_world["queso"].id].qty_to_buy == pytest.approx(300.0)
        # azúcar: stock 100 → shortage 200 (300 needed - 100 stock)
        assert by_ing[subrecipe_world["azucar"].id].qty_to_buy == pytest.approx(200.0)
        # harina: stock 500 ≥ 1000? No → shortage 500
        assert by_ing[subrecipe_world["harina"].id].qty_to_buy == pytest.approx(500.0)
        # purpose text carries the plan date
        purpose = by_ing[subrecipe_world["queso"].id].purpose_text
        assert tomorrow.isoformat() in purpose


def test_from_production_plan_is_idempotent(session_factory, subrecipe_world, client):
    """Calling twice must NOT duplicate rows — it tops up or leaves as-is."""
    from app.rms.models import ShoppingListItem

    tomorrow = date.today() + timedelta(days=1)
    client.post("/shopping-list/from-production-plan", data={"for_date": tomorrow.isoformat()})
    client.post("/shopping-list/from-production-plan", data={"for_date": tomorrow.isoformat()})

    with session_factory() as session:
        items = session.query(ShoppingListItem).filter(
            ShoppingListItem.purchased.is_(False)
        ).all()
        # Same plan, same shortages → quantities unchanged, one row per ingredient
        assert len(items) == 3
        by_ing = {i.ingredient_id: i.qty_to_buy for i in items}
        assert by_ing[subrecipe_world["queso"].id] == pytest.approx(300.0)


def test_shopping_list_groups_by_supplier(session_factory, subrecipe_world, client):
    """Named supplier group sorts first; None-supplier group last."""
    from app.rms.models import Supplier, ShoppingListItem

    with session_factory() as session:
        sup = Supplier(name="Distribuidora Central", phone="0981112223")
        session.add(sup)
        session.flush()
        queso = session.merge(subrecipe_world["queso"])
        queso.supplier_id = sup.id
        session.commit()

    tomorrow = date.today() + timedelta(days=1)
    client.post("/shopping-list/from-production-plan", data={"for_date": tomorrow.isoformat()})

    resp = client.get("/shopping-list")
    assert resp.status_code == 200
    body = resp.text
    assert "Distribuidora Central" in body
    assert "Sin proveedor asignado" in body
    # Named supplier section appears BEFORE the no-supplier section
    assert body.index("Distribuidora Central") < body.index("Sin proveedor asignado")


def test_produccion_page_has_send_to_list_button(client, subrecipe_world):
    """The day view carries the one-click button (POST target + label)."""
    tomorrow = date.today() + timedelta(days=1)
    resp = client.get(f"/produccion?for_date={tomorrow.isoformat()}")
    assert resp.status_code == 200
    assert "/shopping-list/from-production-plan" in resp.text
    assert "Enviar faltantes a lista de compras" in resp.text


def test_consolidate_merges_duplicate_ingredients(session_factory, subrecipe_world):
    """consolidate_open_items merges open rows sharing (ingredient, unit)."""
    from app.routers.shopping import consolidate_open_items
    from app.rms.models import ShoppingListItem

    with session_factory() as session:
        queso = session.merge(subrecipe_world["queso"])
        s1 = ShoppingListItem(
            ingredient_id=queso.id, qty_to_buy=300.0, unit="g",
            purpose_text="Plan #1 (1× Carrot Cake)",
        )
        s2 = ShoppingListItem(
            ingredient_id=queso.id, qty_to_buy=20.0, unit="g",
            purpose_text="Auto: stock 0.253333333333326 < min 0.3",
        )
        session.add_all([s1, s2])
        session.commit()
        id1, id2 = s1.id, s2.id

    with session_factory() as session:
        deleted = consolidate_open_items(session)
        assert deleted >= 1

    with session_factory() as session:
        rows = session.query(ShoppingListItem).filter(
            ShoppingListItem.ingredient_id == queso.id,
            ShoppingListItem.purchased.is_(False),
        ).all()
        assert len(rows) == 1
        assert rows[0].qty_to_buy == pytest.approx(320.0)
        assert "Plan #1" in rows[0].purpose_text
        assert "Auto" in rows[0].purpose_text
        assert "0.253333" not in rows[0].purpose_text
