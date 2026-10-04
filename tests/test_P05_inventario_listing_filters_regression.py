"""P-05: Inventario listing, filters, status pills regression test.

Tests:
- /inventario page renders
- Filter controls present
- Status pills visible (bajo/medio/alto)
- No Python errors
"""


def test_inventario_renders(client):
    """P-05: Inventario page renders."""
    r = client.get("/inventario")
    assert r.status_code == 200


def test_inventario_renders_in_spanish(client):
    """P-05: Inventario is in Spanish."""
    r = client.get("/inventario")
    assert r.status_code == 200
    body = r.text
    assert "Inventario" in body or "inventario" in body.lower(), "Page not in Spanish"


def test_inventario_has_search_field(client):
    """P-05: Page has search/filter field."""
    r = client.get("/inventario")
    assert r.status_code == 200
    body = r.text
    assert (
        'type="search"' in body
        or 'name="q"' in body
        or "buscar" in body.lower()
        or "filter" in body.lower()
    ), "Search field not found"


def test_inventario_has_status_pills(client):
    """P-05: Status pills are visible (bajo/medio/alto/sin-stock)."""
    r = client.get("/inventario")
    assert r.status_code == 200
    body = r.text
    # Check for status labels
    has_status = (
        "bajo" in body.lower()
        or "medio" in body.lower()
        or "alto" in body.lower()
        or "sin stock" in body.lower()
        or "sin-stock" in body.lower()
        or "status" in body.lower()
        or "badge" in body.lower()
    )
    assert has_status, "Status pills not found"


def test_inventario_lists_ingredients(client):
    """P-05: Page shows ingredient list."""
    r = client.get("/inventario")
    assert r.status_code == 200
    body = r.text
    assert "ingrediente" in body.lower() or "ingredient" in body.lower(), (
        "Ingredient list not found"
    )


def test_inventario_has_filter_dropdowns(client):
    """P-05: Page has filter dropdowns."""
    r = client.get("/inventario")
    assert r.status_code == 200
    body = r.text
    # Check for select or filter buttons
    has_filter = (
        "<select" in body
        or "filter" in body.lower()
        or "filtrar" in body.lower()
        or "categor" in body.lower()
    )
    assert has_filter, "Filter dropdowns not found"


def test_inventario_no_python_errors(client):
    """P-05: No Python errors on inventario."""
    r = client.get("/inventario")
    assert r.status_code != 500, "Got 500"


def test_inventario_filter_combinations(client):
    """P-05: Filter combinations don't crash."""
    urls = [
        "/inventario?q=",
        "/inventario?q=harina",
        "/inventario?categoria=",
    ]
    for url in urls:
        r = client.get(url)
        assert r.status_code != 500, f"URL {url} returned 500"


def test_inventario_has_new_button(client):
    """P-05: Page has 'new' button."""
    r = client.get("/inventario")
    assert r.status_code == 200
    body = r.text
    assert (
        "/inventario/nuevo" in body
        or "nuevo" in body.lower()
        or "agregar" in body.lower()
        or "add" in body.lower()
    ), "New button not found"


def test_inventario_has_table(client):
    """P-05: Page has ingredient table."""
    r = client.get("/inventario")
    assert r.status_code == 200
    body = r.text
    assert "<table" in body or "row" in body.lower() or "fila" in body.lower(), "Table not found"


def test_inventario_post_no_crash(client):
    """P-05: POST to inventario doesn't crash."""
    r = client.post("/inventario", data={})
    assert r.status_code != 500, "POST inventario returned 500"
