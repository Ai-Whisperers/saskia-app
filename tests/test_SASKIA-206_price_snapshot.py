"""SASKIA-206 — unit price snapshot on ShoppingListItem.

A row created today at ₲5.000/kg must still show ₲5.000/kg after the
ingredient's catalog price changes to ₲6.000/kg. Pre-113 rows (no
snapshot) fall back to the live price.
"""

from __future__ import annotations

import uuid

import pytest

from app.rms.models import Ingredient, ShoppingListItem

pytestmark = [pytest.mark.smoke]


def _ing(s, *, price: int | None, unit: str = "kg") -> Ingredient:
    ing = Ingredient(
        name=f"Ing-{uuid.uuid4().hex[:8]}",
        unit=unit,
        stock_qty=1.0,
        purchase_price_gs=price if price is not None else 0,
        min_stock_qty=1,
    )
    s.add(ing)
    s.commit()
    s.refresh(ing)
    return ing


def _open_list_page(client):
    r = client.get("/shopping-list")
    assert r.status_code == 200
    return r


def test_add_item_freezes_price(client, session_factory):
    """Manual add snapshots the current purchase price; later catalog
    price changes do NOT alter the row's displayed price."""
    with session_factory() as s:
        ing = _ing(s, price=5000)
        ing_id = ing.id

    r = client.post(
        "/shopping-list/add",
        data={
            "ingredient_id": str(ing_id),
            "qty_to_buy": "2",
            "unit": "kg",
            "purpose_text": "snapshot test",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303

    with session_factory() as s:
        row = s.query(ShoppingListItem).filter_by(ingredient_id=ing_id).one()
        assert row.unit_price_snapshot_gs == 5000

        # Catalog price moves after the row exists
        ing2 = s.get(Ingredient, ing_id)
        ing2.purchase_price_gs = 6000
        s.commit()

    # Page still shows the frozen price (5000 * 2 = 10000)
    page = _open_list_page(client).text
    assert "10.000" in page or "10000" in page


def test_add_item_without_price_gets_null_snapshot(client, session_factory):
    """Ingredient with no price → NULL snapshot; page falls back to live
    price (which is also empty → '—')."""
    with session_factory() as s:
        ing = _ing(s, price=None)
        ing_id = ing.id

    client.post(
        "/shopping-list/add",
        data={
            "ingredient_id": str(ing_id),
            "qty_to_buy": "1",
            "unit": "kg",
            "purpose_text": "",
        },
        follow_redirects=False,
    )

    with session_factory() as s:
        row = s.query(ShoppingListItem).filter_by(ingredient_id=ing_id).one()
        assert row.unit_price_snapshot_gs is None


def test_orm_direct_creation_snapshots_via_helper(session_factory):
    """The _price_snapshot helper returns the int price / None."""
    from app.routers.shopping import _price_snapshot

    with session_factory() as s:
        ing = _ing(s, price=12345)
        assert _price_snapshot(s, ing.id) == 12345

        ing2 = _ing(s, price=None)
        assert _price_snapshot(s, ing2.id) is None
