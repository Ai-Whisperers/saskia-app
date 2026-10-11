"""tests/test_customers_routes.py — SASKIA plan 1.

The customers router (app/routers/customers.py, prefix=/clientes) has
20 routes; existing tests cover the business logic but not these
specific routes. This file adds route smoke tests for the top 8.

Per docs/plans/2026-10-11-plan-1-untested-routers.md.
"""

from __future__ import annotations

import pytest


def test_clientes_list_returns_200(authed_client):
    """GET /clientes → 200 (list page)."""
    r = authed_client.get("/clientes")
    assert r.status_code == 200
    body = r.text.lower()
    assert "cliente" in body or "customer" in body


def test_clientes_new_form_returns_200(authed_client):
    """GET /clientes/nuevo → 200 (create form)."""
    r = authed_client.get("/clientes/nuevo")
    assert r.status_code == 200


def test_clientes_new_post_creates(authed_client, session_factory):
    """POST /clientes/nuevo → 303 redirect + customer row in DB."""
    from tests.factories import _uniq
    name = _uniq("Customer")
    r = authed_client.post(
        "/clientes/nuevo",
        data={"name": name, "phone": "0981123456", "email": "test@example.com"},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text[:300]
    # Verify the customer was created.
    from app.rms.models import Customer
    s = session_factory()
    try:
        c = s.query(Customer).filter(Customer.name == name).first()
        assert c is not None
        assert c.phone == "0981123456"
    finally:
        s.close()


def test_clientes_duplicados_returns_200(authed_client):
    """GET /clientes/duplicados → 200 (duplicate finder)."""
    r = authed_client.get("/clientes/duplicados")
    assert r.status_code == 200


def test_clientes_detail_returns_200(authed_client, session_factory):
    """GET /clientes/{id} → 200 (customer detail)."""
    from tests.factories import make_customer
    s = session_factory()
    try:
        c = make_customer(s, name="Detail Test Customer")
        s.commit()
        cid = c.id
    finally:
        s.close()

    r = authed_client.get(f"/clientes/{cid}")
    assert r.status_code == 200
    assert "Detail Test Customer" in r.text


def test_clientes_edit_form_returns_200(authed_client, session_factory):
    """GET /clientes/{id}/editar → 200 (edit form)."""
    from tests.factories import make_customer
    s = session_factory()
    try:
        c = make_customer(s, name="Edit Test Customer")
        s.commit()
        cid = c.id
    finally:
        s.close()

    r = authed_client.get(f"/clientes/{cid}/editar")
    assert r.status_code == 200


def test_clientes_edit_post_updates(authed_client, session_factory):
    """POST /clientes/{id}/editar → 303 + customer name updated."""
    from tests.factories import make_customer, _uniq
    s = session_factory()
    try:
        c = make_customer(s, name="Before Edit")
        s.commit()
        cid = c.id
    finally:
        s.close()

    new_name = _uniq("After Edit")
    r = authed_client.post(
        f"/clientes/{cid}/editar",
        data={"name": new_name, "phone": "0981999888"},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text[:300]

    from app.rms.models import Customer
    s = session_factory()
    try:
        c = s.get(Customer, cid)
        assert c.name == new_name
    finally:
        s.close()


def test_clientes_api_get_returns_json(authed_client, session_factory):
    """GET /clientes/api/{id} → 200 JSON."""
    from tests.factories import make_customer
    s = session_factory()
    try:
        c = make_customer(s, name="API Test Customer")
        s.commit()
        cid = c.id
    finally:
        s.close()

    r = authed_client.get(f"/clientes/api/{cid}")
    assert r.status_code == 200
    import json
    data = json.loads(r.text)
    assert data["name"] == "API Test Customer"
