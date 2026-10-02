"""Phase 16 (2026-10-02): customer_phone migration + service.

Covers:
  - Migration 098 creates customer_phone + the backfill is idempotent
  - Service layer: add_phone (default promotion, normalization)
  - Service layer: remove_phone (soft-delete + default promotion)
  - Service layer: set_default_phone
  - Service layer: list_phones, get_default_phone
  - Service layer: keeps Customer.phone (legacy) in sync
  - Service layer: add_invoice_profile + remove + set_default
  - API endpoints via the shared `client` fixture (auth bypass via
    SASKIA_TEST_AUTH_DISABLED=1, set in conftest.py).
"""
from __future__ import annotations

import pytest
from sqlalchemy import text


# ── migration 098 ────────────────────────────────────────────────────


def test_migration_098_bumps_schema_version(session_factory):
    """Fresh DB starts at 98 (or higher)."""
    with session_factory() as s:
        v = s.execute(text("SELECT value FROM app_meta WHERE key='schema_version'")).scalar()
    assert v is not None
    assert int(v) >= 98


def test_migration_098_creates_customer_phone_table(session_factory):
    with session_factory() as s:
        bind = s.get_bind()
        from sqlalchemy import inspect
        insp = inspect(bind)
        tables = insp.get_table_names()
        assert "customer_phone" in tables
        cols = {c["name"] for c in insp.get_columns("customer_phone")}
        for required in ("id", "customer_id", "phone", "kind", "label",
                          "is_default", "is_active", "sort_order"):
            assert required in cols, f"missing column {required}"


def test_migration_098_has_indexes(session_factory):
    with session_factory() as s:
        from sqlalchemy import inspect
        insp = inspect(s.get_bind())
        idx_names = {i["name"] for i in insp.get_indexes("customer_phone")}
    assert any("customer_id" in n for n in idx_names)


def test_migration_098_backfill_is_idempotent(session_factory, app_engine):
    """Seeding a customer AFTER migrations → re-running 098 must NOT dup."""
    from app.rms.models import Customer
    from app.rms.migrations._098_customer_phone import _migration_098_customer_phone

    # Seed a customer (post-migration)
    with session_factory() as s:
        s.add(Customer(id=999, name="Backfill Test", phone="+595 981 555 111",
                       loyalty_points=0))
        s.commit()

    # Re-run migration 098 — should insert exactly one row
    with app_engine.begin() as conn:
        _migration_098_customer_phone(conn)
    with app_engine.begin() as conn:
        n = conn.execute(text(
            "SELECT COUNT(*) FROM customer_phone WHERE customer_id=999"
        )).scalar()
    assert n == 1

    # Re-run again — should still be exactly one row
    with app_engine.begin() as conn:
        _migration_098_customer_phone(conn)
    with app_engine.begin() as conn:
        n = conn.execute(text(
            "SELECT COUNT(*) FROM customer_phone WHERE customer_id=999"
        )).scalar()
    assert n == 1


def test_migration_098_skips_customer_with_no_phone(session_factory, app_engine):
    from app.rms.models import Customer
    from app.rms.migrations._098_customer_phone import _migration_098_customer_phone

    with session_factory() as s:
        s.add(Customer(id=998, name="No Phone", phone=None, loyalty_points=0))
        s.commit()

    with app_engine.begin() as conn:
        _migration_098_customer_phone(conn)
    with app_engine.begin() as conn:
        n = conn.execute(text(
            "SELECT COUNT(*) FROM customer_phone WHERE customer_id=998"
        )).scalar()
    assert n == 0


# ── service: add_phone ──────────────────────────────────────────────


def _make_customer(s, cid: int, name: str, phone: str = "+595 981 123 456"):
    from app.rms.models import Customer
    s.add(Customer(id=cid, name=name, phone=phone, loyalty_points=0))
    s.commit()


def test_add_phone_normalizes_formatting(session_factory):
    from app.services.customer_contacts import add_phone, list_phones
    with session_factory() as s:
        _make_customer(s, 1, "Test")
        row = add_phone(s, 1, " 0981-123-456 ", kind="mobile", label="Línea 2")
        s.commit()
        assert "981" in row.phone
        assert "123" in row.phone
        assert "456" in row.phone
        assert row.kind == "mobile"
        assert row.label == "Línea 2"
        assert row.is_active is True


def test_add_phone_rejects_empty(session_factory):
    from app.services.customer_contacts import add_phone
    with session_factory() as s:
        _make_customer(s, 1, "Test")
        with pytest.raises(ValueError, match="vacío"):
            add_phone(s, 1, "  ", kind="mobile")


