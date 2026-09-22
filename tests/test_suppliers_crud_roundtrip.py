"""Suppliers CRUD roundtrip tests."""
from __future__ import annotations

import pytest
from app.rms.models import Supplier


def test_suppliers_page_loads(authed_client):
    """GET /suppliers must return 200."""
    r = authed_client.get("/suppliers")
    assert r.status_code == 200


def test_suppliers_nuevo_form_loads(authed_client):
    """GET /suppliers/nuevo must return 200."""
    r = authed_client.get("/suppliers/nuevo")
    assert r.status_code == 200


def test_supplier_create_then_delete(authed_client, session_factory):
    """Create supplier via ORM, then DELETE via POST. Must work without 500."""
    from app.rms.models import Supplier

    with session_factory() as s:
        sup = Supplier(
            name="CRUD Supplier XYZ",
            phone="+595991234567",
            email="supplier@example.com",
            is_active=True,
        )
        s.add(sup)
        s.commit()
        s.refresh(sup)
        sup_id = sup.id

    # DELETE endpoint
    r = authed_client.post(f"/suppliers/{sup_id}/eliminar")
    assert r.status_code < 500, (
        f"DELETE supplier returned {r.status_code}: {r.text[:200]}"
    )

    with session_factory() as s:
        still_exists = s.execute(
            Supplier.__table__.select().where(Supplier.id == sup_id)
        ).fetchone()
        assert still_exists is None, "Supplier not deleted"


def test_supplier_editar_form_loads(authed_client, session_factory):
    """GET /suppliers/{id}/editar must return 200."""
    from app.rms.models import Supplier

    with session_factory() as s:
        sup = Supplier(
            name="Edit Form Supplier",
            phone="+595992234567",
            is_active=True,
        )
        s.add(sup)
        s.commit()
        s.refresh(sup)
        sup_id = sup.id

    r = authed_client.get(f"/suppliers/{sup_id}/editar")
    assert r.status_code < 500, (
        f"/suppliers/{sup_id}/editar returned {r.status_code}"
    )


def test_supplier_orders_page_loads(authed_client, session_factory):
    """GET /suppliers/{id}/ordenes must return 200 (orders list)."""
    from app.rms.models import Supplier

    with session_factory() as s:
        sup = Supplier(name="Orders Supplier", is_active=True)
        s.add(sup)
        s.commit()
        s.refresh(sup)
        sup_id = sup.id

    r = authed_client.get(f"/suppliers/{sup_id}/ordenes")
    assert r.status_code < 500, (
        f"/suppliers/{sup_id}/ordenes returned {r.status_code}"
    )
