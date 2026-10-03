"""tests/test_address_set_default.py — Phase 14 (2026-10-01).

Tests for the new POST /clientes/api/{customer_id}/addresses/{address_id}/default
endpoint (the existing address_create + address_delete tests already cover
the other CRUD).
"""
import uuid as _uuid


def _make_customer(session_factory):
    from app.rms.models import Customer
    name = "Phase14Addr " + _uuid.uuid4().hex[:6]
    with session_factory() as s:
        c = Customer(name=name, phone="+595 981 000000")
        s.add(c)
        s.commit()
        s.refresh(c)
        return c.id


def _make_address(session_factory, customer_id, address_text, is_default=False):
    from app.rms.models import CustomerAddress
    with session_factory() as s:
        a = CustomerAddress(
            customer_id=customer_id,
            label="casa",
            address_text=address_text,
            is_default=is_default,
        )
        s.add(a)
        s.commit()
        s.refresh(a)
        return a.id


def _csrf_token(client):
    """Pull the CSRF token from the cliente_editar form. The conftest
    client fixture sets one when auth is bypassed."""
    cid = 1  # placeholder — caller will navigate to the right page
    r = client.get("/clientes/1/editar")
    if r.status_code != 200:
        return None
    import re
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.text)
    return m.group(1) if m else None


def test_set_default_clears_other_defaults(client, session_factory):
    """Setting an address default clears the previous default."""
    from app.rms.models import CustomerAddress
    cid = _make_customer(session_factory)
    a1 = _make_address(session_factory, cid, "Casa principal", is_default=True)
    a2 = _make_address(session_factory, cid, "Oficina")

    tok = _csrf_token(client)
    headers = {"X-CSRF-Token": tok} if tok else {}

    r = client.post(
        f"/clientes/api/{cid}/addresses/{a2}/default",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["is_default"] is True

    with session_factory() as s:
        a1_row = s.get(CustomerAddress, a1)
        a2_row = s.get(CustomerAddress, a2)
        assert a1_row.is_default is False
        assert a2_row.is_default is True


def test_set_default_404_for_unknown_address(client, session_factory):
    """Unknown address_id returns 404."""
    cid = _make_customer(session_factory)
    tok = _csrf_token(client)
    headers = {"X-CSRF-Token": tok} if tok else {}
    r = client.post(
        f"/clientes/api/{cid}/addresses/999999/default",
        headers=headers,
    )
    assert r.status_code == 404


def test_set_default_404_for_cross_customer(client, session_factory):
    """Cross-customer set-default is rejected."""
    cid_a = _make_customer(session_factory)
    cid_b = _make_customer(session_factory)
    a_a = _make_address(session_factory, cid_a, "Address A")
    tok = _csrf_token(client)
    headers = {"X-CSRF-Token": tok} if tok else {}
    r = client.post(
        f"/clientes/api/{cid_b}/addresses/{a_a}/default",
        headers=headers,
    )
    assert r.status_code == 404