def test_add_phone_rejects_invalid_kind(session_factory):
    from app.services.customer_contacts import add_phone
    with session_factory() as s:
        _make_customer(s, 1, "Test")
        with pytest.raises(ValueError, match="kind inválido"):
            add_phone(s, 1, "+595 981 999 999", kind="telepathy")


def test_add_phone_demotes_prior_default(session_factory):
    from app.services.customer_contacts import add_phone, list_phones
    with session_factory() as s:
        _make_customer(s, 1, "Test")
        add_phone(s, 1, "+595 981 111 111", is_default=True)
        s.commit()
        new_row = add_phone(s, 1, "+595 981 222 222", kind="whatsapp",
                            label="WhatsApp", is_default=True)
        s.commit()
        rows = list_phones(s, 1)
        defaults = [r for r in rows if r.is_default]
        assert len(defaults) == 1
        assert defaults[0].id == new_row.id


def test_add_phone_keeps_legacy_phone_in_sync(session_factory):
    from app.services.customer_contacts import add_phone
    from app.rms.models import Customer
    with session_factory() as s:
        _make_customer(s, 1, "Test", phone="+595 981 000 000")
        new_row = add_phone(s, 1, "+595 981 999 999", kind="whatsapp",
                            is_default=True)
        s.commit()
        cust = s.get(Customer, 1)
        assert cust.phone == new_row.phone


# ── service: remove_phone ──────────────────────────────────────────


def test_remove_phone_soft_deletes(session_factory):
    from app.services.customer_contacts import add_phone, remove_phone, list_phones
    with session_factory() as s:
        _make_customer(s, 1, "Test")
        row = add_phone(s, 1, "+595 981 999 999", kind="work", label="Oficina")
        s.commit()
        assert remove_phone(s, 1, row.id) is True
        s.commit()
        listed = list_phones(s, 1)
        by_id = {p.id: p for p in listed}
        assert by_id[row.id].is_active is False


def test_remove_phone_returns_false_for_wrong_customer(session_factory):
    from app.services.customer_contacts import remove_phone
    with session_factory() as s:
        _make_customer(s, 1, "Test")
        pid = s.execute(text("SELECT id FROM customer_phone WHERE customer_id=1")).scalar()
        assert remove_phone(s, 999, pid) is False


def test_remove_default_promotes_next_active(session_factory):
    from app.services.customer_contacts import (
        add_phone, remove_phone, get_default_phone,
    )
    with session_factory() as s:
        _make_customer(s, 1, "Test")
        # First: add a default phone
        add_phone(s, 1, "+595 981 000 000", kind="mobile", is_default=True)
        s.commit()
        # Then: add a non-default phone
        second = add_phone(s, 1, "+595 981 999 999", kind="whatsapp",
                           label="WhatsApp", is_default=False)
        s.commit()
        default_id = s.execute(
            text("SELECT id FROM customer_phone WHERE customer_id=1 AND is_default=1")
        ).scalar()
        assert default_id is not None
        remove_phone(s, 1, default_id)
        s.commit()
        new_default = get_default_phone(s, 1)
        assert new_default is not None
        assert new_default.id == second.id


# ── service: set_default_phone ────────────────────────────────────


def test_set_default_phone_demotes_others(session_factory):
    from app.services.customer_contacts import (
        add_phone, set_default_phone, list_phones,
    )
    with session_factory() as s:
        _make_customer(s, 1, "Test")
        other = add_phone(s, 1, "+595 981 999 999", kind="work", label="Oficina")
        s.commit()
        set_default_phone(s, 1, other.id)
        s.commit()
        rows = list_phones(s, 1)
        defaults = [r for r in rows if r.is_default]
        assert len(defaults) == 1
        assert defaults[0].id == other.id


# ── service: invoice profile ──────────────────────────────────────


def test_add_invoice_profile_creates_row(session_factory):
    from app.services.customer_contacts import add_invoice_profile
    with session_factory() as s:
        _make_customer(s, 1, "Test")
        prof = add_invoice_profile(
            s, 1,
            alias="Empresa",
            ruc_ci="80012345-6",
            razon_social="Mi Empresa S.A.",
            tipo_documento="RUC",
            tipo_operacion="B2B",
            is_default=True,
        )
        s.commit()
        assert prof.id is not None
        assert prof.ruc_ci == "80012345-6"
        assert prof.tipo_documento == "RUC"
        assert prof.tipo_operacion == "B2B"


