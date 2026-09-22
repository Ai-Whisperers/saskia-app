"""Tests for the recipe search API and the line_target_id combobox
on /recetas/nueva + /recetas/{id}/editar.
"""

import pytest


# ─────────────────────────────────────────────────────────────────────
# Recipe search API (used by sub-recipe picker)
# ─────────────────────────────────────────────────────────────────────


def test_recipes_api_search_returns_matches(qseed, authed_client):
    """/recetas/api/search?q=muffin returns matching recipes."""
    from app.rms.models import Recipe
    sf = qseed.session_factory
    with sf() as s:
        s.add(Recipe(name="Muffin receta", yield_qty=12, yield_unit="und"))
        s.add(Recipe(name="Muffin especial", yield_qty=10, yield_unit="und"))
        s.add(Recipe(name="Torta vainilla", yield_qty=8, yield_unit="und"))
        s.commit()

    r = authed_client.get("/recetas/api/search?q=muffin")
    assert r.status_code == 200
    body = r.json()
    names = [item["name"] for item in body["results"]]
    assert "Muffin receta" in names
    assert "Muffin especial" in names
    assert "Torta vainilla" not in names  # wouldn't match


def test_recipes_api_search_exclude_id(qseed, authed_client):
    """/recetas/api/search?exclude_id=X omits recipe X (for sub-recipe circular prevention)."""
    from app.rms.models import Recipe
    sf = qseed.session_factory
    with sf() as s:
        r1 = Recipe(name="Masa choux", yield_qty=4, yield_unit="und")
        r2 = Recipe(name="Croissant", yield_qty=12, yield_unit="und")
        s.add_all([r1, r2])
        s.commit()
        r1_id = r1.id
        r2_id = r2.id

    # Without exclude: both returned
    r = authed_client.get("/recetas/api/search?q=")
    body = r.json()
    ids = [item["id"] for item in body["results"]]
    assert r1_id in ids
    assert r2_id in ids

    # Exclude r1: only r2 returned
    r = authed_client.get(f"/recetas/api/search?exclude_id={r1_id}")
    body = r.json()
    ids = [item["id"] for item in body["results"]]
    assert r1_id not in ids
    assert r2_id in ids


def test_recipes_api_search_empty_query_lists_all(qseed, authed_client):
    """Empty query returns all (up to limit)."""
    from app.rms.models import Recipe
    sf = qseed.session_factory
    with sf() as s:
        for i in range(15):
            s.add(Recipe(name=f"Receta {i}", yield_qty=10, yield_unit="und"))
        s.commit()

    r = authed_client.get("/recetas/api/search?q=")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 15


def test_recipes_api_search_result_shape(qseed, authed_client):
    """Each result includes id, name, yield_qty, yield_unit."""
    from app.rms.models import Recipe
    sf = qseed.session_factory
    with sf() as s:
        s.add(Recipe(name="TestRec", yield_qty=12, yield_unit="und"))
        s.commit()

    r = authed_client.get("/recetas/api/search?q=TestRec")
    body = r.json()
    item = body["results"][0]
    for key in ("id", "name", "yield_qty", "yield_unit"):
        assert key in item, f"missing {key}"


# ─────────────────────────────────────────────────────────────────────
# receta_form.html uses comboboxes for line_target_id
# ─────────────────────────────────────────────────────────────────────


def test_receta_form_nueva_uses_combobox(qseed, authed_client):
    """/recetas/nueva line picker is a combobox, not a native <select>."""
    qseed("basic")
    r = authed_client.get("/recetas/nueva")
    assert r.status_code == 200
    body = r.text
    # Generic combo markers
    assert "saskia-combo" in body
    assert "line-target-combo" in body
    assert "line-kind-select" in body
    # Combobox wired to API endpoints via data-source
    assert 'data-source="/inventario/api/search"' in body
    # Component scripts served
    assert "receta-combos.js" in body


def test_receta_form_nueva_javascript_served(client):
    """/static/receta-combos.js + /static/combo.js serve."""
    r1 = client.get("/static/receta-combos.js")
    assert r1.status_code == 200
    assert b"attachLineTargetCombo" in r1.content
    r2 = client.get("/static/combo.js")
    assert r2.status_code == 200
    r3 = client.get("/static/combobox.css")
    assert r3.status_code == 200


def test_receta_form_no_legacy_select_for_target(qseed, authed_client):
    """The line_target_id native <select> is gone from /recetas/nueva."""
    qseed("basic")
    r = authed_client.get("/recetas/nueva")
    body = r.text
    # New lines have empty {{ lines }} so the for loop emits nothing.
    # But the inline "+ Agregar línea" JS template must not include
    # any native <select name="line_target_id"> either.
    assert '<select name="line_target_id">' not in body


def test_receta_form_edit_loads_with_target_names(qseed, authed_client):
    """/recetas/{id}/editar prefills combobox with target name (resolved)."""
    from app.rms.models import Recipe, RecipeLine, Ingredient
    sf = qseed.session_factory
    with sf() as s:
        ing = s.query(Ingredient).first()
        if ing is None:
            ing = Ingredient(name="harina QA", unit="kg", stock_qty=10,
                              min_stock_qty=1, purchase_price_gs=3000)
            s.add(ing); s.flush()
        r = Recipe(name="RecetaEdit", yield_qty=10, yield_unit="und")
        s.add(r); s.flush()
        s.add(RecipeLine(recipe_id=r.id, line_kind="ingredient",
                         line_ref_id=ing.id, qty=0.5, line_unit="kg"))
        s.commit()
        rid = r.id

    r = authed_client.get(f"/recetas/{rid}/editar")
    assert r.status_code == 200
    body = r.text
    assert "harina QA" in body  # pre-filled in combobox input
    assert 'value="' + str(ing.id) + '"' in body  # hidden line_target_id


def test_receta_form_edit_sub_recipe_with_exclude(qseed, authed_client):
    """Edit-page sub-recipe picker excludes self (no circular sub-recipes).

    Renders one sub_recipe line so the data-source actually appears in HTML.
    """
    from app.rms.models import Recipe, RecipeLine
    sf = qseed.session_factory
    parent_id = None
    child_id = None
    with sf() as s:
        parent = Recipe(name="Parent", yield_qty=8, yield_unit="und")
        s.add(parent); s.flush()
        child = Recipe(name="Child Recipes A", yield_qty=4, yield_unit="und")
        s.add(child); s.flush()
        sub_recipe_line = RecipeLine(
            recipe_id=parent.id,
            line_kind="sub_recipe",
            line_ref_id=child.id,
            qty=0.5,
            line_unit="kg",
        )
        s.add(sub_recipe_line)
        s.commit()
        parent_id = parent.id
        child_id = child.id

    r = authed_client.get(f"/recetas/{parent_id}/editar")
    body = r.text
    # The data-source URL must include the recipe id as exclude_id
    assert "/recetas/api/search" in body
    assert "exclude_id=" + str(parent_id) in body
    # The hidden line_target_id should be the child's id
    # (proves the server-side render resolves the target)
    assert (
        f'name="line_target_id" value="{child_id}"' in body
        or f'name="line_target_id" value=\\"{child_id}\\"' in body
    )
