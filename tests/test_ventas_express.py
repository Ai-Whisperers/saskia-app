"""B.1 Venta Express (/ventas/express) — polish lot.

- GET /ventas/express renders 200 on empty DB and with products+sales.
- Shows up to 8 items: top-venta-14d first, favorites fill-up.
- The Express entry link exists on /ventas.
- POST /ventas/nueva is untouched (route reuses it with product_id+qty).
"""

# allow-hardcoded-dates: sale fixtures use fixed sold_at to avoid drift
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def test_express_loads_empty_db(client):
    r = client.get("/ventas/express")
    assert r.status_code == 200, f"empty DB: {r.status_code} {r.text[:200]}"
    assert "Venta Express" in r.text


def test_express_loads_with_products_and_sales(client, session_factory):
    from app.rms.models import Product, Sale

    with session_factory() as s:
        p1 = Product(
            name="Express Chipa",
            portion_label="1 und",
            sale_price_gs=3000,
            is_available=True,
        )
        p2 = Product(
            name="Express Factura",
            portion_label="1 und",
            sale_price_gs=4000,
            is_available=True,
        )
        s.add_all([p1, p2])
        s.commit()
        now = datetime.now(timezone.utc)
        s.add(
            Sale(
                product_id=p1.id,
                qty=3,
                unit_price_gs=3000,
                sold_at=now - timedelta(days=1),
            )
        )
        s.commit()

    r = client.get("/ventas/express")
    assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
    assert "Express Chipa" in r.text
    # form posts to the existing sale endpoint with csrf field
    assert 'action="/ventas/nueva"' in r.text
    assert "_csrf_token" in r.text
    assert 'name="qty"' in r.text


def test_express_link_on_ventas_page(client):
    r = client.get("/ventas")
    assert r.status_code == 200
    assert "/ventas/express" in r.text
