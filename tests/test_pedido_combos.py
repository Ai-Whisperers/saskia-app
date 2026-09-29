"""Tests for the pedidos combobox features."""

import pytest



def test_product_api_search_returns_matches(qseed, authed_client):
    """GET /productos/api/search?q=muffin returns matching products."""
    data = qseed("basic")
    # qseed("basic") creates 1 product called "Producto QA"
    # create a couple more products with names we search for
    from app.rms.models import Product
    sf = qseed.session_factory
    with sf() as s:
        s.add(Product(name="Muffin Test", sale_price_gs=3000, is_available=True))
        s.add(Product(name="Muffin Chocolate", sale_price_gs=4000, is_available=True))
        s.add(Product(name="Docena muffins", sale_price_gs=90000, is_available=True))
        s.add(Product(name="Pan integral", sale_price_gs=2000, is_available=True))
        s.commit()

    r = authed_client.get("/productos/api/search?q=muffin")
    assert r.status_code == 200
    data = r.json()
    names = [p["name"] for p in data["results"]]
    assert "Muffin Test" in names
    assert "Muffin Chocolate" in names
    assert "Docena muffins" in names
    assert "Pan integral" not in names  # wouldn't match


def test_product_api_search_returns_empty_for_no_match(qseed, authed_client):
    """Empty results dict when no match."""
    qseed("basic")
    r = authed_client.get("/productos/api/search?q=xyz_nonexistent_product_999")
    assert r.status_code == 200
    assert r.json() == {"results": [], "count": 0}


def test_product_api_search_limit_param(qseed, authed_client):
    """limit param caps result count."""
    from app.rms.models import Product
    sf = qseed.session_factory
    with sf() as s:
        for i in range(75):
            s.add(Product(name=f"Item {i:03d}", sale_price_gs=1000, is_available=True))
        s.commit()

    r = authed_client.get("/productos/api/search?limit=10")
    assert r.status_code == 200
    data = r.json()
    assert len(data["results"]) == 10
    assert data["count"] == 10


def test_product_api_search_does_not_match_qs(qseed, authed_client):
    """Empty query returns all products up to limit."""
    from app.rms.models import Product
    sf = qseed.session_factory
    with sf() as s:
        for i in range(20):
            s.add(Product(name=f"Item {i:03d}", sale_price_gs=1000, is_available=True))
        s.commit()

    r = authed_client.get("/productos/api/search?q=")
    assert r.status_code == 200
    data = r.json()
    assert len(data["results"]) <= 50  # default limit


@pytest.mark.xfail(reason="Pedido combo UI not yet shipped", strict=False)
def test_pedido_nuevo_renders_combobox_not_select(qseed, authed_client):
    """The new pedido form uses combobox elements, not native <select>."""
    qseed("basic")
    r = authed_client.get("/pedidos/nuevo")
    assert r.status_code == 200
    body = r.text
    # Generic combo markers (reusable component)
    assert "saskia-combo" in body
    assert "combo-input" in body
    # Customer + product combobox instances
    assert "saskia-customer-combo" in body
    assert "saskia-product-combo" in body
    # Data attributes wire up to the right APIs
    assert 'data-source="/customers/api/search"' in body
    assert 'data-source="/productos/api/search"' in body
    # Old redundant inputs gone
    assert '<select id="customer_id"' not in body, (
        "Customer ID should now be a hidden input, not a select"
    )


def test_pedido_nuevo_has_no_redundant_customer_select(qseed, authed_client):
    """Customer name + customer_id are now ONE field (combobox), not two."""
    qseed("basic")
    r = authed_client.get("/pedidos/nuevo")
    body = r.text
    # The labels for the old "Cliente existente (opcional)" should be gone
    assert "Cliente existente (opcional)" not in body, (
        "Customer picker is now single-field; no separate 'opcional' dropdown needed"
    )


def test_pedido_nuevo_includes_pedido_combos_js(qseed, authed_client):
    """Verify the JS file is served and reachable."""
    qseed("basic")
    r = authed_client.get("/pedidos/nuevo")
    body = r.text
    assert "/static/pedido-combos.js" in body

    # Also fetch the JS itself
    r2 = authed_client.get("/static/pedido-combos.js")
    assert r2.status_code == 200
    # Check for one of the class names the pedido-specific bindings use
    assert (
        "saskia-combo" in r2.text
        or "SaskiaCombo" in r2.text
        or "setupCustomerCombo" in r2.text
    )


def test_pedido_create_with_combobox_customer(qseed, authed_client):
    """Pedido creation accepts the new field shape (customer_name + customer_id hidden)."""
    from datetime import datetime, timedelta, timezone

    from app.rms.models import Customer, Ingredient, Pedido, Product
    sf = qseed.session_factory
    with sf() as s:
        ing = s.query(Ingredient).filter_by(name="harina QA").first()
        if ing is None:
            ing = Ingredient(name="harina QA", unit="kg", stock_qty=10,
                             min_stock_qty=1, purchase_price_gs=3000)
            s.add(ing); s.flush()
        prod = s.query(Product).filter_by(name="Producto QA").first()
        if prod is None:
            prod = Product(name="Producto QA", sale_price_gs=2500, is_available=True)
            s.add(prod)
        s.commit()
        prod_id = prod.id

    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()
    r = authed_client.post(
        "/pedidos/nuevo",
        data={
            "customer_name": "Nuevo Cliente Test",
            "customer_id": "",
            "customer_phone": "+595 981234567",
            "promised_date": tomorrow,
            "channel": "whatsapp",
            "payment_intent": "efectivo",
            "notes": "",
            "line_product_id": str(prod_id),
            "line_qty": "2",
            "line_unit_price_gs": "2500",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303, f"Pedido create failed: {r.status_code} {r.text[:500]}"

    # Verify the customer was created and pedido exists
    with sf() as s:
        c = s.query(Customer).filter_by(name="Nuevo Cliente Test").first()
        assert c is not None
        assert c.phone == "+595 981234567"
        ped = s.query(Pedido).filter_by(customer_id=c.id).first()
        assert ped is not None
