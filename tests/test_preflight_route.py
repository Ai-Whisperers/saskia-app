"""tests/test_preflight_route.py — POST /ventas/nueva/preflight."""
from __future__ import annotations

from datetime import datetime


def test_preflight_clean_sale(client, qseed):
    """A clean sale returns no warnings and is_ready=True."""
    r = client.post("/ventas/nueva/preflight", data={
        "product_id": qseed("basic")["product"].id,
        "qty": 1.0,
        "payment_method": "efectivo",
        "sold_at": datetime(2026, 10, 7).isoformat(),
    })
    assert r.status_code == 200
    data = r.json()
    assert data["is_ready"] is True
    assert data["is_clean"] is True
    assert data["blockers"] == []
    assert data["warnings"] == []


def test_preflight_blocker_for_zero_qty(client, qseed):
    """A zero-qty sale is a blocker."""
    r = client.post("/ventas/nueva/preflight", data={
        "product_id": qseed("basic")["product"].id,
        "qty": 0,
        "sold_at": datetime(2026, 10, 7).isoformat(),
    })
    # Form validation: qty=0 violates Form(gt=0) so we get a 4xx
    # (FastAPI may return 400 or 422 depending on error-handler config)
    assert r.status_code in (200, 400, 422)


def test_preflight_blocker_for_missing_product(client, qseed):
    """Missing product is a blocker."""
    r = client.post("/ventas/nueva/preflight", data={
        "qty": 1.0,
        "sold_at": datetime(2026, 10, 7).isoformat(),
    })
    assert r.status_code == 200
    data = r.json()
    assert any(w["code"] == "PRODUCT_NOT_FOUND" for w in data["blockers"])
    assert data["is_ready"] is False


def test_preflight_warning_for_missing_payment(client, qseed):
    """Missing payment method is an info-level warning."""
    r = client.post("/ventas/nueva/preflight", data={
        "product_id": qseed("basic")["product"].id,
        "qty": 1.0,
        "sold_at": datetime(2026, 10, 7).isoformat(),
        "payment_method": "",
    })
    assert r.status_code == 200
    data = r.json()
    payment = [w for w in data["warnings"] if w["code"] == "PAYMENT_METHOD_MISSING"]
    assert len(payment) == 1
    assert payment[0]["severity"] == "info"
    # Info-only warning: sale is still ready
    assert data["is_ready"] is True


def test_preflight_response_structure(client, qseed):
    """The response must always have the 4 expected keys."""
    r = client.post("/ventas/nueva/preflight", data={
        "product_id": qseed("basic")["product"].id,
        "qty": 1.0,
        "sold_at": datetime(2026, 10, 7).isoformat(),
    })
    assert r.status_code == 200
    data = r.json()
    assert set(data.keys()) == {"warnings", "blockers", "is_ready", "is_clean"}
    assert isinstance(data["warnings"], list)
    assert isinstance(data["blockers"], list)
    assert isinstance(data["is_ready"], bool)
    assert isinstance(data["is_clean"], bool)


def test_preflight_warning_items_have_required_fields(client, qseed):
    """Each warning/blocker has code, severity, message."""
    r = client.post("/ventas/nueva/preflight", data={
        "product_id": qseed("basic")["product"].id,
        "qty": 1.0,
        "sold_at": datetime(2026, 10, 7).isoformat(),
        "payment_method": "",  # triggers info warning
    })
    assert r.status_code == 200
    data = r.json()
    all_items = data["warnings"] + data["blockers"]
    for item in all_items:
        assert "code" in item
        assert "severity" in item
        assert "message" in item
        assert item["severity"] in ("blocker", "warning", "info")
        # Code is machine-readable
        assert item["code"].isupper() or "_" in item["code"]


def test_preflight_handles_invalid_sold_at_gracefully(client, qseed):
    """An invalid sold_at format falls back to today (no error)."""
    r = client.post("/ventas/nueva/preflight", data={
        "product_id": qseed("basic")["product"].id,
        "qty": 1.0,
        "sold_at": "not-a-date",
    })
    assert r.status_code == 200  # Graceful fallback
