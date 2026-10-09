"""SASKIA-205 — mark-purchased triggers inventory.

Two purchase flows previously only flipped a boolean; bought stock
never landed on /inventario:

1. POST /shopping-list/{id}/mark-purchased  → ingredient.stock_qty bump
   + StockMovement(movement_type='reorder', reference_type='reorder')
2. POST /wishlist/{id}/mark-purchased       → [EQUIPMENT] pseudo-ingredient
   created/updated + StockMovement row

Contract locked here:
- Stock bumps ONLY on the False→True transition (idempotent re-mark).
- /unmark does NOT subtract stock (physical stock doesn't un-arrive).
- Unit conversion: qty_to_buy unit ≠ ingredient unit converts when
  possible ('g' → 'kg'); non-convertible ('und' → 'kg') lands raw qty.
- Wishlist mark-purchased creates the [EQUIPMENT] ingredient on the fly
  when send-to-shopping-list was never used.
"""

from __future__ import annotations

import pytest

from app.rms.models import Ingredient, ShoppingListItem, StockMovement, WishlistItem

pytestmark = [pytest.mark.smoke]


def _make_ingredient(s, *, name: str, unit: str = "kg", stock: float = 0.0) -> Ingredient:
    ing = Ingredient(
        name=name,
        unit=unit,
        stock_qty=stock,
        purchase_price_gs=1000,
        min_stock_qty=1,
    )
    s.add(ing)
    s.commit()
    s.refresh(ing)
    return ing


def _make_sl_item(
    s,
    ing: Ingredient,
    *,
    qty: float = 5.0,
    unit: str | None = None,
    purchased: bool = False,
) -> ShoppingListItem:
    item = ShoppingListItem(
        ingredient_id=ing.id,
        qty_to_buy=qty,
        unit=unit or ing.unit,
        purpose_text="test",
        purchased=purchased,
    )
    s.add(item)
    s.commit()
    s.refresh(item)
    return item


# ── Shopping-list mark-purchased → stock ─────────────────────────────────


def test_sl_mark_purchased_bumps_stock(client, session_factory):
    """Marking bought adds qty_to_buy to ingredient.stock_qty and writes
    a reorder StockMovement."""
    with session_factory() as s:
        ing = _make_ingredient(
            s, name=f"Harina SL-{__import__('uuid').uuid4().hex[:6]}", unit="kg", stock=2.0
        )
        item = _make_sl_item(s, ing, qty=5.0, unit="kg")
        item_id, ing_id = item.id, ing.id

        r = client.post(f"/shopping-list/{item_id}/mark-purchased", follow_redirects=False)
        assert r.status_code == 303

        s.expire_all()  # the route's session committed; drop cached state
        ing2 = s.get(Ingredient, ing_id)
        assert float(ing2.stock_qty) == pytest.approx(7.0)  # 2.0 + 5.0
        moves = (
            s.query(StockMovement).filter_by(ingredient_id=ing_id, movement_type="reorder").all()
        )
        assert len(moves) == 1
        assert moves[0].qty == pytest.approx(5.0)
        assert moves[0].reference_id == item_id


def test_sl_mark_purchased_idempotent(client, session_factory):
    """Re-marking does NOT double the stock."""
    with session_factory() as s:
        ing = _make_ingredient(
            s, name=f"Azucar SL-{__import__('uuid').uuid4().hex[:6]}", unit="kg", stock=1.0
        )
        item = _make_sl_item(s, ing, qty=3.0, unit="kg")
        item_id, ing_id = item.id, ing.id

        client.post(f"/shopping-list/{item_id}/mark-purchased", follow_redirects=False)
        client.post(f"/shopping-list/{item_id}/mark-purchased", follow_redirects=False)  # again

        s.expire_all()
        ing2 = s.get(Ingredient, ing_id)
        assert float(ing2.stock_qty) == pytest.approx(4.0)  # 1.0 + 3.0, not +6
        moves = (
            s.query(StockMovement).filter_by(ingredient_id=ing_id, movement_type="reorder").all()
        )
        assert len(moves) == 1


def test_sl_mark_purchased_converts_units(client, session_factory):
    """5000 g bought for a kg-stock ingredient lands as +5 kg."""
    with session_factory() as s:
        ing = _make_ingredient(
            s, name=f"Manteca SL-{__import__('uuid').uuid4().hex[:6]}", unit="kg", stock=0.0
        )
        item = _make_sl_item(s, ing, qty=5000.0, unit="g")
        item_id, ing_id = item.id, ing.id

        client.post(f"/shopping-list/{item_id}/mark-purchased", follow_redirects=False)

        s.expire_all()
        ing2 = s.get(Ingredient, ing_id)
        assert float(ing2.stock_qty) == pytest.approx(5.0)


