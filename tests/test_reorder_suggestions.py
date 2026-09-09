"""tests/test_reorder_suggestions.py — operator-impact feature.

For each ingredient below min_stock, compute:
  suggested_qty = max_stock - current_stock
This is the simple "fill back to max" heuristic. Operators then use
this list to place manual orders with their suppliers.
"""
from __future__ import annotations


def test_reorder_endpoint_lists_low_stock(client, session_factory):
    """/reorder lists ingredients below min_stock."""
    from app.rms.models import Ingredient

    with session_factory() as s:
        s.add(Ingredient(name="Low_ing", unit="kg", stock_qty=2.0,
                         purchase_price_gs=5000, min_stock_qty=5.0, max_stock_qty=20.0))
        s.add(Ingredient(name="Ok_ing", unit="kg", stock_qty=15.0,
                         purchase_price_gs=5000, min_stock_qty=5.0, max_stock_qty=20.0))
        s.add(Ingredient(name="Critical_ing", unit="kg", stock_qty=0.0,
                         purchase_price_gs=5000, min_stock_qty=5.0, max_stock_qty=20.0))
        s.commit()

    resp = client.get("/reorder")
    assert resp.status_code == 200
    body = resp.text
    assert "Low_ing" in body
    assert "Critical_ing" in body
    assert "Ok_ing" not in body  # Above min, no reorder needed


def test_reorder_suggested_qty_is_max_minus_current(client, session_factory):
    """suggested_qty = max_stock - current_stock."""
    from app.rms.models import Ingredient

    with session_factory() as s:
        s.add(Ingredient(name="FillMeUp", unit="kg", stock_qty=3.0,
                         purchase_price_gs=5000, min_stock_qty=5.0, max_stock_qty=20.0))
        s.commit()

    resp = client.get("/reorder")
    assert resp.status_code == 200
    body = resp.text
    # 20 - 3 = 17 kg to reorder
    assert "17" in body or "17.0" in body


def test_reorder_sorted_by_urgency(client, session_factory):
    """Most-urgent (lowest stock / min ratio) listed first."""
    from app.rms.models import Ingredient

    with session_factory() as s:
        # Less urgent: 4.9/5 = 0.98 ratio (just below min)
        s.add(Ingredient(name="AlmostOK", unit="kg", stock_qty=4.9,
                         purchase_price_gs=5000, min_stock_qty=5.0, max_stock_qty=20.0))
        # Most urgent: 0/5 = 0 ratio (zero stock)
        s.add(Ingredient(name="OutOfStock", unit="kg", stock_qty=0.0,
                         purchase_price_gs=5000, min_stock_qty=5.0, max_stock_qty=20.0))
        s.commit()

    resp = client.get("/reorder")
    body = resp.text
    # OutOfStock should appear before AlmostOK in the rendered list.
    assert body.index("OutOfStock") < body.index("AlmostOK")


def test_reorder_json_format(client, session_factory):
    """/reorder?format=json returns machine-readable suggestions."""
    from app.rms.models import Ingredient

    with session_factory() as s:
        s.add(Ingredient(name="Json_ing", unit="kg", stock_qty=1.0,
                         purchase_price_gs=5000, min_stock_qty=5.0, max_stock_qty=20.0))
        s.commit()

    resp = client.get("/reorder?format=json")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    items = data["items"]
    assert len(items) == 1
    item = items[0]
    assert item["name"] == "Json_ing"
    assert item["current_stock"] == 1.0
    assert item["min_stock"] == 5.0
    assert item["max_stock"] == 20.0
    assert item["suggested_qty"] == 19.0
    assert item["estimated_cost_gs"] == 19 * 5000  # 19 kg * 5000 Gs/kg


def test_reorder_empty_when_all_stock_ok(client, session_factory):
    """All ingredients above min → empty list."""
    from app.rms.models import Ingredient

    with session_factory() as s:
        s.add(Ingredient(name="Fine_ing", unit="kg", stock_qty=100.0,
                         purchase_price_gs=5000, min_stock_qty=5.0, max_stock_qty=50.0))
        s.commit()

    resp = client.get("/reorder?format=json")
    data = resp.json()
    assert data["items"] == []
