"""Test merma combo API endpoints."""

import pytest
from fastapi.testclient import TestClient
from app.rms.waste import WasteReason
from app.rms.units import Unit


def test_recipes_api_search(client: TestClient):
    """Test recipe search API endpoint."""
    response = client.get("/recetas/api/search?q=muffin&limit=5")
    assert response.status_code == 200
    
    data = response.json()
    assert "results" in data
    assert "count" in data
    assert isinstance(data["results"], list)


def test_recipes_api_units(client: TestClient):
    """Test units API endpoint."""
    response = client.get("/recetas/api/units")
    assert response.status_code == 200
    
    data = response.json()
    assert "results" in data
    assert "count" in data
    assert isinstance(data["results"], list)
    
    # Should have all canonical units
    unit_values = [r["value"] for r in data["results"]]
    expected_units = [unit.value for unit in Unit]
    assert set(unit_values) == set(expected_units)


def test_merma_api_reasons(client: TestClient):
    """Test waste reasons API endpoint."""
    response = client.get("/merma/api/reasons")
    assert response.status_code == 200
    
    data = response.json()
    assert "results" in data
    assert "count" in data
    assert isinstance(data["results"], list)
    
    # Should have all waste reasons
    reason_values = [r["value"] for r in data["results"]]
    expected_reasons = [reason.value for reason in WasteReason]
    assert set(reason_values) == set(expected_reasons)


def test_combo_row_label_recipe(client: TestClient):
    """Test that recipeSearchRowLabel function is available in combo-rows.js."""
    response = client.get("/static/combo-rows.js")
    assert response.status_code == 200
    
    # Check for the recipe row builder function
    assert "window.recipeSearchRowLabel" in response.text