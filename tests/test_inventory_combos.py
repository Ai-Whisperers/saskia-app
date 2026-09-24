"""Test inventory form combo conversion."""

import pytest
from fastapi.testclient import TestClient
from app.rms.units import Unit


def test_inventory_form_unit_combo(client: TestClient):
    """Test that inventory form uses combobox for unit selection."""
    response = client.get("/inventario/nuevo")
    assert response.status_code == 200

    # Check for combobox elements instead of native selects
    assert 'class="saskia-combo"' in response.text
    assert 'data-source="/recetas/api/units"' in response.text
    assert "unit_combo" in response.text
    assert "combo-input" in response.text

    # Should not contain native unit select
    assert '<select id="unit"' not in response.text


def test_inventory_form_category_combo(client: TestClient):
    """Test that inventory form uses combobox for category selection."""
    response = client.get("/inventario/nuevo")
    assert response.status_code == 200
    
    # Check for category combobox
    assert "category_combo" in response.text
    assert "data-allow-create=\"true\"" in response.text
    assert "categoryRowLabel" in response.text
    
    # Should not contain native category select
    assert '<select id="category"' not in response.text


def test_recetas_api_units_available(client: TestClient):
    """Test that units API endpoint is available and working."""
    response = client.get("/recetas/api/units")
    assert response.status_code == 200
    
    data = response.json()
    assert "results" in data
    assert "count" in data
    assert len(data["results"]) == 5  # g, kg, ml, l, und
    
    # Check all canonical units are present
    unit_values = [r["value"] for r in data["results"]]
    expected_units = [unit.value for unit in Unit]
    assert set(unit_values) == set(expected_units)


def test_inventory_form_structure(client: TestClient):
    """Test that inventory form has proper structure."""
    response = client.get("/inventario/nuevo")
    assert response.status_code == 200

    # Check for required form elements
    assert 'method="post"' in response.text
    assert 'action="/inventario/nuevo"' in response.text

    # Check for form rows
    assert '<div class="form-row">' in response.text
    assert response.text.count('<div class="form-row">') >= 3  # name, category, unit at minimum

    # Check for combo system integration
    assert "/static/combo.js" in response.text
    assert "/static/combobox.css" in response.text
