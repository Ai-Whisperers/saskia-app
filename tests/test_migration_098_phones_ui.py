"""Phase 16 (2026-10-02): prefill exposes available_phones + the customer
detail + edit pages render the new phones fieldset correctly."""
from __future__ import annotations

import pytest
from sqlalchemy import text


# ── prefill ──────────────────────────────────────────────────────────


def test_prefill_exposes_available_phones(qseed, session_factory):
    """When a customer has multiple phones, compute_customer_defaults()
    lists them in available_phones (default first)."""
    from app.services.customer_contacts import add_phone
    from app.services.customer_prefill import compute_customer_defaults
    from app.rms.models import Customer

    qseed("with_kyrian_full")
    with session_factory() as s:
        kyrian = s.query(Customer).filter_by(name="kyrian weiss").one()
        # Add two phones — one default, one WhatsApp
        add_phone(
            s, kyrian.id, "+595 981 000 000", kind="mobile",
            label="Personal", is_default=True,
        )
        add_phone(
            s, kyrian.id, "+595 981 999 000", kind="whatsapp",
            label="WhatsApp", is_default=False,
        )
        s.commit()

        prefill = compute_customer_defaults(s, kyrian.id)
        assert hasattr(prefill, "available_phones")
        assert len(prefill.available_phones) >= 2
        # Default comes first
        first = prefill.available_phones[0]
        assert first["is_default"] is True
        # And prefill.phone is the default's value
        assert prefill.phone == first["phone"]
        # Second one is WhatsApp
        kinds = [p["kind"] for p in prefill.available_phones]
        assert "whatsapp" in kinds


def test_prefill_phones_empty_when_no_phones(session_factory):
    """If the customer has zero phones, available_phones is empty and
    prefill.phone is whatever Customer.phone is (legacy column)."""
    from app.services.customer_prefill import compute_customer_defaults
    from app.rms.models import Customer

    with session_factory() as s:
        s.add(Customer(id=1, name="No Phone", phone="+595 981 000 000",
                       loyalty_points=0))
        s.commit()
        prefill = compute_customer_defaults(s, 1)
        assert prefill.available_phones == []
        # Legacy column still drives the form
        assert prefill.phone == "+595 981 000 000"


def test_prefill_phones_serialization(session_factory):
    """customer_defaults_as_json includes the available_phones key."""
    from app.services.customer_contacts import add_phone
    from app.services.customer_prefill import customer_defaults_as_json
    from app.rms.models import Customer

    with session_factory() as s:
        s.add(Customer(id=1, name="Test", phone="+595 981 111 111",
                       loyalty_points=0))
        s.commit()
        add_phone(s, 1, "+595 981 111 111", kind="mobile", label="Personal",
                  is_default=True)
        add_phone(s, 1, "+595 981 222 222", kind="work", label="Oficina",
                  is_default=False)
        s.commit()
        js = customer_defaults_as_json(s, 1)
        assert "available_phones" in js
        assert isinstance(js["available_phones"], list)
        assert len(js["available_phones"]) == 2


# ── detail page ──────────────────────────────────────────────────────


def test_cliente_detalle_shows_all_phones(client, session_factory):
    """GET /clientes/{id} renders every active phone (default first)."""
    from app.rms.models import Customer
    from app.services.customer_contacts import add_phone

    with session_factory() as s:
        s.add(Customer(id=1, name="Multi", phone="+595 981 111 111",
                       loyalty_points=0))
        s.commit()
        add_phone(s, 1, "+595 981 111 111", kind="mobile", label="Personal",
                  is_default=True)
        add_phone(s, 1, "+595 981 222 222", kind="whatsapp", label="WhatsApp",
                  is_default=False)
        add_phone(s, 1, "+595 981 333 333", kind="work", label="Oficina",
                  is_default=False)
        s.commit()

    r = client.get("/clientes/1")
    assert r.status_code == 200
    html = r.text
    assert "+595 981 111 111" in html
    assert "+595 981 222 222" in html
    assert "+595 981 333 333" in html
    assert "Teléfonos" in html  # plural heading
    assert "predet." in html  # default badge


# ── edit page ────────────────────────────────────────────────────────


def test_cliente_editar_shows_phones_panel(client, session_factory):
    """GET /clientes/{id}/editar shows the Phones fieldset with rows."""
    from app.rms.models import Customer
    from app.services.customer_contacts import add_phone

    with session_factory() as s:
        s.add(Customer(id=1, name="Edit", phone="+595 981 000 000",
                       loyalty_points=0))
        s.commit()
        add_phone(s, 1, "+595 981 000 000", kind="mobile", label="Personal",
                  is_default=True)
        add_phone(s, 1, "+595 981 555 555", kind="whatsapp", label="WhatsApp",
                  is_default=False)
        s.commit()

    r = client.get("/clientes/1/editar")
    assert r.status_code == 200
    html = r.text
    assert "Teléfonos" in html
    assert "phone-add" in html  # the add button
    assert "phone-default" in html  # the star button for non-default
    assert "phone-del" in html  # the delete button
    assert "Personal" in html
    assert "WhatsApp" in html


def test_cliente_editar_empty_state_shows_hint(client, session_factory):
    """A customer with no phones still shows the fieldset + 'Sin teléfonos'."""
    from app.rms.models import Customer
    with session_factory() as s:
        s.add(Customer(id=1, name="NoPhones", phone=None, loyalty_points=0))
        s.commit()

    r = client.get("/clientes/1/editar")
    assert r.status_code == 200
    html = r.text
    assert "Sin teléfonos guardados" in html
    assert "+ Agregar teléfono" in html


# ── detail payload ──────────────────────────────────────────────────


def test_customer_detail_payload_includes_phones(client, session_factory):
    """The /clientes/api/{id} JSON payload exposes the phones list."""
    from app.rms.models import Customer
    from app.services.customer_contacts import add_phone

    with session_factory() as s:
        s.add(Customer(id=1, name="Api", phone="+595 981 999 999",
                       loyalty_points=0))
        s.commit()
        add_phone(s, 1, "+595 981 999 999", kind="mobile", is_default=True)
        add_phone(s, 1, "+595 981 888 888", kind="whatsapp", is_default=False)
        s.commit()

    r = client.get("/clientes/api/1")
    assert r.status_code == 200
    data = r.json()
    assert "phones" in data
    assert len(data["phones"]) == 2
    assert data["phones"][0]["is_default"] is True
    assert data["phones"][0]["kind"] == "mobile"
    assert data["phones"][1]["kind"] == "whatsapp"
