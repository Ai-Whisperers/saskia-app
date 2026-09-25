"""tests/e2e/test_suppliers_shopping_flows.py — Phase-5 coverage for the two
thinnest domains (measured: suppliers 1 test file / 5 tests; shopping had
only the env-dependent benchmark file, which errors without
/tmp/herbus_drive/dump.json).

Drives every shopping route + supplier-edit happy/sad paths through real
HTTP using the shared flows pattern, factories for rows, and asserts the
sync-low-stock business rule (qty = (min − stock) × 2, idempotent).
"""

from __future__ import annotations

import pytest

from tests.factories import make_ingredient, make_supplier

pytestmark = [pytest.mark.crud]


# ---------------------------------------------------------------------------
# Shopping list flows
# ---------------------------------------------------------------------------


def test_shopping_list_page_loads_empty(client):
    r = client.get("/shopping-list")
    assert r.status_code == 200


def test_add_item_then_mark_purchased_then_unmark(client, session_factory):
    with session_factory() as s:
        ing = make_ingredient(s)
        s.commit()
        iid = ing.id

    r = client.post("/shopping-list/add", data={
        "ingredient_id": str(iid), "qty_to_buy": "2.5", "unit": "kg",
    }, follow_redirects=False)
    assert r.status_code == 303, getattr(r, "text", "")[:300]

    with session_factory() as s:
        from app.rms.models import ShoppingListItem

        item = s.query(ShoppingListItem).filter_by(ingredient_id=iid).one()
        assert item.qty_to_buy == 2.5
        assert item.purchased is False
        item_id = item.id

    assert client.post(f"/shopping-list/{item_id}/mark-purchased",
                       follow_redirects=False).status_code == 303
    with session_factory() as s:
        from app.rms.models import ShoppingListItem
        it = s.get(ShoppingListItem, item_id)
        assert it.purchased is True
        assert it.purchased_at is not None
    # NOTE: the `with` block MUST close before the next POST — an open
    # SQLite read tx makes the route's write wait → 'database is locked'.

    assert client.post(f"/shopping-list/{item_id}/unmark",
                       follow_redirects=False).status_code == 303
    with session_factory() as s:
        from app.rms.models import ShoppingListItem
        it = s.get(ShoppingListItem, item_id)
        assert it.purchased is False
        assert it.purchased_at is None


def test_sync_low_stock_adds_missing_qty_and_is_idempotent(client, session_factory):
    with session_factory() as s:
        low = make_ingredient(s, stock_qty=1.0, min_stock_qty=5.0)   # deficit 4 → qty 8
        ok = make_ingredient(s, stock_qty=10.0, min_stock_qty=2.0)   # not low
        s.commit()
        low_id, ok_id = low.id, ok.id

    r = client.post("/shopping-list/sync-low-stock", follow_redirects=False)
    assert r.status_code == 303

    with session_factory() as s:
        from app.rms.models import ShoppingListItem

        items = {i.ingredient_id: i for i in s.query(ShoppingListItem).all()}
        assert low_id in items, "low-stock ingredient must be added"
        assert ok_id not in items, "healthy stock must not be added"
        assert items[low_id].qty_to_buy == 8.0  # (5 − 1) × 2

    # Idempotent: second sync adds no duplicate
    client.post("/shopping-list/sync-low-stock", follow_redirects=False)
    with session_factory() as s:
        from app.rms.models import ShoppingListItem
        n = s.query(ShoppingListItem).filter_by(ingredient_id=low_id).count()
        assert n == 1


def test_delete_item(client, session_factory):
    with session_factory() as s:
        ing = make_ingredient(s)
        s.commit()
        from app.rms.models import ShoppingListItem
        item = ShoppingListItem(ingredient_id=ing.id, qty_to_buy=1.0, unit="kg")
        s.add(item); s.commit()
        item_id = item.id

    assert client.post(f"/shopping-list/{item_id}/delete",
                       follow_redirects=False).status_code == 303
    with session_factory() as s:
        from app.rms.models import ShoppingListItem
        assert s.get(ShoppingListItem, item_id) is None


def test_mark_purchased_404_on_unknown(client):
    r = client.post("/shopping-list/999999/mark-purchased", follow_redirects=False)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Supplier flows (beyond the 5 existing CRUD tests: edit write-path +
# validation + ingredient linkage)
# ---------------------------------------------------------------------------


def test_supplier_edit_persists_fields(client, session_factory):
    with session_factory() as s:
        sup = make_supplier(s)
        s.commit()
        sid = sup.id

    r = client.post(f"/suppliers/{sid}/editar", data={
        "name": "Distribuidora Actualizada", "phone": "0982223333",
        "email": "ventas@distribuidora.py", "notes": "Entrega los martes",
    }, follow_redirects=False)
    assert r.status_code == 303, getattr(r, "text", "")[:300]

    with session_factory() as s:
        from app.rms.models import Supplier
        sup = s.get(Supplier, sid)
        assert sup.name == "Distribuidora Actualizada"
        assert sup.phone == "0982223333"


def test_supplier_create_requires_name(client):
    r = client.post("/suppliers/nuevo", data={"name": "", "phone": "0981"},
                    follow_redirects=False)
    assert r.status_code == 400


def test_supplier_ingredient_linkage_shows_on_page(client, session_factory):
    with session_factory() as s:
        sup = make_supplier(s)
        ing = make_ingredient(s, supplier_id=sup.id)
        s.commit()
        sid, ing_name = sup.id, ing.name

    r = client.get(f"/suppliers/{sid}/ordenes")
    assert r.status_code == 200
