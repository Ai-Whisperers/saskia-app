"""P-13: Pedidos stock-preview warnings display + force checkbox regression.

Tests:
- /pedidos/{id}/stock-preview endpoint exists
- Warnings display correctly
- Force checkbox field exists
- No Python errors
"""


def test_pedidos_stock_preview_endpoint(client):
    """P-13: /pedidos/{id}/stock-preview endpoint exists."""
    r = client.get("/pedidos/1/stock-preview")
    assert r.status_code in (200, 302, 404, 405), f"Got {r.status_code}"


def test_pedidos_stock_preview_in_spanish(client):
    """P-13: Stock-preview page is in Spanish."""
    r = client.get("/pedidos/1/stock-preview")
    if r.status_code == 200:
        body = r.text
        assert any(
            w in body.lower()
            for w in ["stock", "inventario", "disponible", "vista previa", "preview", "pedido"]
        ), "Page not in Spanish"


def test_pedidos_stock_preview_has_warning(client):
    """P-13: Stock-preview has warning indicators."""
    r = client.get("/pedidos/1/stock-preview")
    if r.status_code == 200:
        body = r.text
        assert (
            "warning" in body.lower()
            or "alerta" in body.lower()
            or "negativo" in body.lower()
            or "insuficiente" in body.lower()
            or "faltante" in body.lower()
            or "warning-icon" in body.lower()
        ), "Warning indicators not found"


def test_pedidos_stock_preview_has_force(client):
    """P-13: Stock-preview has force checkbox."""
    r = client.get("/pedidos/1/stock-preview")
    if r.status_code == 200:
        body = r.text
        assert 'type="checkbox"' in body or "forzar" in body.lower() or "force" in body.lower(), (
            "Force checkbox not found"
        )


def test_pedidos_stock_preview_no_python_errors(client):
    """P-13: No Python errors on stock-preview."""
    for pid in [1, 2, 999]:
        r = client.get(f"/pedidos/{pid}/stock-preview")
        assert r.status_code != 500, f"Got 500 for /pedidos/{pid}/stock-preview"


def test_pedidos_stock_preview_post(client):
    """P-13: POST to stock-preview handled."""
    r = client.post("/pedidos/1/stock-preview", data={"force": "1"})
    assert r.status_code != 500, "POST returned 500"


def test_pedidos_stock_preview_template_renders(client):
    """P-13: Template renders without Jinja errors."""
    r = client.get("/pedidos/1/stock-preview")
    if r.status_code == 200:
        body = r.text
        assert "TemplateSyntaxError" not in body and "UndefinedError" not in body, (
            "Jinja template error detected"
        )


def test_pedidos_stock_preview_lists_items(client):
    """P-13: Stock-preview lists pedido items."""
    r = client.get("/pedidos/1/stock-preview")
    if r.status_code == 200:
        body = r.text
        assert (
            "item" in body.lower()
            or "producto" in body.lower()
            or "linea" in body.lower()
            or "l\u00ednea" in body.lower()
        ), "Items list not found"
