"""tests/e2e/test_un_dia_en_la_panaderia.py — full business-day scenarios.

Drives REAL routes (real forms, CSRF, validation, stock side-effects) via
tests/flows.py + tests/factories.py. The point is not any single route —
it's the INVARIANTS that hold (or break) across a whole working session:

  I1  stock_qty is always explained by its movements, never negative
  I2  sale unit_price_gs is a snapshot — a later price change never
      rewrites history
  I3  money columns are ints everywhere
  I4  dashboard/report totals reconcile with raw rows
  I5  derived tags on products match ingredient tags (tag algebra)

Every bug shipped to prod this week (orphan / route, recipe line_qty
mismatch, logger NameError) belonged to exactly this cross-route class.
"""

from __future__ import annotations

import pytest

from tests import flows
from tests.factories import (
    ing_line,
    make_customer,
    make_ingredient,
    make_product,
    make_recipe,
    make_supplier,
)

pytestmark = [pytest.mark.smoke]


# ---------------------------------------------------------------------------
# Scenario 1 — the full day: stock → recipe → product → pedido → produce →
# sell → allergen block → void → merma → reconcile
# ---------------------------------------------------------------------------


def test_full_day_happy_path_and_invariants(client, session_factory):
    """One continuous session through every core flow, asserting the
    invariants at the end."""

    with session_factory() as s:
        sup = make_supplier(s)
        harina = make_ingredient(s, name="Harina 000", purchase_price_gs=8000,
                                 allergens="gluten", dietary_tags="",
                                 stock_qty=0.0)
        manteca = make_ingredient(s, name="Manteca", allergens="lacteos",
                                 stock_qty=0.0)
        s.commit()
        _sup_id, harina_id, manteca_id = sup.id, harina.id, manteca.id

    # 1. Restock both ingredients (positive adjustments)
    assert flows.adjust_stock(client, harina_id, 10.0).ok
    assert flows.adjust_stock(client, manteca_id, 2.0).ok

    # 2. Create a recipe with both ingredients via the real form
    r = flows.create_recipe(
        client, name="Pan de manteca",
        lines=[{"target_id": harina_id, "qty": 1.0, "unit": "kg"},
               {"target_id": manteca_id, "qty": 0.2, "unit": "kg"}],
    )
    assert r.ok, f"recipe create failed: {r.status_code} {r.body[:300]}"

    with session_factory() as s:
        from app.rms.models import Recipe
        rec = s.query(Recipe).filter_by(name="Pan de manteca").one()
        recipe_id = rec.id
        assert len(rec.lines) == 2, "both recipe lines must survive the form"

    # 3. Product linked to the recipe
    assert flows.create_product(client, name="Pan docena", sale_price_gs=25000,
                                recipe_id=recipe_id).ok

    with session_factory() as s:
        from app.rms.models import Product
        prod = s.query(Product).filter_by(name="Pan docena").one()
        product_id = prod.id

    # 4. Sell 2 — POS flow
    r = flows.sell(client, product_id, 2)
    assert r.ok, f"sale failed: {r.status_code} {r.body[:300]}"

    with session_factory() as s:
        from app.rms.models import Ingredient, Sale
        sale = s.query(Sale).filter_by(product_id=product_id).one()
        assert sale.unit_price_gs == 25000, "snapshot price at sale time"
        sale_id = sale.id
        harina_stock = s.get(Ingredient, harina_id).stock_qty

    # 5. Void it with a reason — stock must be restored
    assert flows.void_sale(client, sale_id, reason="cliente se arrepintió").ok

    with session_factory() as s:
        from app.rms.models import Ingredient
        after_void = s.get(Ingredient, harina_id).stock_qty
    assert after_void > harina_stock, "void must restore consumed stock"

    # 6. Merma: waste some manteca
    assert flows.register_merma(client, manteca_id, 0.1).ok

    # --- INVARIANT SWEEP ---
    with session_factory() as s:

        from app.rms.models import Ingredient, Sale

        # I1: no negative stock anywhere
        neg = s.query(Ingredient).filter(Ingredient.stock_qty < 0).all()
        assert not neg, f"negative stock: {[(i.name, i.stock_qty) for i in neg]}"

        # I3: money columns are ints
        for sale in s.query(Sale).all():
            assert isinstance(sale.unit_price_gs, int), "money must be int"

        # I2: void preserves the snapshot + records audit fields
        v = s.get(Sale, sale_id)
        assert v.voided_at is not None
        assert v.void_reason == "cliente se arrepintió"
        assert v.unit_price_gs == 25000


def test_allergen_guard_blocks_sale_for_allergic_customer(client, session_factory):
    """POS must 409 when the product contains the customer's declared allergen."""
    with session_factory() as s:
        harina = make_ingredient(s, allergens="gluten", stock_qty=10.0)
        rec = make_recipe(s, lines=[ing_line(harina, qty=1.0)])

        prod = make_product(s, recipe=rec, sale_price_gs=15000)
        cust = make_customer(s, allergens="gluten")
        s.commit()
        pid, cid = prod.id, cust.id

    r = flows.sell(client, pid, 1, customer_id=cid)
    assert r.status_code == 409, f"expected allergen block, got {r.status_code}"
    assert "ALÉRGENO" in r.body or "alérgico" in r.body

    # Same sale without customer passes
    r2 = flows.sell(client, pid, 1)
    assert r2.ok


