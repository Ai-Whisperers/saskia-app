"""tests/test_preflight_multi_route.py — POST /ventas/nueva/preflight/multi."""

from __future__ import annotations

from datetime import datetime


def _seed_cart(client, qseed):
    """Build a 2-line cart from qseed: 1 unit of basic + 1 unit of with_sale."""
    data = qseed("basic")
    p = data["product"]
    return [
        {"product_id": p.id, "qty": 1.0, "discount_gs": 0},
    ]


def test_preflight_multi_empty_cart_is_blocker(client, qseed):
    r = client.post(
        "/ventas/nueva/preflight/multi",
        json={
            "items": [],
            "payment_method": "efectivo",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert any(w["code"] == "CART_EMPTY" for w in data["blockers"])
    assert data["is_ready"] is False


def test_preflight_multi_clean_cart(client, qseed):
    items = _seed_cart(client, qseed)
    r = client.post(
        "/ventas/nueva/preflight/multi",
        json={
            "items": items,
            "payment_method": "efectivo",
            "sold_at": datetime(2026, 10, 7).isoformat(),
        },
    )
    assert r.status_code == 200
    data = r.json()
    # Missing payment info shouldn't fire (we provided one)
    assert data["is_ready"] is True
    assert data["line_count"] == 1


def test_preflight_multi_missing_payment_is_info(client, qseed):
    items = _seed_cart(client, qseed)
    r = client.post(
        "/ventas/nueva/preflight/multi",
        json={
            "items": items,
            "payment_method": "",
        },
    )
    assert r.status_code == 200
    data = r.json()
    payment = [w for w in data["warnings"] if w["code"] == "CART_PAYMENT_METHOD_MISSING"]
    assert len(payment) == 1
    assert payment[0]["severity"] == "info"
    # Info doesn't block
    assert data["is_ready"] is True


def test_preflight_multi_per_line_qty_blocker(client, qseed):
    items = _seed_cart(client, qseed)
    items[0]["qty"] = -1  # negative qty
    r = client.post(
        "/ventas/nueva/preflight/multi",
        json={
            "items": items,
            "payment_method": "efectivo",
        },
    )
    assert r.status_code == 200
    data = r.json()
    # The QTY_NOT_POSITIVE@0 should fire on line 0
    codes = {w["code"] for w in data["blockers"]}
    assert any(c.startswith("QTY_NOT_POSITIVE@0") for c in codes)


def test_preflight_multi_response_shape(client, qseed):
    items = _seed_cart(client, qseed)
    r = client.post(
        "/ventas/nueva/preflight/multi",
        json={
            "items": items,
            "payment_method": "efectivo",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert set(data.keys()) >= {"warnings", "blockers", "is_ready", "is_clean", "line_count"}
    assert data["line_count"] == 1


def test_preflight_multi_invalid_json_returns_400(client):
    r = client.post(
        "/ventas/nueva/preflight/multi",
        content="not json",
        headers={"content-type": "application/json"},
    )
    # FastAPI may return 400 or 422 depending on body parsing
    assert r.status_code in (400, 422)


def test_preflight_multi_malformed_line_is_skipped(client, qseed):
    """A non-dict item in the list should be skipped, not crash."""
    items = _seed_cart(client, qseed)
    items.append("not-a-dict")  # malformed
    r = client.post(
        "/ventas/nueva/preflight/multi",
        json={
            "items": items,
            "payment_method": "efectivo",
        },
    )
    assert r.status_code == 200
    data = r.json()
    # The good line is still counted
    assert data["line_count"] == 1  # bad item was skipped


def test_preflight_multi_customer_id_in_body(client, qseed):
    """A customer_id in the body is accepted and applied at cart level."""
    items = _seed_cart(client, qseed)
    r = client.post(
        "/ventas/nueva/preflight/multi",
        json={
            "items": items,
            "customer_id": 999,  # may not exist — should be a no-op for the preflight
            "payment_method": "efectivo",
        },
    )
    assert r.status_code == 200
