"""Tests for the /ventas form combobox conversion (product picker + filter)."""

import pytest


def test_ventas_form_uses_combobox_for_product(qseed, authed_client):
    """/ventas (POS screen) product picker is a combobox."""
    qseed("basic")
    r = authed_client.get("/ventas")
    assert r.status_code == 200
    body = r.text
    # Combobox markers
    assert 'saskia-combo' in body
    assert 'id="product_combo"' in body
    # Old native select for product is gone
    assert '<select id="product_id" name="product_id" required>' not in body
    assert '<select name="product_id" required>' not in body


def test_ventas_filter_form_uses_combobox(qseed, authed_client):
    """/ventas filter form product picker is also combobox (replaces 30+ <select>)."""
    qseed("basic")
    r = authed_client.get("/ventas")
    assert r.status_code == 200
    body = r.text
    # Filter combobox exists
    assert 'data-source="/productos/api/search"' in body
    # Filter is now a hidden input controlled by combobox
    assert 'name="product_id"' in body


def test_ventas_combo_emits_hidden_product_id_field(qseed, authed_client):
    """The combobox's hidden <input name="product_id"> is preserved by the form."""
    qseed("basic")
    r = authed_client.get("/ventas")
    body = r.text
    # Hidden inputs for product_id still exist (so the form picks up combobox selection).
    assert 'type="hidden" id="product_id" name="product_id"' in body


def test_ventas_sku_lookup_adapted_for_combobox(qseed, client):
    """/ventas/buscar returns {found, product_id, name, sale_price_gs, sku}."""
    from app.rms.models import Product
    sf = qseed.session_factory
    pid = None
    with sf() as s:
        p = Product(name="Test Combo SKU", sku="TCS-001", sale_price_gs=5000)
        s.add(p); s.commit()
        pid = p.id

    r = client.get(f"/ventas/buscar?sku=TCS-001")
    assert r.status_code == 200
    data = r.json()
    assert data["found"] is True
    assert data["product_id"] == pid
    assert data["name"] == "Test Combo SKU"
    assert data["sku"] == "TCS-001"


def test_ventas_sku_lookup_unknown_returns_not_found(client):
    """/ventas/buscar?sku=NONEXISTENT returns {found: false}."""
    r = client.get("/ventas/buscar?sku=Z9X-DOES-NOT-EXIST")
    assert r.status_code == 200
    data = r.json()
    assert data["found"] is False


def test_ventas_form_channel_payment_unchanged(qseed, authed_client):
    """Channel + payment select (3-7 options) are NOT comboboxed — they're
    short enough to scroll through fine.
    """
    qseed("basic")
    r = authed_client.get("/ventas")
    body = r.text
    # Channel + payment method are still <select> (3-7 options each — fine)
    assert '<select id="channel" name="channel">' in body
    assert '<select id="payment_method" name="payment_method">' in body
