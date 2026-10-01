"""tests/test_invoice_profile_crud.py — Phase 14 (2026-10-01).

Tests for the new customer invoice-profile CRUD endpoints:
  POST /clientes/api/{customer_id}/invoice-profiles
  POST /clientes/api/{customer_id}/invoice-profiles/{pid}/default
  DELETE /clientes/api/{customer_id}/invoice-profiles/{pid}
"""
import json


def _make_customer(client, session_factory):
    """Insert a customer via ORM and return its id."""
    import uuid as _uuid
    from app.rms.models import Customer
    name = "Phase14Inv " + _uuid.uuid4().hex[:6]
    with session_factory() as s:
        c = Customer(name=name, phone="+595 981 000000")
        s.add(c)
        s.commit()
        s.refresh(c)
        return c.id


def test_create_invoice_profile_creates_default_when_first(client, session_factory):
    """First profile for a customer auto-becomes the default."""
    cid = _make_customer(client, session_factory)
    r = client.post(
        f"/clientes/api/{cid}/invoice-profiles",
        json={
            "ruc_ci": "80012345-6",
            "razon_social": "Empresa A S.A.",
            "alias": "Empresa A",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ruc_ci"] == "80012345-6"
    assert body["razon_social"] == "Empresa A S.A."
    assert body["is_default"] is True
    assert body["alias"] == "Empresa A"


def test_create_second_profile_does_not_become_default(client, session_factory):
    """Second profile stays non-default (single-default rule)."""
    cid = _make_customer(client, session_factory)
    client.post(
        f"/clientes/api/{cid}/invoice-profiles",
        json={"ruc_ci": "80011111-1", "razon_social": "First S.A.", "alias": "First"},
    )
    r = client.post(
        f"/clientes/api/{cid}/invoice-profiles",
        json={"ruc_ci": "80022222-2", "razon_social": "Second S.A.", "alias": "Second"},
    )
    assert r.status_code == 200
    assert r.json()["is_default"] is False


def test_set_default_clears_other_defaults(client, session_factory):
    """Setting a profile default clears the previous default."""
    cid = _make_customer(client, session_factory)
    r1 = client.post(
        f"/clientes/api/{cid}/invoice-profiles",
        json={"ruc_ci": "80011111-1", "razon_social": "A S.A."},
    ).json()
    r2 = client.post(
        f"/clientes/api/{cid}/invoice-profiles",
        json={"ruc_ci": "80022222-2", "razon_social": "B S.A."},
    ).json()
    # Make B the default
    rd = client.post(f"/clientes/api/{cid}/invoice-profiles/{r2['id']}/default")
    assert rd.status_code == 200
    assert rd.json()["is_default"] is True

    # Verify A is no longer the default (read back from DB)
    from app.rms.models import CustomerInvoiceProfile
    with session_factory() as s:
        a = s.get(CustomerInvoiceProfile, r1["id"])
        b = s.get(CustomerInvoiceProfile, r2["id"])
        assert a.is_default is False
        assert b.is_default is True


def test_delete_default_profile_is_rejected(client, session_factory):
    """The default profile can't be soft-deleted (operator must set
    another default first)."""
    cid = _make_customer(client, session_factory)
    r1 = client.post(
        f"/clientes/api/{cid}/invoice-profiles",
        json={"ruc_ci": "80011111-1", "razon_social": "Default S.A."},
    ).json()
    rd = client.delete(f"/clientes/api/{cid}/invoice-profiles/{r1['id']}")
    assert rd.status_code == 400
    assert rd.json()["error"] == "cannot_delete_default"


def test_delete_non_default_profile_soft_deletes(client, session_factory):
    """Soft-delete sets is_active=False; row remains queryable but
    excluded from active lists."""
    cid = _make_customer(client, session_factory)
    r1 = client.post(
        f"/clientes/api/{cid}/invoice-profiles",
        json={"ruc_ci": "80011111-1", "razon_social": "Default S.A."},
    ).json()
    r2 = client.post(
        f"/clientes/api/{cid}/invoice-profiles",
        json={"ruc_ci": "80022222-2", "razon_social": "Second S.A."},
    ).json()
    rd = client.delete(f"/clientes/api/{cid}/invoice-profiles/{r2['id']}")
    assert rd.status_code == 200

    from app.rms.models import CustomerInvoiceProfile
    with session_factory() as s:
        row = s.get(CustomerInvoiceProfile, r2["id"])
        assert row is not None
        assert row.is_active is False


def test_create_requires_ruc_and_name(client, session_factory):
    """Validation: 400 if ruc_ci or razon_social are missing."""
    cid = _make_customer(client, session_factory)
    r = client.post(
        f"/clientes/api/{cid}/invoice-profiles",
        json={"ruc_ci": "", "razon_social": "X"},
    )
    assert r.status_code == 400
    r = client.post(
        f"/clientes/api/{cid}/invoice-profiles",
        json={"ruc_ci": "X", "razon_social": ""},
    )
    assert r.status_code == 400


def test_create_404_for_unknown_customer(client, session_factory):
    """404 when the customer_id doesn't exist."""
    r = client.post(
        "/clientes/api/999999/invoice-profiles",
        json={"ruc_ci": "X", "razon_social": "Y"},
    )
    assert r.status_code == 404


def test_set_default_404_for_wrong_customer(client, session_factory):
    """Cross-customer default-set is rejected (security: profile 1
    belongs to customer A; passing customer B returns 404)."""
    cid_a = _make_customer(client, session_factory)
    cid_b = _make_customer(client, session_factory)
    prof = client.post(
        f"/clientes/api/{cid_a}/invoice-profiles",
        json={"ruc_ci": "X", "razon_social": "Y"},
    ).json()
    r = client.post(
        f"/clientes/api/{cid_b}/invoice-profiles/{prof['id']}/default"
    )
    assert r.status_code == 404