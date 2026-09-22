"""Tests for the /productos form combobox conversion (recipe picker)."""

import pytest


def test_producto_form_uses_combobox_for_recipe(qseed, authed_client):
    """/productos/nuevo recipe picker is a combobox (not 12+ recipe <select>)."""
    qseed("basic")
    r = authed_client.get("/productos/nuevo")
    assert r.status_code == 200
    body = r.text
    # Combobox markers
    assert "saskia-combo" in body
    assert "recipe_combo" in body
    # Old 12+ <select> for recipes is gone
    assert '<select id="recipe_id" name="recipe_id">' not in body
    # Hidden input still exists (so recipe_id is submitted)
    assert 'name="recipe_id"' in body
