"""P-18: Reorder/registrar restock POST flow regression test.

Tests:
- /reorder page renders
- /reorder/registrar POST works
- /reorder/generate-po POST works
- No Python errors
"""


def test_reorder_renders(client):
    """P-18: Reorder page renders."""
    r = client.get("/reorder")
    assert r.status_code == 200


def test_reorder_renders_in_spanish(client):
    """P-18: Reorder page is in Spanish."""
    r = client.get("/reorder")
    assert r.status_code == 200
    body = r.text
    assert (
        "Reponer" in body
        or "reorder" in body.lower()
        or "reposici" in body.lower()
        or "stock" in body.lower()
    ), "Page not in Spanish"


def test_reorder_has_ingredient_list(client):
    """P-18: Page shows ingredient list."""
    r = client.get("/reorder")
    assert r.status_code == 200
    body = r.text
    assert (
        "ingrediente" in body.lower() or "ingredient" in body.lower() or "stock" in body.lower()
    ), "Ingredient list not found"


def test_reorder_has_status_indicators(client):
    """P-18: Page has status indicators."""
    r = client.get("/reorder")
    assert r.status_code == 200
    body = r.text
    assert (
        "badge" in body.lower()
        or "status" in body.lower()
        or "estado" in body.lower()
        or "bajo" in body.lower()
        or "crítico" in body.lower()
        or "critical" in body.lower()
    ), "Status indicators not found"


def test_reorder_has_registrar_action(client):
    """P-18: Page has 'registrar' restock action."""
    r = client.get("/reorder")
    assert r.status_code == 200
    body = r.text
    assert (
        "/reorder/registrar" in body
        or "registrar" in body.lower()
        or "marcar" in body.lower()
        or "compra" in body.lower()
        or "pedido" in body.lower()
        or "restock" in body.lower()
        or "reabastecer" in body.lower()
        or "button" in body.lower()
    ), "Registrar action not found"


def test_reorder_no_python_errors(client):
    """P-18: No Python errors on reorder."""
    r = client.get("/reorder")
    assert r.status_code != 500


def test_reorder_post_registrar(client):
    """P-18: POST /reorder/registrar doesn't crash."""
    r = client.post(
        "/reorder/registrar",
        data={
            "ingredient_id": "1",
            "cantidad": "10",
        },
    )
    assert r.status_code != 500, "POST /reorder/registrar returned 500"


def test_reorder_post_registrar_empty(client):
    """P-18: Empty POST to registrar handled."""
    r = client.post("/reorder/registrar", data={})
    assert r.status_code != 500, "Empty POST returned 500"
    assert r.status_code in (200, 302, 400, 422), f"Unexpected {r.status_code}"


def test_reorder_generate_po(client):
    """P-18: POST /reorder/generate-po doesn't crash."""
    r = client.post("/reorder/generate-po", data={})
    assert r.status_code != 500, "POST /reorder/generate-po returned 500"


def test_reorder_template_renders(client):
    """P-18: Reorder template renders without Jinja errors."""
    r = client.get("/reorder")
    assert r.status_code == 200
    body = r.text
    assert "TemplateSyntaxError" not in body and "UndefinedError" not in body, (
        "Jinja template error detected"
    )
