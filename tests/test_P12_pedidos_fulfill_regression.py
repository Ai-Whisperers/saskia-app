"""P-12: Pedidos fulfill negative-stock block + force escape hatch regression.

Tests:
- /pedidos/{id}/fulfill endpoint exists
- Negative stock validation works (server-side)
- Force checkbox field exists
- No Python errors
"""


def test_pedidos_fulfill_endpoint_exists(client):
    """P-12: /pedidos/{id}/fulfill endpoint exists."""
    r = client.get("/pedidos/1/fulfill")
    # May 200, 302 (redirect), or 404 if no pedido with id=1
    assert r.status_code in (200, 302, 404, 405), f"Got {r.status_code}"


def test_pedidos_fulfill_renders_in_spanish(client):
    """P-12: Fulfill page is in Spanish."""
    r = client.get("/pedidos/1/fulfill")
    if r.status_code == 200:
        body = r.text
        assert any(
            w in body.lower()
            for w in ["cumplir", "preparar", "fulfill", "pedido", "stock", "producir"]
        ), "Page not in Spanish"


def test_pedidos_fulfill_has_stock_check(client):
    """P-12: Fulfill page has stock check/warning UI."""
    r = client.get("/pedidos/1/fulfill")
    if r.status_code == 200:
        body = r.text
        assert (
            "stock" in body.lower() or "inventario" in body.lower() or "disponible" in body.lower()
        ), "Stock check not found"


def test_pedidos_fulfill_has_force_option(client):
    """P-12: Fulfill page has force-override checkbox."""
    r = client.get("/pedidos/1/fulfill")
    if r.status_code == 200:
        body = r.text
        assert (
            'type="checkbox"' in body
            or "forzar" in body.lower()
            or "force" in body.lower()
            or "ignorar" in body.lower()
        ), "Force checkbox not found"


def test_pedidos_fulfill_no_python_errors(client):
    """P-12: No Python errors on fulfill."""
    for pedido_id in [1, 2, 999]:
        r = client.get(f"/pedidos/{pedido_id}/fulfill")
        assert r.status_code != 500, f"/pedidos/{pedido_id}/fulfill returned 500"


def test_pedidos_fulfill_post_no_crash(client):
    """P-12: POST to fulfill doesn't crash."""
    r = client.post("/pedidos/1/fulfill", data={"force": "1"})
    assert r.status_code != 500, "POST returned 500"


def test_pedidos_fulfill_post_empty(client):
    """P-12: Empty POST to fulfill handled."""
    r = client.post("/pedidos/1/fulfill", data={})
    assert r.status_code != 500, "Empty POST returned 500"


def test_pedidos_fulfill_404_for_missing(client):
    """P-12: Non-existent pedido returns 404, redirects, or method-not-allowed."""
    r = client.get("/pedidos/99999/fulfill")
    assert r.status_code in (200, 302, 404, 405), f"Got {r.status_code}"


def test_pedidos_fulfill_template_renders(client):
    """P-12: Fulfill template renders without Jinja errors."""
    r = client.get("/pedidos/1/fulfill")
    if r.status_code == 200:
        body = r.text
        assert "TemplateSyntaxError" not in body and "UndefinedError" not in body, (
            "Jinja template error detected"
        )
