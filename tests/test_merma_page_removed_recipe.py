"""Tests that /merma page no longer renders the recipe-batch merma card.

The recipe card moved to /produccion (per-row quick-merma modal). /merma
now keeps only the ingredient card + summary + eventos log + a callout
pointing operators to /produccion for batch losses.
"""

from __future__ import annotations


def test_merma_does_not_render_recipe_form_card(authed_client):
    """/merma must not show the 'Merma de receta completa' <section>."""
    r = authed_client.get("/merma")
    assert r.status_code == 200
    body = r.text
    assert "Merma de receta completa" not in body, (
        "Recipe-card section still rendered on /merma — should be removed"
    )
    # Action URL for the old recipe form must not appear
    assert "/merma/receta" not in body, (
        "/merma/receta form action still wired in merma.html — should be removed"
    )


def test_merma_still_renders_ingredient_form(authed_client):
    """/merma must still show the ingredient merma form (the historical entry path)."""
    r = authed_client.get("/merma")
    body = r.text
    assert "Registrar merma de ingrediente" in body or "merma de ingrediente" in body.lower(), (
        "Ingredient merma card missing — must remain on /merma"
    )
    # Combobox endpoint for ingredients
    assert "/inventario/api/search" in body, "Ingredient combo endpoint missing"


def test_merma_has_callout_pointing_to_produccion(authed_client):
    """/merma must surface a callout that points operators to /produccion for batch loss."""
    r = authed_client.get("/merma")
    body = r.text
    assert "/produccion" in body, "/merma should link to /produccion for batch-loss entry"
    # Should mention both 'lote' or 'tanda' (batch) and the quick-merma trigger
    assert "lote" in body.lower() or "tanda" in body.lower(), (
        "Callout should reference batches/lotes"
    )
