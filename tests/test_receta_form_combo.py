"""Tests for the recipe form combobox conversion (category picker + line items).

NOTE 2026-09-29: US 3.1 sub-recipe UI partially shipped. Inventory form
conversion (this file's last test) is done; recipe line conversion is
still pending.
"""

import pytest

# Inventory form conversion is SHIPPED. Recipe line conversion still pending.
_RECIPE_LINE_TESTS = {
    "test_receta_form_category_uses_combobox",
    "test_receta_form_line_uses_combobox_for_items",
    "test_receta_form_has_line_kind_switching_js",
    "test_receta_form_dynamic_line_creation",
}


def pytest_collection_modifyitems(config, items):
    """Mark only the not-yet-shipped recipe line tests as xfail."""
    for item in items:
        if item.name in _RECIPE_LINE_TESTS:
            item.add_marker(pytest.mark.xfail(
                reason="US 3.1 recipe line conversion still pending",
                strict=False,
            ))



def test_receta_form_category_uses_menu_tags_picker(qseed, authed_client):
    """/recetas/nueva categorization = menu_tags multi-picker
    (single-value family combo retired 2026-09-30)."""
    qseed("basic")
    r = authed_client.get("/recetas/nueva")
    assert r.status_code == 200
    body = r.text
    assert "saskia-combo" in body  # other combos (lines, scale) still exist
    assert 'name="menu_tags"' in body or "name='menu_tags'" in body
    assert "family_combo" not in body
    assert "categoryRowLabel" not in body
    # Old native input is gone
    assert '<input type="text" id="family" name="family"' not in body


def test_receta_form_line_uses_combobox_for_items(qseed, authed_client):
    """/recetas/nueva line items use combobox for ingredient/sub-recipe selection."""
    qseed("basic")
    r = authed_client.get("/recetas/nueva")
    assert r.status_code == 200
    body = r.text
    # Line combo markers
    assert "saskia-combo" in body
    assert "data-source=\"/inventario/api/search\"" in body
    # Dynamic line switching JS is present
    assert "updateLineSource" in body
    assert "recetas/api/search" in body  # JS code has this URL
    # Old selects are gone
    assert '<select name="line_target_id">' not in body


def test_receta_form_has_line_kind_switching_js(qseed, authed_client):
    """/recetas/nueva has JavaScript to handle line kind switching."""
    qseed("basic")
    r = authed_client.get("/recetas/nueva")
    assert r.status_code == 200
    body = r.text
    # JavaScript function that recomputes the item combo source when kind changes
    assert "updateLineSource" in body
    # Wiring helper that listens to combo selection events
    assert "wireLineKindHandlers" in body
    # Reads the line_kind value from the combo's hidden input (not a <select>)
    assert "kindHidden" in body


def test_receta_form_dynamic_line_creation(qseed, authed_client):
    """/recetas/nueva can add new lines dynamically with comboboxes."""
    qseed("basic")
    r = authed_client.get("/recetas/nueva")
    assert r.status_code == 200
    body = r.text
    # Add line button exists
    assert "id=\"add-line\"" in body
    # New line creation includes combo initialization
    assert "new SaskiaCombo" in body


def test_inventario_form_category_uses_combobox(qseed, authed_client):
    """/inventario/nuevo category picker is a combobox with creation support."""
    qseed("basic")
    r = authed_client.get("/inventario/nuevo")
    assert r.status_code == 200
    body = r.text
    # Combo markers for category
    assert "saskia-combo" in body
    assert "categoryRowLabel" in body
    assert "data-allow-create=\"true\"" in body
    # Old native input is gone
    assert '<input type="text" id="category" name="category">' not in body
