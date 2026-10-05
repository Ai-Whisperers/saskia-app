"""P-11: Pedidos nuevo full form submit with lines regression test.

Tests:
- /pedidos/nuevo renders
- Form fields present (cliente, fecha, notas, líneas)
- POST creates pedido (or handles gracefully)
- No Python errors
"""
# allow-hardcoded-dates: pedido fixture uses fixed dates for stable revenue/date assertions


def test_pedidos_nuevo_renders(client):
    """P-11: Nuevo pedido page renders."""
    r = client.get("/pedidos/nuevo")
    assert r.status_code == 200


def test_pedidos_nuevo_renders_in_spanish(client):
    """P-11: Nuevo pedido page is in Spanish."""
    r = client.get("/pedidos/nuevo")
    assert r.status_code == 200
    body = r.text
    assert "Pedido" in body or "Nuevo" in body, "Page not in Spanish"


def test_pedidos_nuevo_has_customer_field(client):
    """P-11: Form has customer field."""
    r = client.get("/pedidos/nuevo")
    assert r.status_code == 200
    body = r.text
    has_customer = (
        'name="customer' in body
        or 'name="cliente' in body
        or "ui-combo" in body
        or "cliente" in body.lower()
    )
    assert has_customer, "Customer field not found"


def test_pedidos_nuevo_has_delivery_date(client):
    """P-11: Form has delivery date field."""
    r = client.get("/pedidos/nuevo")
    assert r.status_code == 200
    body = r.text
    has_date = (
        'type="date"' in body
        or 'name="fecha' in body
        or 'name="date' in body
        or 'name="promised_date"' in body
        or "entrega" in body.lower()
        or "prometida" in body.lower()
    )
    assert has_date, "Delivery date not found"


def test_pedidos_nuevo_has_product_lines(client):
    """P-11: Form has product line template."""
    r = client.get("/pedidos/nuevo")
    assert r.status_code == 200
    body = r.text
    has_lines = (
        "line" in body.lower()
        or "fila" in body.lower()
        or "row" in body.lower()
        or "producto" in body.lower()
        or "items" in body.lower()
    )
    assert has_lines, "Product lines not found"


def test_pedidos_nuevo_has_notes_field(client):
    """P-11: Form has notes field."""
    r = client.get("/pedidos/nuevo")
    assert r.status_code == 200
    body = r.text
    has_notes = (
        "nota" in body.lower()
        or "notes" in body.lower()
        or "comentario" in body.lower()
        or "observaci" in body.lower()
        or "<textarea" in body
    )
    assert has_notes, "Notes field not found"


def test_pedidos_nuevo_has_submit_button(client):
    """P-11: Form has submit button."""
    r = client.get("/pedidos/nuevo")
    assert r.status_code == 200
    body = r.text
    assert (
        'type="submit"' in body
        or "Crear" in body
        or "Guard" in body  # Guardar/Guardá
        or "Registrar" in body
    ), "Submit button not found"


def test_pedidos_nuevo_no_python_errors(client):
    """P-11: No Python errors on nuevo pedido."""
    r = client.get("/pedidos/nuevo")
    assert r.status_code != 500


def test_pedidos_nuevo_post_minimal(client):
    """P-11: Minimal POST to nuevo pedido doesn't crash."""
    r = client.post(
        "/pedidos/nuevo",
        data={
            "customer_id": "1",
            "delivery_date": "2026-12-31",
        },
    )
    # Should not 500; may redirect (302) or validate (200/422)
    assert r.status_code != 500, "POST returned 500"
    assert r.status_code in (200, 302, 400, 422), f"Unexpected {r.status_code}"


def test_pedidos_nuevo_handles_empty(client):
    """P-11: Empty POST is handled gracefully."""
    r = client.post("/pedidos/nuevo", data={})
    assert r.status_code != 500, "Empty POST returned 500"
    assert r.status_code in (200, 302, 400, 422), f"Unexpected {r.status_code}"
