"""P3 delivery batch: customer addresses + pedido delivery fields + favorites.

- POST /pedidos/nuevo persists address_text, delivery window, invoice_ruc/name
- save_address=1 creates a CustomerAddress (first = default) + preferred_zone
- GET /pedidos/api/customer/{id}/addresses returns the address book
- Product.is_favorite filter on /ventas quick-sale grid
- migration 069: columns exist (covered by conftest's migrate-on-startup)
"""

from __future__ import annotations

import pytest

from tests.factories import make_customer, make_product


# ── POST /pedidos/nuevo with delivery fields ────────────────────────────

def test_pedido_create_persists_address_window_ruc(client, session_factory):
    with session_factory() as s:
        p = make_product(s, name="ProdDlvUX", sale_price_gs=15000)
        s.commit()
        pid = p.id
    r = client.post(
        "/pedidos/nuevo",
        data={
            "customer_name": "Cliente Delivery UX",
            "customer_phone": "0981112222",
            "promised_date": "2030-01-15",
            "promised_time": "15:00",
            "line_product_id": str(pid),
            "line_qty": "2",
            "line_unit_price_gs": "15000",
            "delivery_zone_id": "",
            "address_text": "Av. Mcal. López 123, casi Santíssima",
            "delivery_window_start": "14:00",
            "delivery_window_end": "17:00",
            "invoice_ruc": "80012345-6",
            "invoice_name": "Cliente Delivery UX S.A.",
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303), r.status_code
    from app.rms.models import Pedido
    with session_factory() as s:
        ped = s.query(Pedido).order_by(Pedido.id.desc()).first()
        assert ped is not None
        assert ped.address_text == "Av. Mcal. López 123, casi Santíssima"
        assert ped.delivery_window_start == "14:00"
        assert ped.delivery_window_end == "17:00"
        assert ped.invoice_ruc == "80012345-6"
        assert ped.invoice_name == "Cliente Delivery UX S.A."


def test_pedido_save_address_creates_customer_address(client, session_factory):
    with session_factory() as s:
        p = make_product(s, name="ProdDlvUX2", sale_price_gs=12000)
        s.commit()
        pid = p.id
    r = client.post(
        "/pedidos/nuevo",
        data={
            "customer_name": "Cliente AddrBook UX",
            "promised_date": "2030-01-16",
            "line_product_id": str(pid),
            "line_qty": "1",
            "line_unit_price_gs": "12000",
            "address_text": "Casa 1, Barrio Jara",
            "save_address": "1",
            "address_label": "casa",
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    from app.rms.models import CustomerAddress, Customer
    with session_factory() as s:
        cust = s.query(Customer).filter_by(name="Cliente AddrBook UX").one()
        addrs = s.query(CustomerAddress).filter_by(customer_id=cust.id).all()
        assert len(addrs) == 1
        assert addrs[0].label == "casa"
        assert addrs[0].address_text == "Casa 1, Barrio Jara"
        assert addrs[0].is_default is True


def test_pedido_save_address_requires_customer_and_text(client, session_factory):
    """save_address without a customer or empty address = no row, no crash."""
    with session_factory() as s:
        p = make_product(s, name="ProdDlvUX3", sale_price_gs=10000)
        s.commit()
        pid = p.id
    r = client.post(
        "/pedidos/nuevo",
        data={
            "promised_date": "2030-01-17",
            "line_product_id": str(pid),
            "line_qty": "1",
            "line_unit_price_gs": "10000",
            "save_address": "1",  # but no customer_name and no address_text
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    from app.rms.models import CustomerAddress
    with session_factory() as s:
        assert s.query(CustomerAddress).count() == 0


# ── Addresses API ────────────────────────────────────────────────────────

def test_customer_addresses_api_roundtrip(client, session_factory):
    from app.rms.models import CustomerAddress
    with session_factory() as s:
        cust = make_customer(s, name="AddrApi UX", phone="0981")
        s.flush()
        s.add(CustomerAddress(customer_id=cust.id, label="oficina",
                              address_text="Edificio Torre, piso 3"))
        s.add(CustomerAddress(customer_id=cust.id, label="casa",
                              address_text="Barrio Obrero", is_default=True))
        s.commit()
        cid = cust.id
    r = client.get(f"/pedidos/api/customer/{cid}/addresses")
    assert r.status_code == 200
    data = r.json()
    assert data["preferred_zone_id"] is None
    labels = [a["label"] for a in data["addresses"]]
    assert labels[0] == "casa"  # default first
    assert set(labels) == {"casa", "oficina"}
    # unknown customer → empty, not 404 (form handles gracefully)
    r2 = client.get("/pedidos/api/customer/999999/addresses")
    assert r2.status_code == 200
    assert r2.json()["addresses"] == []


# ── Product favorites ────────────────────────────────────────────────────

def test_product_is_favorite_filter(client, session_factory):
    with session_factory() as s:
        fav = make_product(s, name="FavPan UX", sale_price_gs=8000)
        fav.is_favorite = True
        plain = make_product(s, name="FavCafe UX", sale_price_gs=12000)
        s.commit()
    r = client.get("/ventas?fav=1")
    assert r.status_code == 200
    body = r.text
    assert "FavPan UX" in body
    assert "FavCafe UX" not in body
