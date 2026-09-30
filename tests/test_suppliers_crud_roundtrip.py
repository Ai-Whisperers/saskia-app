"""Suppliers CRUD roundtrip tests."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.crud
from app.rms.models import Supplier


def test_suppliers_page_loads(authed_client):
    """GET /suppliers must return 200."""
    r = authed_client.get("/suppliers")
    assert r.status_code == 200


def test_suppliers_nuevo_form_loads(authed_client):
    """GET /suppliers/nuevo must return 200."""
    r = authed_client.get("/suppliers/nuevo")
    assert r.status_code == 200


def test_supplier_create_then_soft_delete(authed_client, session_factory):
    """Create supplier, soft-delete via POST, verify is_active=False.

    The endpoint changed from hard-delete (commit 9b4e3f7 era) to
    soft-delete (sets is_active=False, preserves history). Reactivation
    lives at POST /{id}/reactivar.
    """

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

    # DELETE endpoint — now a soft-delete
    r = authed_client.post(f"/suppliers/{sup_id}/eliminar")
    assert r.status_code < 500, (
        f"DELETE supplier returned {r.status_code}: {r.text[:200]}"
    )

    with session_factory() as s:
        row = s.execute(
            Supplier.__table__.select().where(Supplier.id == sup_id)
        ).fetchone()
        assert row is not None, "soft-delete removed the row (should preserve history)"
        # The (id, name, ..., is_active, ...) tuple — assert is_active=False
        assert row.is_active is False or row[-1] is False, (
            f"is_active must be False after /eliminar; got row={row}"
        )

    # Reactivate — the same row, but is_active=True again
    r = authed_client.post(f"/suppliers/{sup_id}/reactivar")
    assert r.status_code < 500, (
        f"reactivar returned {r.status_code}: {r.text[:200]}"
    )

    with session_factory() as s:
        row = s.execute(
            Supplier.__table__.select().where(Supplier.id == sup_id)
        ).fetchone()
        assert row is not None, "reactivar removed the row"
        assert row.is_active is True or row[-1] is True, (
            f"is_active must be True after /reactivar; got row={row}"
        )


def test_supplier_editar_form_loads(authed_client, session_factory):
    """GET /suppliers/{id}/editar must return 200."""

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
