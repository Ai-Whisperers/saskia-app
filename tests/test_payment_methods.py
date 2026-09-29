"""tests/test_payment_methods.py — Spanish payment-method taxonomy.

Verifies the /ventas form + POST handler accept the 5 Spanish values
Saskia uses in Ciudad del Este (efectivo/transferencia/qr/tarjeta/otro),
reject unknown values, and default the form-select to 'efectivo'.
"""
from __future__ import annotations


def test_payment_methods_includes_qr():
    """The set must include qr alongside the 4 legacy values."""
    from app.rms.schemas import ALLOWED_PAYMENT_METHODS
    expected = {"efectivo", "transferencia", "qr", "tarjeta", "otro"}
    assert expected == set(ALLOWED_PAYMENT_METHODS)


def test_payment_method_default_is_efectivo():
    """The form-select must default to 'efectivo' (most common)."""
    from app.rms.schemas import PAYMENT_METHOD_DEFAULT
    assert PAYMENT_METHOD_DEFAULT == "efectivo"


def test_payment_methods_display_order():
    """Display order: efectivo first, the rest follow."""
    from app.rms.schemas import PAYMENT_METHODS_DISPLAY
    assert PAYMENT_METHODS_DISPLAY[0] == "efectivo"
    assert set(PAYMENT_METHODS_DISPLAY) == {"efectivo", "transferencia", "qr", "tarjeta", "otro"}


def test_ventas_page_renders_all_five_payment_methods(client):
    """/ventas must render all 5 payment-method options + the helper text."""
    resp = client.get("/ventas")
    assert resp.status_code == 200
    body = resp.text
    # Check for payment method combo data source
    for pm in ("efectivo", "transferencia", "qr", "tarjeta", "otro"):
        assert f'"value": "{pm}"' in body, f"missing option for {pm}"
    # Helper text the operator asked for
    assert "transferencia/QR" in body
    assert "alias" in body


def test_ventas_page_default_selected_is_efectivo(client):
    """On first load, the efectivo option is marked selected in the combo."""
    resp = client.get("/ventas")
    body = resp.text
    # Look for the payment method combo and check default value
    assert "payment_method" in body
    assert 'value=""' in body  # Hidden input for payment_method should be empty by default


def test_post_sale_accepts_all_five_payment_methods(client, session_factory):
    """POST /ventas/nueva with each of the 5 values must persist it."""
    from app.rms.models import Product, Sale

    # One product to sell (no recipe — avoids stock-drop side effects).
    with session_factory() as s:
        p = Product(name="PM Test Product", sale_price_gs=10000, recipe_id=None)
        s.add(p)
        s.commit()
        product_id = p.id

    for pm in ("efectivo", "transferencia", "qr", "tarjeta", "otro"):
        resp = client.post(
            "/ventas/nueva",
            data={"product_id": str(product_id), "qty": "1", "payment_method": pm},
            follow_redirects=False,
        )
        assert resp.status_code in (200, 303), f"{pm!r} got {resp.status_code}: {resp.text[:200]}"

    with session_factory() as s:
        methods = sorted(
            row.payment_method
            for row in s.query(Sale).all()
            if row.payment_method is not None
        )
    assert methods == ["efectivo", "otro", "qr", "tarjeta", "transferencia"]


def test_post_sale_rejects_unknown_payment_method(client, session_factory):
    """Unknown payment_method must be rejected (400) — not silently dropped."""
    from app.rms.models import Product, Sale

    with session_factory() as s:
        p = Product(name="PM Reject Product", sale_price_gs=10000, recipe_id=None)
        s.add(p)
        s.commit()
        product_id = p.id

    resp = client.post(
        "/ventas/nueva",
        data={"product_id": str(product_id), "qty": "1", "payment_method": "bitcoin"},
        follow_redirects=False,
    )
    assert resp.status_code == 400, f"expected 400, got {resp.status_code}"

    with session_factory() as s:
        rows = s.query(Sale).filter(Sale.payment_method == "bitcoin").all()
    assert rows == [], "rejected payment_method must not be persisted"
