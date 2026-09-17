"""tests/test_pydantic_forms.py — Pydantic validation for state-changing endpoints.

Prior: raw form.get()/int()/float() parsing, no validation. Negative
discounts, zero sales, integer overflow could pass silently.

Post: FastAPI's Form(...) rejects bad input with 422 before the route
handler runs.
"""
from __future__ import annotations


def test_ventas_nueva_rejects_negative_discount(client):
    """Negative discount_gs must be 422."""
    resp = client.post("/ventas/nueva", data={
        "product_id": "1", "qty": "1", "discount_gs": "-100",
    })
    assert resp.status_code == 422, f"Expected 422 for negative discount, got {resp.status_code}"


def test_ventas_nueva_rejects_huge_qty(client):
    """qty above the sanity cap must be 422."""
    resp = client.post("/ventas/nueva", data={
        "product_id": "1", "qty": "99999999", "discount_gs": "0",
    })
    assert resp.status_code == 422


def test_ventas_nueva_rejects_zero_qty(client):
    """qty=0 must be 422 (gt=0)."""
    resp = client.post("/ventas/nueva", data={"product_id": "1", "qty": "0"})
    assert resp.status_code == 422


def test_ventas_nueva_rejects_missing_product_id(client):
    """Missing required product_id must be 422."""
    resp = client.post("/ventas/nueva", data={"qty": "1"})
    assert resp.status_code == 422


def test_payment_method_set_in_schemas():
    """ALLOWED_PAYMENT_METHODS covers the Spanish labels Saskia actually uses.

    Includes 'qr' alongside efectivo/transferencia/tarjeta/otro so the
    Ciudad del Este workflow (efectivo/transferencia/QR) is supported.
    """
    from app.rms.schemas import ALLOWED_PAYMENT_METHODS
    expected = {"efectivo", "transferencia", "qr", "tarjeta", "otro"}
    assert expected.issubset(set(ALLOWED_PAYMENT_METHODS))
    # default is the most common sale type
    assert "efectivo" in ALLOWED_PAYMENT_METHODS


def test_schemas_module_exposes_constants():
    """schemas module exposes the validation constants."""
    from app.rms import schemas
    assert hasattr(schemas, "MAX_QTY")
    assert hasattr(schemas, "MAX_DISCOUNT_GS")
    assert hasattr(schemas, "ALLOWED_PAYMENT_METHODS")
    assert schemas.MAX_QTY > 0
    assert schemas.MAX_DISCOUNT_GS > 0
