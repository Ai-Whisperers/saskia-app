"""Tests for the new /clientes/nuevo GET + POST endpoints.

Closes Phase-14 TODO #nav:217 — previously the topbar "+ Cliente" link
went to /clientes (the listing) because /clientes/nuevo did not exist.
"""
from __future__ import annotations

import pytest

from app.rms.models import Customer

pytestmark = pytest.mark.crud


def test_clientes_nuevo_get_renders_form(authed_client):
    """GET /clientes/nuevo must return 200 with the form."""
    r = authed_client.get("/clientes/nuevo")
    assert r.status_code == 200
    assert "Nuevo cliente" in r.text
    # Form fields the operator sees:
    assert 'name="name"' in r.text
    assert 'name="phone"' in r.text
    assert 'name="email"' in r.text
    assert 'name="cedula"' in r.text
    # Submit button present:
    assert "Crear cliente" in r.text or "type=\"submit\"" in r.text
    # Breadcrumb back to /clientes:
    assert "/clientes" in r.text


def test_clientes_nuevo_post_creates_customer_and_redirects(
    authed_client, session_factory
):
    """POST /clientes/nuevo must create row + 303 to /clientes/{id}."""
    # Real-looking Paraguayan phone that passes validate_phone regex.
    payload = {
        "name": "Nuevo Cliente Test",
        "phone": "+595981234567",
        "email": "nuevo+test@example.com",
        "cedula": "1234567",
        "notes": "Created via /nuevo",
    }
    r = authed_client.post("/clientes/nuevo", data=payload, follow_redirects=False)
    assert r.status_code == 303, r.text[:400]
    # Redirect points to /clientes/{id}
    loc = r.headers.get("location", "")
    assert loc.startswith("/clientes/"), loc
    assert loc != "/clientes"  # must be a specific id
    new_id = int(loc.split("/")[-1])
    # Row exists with expected fields.
    with session_factory() as s:
        c = s.get(Customer, new_id)
        assert c is not None
        assert c.name == "Nuevo Cliente Test"
        assert c.phone == "+595981234567"


def test_clientes_nuevo_post_rejects_empty_name(authed_client):
    """POST with empty name must 422 and re-render form with error."""
    r = authed_client.post(
        "/clientes/nuevo",
        data={"name": "", "phone": "+595981234568"},
        follow_redirects=False,
    )
    assert r.status_code == 422
    # Re-rendered form preserves user's phone so they don't retype.
    assert "+595981234568" in r.text
    # Form contains the required field again.
    assert 'name="name"' in r.text


def test_clientes_nuevo_post_rejects_invalid_email(authed_client):
    """POST with bad email must 422."""
    r = authed_client.post(
        "/clientes/nuevo",
        data={"name": "Test", "email": "not-an-email"},
        follow_redirects=False,
    )
    assert r.status_code == 422
    # User's input preserved in the re-render.
    assert "not-an-email" in r.text


def test_clientes_nuevo_phone_match_updates_existing(
    authed_client, session_factory
):
    """If phone matches an existing customer, that row is updated (not duplicated)."""
    # Seed an existing customer.
    with session_factory() as s:
        existing = Customer(
            name="Old Name", phone="+595981234567",
            email="old@example.com",
        )
        s.add(existing)
        s.commit()
        s.refresh(existing)
        existing_id = existing.id

    r = authed_client.post(
        "/clientes/nuevo",
        data={
            "name": "New Name",
            "phone": "+595981234567",  # same phone
            "email": "new@example.com",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    # Same id — updated, not duplicated.
    assert f"/clientes/{existing_id}" in r.headers.get("location", "")
    with session_factory() as s:
        all_cust = s.query(Customer).filter(
            Customer.phone == "+595981234567"
        ).all()
        assert len(all_cust) == 1
        assert all_cust[0].id == existing_id
        # Name was updated.
        assert all_cust[0].name == "New Name"


def test_clientes_nuevo_idempotent_duplicate_post(
    authed_client, session_factory
):
    """Posting twice with same data → still one customer."""
    payload = {"name": "Idem Test", "phone": "+595981234577"}
    r1 = authed_client.post("/clientes/nuevo", data=payload, follow_redirects=False)
    assert r1.status_code == 303
    r2 = authed_client.post("/clientes/nuevo", data=payload, follow_redirects=False)
    assert r2.status_code == 303
    with session_factory() as s:
        n = s.query(Customer).filter(Customer.phone == "+595981234577").count()
        assert n == 1


def test_topbar_create_action_points_to_clientes_nuevo(authed_client):
    """The '+ Cliente' nav entry must point to /clientes/nuevo, not /clientes."""
    r = authed_client.get("/clientes")
    assert r.status_code == 200
    # The nav rendering: look for the new URL somewhere in the topbar.
    # We check by looking for any href to /clientes/nuevo in the page.
    assert "/clientes/nuevo" in r.text