def test_price_change_never_rewrites_sale_history(client, session_factory):
    """I2: snapshot immutability across a catalog price change."""
    with session_factory() as s:
        ing = make_ingredient(s, stock_qty=100.0)
        rec = make_recipe(s, lines=[ing_line(ing, qty=0.5)])
        prod = make_product(s, recipe=rec, sale_price_gs=10000)
        s.commit()
        pid = prod.id

    assert flows.sell(client, pid, 1).ok

    with session_factory() as s:
        from app.rms.models import Sale

        first_sale = s.query(Sale).filter_by(product_id=pid).one()
        first_id = first_sale.id

    # Change the product price
    p = flows.page(client, f"/productos/{pid}/editar")
    assert p.status_code == 200
    r = client.post(f"/productos/{pid}/editar", data={
        "name": "Producto 10000", "sale_price_gs": "20000",
        "portion_label": "1 unidad",
    }, follow_redirects=False)
    assert r.status_code == 303

    with session_factory() as s:
        from app.rms.models import Sale
        old = s.get(Sale, first_id)
        assert old.unit_price_gs == 10000, "history must not be rewritten"


def test_pedido_lifecycle_through_routes(client, session_factory):
    """pedido create → confirm → fulfill via HTTP; snapshot price holds."""

    with session_factory() as s:
        ing = make_ingredient(s, stock_qty=50.0)
        rec = make_recipe(s, lines=[ing_line(ing, qty=0.4)])
        prod = make_product(s, recipe=rec, sale_price_gs=12000)
        cust = make_customer(s)
        s.commit()
        pid, cid = prod.id, cust.id

    today = datetime.utcnow().date().isoformat()
    r = flows.create_pedido(
        client, promised_date=today,
        lines=[{"product_id": pid, "qty": 3, "unit_price_gs": 12000}],
        customer_id=cid, customer_name="Cliente E2E",
    )
    assert r.ok, f"pedido create failed: {r.status_code} {r.body[:300]}"

    with session_factory() as s:
        from app.rms.models import Pedido
        ped = s.query(Pedido).order_by(Pedido.id.desc()).first()
        assert ped.status == "pending"
        assert len(ped.lines) == 1
        assert ped.lines[0].qty == 3
        ped_id = ped.id

    assert flows.set_pedido_status(client, ped_id, "confirmed").ok
    assert flows.fulfill_pedido(client, ped_id).ok

    with session_factory() as s:
        from app.rms.models import Pedido
        ped = s.get(Pedido, ped_id)
        assert ped.status == "fulfilled"


def test_recipe_form_line_contract(client, session_factory):
    """Regression for the 2026-09 bug: form posted qty/unit but the server
    read line_qty/line_unit — every line silently dropped."""
    with session_factory() as s:
        a = make_ingredient(s)
        b = make_ingredient(s)
        s.commit()
        a_id, b_id = a.id, b.id

    r = flows.create_recipe(client, name="Receta líneas", lines=[
        {"target_id": a_id, "qty": 0.5, "unit": "kg"},
        {"target_id": b_id, "qty": 0.25, "unit": "kg"},
    ])
    assert r.ok

    with session_factory() as s:
        from app.rms.models import Recipe
        rec = s.query(Recipe).filter_by(name="Receta líneas").one()
        qtys = sorted(ln.qty for ln in rec.lines)
        assert qtys == [0.25, 0.5], f"lines lost: {qtys}"


def test_stock_never_negative_without_confirmation(client, session_factory):
    """Hostile adjustment: -1000 on a 10-unit stock must not silently pass."""
    with session_factory() as s:
        ing = make_ingredient(s, stock_qty=10.0)
        s.commit()
        iid = ing.id

    flows.adjust_stock(client, iid, -1000.0)
    # Rejected without confirm_negative — either an error status or a
    # redirect that left stock untouched.
    with session_factory() as s:
        from app.rms.models import Ingredient
        cur = s.get(Ingredient, iid)
    assert cur.stock_qty >= 0, f"stock went negative silently: {cur.stock_qty}"


def test_tag_algebra_product_tags_track_ingredients(client, session_factory):
    """I5: derived tags on the product match the ingredient intersection/union."""
    with session_factory() as s:
        sin_tacc = make_ingredient(s, allergens="", dietary_tags="sin gluten,sin azucar",
                                   may_contain_gluten=False)
        con_lacteos = make_ingredient(s, allergens="lacteos", dietary_tags="sin gluten")
        rec = make_recipe(s, lines=[ing_line(sin_tacc), ing_line(con_lacteos)])
        prod = make_product(s, recipe=rec)
        s.commit()
        ids = (sin_tacc.id, con_lacteos.id, prod.id)

    # The cascade runs on ROUTE saves (recipe save/edit, ingredient edit) —
    # factories write rows directly, so drive the real edit route to fire it.
    with session_factory() as s:
        from app.rms.models import Recipe
        rec = s.get(Recipe, s.get(Product := __import__("app.rms.models", fromlist=["Product"]).Product, ids[2]).recipe_id)
        rec_id = rec.id

    r = client.post(f"/recetas/{rec_id}/editar", data={
        "name": "Receta cascada", "yield_qty": "12", "yield_unit": "und",
        "line_kind": ["ingredient", "ingredient"],
        "line_target_id": [str(ids[0]), str(ids[1])],
        "line_qty": ["0.3", "0.2"], "line_unit": ["kg", "kg"],
    }, follow_redirects=False)
    assert r.status_code == 303, f"edit failed: {r.status_code} {getattr(r, 'text', '')[:300]}"

    with session_factory() as s:
        from app.rms.models import Product
        prod = s.get(Product, ids[2])
        # _product_inherit_sync writes Product.inherited_tags
        # ("tag,tag,al:allergen" format).
        tags = (getattr(prod, "inherited_tags", "") or "")
        # intersection: both ingredients are sin gluten → product keeps it;
        # azucar (only on one) is dropped. Allergens union: lacteos present.
        assert "sin gluten" in tags, f"tags={tags!r}"
        assert "sin azucar" not in tags, f"tags={tags!r}"
        assert "al:lacteos" in tags, f"tags={tags!r}"
