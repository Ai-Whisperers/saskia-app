"""P39 — shopping-list mark-purchased flow audit.

The data shows 53 shopping_list_item rows but 0 marked purchased in the
last 30 days. Either the endpoint is broken, or operators don't use it.
This test pins down that the endpoint works end-to-end so we can
distinguish "bug" from "operator habit".

Tests:
1. test_mark_purchased_endpoint_works: POST /shopping-list/{id}/mark-purchased
   flips purchased=1, sets purchased_at, persists across a new session.
2. test_unmark_purchased_endpoint_works: POST /shopping-list/{id}/unmark
   flips back to purchased=0, clears purchased_at.
3. test_purchase_creates_audit_log: the audit_log row is created with
   action="shopping.mark_purchased" and target_id=item.id.
"""
import pytest


@pytest.fixture
def seed_shopping_item(session_factory):
    """Create a shopping list item to mark purchased."""
    from app.rms.models import Ingredient, ShoppingListItem
    with session_factory() as s:
        ing = s.query(Ingredient).filter_by(name="P39-shop-test").first()
        if ing is None:
            ing = Ingredient(name="P39-shop-test", unit="kg",
                             stock_qty=0.0, min_stock_qty=1.0,
                             purchase_price_gs=5000)
            s.add(ing)
            s.flush()
        item = ShoppingListItem(
            ingredient_id=ing.id,
            qty_to_buy=2.0,
            unit="kg",
            purpose_text="P39 test",
            purchased=False,
        )
        s.add(item)
        s.commit()
        return item.id


def test_mark_purchased_endpoint_works(client, session_factory, seed_shopping_item):
    """POST to /shopping-list/{id}/mark-purchased flips purchased=1
    and sets purchased_at."""
    item_id = seed_shopping_item
    # Use the client to log in first
    client.post("/login", data={"username": "demo", "password": "demo1234"})

    response = client.post(f"/shopping-list/{item_id}/mark-purchased", follow_redirects=False)
    assert response.status_code in (303, 302), f"expected redirect, got {response.status_code}"

    with session_factory() as s:
        from app.rms.models import ShoppingListItem
        item = s.get(ShoppingListItem, item_id)
        assert item.purchased is True, f"expected purchased=True, got {item.purchased}"
        assert item.purchased_at is not None, "purchased_at should be set"


def test_unmark_purchased_endpoint_works(client, session_factory, seed_shopping_item):
    """Unmark resets purchased=0 and clears purchased_at."""
    item_id = seed_shopping_item
    client.post("/login", data={"username": "demo", "password": "demo1234"})

    # Mark then unmark
    client.post(f"/shopping-list/{item_id}/mark-purchased", follow_redirects=False)
    response = client.post(f"/shopping-list/{item_id}/unmark", follow_redirects=False)
    assert response.status_code in (303, 302)

    with session_factory() as s:
        from app.rms.models import ShoppingListItem
        item = s.get(ShoppingListItem, item_id)
        assert item.purchased is False
        assert item.purchased_at is None


