"""tests/test_sales_overhaul.py — Phase 5 sales form features."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select


def test_sale_accepts_payment_method(session_factory):
    """apply_sale with payment_method persists it."""
    from app.rms.costing import apply_sale
    from app.rms.models import Product, Sale

    with session_factory() as s:
        p = Product(name="Test P", sale_price_gs=10000, recipe_id=None)
        s.add(p)
        s.flush()
        apply_sale(
            s, product_id=p.id, qty=1, sold_at=datetime.utcnow(),
            payment_method="cash",
        )
        s.commit()

    with session_factory() as s:
        sale = s.execute(select(Sale).where(Sale.product_id == p.id)).scalar_one()
        assert sale.payment_method == "cash"


def test_sale_accepts_discount(session_factory):
    """apply_sale with discount_gs persists the discount."""
    from app.rms.costing import apply_sale
    from app.rms.models import Product, Sale

    with session_factory() as s:
        p = Product(name="Test D", sale_price_gs=10000, recipe_id=None)
        s.add(p)
        s.flush()
        apply_sale(
            s, product_id=p.id, qty=1, sold_at=datetime.utcnow(),
            discount_gs=500,
        )
        s.commit()

    with session_factory() as s:
        sale = s.execute(select(Sale).where(Sale.product_id == p.id)).scalar_one()
        assert sale.discount_gs == 500


def test_ventas_page_has_quick_sell_section(client):
    """/ventas shows quick-sell section when there's sale history."""
    resp = client.get("/ventas")
    assert resp.status_code == 200
    # Even with no history the section shouldn't 500
    assert "Nueva venta" in resp.text


def test_ventas_page_has_payment_method_field(client):
    """Ventas form must include payment_method + discount_gs + customer_phone."""
    resp = client.get("/ventas")
    assert resp.status_code == 200
    body = resp.text
    for field in ["payment_method", "discount_gs", "customer_phone"]:
        assert field in body, f"Missing field {field} in ventas form"
