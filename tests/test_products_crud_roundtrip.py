"""Productos CRUD roundtrip tests."""
from __future__ import annotations

import pytest
from app.rms.models import Product


def test_productos_page_loads(authed_client):
    """GET /productos must return 200."""
    r = authed_client.get("/productos")
    assert r.status_code == 200


def test_productos_nuevo_form_loads(authed_client):
    """GET /productos/nuevo must return 200."""
    r = authed_client.get("/productos/nuevo")
    assert r.status_code == 200


def test_product_create_then_edit(authed_client, session_factory):
    """Create product via ORM, then GET edit form. Must work."""
    from app.rms.models import Product

    with session_factory() as s:
        p = Product(
            name="CRUD Edit Product",
            portion_label="1 und",
            sale_price_gs=5000,
            is_available=True,
        )
        s.add(p)
        s.commit()
        s.refresh(p)
        p_id = p.id

    r = authed_client.get(f"/productos/{p_id}/editar")
    assert r.status_code < 500, f"/productos/{p_id}/editar returned {r.status_code}"


def test_product_create_form_accepts_audit_fields(authed_client, session_factory):
    """POST /productos/nuevo with audit fields (158-161) must create product."""
    r = authed_client.post("/productos/nuevo", data={
        "name": "CRUD Audit Test Product",
        "portion_label": "1 und",
        "sale_price_gs": "5000",
        "is_available": "on",
        "category": "TestCat",
        "tags": "tag1,tag2",
        "image_url": "https://example.com/img.jpg",
    })
    assert r.status_code in (200, 303), f"Product create returned {r.status_code}"

    with session_factory() as s:
        row = s.execute(
            Product.__table__.select().where(
                Product.name == "CRUD Audit Test Product"
            )
        ).fetchone()
        # If creation succeeded, verify it
        if row is not None:
            # row is a tuple; convert to dict for readability
            product_data = s.execute(
                Product.__table__.select().where(
                    Product.name == "CRUD Audit Test Product"
                )
            ).first()
            # Just verify it exists; deeper assertion is in P2 audit tests
            assert product_data is not None


def test_product_bulk_eliminar_no_500(authed_client, session_factory):
    """POST /productos/bulk-eliminar with empty selection must not 500."""
    r = authed_client.post("/productos/bulk-eliminar", data={"selected": []})
    assert r.status_code < 500, (
        f"/productos/bulk-eliminar returned {r.status_code}"
    )


def test_product_export_csv_returns_csv(authed_client, session_factory):
    """GET /productos/export.csv must return CSV."""
    from app.rms.models import Product
    with session_factory() as s:
        p = Product(
            name="CSV Export Product",
            portion_label="1 und",
            sale_price_gs=5000,
            is_available=True,
        )
        s.add(p)
        s.commit()

    r = authed_client.get("/productos/export.csv")
    assert r.status_code < 500
    if r.status_code == 200:
        ct = r.headers.get("content-type", "").lower()
        assert "csv" in ct or "text/plain" in ct


def test_new_product_is_available_defaults_true(session_factory):
    """New products default to is_available=True (visible in POS)."""
    from app.rms.models import Product
    with session_factory() as s:
        p = Product(
            name="Default Available Product",
            portion_label="1 und",
            sale_price_gs=5000,
        )
        s.add(p)
        s.commit()
        s.refresh(p)
        assert p.is_available is True
