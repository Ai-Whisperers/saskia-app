"""P40 — /reorder/quick-restock one-tap "I bought it" button.

Pre-P40: 0 records in shopping_list_item.purchased_at in 30 days because
the restock form required filling qty + price + supplier on every row.
P40 adds /reorder/quick-restock (single ingredient) and
/reorder/bulk-quick-restock (comma-separated ids).
"""

import pytest
from sqlalchemy import select

from app.rms.models import Ingredient, IngredientPriceEvent, Supplier


def test_quick_restock_fills_to_max(client, session_factory):
    """Ingredient at 0.5kg with min=10/max=20 → quick-restock brings it to 20."""
    with session_factory() as s:
        sup = s.execute(select(Supplier).limit(1)).scalar_one_or_none()
        if sup is None:
            sup = Supplier(name="TestSup", phone="+595981234567", is_active=True)
            s.add(sup)
            s.flush()
        ing = Ingredient(
            name="Harina P40",
            unit="kg",
            stock_qty=0.5,
            min_stock_qty=10.0,
            max_stock_qty=20.0,
            purchase_price_gs=35000,
            supplier_id=sup.id,
        )
        s.add(ing)
        s.flush()
        s.add(
            IngredientPriceEvent(
                ingredient_id=ing.id,
                price_gs=35000,
                source="seed",
                supplier_id=sup.id,
            )
        )
        s.commit()
        iid = ing.id

    r = client.post(
        "/reorder/quick-restock",
        data={"ingredient_id": str(iid)},
        follow_redirects=False,
    )
    assert r.status_code == 303, f"got {r.status_code}: {r.text}"
    assert r.headers["location"] == "/reorder"

    with session_factory() as s:
        refreshed = s.get(Ingredient, iid)
        assert refreshed.stock_qty == pytest.approx(20.0)
        evts = (
            s.execute(
                select(IngredientPriceEvent).where(
                    IngredientPriceEvent.ingredient_id == iid,
                    IngredientPriceEvent.source == "restock",
                )
            )
            .scalars()
            .all()
        )
        assert len(evts) == 1
        assert evts[0].price_gs == 35000


def test_quick_restock_idempotent_when_full(client, session_factory):
    """If already at max, no price event is added but the route still 303s."""
    with session_factory() as s:
        ing = Ingredient(
            name="AlreadyFull P40",
            unit="kg",
            stock_qty=10.0,
            min_stock_qty=5.0,
            max_stock_qty=10.0,
            purchase_price_gs=1000,
        )
        s.add(ing)
        s.commit()
        iid = ing.id

    r = client.post(
        "/reorder/quick-restock",
        data={"ingredient_id": str(iid)},
        follow_redirects=False,
    )
    assert r.status_code == 303
    with session_factory() as s:
        refreshed = s.get(Ingredient, iid)
        assert refreshed.stock_qty == pytest.approx(10.0)  # unchanged


def test_bulk_quick_restock_updates_all(client, session_factory):
    with session_factory() as s:
        a = Ingredient(
            name="BulkA", unit="kg", stock_qty=0.0, min_stock_qty=5.0, max_stock_qty=10.0
        )
        b = Ingredient(
            name="BulkB", unit="kg", stock_qty=1.0, min_stock_qty=10.0, max_stock_qty=20.0
        )
        s.add_all([a, b])
        s.commit()
        a_id, b_id = a.id, b.id

    r = client.post(
        "/reorder/bulk-quick-restock",
        data={"ingredient_ids": f"{a_id},{b_id}"},
        follow_redirects=False,
    )
    assert r.status_code == 303

    with session_factory() as s:
        ra = s.get(Ingredient, a_id)
        rb = s.get(Ingredient, b_id)
        assert ra.stock_qty == pytest.approx(10.0)
        assert rb.stock_qty == pytest.approx(20.0)


def test_bulk_quick_restock_empty_is_noop(client):
    r = client.post(
        "/reorder/bulk-quick-restock",
        data={"ingredient_ids": ""},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/reorder"


def test_quick_restock_404_on_unknown(client):
    r = client.post(
        "/reorder/quick-restock",
        data={"ingredient_id": "999999999"},
        follow_redirects=False,
    )
    assert r.status_code in (404, 422)
