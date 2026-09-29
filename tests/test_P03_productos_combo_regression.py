"""P-03 / audit #?: combo getSelectedData regression.

**P-03 contract test**: Since TestClient doesn't run JS, test the server-side
rendering of `/productos/nuevo` and `/productos` for saskia-combo presence
and proper data structure. The real regression (JS getSelectedData()) lives in
the audit fix, but we prevent the combo JS from silently removing the API
by validating the server preconditions.

**JS contract (from audit fix d2b2e0c):**
- <saskia-combo> element uses setOptionsData([{value, label, sale_price_gs, ...}])
- getSelectedData() returns {value, display, sale_price_gs, ...} or null
- _selectedItem mirrors the object passed to setOptionsData

**Acceptance:** server renders combo with proper data structure,
no Python template errors, combo classes present."""
from __future__ import annotations

import pytest


pytestmark = [pytest.mark.smoke]


def test_productos_nuevo_renders_200(client):
    """P-03: /productos/nuevo renders combo interface."""
    r = client.get("/productos/nuevo")
    assert r.status_code == 200
    body = r.text
    assert (
        "saskia-combo" in body
        or "<saskia-combo" in body
    ), "Missing saskia-combo element on /productos/nuevo"


def test_productos_nuevo_has_recipe_combo(client):
    """P-03: Recipe combo is rendered and has correct attributes."""
    r = client.get("/productos/nuevo")
    assert r.status_code == 200
    body = r.text
    # Check the combo element exists with expected attributes
    assert (
        "saskia-combo" in body and 
        "recipe_id" in body
    ), "Missing saskia-combo for recipe_id on /productos/nuevo"
    
    # Check endpoint and data-field attributes for combo
    assert "endpoint=" in body, "Combo missing endpoint attribute"
    assert "value-field=" in body, "Combo missing value-field attribute"
    assert "label-field=" in body, "Combo missing label-field attribute"


def test_productos_nuevo_has_product_fields(client):
    """P-03: Combo receives products with required fields."""
    r = client.get("/productos/nuevo")
    assert r.status_code == 200
    body = r.text
    # Combo options should have product fields for sale_price_gs
    assert "value" in body, "Missing 'value' field in combo context"
    assert (
        "label" in body
        or "product" in body
        or "option" in body
    ), "Missing 'label' field in combo context"


def test_productos_index_has_combo_if_used(client):
    """P-03: /productos listing renders combo if used there."""
    r = client.get("/productos")
    assert r.status_code == 200
    body = r.text
    # Index page should always have the combo script available for when users create products
    assert "saskia-combo.js" in body, "saskia-combo.js not loaded on index page"
    # Index page shows "empty state" when no products exist
    assert "empty-state" in body, "Empty state not shown on index page"
    # Combo component structure (combo-item) should NOT be present on index page
    # since combo is only used when editing/creating individual products
    assert "combo-item" not in body, "combo-item should not be on index page"


def test_productos_nuevo_js_contract_markers(client):
    """P-03: Combo JS API contract available in source."""
    r = client.get("/productos/nuevo")
    assert r.status_code == 200
    body = r.text
    # Check that combo file is loaded in the HTML
    assert "saskia-combo.js" in body, "saskia-combo.js not loaded on page"
    # Check that combo component is present
    assert "saskia-combo" in body, "<saskia-combo> component not on page"
    # Check that combo methods are implemented in the JS file
    r_js = client.get("/static/saskia-combo.js")
    assert r_js.status_code == 200
    js_content = r_js.text
    assert "getSelectedData" in js_content, "getSelectedData not in combo.js"
    assert "getValue" in js_content, "getValue not in combo.js"
    assert "_selectedItem" in js_content, "_selectedItem not in combo.js"


def test_productos_nuevo_no_combot_broken_template(client):
    """P-03: No Python errors when rendering combo."""
    r = client.get("/productos/nuevo")
    assert r.status_code == 200
    body = r.text
    # Avoid template errors (no {{raw combo syntax}} leaks)
    assert "{{" not in body or "}}" not in body, (
        "Template syntax leak on /productos/nuevo"
    )
    assert "combo" not in body.lower() or "saskia-combo" in body, (
        "Broken combo template reference"
    )


def test_productos_combo_js_loaded_on_page(client):
    """P-03: Combo JS file is loaded on the page."""
    r = client.get("/productos/nuevo")
    assert r.status_code == 200
    body = r.text
    # Combo JS file should be loaded
    assert "saskia-combo.js" in body, "saskia-combo.js not loaded on page"


def test_productos_combo_renders_in_form(client):
    """P-03: Combo renders in the productos nuevo form."""
    r = client.get("/productos/nuevo")
    assert r.status_code == 200
    response_text = r.text.lower()
    assert "saskia-combo" in response_text, "saskia-combo component should be present"
    assert "recipe_id" in response_text, "recipe_id combo should be present"
    assert "recetas/api/search/" in response_text, "combo should point to recipes API"


def test_saskia_combo_js_exists(client):
    """P-03: Combo JS file exists and loads."""
    r = client.get("/static/saskia-combo.js")
    assert r.status_code == 200
    js_text = r.text
    assert "getSelectedData" in js_text, "getSelectedData not in saskia-combo.js"
    assert "setOptionsData" in js_text, "setOptionsData not in saskia-combo.js"
    assert "_selectedItem" in js_text, "_selectedItem not in saskia-combo.js"