def test_add_invoice_profile_rejects_empty_ruc(session_factory):
    from app.services.customer_contacts import add_invoice_profile
    with session_factory() as s:
        _make_customer(s, 1, "Test")
        with pytest.raises(ValueError, match="ruc_ci"):
            add_invoice_profile(s, 1, alias="x", ruc_ci="  ", razon_social="Y")


def test_add_invoice_profile_rejects_invalid_tipo_documento(session_factory):
    from app.services.customer_contacts import add_invoice_profile
    with session_factory() as s:
        _make_customer(s, 1, "Test")
        with pytest.raises(ValueError, match="tipo_documento"):
            add_invoice_profile(
                s, 1, alias="x", ruc_ci="123", razon_social="y",
                tipo_documento="FOO",
            )


def test_add_invoice_profile_keeps_legacy_ruc_in_sync(session_factory):
    from app.services.customer_contacts import add_invoice_profile
    from app.rms.models import Customer
    with session_factory() as s:
        _make_customer(s, 1, "Test")
        prof = add_invoice_profile(
            s, 1,
            alias="Personal",
            ruc_ci="1234567",
            razon_social="Test",
            is_default=True,
        )
        s.commit()
        cust = s.get(Customer, 1)
        assert cust.invoice_ruc == prof.ruc_ci
        assert cust.invoice_name == prof.razon_social


def test_remove_invoice_profile_promotes_next(session_factory):
    from app.services.customer_contacts import (
        add_invoice_profile, remove_invoice_profile, list_invoice_profiles,
    )
    with session_factory() as s:
        _make_customer(s, 1, "Test")
        first = add_invoice_profile(
            s, 1, alias="P1", ruc_ci="111", razon_social="R1", is_default=True,
        )
        second = add_invoice_profile(
            s, 1, alias="P2", ruc_ci="222", razon_social="R2", is_default=False,
        )
        s.commit()
        remove_invoice_profile(s, 1, first.id)
        s.commit()
        rows = list_invoice_profiles(s, 1)
        active = [p for p in rows if p.is_active]
        defaults = [p for p in active if p.is_default]
        assert len(defaults) == 1
        assert defaults[0].id == second.id


# ── API endpoints ──────────────────────────────────────────────────


def test_api_phones_list_returns_seeded(client, session_factory):
    """A customer with one phone returns that phone in the list."""
    from app.rms.models import Customer
    from app.services.customer_contacts import add_phone
    with session_factory() as s:
        s.add(Customer(id=1, name="API Test", phone="+595 981 123 456",
                       loyalty_points=0))
        s.commit()
        from app.services.customer_contacts import add_phone
        add_phone(s, 1, "+595 981 123 456", kind="mobile", label="Personal",
                  is_default=True)
        s.commit()

        add_phone(s, 1, "+595 981 123 456", kind="mobile", label="Personal",
                  is_default=True)
        s.commit()

    r = client.get("/clientes/api/1/phones")
    assert r.status_code == 200
    data = r.json()
    assert "phones" in data
    assert len(data["phones"]) >= 1
    assert data["default_phone_id"] is not None
    assert data["legacy_phone"] == "+595 981 123 456"


def test_api_phones_list_backfilled_via_migration(client, app_engine, session_factory):
    """Re-running migration 098 on a DB with a phone-bearing customer
    inserts the backfill row, and the API returns it."""
    from app.rms.models import Customer
    from app.rms.migrations._098_customer_phone import _migration_098_customer_phone

    with session_factory() as s:
        s.add(Customer(id=1, name="Backfilled", phone="+595 981 111 222",
                       loyalty_points=0))
        s.commit()
    with app_engine.begin() as conn:
        _migration_098_customer_phone(conn)

    r = client.get("/clientes/api/1/phones")
    assert r.status_code == 200
    data = r.json()
    assert len(data["phones"]) == 1
    assert data["phones"][0]["phone"] == "+595 981 111 222"


