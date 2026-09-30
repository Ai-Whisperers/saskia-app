"""Regression: /clientes/{id} 500 TypeError (naive vs aware datetime, ref 9da40358ea00)."""
from datetime import datetime, timezone

from tests.factories import make_customer, make_product


def test_cliente_detalle_badge_with_naive_last_sale(client, session_factory):
    """SQLite returns naive sold_at; the old template subtracted it from an
    aware now() -> TypeError 500. Must render 200 with a tier badge."""
    with session_factory() as s:
        c = make_customer(s, name="BadgeNaive UX", phone="0982")
        s.flush()
        p = make_product(s, name="BadgeProd UX")
# allow-hardcoded-dates: fixed instants required for deterministic TZ assertions
        s.flush()
        from app.rms.models import Sale
        # naive sold_at — exactly what SQLite hands back on prod
        s.add(Sale(product_id=p.id, customer_id=c.id, qty=1,
                   unit_price_gs=1000, sold_at=datetime(2026, 9, 1, 12, 0)))
        s.commit()
        cid = c.id
    r = client.get(f"/clientes/{cid}")
    assert r.status_code == 200, r.status_code
    assert ("Inactivo" in r.text or "Frecuente" in r.text or "Nuevo" in r.text)


def test_cliente_detalle_no_sales_yet(client, session_factory):
    with session_factory() as s:
        c = make_customer(s, name="BadgeEmpty UX")
        s.commit()
        cid = c.id
    r = client.get(f"/clientes/{cid}")
    assert r.status_code == 200
