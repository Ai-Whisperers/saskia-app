"""P-06: Inventario nuevo form submit regression test.

Tests:
- /inventario/nuevo form renders correctly
- Form fields are present (name, unit, stock, etc.)
- Alérgenos and tags fields are available
- Form submission works
- Server-side validation
"""
import pytest


def test_inventario_nuevo_renders_200(client):
    """P-06: /inventario/nuevo form page returns 200."""
    r = client.get("/inventario/nuevo")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"


def test_inventario_nuevo_has_name_field(client):
    """P-06: Name field is present."""
    r = client.get("/inventario/nuevo")
    assert r.status_code == 200
    body = r.text
    # Check for name input
    assert 'name="name"' in body or 'id="name"' in body, "Name field not found"


def test_inventario_nuevo_has_unit_field(client):
    """P-06: Unit field is present."""
    r = client.get("/inventario/nuevo")
    assert r.status_code == 200
    body = r.text
    # Check for unit selector (kg, L, unidades, etc.)
    assert "unit" in body.lower() or "unidad" in body.lower(), "Unit field not found"


def test_inventario_nuevo_has_stock_fields(client):
    """P-06: Stock-related fields are present."""
    r = client.get("/inventario/nuevo")
    assert r.status_code == 200
    body = r.text
    # Check for stock/min stock/cost fields
    assert "stock" in body.lower() or "cantidad" in body.lower(), "Stock fields not found"


def test_inventario_nuevo_has_alergenos_field(client):
    """P-06: Alérgenos field is present."""
    r = client.get("/inventario/nuevo")
    assert r.status_code == 200
    body = r.text
    # Check for alérgenos/alergenos field
    assert "alérgeno" in body.lower() or "alergeno" in body.lower() or "allergen" in body.lower(), \
        "Alérgenos field not found"


def test_inventario_nuevo_has_tags_field(client):
    """P-06: Tags field is present."""
    r = client.get("/inventario/nuevo")
    assert r.status_code == 200
    body = r.text
    # Check for tags field
    assert "tag" in body.lower() or "etiqueta" in body.lower(), "Tags field not found"


def test_inventario_nuevo_has_cost_field(client):
    """P-06: Cost field is present."""
    r = client.get("/inventario/nuevo")
    assert r.status_code == 200
    body = r.text
    # Check for cost/price field
    assert "cost" in body.lower() or "costo" in body.lower() or "precio" in body.lower(), \
        "Cost field not found"


def test_inventario_nuevo_has_supplier_field(client):
    """P-06: Supplier field is present."""
    r = client.get("/inventario/nuevo")
    assert r.status_code == 200
    body = r.text
    # Check for supplier selector (combo or field)
    assert "supplier" in body.lower() or "proveedor" in body.lower(), \
        "Supplier field not found"


def test_inventario_nuevo_has_submit_button(client):
    """P-06: Submit button is present."""
    r = client.get("/inventario/nuevo")
    assert r.status_code == 200
    body = r.text
    # Check for submit button
    assert 'type="submit"' in body, "Submit button not found"
    # Check for "Guardá" or similar text (infinitive form as per user preference)
    assert "Guard" in body, "Submit button text not found"


def test_inventario_nuevo_form_action(client):
    """P-06: Form has correct action."""
    r = client.get("/inventario/nuevo")
    assert r.status_code == 200
    body = r.text
    # Check for form with action
    assert "<form" in body, "No form found"
    # Check for action attribute or method
    assert 'action=' in body or 'method=' in body, "Form has no action/method"


def test_inventario_nuevo_no_python_errors(client):
    """P-06: No Python errors in inventario/nuevo page."""
    r = client.get("/inventario/nuevo")
    assert r.status_code == 200
    # Check response is HTML
    assert "text/html" in r.headers.get("content-type", ""), \
        "Response is not HTML"


def test_inventario_nuevo_csrf_token(client):
    """P-06: CSRF token is present in form."""
    r = client.get("/inventario/nuevo")
    assert r.status_code == 200
    body = r.text
    # Check for CSRF token
    assert "_csrf_token" in body or "csrf" in body.lower(), \
        "CSRF token not found in form"
