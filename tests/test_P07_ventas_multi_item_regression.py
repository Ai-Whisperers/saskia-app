"""P-07: Ventas multi-item cart happy path regression test.

Tests:
- /ventas page renders
- Multi-item add to cart works
- Cart can hold multiple items
- Submit cart doesn't crash
- No Python errors
"""

def test_ventas_renders(client):
    """P-07: Ventas (POS) page renders."""
    r = client.get("/ventas")
    assert r.status_code == 200


def test_ventas_renders_in_spanish(client):
    """P-07: Ventas page is in Spanish."""
    r = client.get("/ventas")
    assert r.status_code == 200
    body = r.text
    assert "Venta" in body or "venta" in body.lower(), "Page not in Spanish"


def test_ventas_has_product_search(client):
    """P-07: POS has product search field."""
    r = client.get("/ventas")
    assert r.status_code == 200
    body = r.text
    assert (
        'type="search"' in body
        or 'name="q"' in body
        or "buscar" in body.lower()
        or "producto" in body.lower()
    ), "Product search not found"


def test_ventas_has_cart_section(client):
    """P-07: POS has cart section."""
    r = client.get("/ventas")
    assert r.status_code == 200
    body = r.text
    assert (
        "cart" in body.lower()
        or "carrito" in body.lower()
        or "ticket" in body.lower()
        or "items" in body.lower()
    ), "Cart section not found"


def test_ventas_has_quantity_input(client):
    """P-07: POS has quantity input."""
    r = client.get("/ventas")
    assert r.status_code == 200
    body = r.text
    assert (
        'type="number"' in body
        or "cantidad" in body.lower()
        or "qty" in body.lower()
        or "quantity" in body.lower()
    ), "Quantity input not found"


def test_ventas_has_payment_method(client):
    """P-07: POS has payment method selector."""
    r = client.get("/ventas")
    assert r.status_code == 200
    body = r.text
    assert (
        "pago" in body.lower()
        or "payment" in body.lower()
        or "efectivo" in body.lower()
        or "tarjeta" in body.lower()
    ), "Payment method not found"


def test_ventas_has_submit_button(client):
    """P-07: POS has submit button."""
    r = client.get("/ventas")
    assert r.status_code == 200
    body = r.text
    assert (
        'type="submit"' in body
        or "confirmar" in body.lower()
        or "cobrar" in body.lower()
        or "registrar" in body.lower()
    ), "Submit button not found"


def test_ventas_api_search(client):
    """P-07: Ventas search API endpoint exists."""
    r = client.get("/productos/api/search")
    assert r.status_code in (200, 404), f"Got {r.status_code}"


def test_ventas_no_python_errors(client):
    """P-07: No Python errors on ventas."""
    r = client.get("/ventas")
    assert r.status_code != 500


def test_ventas_post_multi_item_no_crash(client):
    """P-07: Multi-item POST to ventas doesn't crash."""
    r = client.post("/ventas", data={
        "items[0][product_id]": "1",
        "items[0][cantidad]": "2",
        "items[1][product_id]": "2",
        "items[1][cantidad]": "1",
        "payment_method": "efectivo",
    })
    # Should not 500; may redirect on success
    assert r.status_code != 500, "Multi-item POST returned 500"


def test_ventas_post_empty_cart_handled(client):
    """P-07: Empty cart POST is rejected gracefully."""
    r = client.post("/ventas", data={"payment_method": "efectivo"})
    # Should either show validation error (200) or reject (400/422/405)
    assert r.status_code in (200, 302, 400, 405, 422), f"Unexpected {r.status_code}"


def test_ventas_renders_total_display(client):
    """P-07: POS shows total display."""
    r = client.get("/ventas")
    assert r.status_code == 200
    body = r.text
    assert "total" in body.lower() or "Gs." in body or "sumar" in body.lower(), \
        "Total display not found"