def test_api_phones_add_then_list(client, session_factory):
    from app.rms.models import Customer
    with session_factory() as s:
        s.add(Customer(id=1, name="API Test", phone="+595 981 123 456",
                       loyalty_points=0))
        s.commit()
        from app.services.customer_contacts import add_phone
        add_phone(s, 1, "+595 981 123 456", kind="mobile", label="Personal",
                  is_default=True)
        s.commit()


    r = client.post(
        "/clientes/api/1/phones",
        json={"phone": "0981-999-888", "kind": "whatsapp", "label": "WhatsApp"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["phone"]["kind"] == "whatsapp"
    assert body["phone"]["is_default"] is False

    r2 = client.get("/clientes/api/1/phones")
    phones = r2.json()["phones"]
    assert len(phones) == 2


def test_api_phones_add_default_demotes_prior(client, session_factory):
    from app.rms.models import Customer
    with session_factory() as s:
        s.add(Customer(id=1, name="API Test", phone="+595 981 123 456",
                       loyalty_points=0))
        s.commit()
        from app.services.customer_contacts import add_phone
        add_phone(s, 1, "+595 981 123 456", kind="mobile", label="Personal",
                  is_default=True)
        s.commit()


    r = client.post(
        "/clientes/api/1/phones",
        json={"phone": "+595 981 999 999", "kind": "mobile", "is_default": True},
    )
    assert r.status_code == 200, r.text
    r2 = client.get("/clientes/api/1/phones")
    phones = r2.json()["phones"]
    defaults = [p for p in phones if p["is_default"]]
    assert len(defaults) == 1
    assert "999 999" in defaults[0]["phone"]


def test_api_phones_add_rejects_empty(client, session_factory):
    from app.rms.models import Customer
    with session_factory() as s:
        s.add(Customer(id=1, name="API Test", phone="+595 981 123 456",
                       loyalty_points=0))
        s.commit()
        from app.services.customer_contacts import add_phone
        add_phone(s, 1, "+595 981 123 456", kind="mobile", label="Personal",
                  is_default=True)
        s.commit()

    r = client.post("/clientes/api/1/phones", json={"phone": ""})
    assert r.status_code == 400
    assert r.json()["error"] == "phone_required"


def test_api_phones_add_rejects_invalid_kind(client, session_factory):
    from app.rms.models import Customer
    with session_factory() as s:
        s.add(Customer(id=1, name="API Test", phone="+595 981 123 456",
                       loyalty_points=0))
        s.commit()
        from app.services.customer_contacts import add_phone
        add_phone(s, 1, "+595 981 123 456", kind="mobile", label="Personal",
                  is_default=True)
        s.commit()

    r = client.post(
        "/clientes/api/1/phones",
        json={"phone": "+595 981 123", "kind": "telepathy"},
    )
    assert r.status_code == 400
    assert "kind inválido" in r.json()["error"]


def test_api_phones_set_default(client, session_factory):
    from app.rms.models import Customer
    with session_factory() as s:
        s.add(Customer(id=1, name="API Test", phone="+595 981 123 456",
                       loyalty_points=0))
        s.commit()
        from app.services.customer_contacts import add_phone
        add_phone(s, 1, "+595 981 123 456", kind="mobile", label="Personal",
                  is_default=True)
        s.commit()

    r = client.post(
        "/clientes/api/1/phones",
        json={"phone": "0981-999-777", "kind": "work", "label": "Oficina"},
    )
    new_id = r.json()["phone"]["id"]
    r2 = client.post(f"/clientes/api/1/phones/{new_id}/default")
    assert r2.status_code == 200
    r3 = client.get("/clientes/api/1/phones")
    defaults = [p for p in r3.json()["phones"] if p["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] == new_id


def test_api_phones_delete(client, session_factory):
    from app.rms.models import Customer
    with session_factory() as s:
        s.add(Customer(id=1, name="API Test", phone="+595 981 123 456",
                       loyalty_points=0))
        s.commit()
        from app.services.customer_contacts import add_phone
        add_phone(s, 1, "+595 981 123 456", kind="mobile", label="Personal",
                  is_default=True)
        s.commit()

    r = client.post(
        "/clientes/api/1/phones",
        json={"phone": "0981-999-666", "kind": "home", "label": "Casa"},
    )
    pid = r.json()["phone"]["id"]
    r2 = client.delete(f"/clientes/api/1/phones/{pid}")
    assert r2.status_code == 200
    r3 = client.get("/clientes/api/1/phones")
    by_id = {p["id"]: p for p in r3.json()["phones"]}
    assert by_id[pid]["is_active"] is False


def test_api_phones_list_404_for_missing_customer(client):
    r = client.get("/clientes/api/999/phones")
    assert r.status_code == 404


def test_api_phones_add_form_encoded(client, session_factory):
    """Form-encoded POST also works (legacy callers)."""
    from app.rms.models import Customer
    with session_factory() as s:
        s.add(Customer(id=1, name="API Test", phone="+595 981 123 456",
                       loyalty_points=0))
        s.commit()
        from app.services.customer_contacts import add_phone
        add_phone(s, 1, "+595 981 123 456", kind="mobile", label="Personal",
                  is_default=True)
        s.commit()

    r = client.post(
        "/clientes/api/1/phones",
        data={"phone": "+595 981 555 444", "kind": "work"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["phone"]["kind"] == "work"
