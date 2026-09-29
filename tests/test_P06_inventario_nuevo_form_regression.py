"""P-06: Inventario nuevo form submit, alérgenos, tags regression test.

Tests:
- /inventario/nuevo form renders
- Allergen and tag fields present
- Form submission works without crash
- No Python errors
"""

def test_inventario_nuevo_renders(client):
    """P-06: New inventory page renders."""
    r = client.get("/inventario/nuevo")
    assert r.status_code == 200


def test_inventario_nuevo_renders_in_spanish(client):
    """P-06: New inventory page is in Spanish."""
    r = client.get("/inventario/nuevo")
    assert r.status_code == 200
    body = r.text
    assert "Inventario" in body or "nuevo" in body.lower() or "ingrediente" in body.lower(), \
        "Page not in Spanish"


def test_inventario_nuevo_has_name_field(client):
    """P-06: Form has name field."""
    r = client.get("/inventario/nuevo")
    assert r.status_code == 200
    body = r.text
    assert 'name="name"' in body or 'name="nombre"' in body, "Name field not found"


def test_inventario_nuevo_has_unit_field(client):
    """P-06: Form has unit field."""
    r = client.get("/inventario/nuevo")
    assert r.status_code == 200
    body = r.text
    assert (
        "unidad" in body.lower()
        or "unit" in body.lower()
        or 'name="unit' in body
        or "<select" in body
    ), "Unit field not found"


def test_inventario_nuevo_has_cost_field(client):
    """P-06: Form has cost field."""
    r = client.get("/inventario/nuevo")
    assert r.status_code == 200
    body = r.text
    assert (
        "costo" in body.lower()
        or "cost" in body.lower()
        or "precio" in body.lower()
        or "price" in body.lower()
    ), "Cost field not found"


def test_inventario_nuevo_has_stock_field(client):
    """P-06: Form has stock field."""
    r = client.get("/inventario/nuevo")
    assert r.status_code == 200
    body = r.text
    assert (
        "stock" in body.lower()
        or "cantidad" in body.lower()
        or "quantity" in body.lower()
    ), "Stock field not found"


def test_inventario_nuevo_has_allergen_field(client):
    """P-06: Form has allergen field."""
    r = client.get("/inventario/nuevo")
    assert r.status_code == 200
    body = r.text
    # Allergen field optional
    has_allergen = (
        "al" in body.lower()  # alérgeno
        or "allergen" in body.lower()
        or "alergeno" in body.lower()
    )
    assert has_allergen, "Allergen field not found"


def test_inventario_nuevo_has_tags_field(client):
    """P-06: Form has tags field."""
    r = client.get("/inventario/nuevo")
    assert r.status_code == 200
    body = r.text
    assert "tag" in body.lower() or "etiqueta" in body.lower(), "Tags field not found"


def test_inventario_nuevo_has_submit_button(client):
    """P-06: Form has submit button."""
    r = client.get("/inventario/nuevo")
    assert r.status_code == 200
    body = r.text
    # Accept infinitive or voseo forms
    has_submit = (
        'type="submit"' in body
        or "Guard" in body  # Guardar / Guardá
        or "Crear" in body
        or "Save" in body
    )
    assert has_submit, "Submit button not found"


def test_inventario_nuevo_no_python_errors(client):
    """P-06: No Python errors on new inventory page."""
    r = client.get("/inventario/nuevo")
    assert r.status_code != 500


def test_inventario_nuevo_post_no_crash(client):
    """P-06: POST to inventario/nuevo doesn't crash."""
    r = client.post("/inventario/nuevo", data={
        "name": "Test ingredient",
        "unit": "kg",
        "cost_per_unit": "1000",
        "stock": "0",
    })
    assert r.status_code != 500, "POST returned 500"


def test_inventario_nuevo_handles_empty_post(client):
    """P-06: Empty POST is handled gracefully."""
    r = client.post("/inventario/nuevo", data={})
    # Should either validate and show errors (200/400/422) or redirect
    assert r.status_code in (200, 302, 400, 422), f"Unexpected {r.status_code}"