def test_sl_unmark_does_not_subtract(client, session_factory):
    """Unmark flips the boolean but stock stays (physical stock doesn't
    un-arrive)."""
    with session_factory() as s:
        ing = _make_ingredient(
            s, name=f"Leche SL-{__import__('uuid').uuid4().hex[:6]}", unit="l", stock=1.0
        )
        item = _make_sl_item(s, ing, qty=4.0, unit="l")
        item_id, ing_id = item.id, ing.id

        client.post(f"/shopping-list/{item_id}/mark-purchased", follow_redirects=False)
        client.post(f"/shopping-list/{item_id}/unmark", follow_redirects=False)

        s.expire_all()
        ing2 = s.get(Ingredient, ing_id)
        assert float(ing2.stock_qty) == pytest.approx(5.0)  # unchanged
        assert s.get(ShoppingListItem, item_id).purchased is False


# ── Wishlist mark-purchased → equipment stock ────────────────────────────


def _make_wishlist(s, *, name: str, qty: int = 1, price: int = 500_000) -> WishlistItem:
    item = WishlistItem(
        code=f"WS-{__import__('uuid').uuid4().hex[:6]}",
        name=name,
        priority="must_have",
        quantity=qty,
        unit_price_gs=price,
        purchased=False,
    )
    s.add(item)
    s.commit()
    s.refresh(item)
    return item


def test_wishlist_mark_purchased_creates_equipment_stock(client, session_factory):
    """Direct mark-purchased (no send-to-shopping-list) creates the
    [EQUIPMENT] pseudo-ingredient with stock."""
    with session_factory() as s:
        item = _make_wishlist(
            s, name=f"Batedeira W1-{__import__('uuid').uuid4().hex[:4]}", qty=2, price=1_200_000
        )
        item_id, name = item.id, item.name

        r = client.post(f"/wishlist/{item_id}/mark-purchased", follow_redirects=False)
        assert r.status_code == 303

        eq = s.query(Ingredient).filter_by(name=f"[EQUIPMENT] {name}").one_or_none()
        assert eq is not None
        assert float(eq.stock_qty) == pytest.approx(2.0)
        assert eq.purchase_price_gs == 1_200_000
        assert eq.category == "Equipment"

        moves = s.query(StockMovement).filter_by(ingredient_id=eq.id, movement_type="reorder").all()
        assert len(moves) == 1
        assert moves[0].qty == pytest.approx(2.0)


def test_wishlist_mark_purchased_idempotent(client, session_factory):
    """Re-marking a wishlist item does not double equipment stock."""
    with session_factory() as s:
        item = _make_wishlist(s, name=f"Horno W2-{__import__('uuid').uuid4().hex[:4]}", qty=1)
        item_id, name = item.id, item.name

        client.post(f"/wishlist/{item_id}/mark-purchased", follow_redirects=False)
        client.post(f"/wishlist/{item_id}/mark-purchased", follow_redirects=False)

        s.expire_all()
        eq = s.query(Ingredient).filter_by(name=f"[EQUIPMENT] {name}").one()
        assert float(eq.stock_qty) == pytest.approx(1.0)


def test_wishlist_mark_purchased_updates_existing_equipment(client, session_factory):
    """If send-to-shopping-list already created the [EQUIPMENT] ingredient,
    mark-purchased updates it instead of duplicating."""
    with session_factory() as s:
        item = _make_wishlist(s, name=f"Freezer W3-{__import__('uuid').uuid4().hex[:4]}", qty=1)
        item_id, name = item.id, item.name
        # simulate the send-to-shopping-list pseudo-ingredient creation
        pre = Ingredient(
            name=f"[EQUIPMENT] {name}",
            unit="und",
            stock_qty=0.0,
            purchase_price_gs=999,
            min_stock_qty=0,
            category="Equipment",
        )
        s.add(pre)
        s.commit()
        s.refresh(pre)

        client.post(f"/wishlist/{item_id}/mark-purchased", follow_redirects=False)

        s.expire_all()
        eqs = s.query(Ingredient).filter_by(name=f"[EQUIPMENT] {name}").all()
        assert len(eqs) == 1  # no duplicate
        assert float(eqs[0].stock_qty) == pytest.approx(1.0)
        assert eqs[0].purchase_price_gs == 500_000  # price updated
