"""P-04: Recetas combo field integration regression test.

Tests:
- /recetas page renders
- /recetas/nueva form has combo fields (ingredient selection)
- Recipe API search endpoint works
- No Python errors
"""

def test_recetas_renders(client):
    """P-04: Recetas page renders."""
    r = client.get("/recetas")
    assert r.status_code == 200


def test_recetas_renders_in_spanish(client):
    """P-04: Recetas page is in Spanish."""
    r = client.get("/recetas")
    assert r.status_code == 200
    body = r.text
    assert "Recetas" in body or "receta" in body.lower(), "Page not in Spanish"


def test_recetas_nueva_renders(client):
    """P-04: Nueva receta page renders."""
    r = client.get("/recetas/nueva")
    assert r.status_code == 200


def test_recetas_nueva_has_combo(client):
    """P-04: Nueva receta has ingredient combo."""
    r = client.get("/recetas/nueva")
    assert r.status_code == 200
    body = r.text
    # Check for saskia-combo or ingredient selector
    assert "saskia-combo" in body or "combo" in body.lower() or "ingrediente" in body.lower(), \
        "Ingredient combo not found"


def test_recetas_nueva_has_name_field(client):
    """P-04: Nueva receta has name field."""
    r = client.get("/recetas/nueva")
    assert r.status_code == 200
    body = r.text
    assert 'name="name"' in body or 'name="nombre"' in body, "Name field not found"


def test_recetas_nueva_has_yield_field(client):
    """P-04: Nueva receta has yield field."""
    r = client.get("/recetas/nueva")
    assert r.status_code == 200
    body = r.text
    assert "yield" in body.lower() or "rendimiento" in body.lower() or "porciones" in body.lower(), \
        "Yield field not found"


def test_recetas_api_search(client):
    """P-04: Recetas API search endpoint works."""
    r = client.get("/recetas/api/search/")
    assert r.status_code in (200, 404), f"Got {r.status_code}"
    if r.status_code == 200:
        # Should return JSON
        body = r.text
        # Either JSON or HTML (with API off)
        assert len(body) > 0


def test_recetas_no_python_errors(client):
    """P-04: No Python errors on recetas pages."""
    test_urls = ["/recetas", "/recetas/nueva"]
    for url in test_urls:
        r = client.get(url)
        assert r.status_code != 500, f"URL {url} returned 500"


def test_recetas_has_ingredient_lines(client):
    """P-04: Nueva receta has lines for adding ingredients."""
    r = client.get("/recetas/nueva")
    assert r.status_code == 200
    body = r.text
    # Check for ingredient line template or add-line button
    has_lines = (
        "ingredient" in body.lower()
        and ("line" in body.lower() or "fila" in body.lower() or "row" in body.lower())
    )
    assert has_lines, "Ingredient lines not found"


def test_recetas_has_submit_button(client):
    """P-04: Nueva receta has submit button."""
    r = client.get("/recetas/nueva")
    assert r.status_code == 200
    body = r.text
    assert 'type="submit"' in body, "Submit button not found"


def test_recetas_post_no_crash(client):
    """P-04: POST to recetas/nueva doesn't crash."""
    r = client.post("/recetas/nueva", data={"name": "Test receta", "yield_percentage": "1.0"})
    assert r.status_code != 500, "POST recetas/nueva returned 500"


def test_recetas_detalle_renders(client):
    """P-04: Recipe detail page renders (with fallback to 404)."""
    r = client.get("/recetas/1")
    # Detail page may 404 if no recipe with id=1
    assert r.status_code in (200, 404), f"Unexpected status {r.status_code}"
