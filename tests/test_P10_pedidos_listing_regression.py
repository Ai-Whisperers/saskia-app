"""P-10: Pedidos listing, tabs, kanban view regression test.

Tests:
- /pedidos page renders
- Tabs/kanban display
- Status indicators
- No Python errors
"""


def test_pedidos_renders(client):
    """P-10: Pedidos page renders."""
    r = client.get("/pedidos")
    assert r.status_code == 200


def test_pedidos_renders_in_spanish(client):
    """P-10: Pedidos page is in Spanish."""
    r = client.get("/pedidos")
    assert r.status_code == 200
    body = r.text
    assert "Pedido" in body or "pedido" in body.lower(), "Page not in Spanish"


def test_pedidos_has_tabs(client):
    """P-10: Pedidos has tabs (kanban columns)."""
    r = client.get("/pedidos")
    assert r.status_code == 200
    body = r.text
    # Check for tab/column markers
    has_tabs = (
        "tab" in body.lower()
        or "column" in body.lower()
        or "kanban" in body.lower()
        or "pendiente" in body.lower()
        or "en preparaci" in body.lower()
        or "listo" in body.lower()
    )
    assert has_tabs, "Tabs/columns not found"


def test_pedidos_has_new_button(client):
    """P-10: Pedidos has 'new' button."""
    r = client.get("/pedidos")
    assert r.status_code == 200
    body = r.text
    assert (
        "/pedidos/nuevo" in body
        or "nuevo" in body.lower()
        or "crear" in body.lower()
        or "agregar" in body.lower()
    ), "New button not found"


def test_pedidos_has_status_filter(client):
    """P-10: Pedidos has status filter."""
    r = client.get("/pedidos")
    assert r.status_code == 200
    body = r.text
    assert (
        "estado" in body.lower()
        or "status" in body.lower()
        or "filtro" in body.lower()
        or "filter" in body.lower()
    ), "Status filter not found"


def test_pedidos_no_python_errors(client):
    """P-10: No Python errors on pedidos."""
    r = client.get("/pedidos")
    assert r.status_code != 500


def test_pedidos_filter_combinations(client):
    """P-10: Filter combinations don't crash."""
    urls = [
        "/pedidos?status=pendiente",
        "/pedidos?status=en_preparacion",
        "/pedidos?status=listo",
        "/pedidos?status=entregado",
    ]
    for url in urls:
        r = client.get(url)
        assert r.status_code != 500, f"URL {url} returned 500"


def test_pedidos_nuevo_link_visible(client):
    """P-10: Link to /pedidos/nuevo is visible."""
    r = client.get("/pedidos")
    assert r.status_code == 200
    body = r.text
    assert "/pedidos/nuevo" in body, "Link to new pedido not visible"


def test_pedidos_has_date_filter(client):
    """P-10: Pedidos has date filter."""
    r = client.get("/pedidos")
    assert r.status_code == 200
    body = r.text
    has_date = 'type="date"' in body or "fecha" in body.lower() or "date" in body.lower()
    assert has_date, "Date filter not found"


def test_pedidos_has_customer_column(client):
    """P-10: Pedidos has customer column."""
    r = client.get("/pedidos")
    assert r.status_code == 200
    body = r.text
    assert "cliente" in body.lower() or "customer" in body.lower(), "Customer column not found"
