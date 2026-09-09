"""tests/test_sale_via_sku.py — barcode/scan-based sale creation.

Cashier scans a product barcode → lookup SKU → create sale with the
matched product. This is the primary UX on a busy day.
"""
from __future__ import annotations


def test_sale_via_sku_route_lookup(client, session_factory):
    """GET /ventas/buscar?sku=X returns product match info as JSON.

    Used by the cashier-facing scan UI: scan → JSON response → form fills.
    """
    from app.rms.models import Product

    with session_factory() as s:
        p = Product(name="ScanProd", sale_price_gs=15000, sku="SCAN-001")
        s.add(p)
        s.commit()
        pid = p.id

    resp = client.get("/ventas/buscar?sku=SCAN-001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True
    assert body["product_id"] == pid
    assert body["name"] == "ScanProd"


def test_sale_via_sku_not_found(client):
    """Unknown SKU returns 200 with found=False."""
    resp = client.get("/ventas/buscar?sku=NOPE-999")
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is False


def test_sale_via_sku_no_sku_param(client):
    """Missing sku param returns 400."""
    resp = client.get("/ventas/buscar")
    assert resp.status_code == 422


def test_post_sale_accepts_sku(client, session_factory):
    """POST /ventas/nueva with sku= field looks up product automatically.

    This is the cashier flow: scan → POST with sku → sale created.
    """
    from app.rms.models import Product

    with session_factory() as s:
        p = Product(name="ScanSale", sale_price_gs=20000, sku="SCAN-002")
        s.add(p)
        s.commit()
        pid = p.id

    resp = client.post(
        "/ventas/nueva",
        data={"sku": "SCAN-002", "qty": "1", "discount_gs": "0"},
        follow_redirects=False,
    )
    # 303 redirect on success
    assert resp.status_code == 303, f"Got {resp.status_code}: {resp.text[:200]}"
    # Verify the sale was created with the right product
    from app.rms.models import Sale
    with session_factory() as s2:
        sales = s2.query(Sale).all()
        assert any(sale.product_id == pid for sale in sales)
