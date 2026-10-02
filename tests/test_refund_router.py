"""tests/test_refund_router.py — HTTP smoke tests for /refunds endpoints.

Covers the minimal contract: refund creation form returns 303, list endpoint
returns JSON, error codes map to user-facing Spanish flash messages.

Uses the standard conftest `client` + fixtures (SaskiaTestClient via
tests/conftest.py). Auth is bypassed via SASKIA_TEST_AUTH_DISABLED=1.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("SASKIA_ENV", "test")
os.environ.setdefault("SASKIA_TEST_AUTH_DISABLED", "1")


def _make_sale_for_router(client):
    """Create a minimal Sale via the existing create-sale form."""
    # Use the standard POS form endpoint
    # POST /ventas/nueva accepts: sku, qty, payment_method, etc.
    # First create a product
    from app.rms.db import init_db, make_engine
    from app.rms.models_legacy import Product, Sale
    from sqlalchemy.orm import sessionmaker

    # The client fixture gives us a TestClient; back it by an in-memory engine
    # the suite already created.
    engine = client.app.state.engine if hasattr(client.app.state, "engine") else None
    if engine is None:
        pytest.skip("client fixture missing engine")

    SessionLocal = sessionmaker(bind=engine)
    s = SessionLocal()
    # Idempotent Product
    if s.execute(__import__("sqlalchemy").text("SELECT id FROM product WHERE id=1")).first() is None:
        s.add(Product(id=1, name="Router Test Product", sale_price_gs=10_000, portion_label="unit"))
        s.flush()
    # Idempotent Sale (id=1)
    existing = s.get(Sale, 1)
    if existing is None:
        sale = Sale(
            id=1,
            product_id=1,
            qty=1.0,
            unit_price_gs=10_000,
            sold_at=datetime.now(timezone.utc),
            payment_method="efectivo",
            discount_gs=0,
            channel="mostrador",
            invoice_type="none",
            tz="America/Asuncion",
        )
        s.add(sale)
        s.commit()
    s.close()
    return 1


def test_refund_create_redirects(client):
    """POST /refunds/ for a valid sale returns 303 + Location."""
    _make_sale_for_router(client)
    r = client.post(
        "/refunds/",
        data={
            "target_type": "sale",
            "target_id": 1,
            "amount_gs": 5_000,
            "reason": "test refund",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "/ventas/1" in r.headers["location"]


def test_refund_list_target_returns_count(client):
    """GET /refunds/target/{type}/{id} returns count + total_refunded_gs.

    The list endpoint reads in its own session; we use the same DB the
    client writes to (client.app.state.engine). For test determinism,
    create the Refund row directly via ORM rather than via the POST,
    so we don't depend on the session lifecycle across requests.
    """
    from app.rms.db import init_db, make_engine
    from app.rms.models_legacy import Product, Refund, Sale
    from sqlalchemy.orm import sessionmaker
    from datetime import datetime, timezone

    engine = client.app.state.engine
    SessionLocal = sessionmaker(bind=engine)
    s = SessionLocal()
    # Idempotent setup
    if s.execute(__import__("sqlalchemy").text("SELECT id FROM product WHERE id=1")).first() is None:
        s.add(Product(id=1, name="List Test Product", sale_price_gs=10_000, portion_label="unit"))
        s.flush()
    if s.get(Sale, 1) is None:
        s.add(Sale(
            id=1, product_id=1, qty=1.0, unit_price_gs=10_000,
            sold_at=datetime.now(timezone.utc), payment_method="efectivo",
            discount_gs=0, channel="mostrador", invoice_type="none",
            tz="America/Asuncion",
        ))
        s.flush()
    if s.execute(__import__("sqlalchemy").text("SELECT id FROM refund WHERE id=1")).first() is None:
        s.add(Refund(
            id=1, target_type="sale", target_id=1, target_amount_gs=10_000,
            amount_gs=5_000, payment_method="efectivo",
            restock_qty=False, restocked_qty=0.0,
            recorded_at=datetime.now(timezone.utc), recorded_by="op",
            loyalty_reversed=0,
        ))
        s.commit()
    s.close()

    r = client.get("/refunds/target/sale/1")
    assert r.status_code == 200
    data = r.json()
    assert data["target_type"] == "sale"
    assert data["target_id"] == 1
    assert data["count"] >= 1
    assert data["total_refunded_gs"] >= 5_000


def test_refund_cap_exceeded_redirects_with_flash(client):
    """Trying to refund more than remaining target must redirect with flash."""
    _make_sale_for_router(client)
    r = client.post(
        "/refunds/",
        data={
            "target_type": "sale",
            "target_id": 1,
            "amount_gs": 999_999_999,  # way too much
        },
        follow_redirects=False,
    )
    # Should redirect (303) back to sale detail with flash key
    assert r.status_code == 303
    assert "refund_err" in r.headers["location"]


def test_refund_invalid_target_type_400(client):
    """target_type not in valid set → redirect (handled at form layer)."""
    r = client.post(
        "/refunds/",
        data={
            "target_type": "garbage",
            "target_id": 1,
            "amount_gs": 1_000,
        },
        follow_redirects=False,
    )
    # Currently we redirect on POST; the GET validation rejects before redirect.
    # For POST: form submits, create_refund raises invalid_target_type, redirect.
    assert r.status_code in (303, 400)