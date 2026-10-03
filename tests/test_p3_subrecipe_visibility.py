"""P3 sub-recipe visibility: effective-ingredients API + merged_count.

- GET /recetas/api/{id}/effective-ingredients returns exploded raw lines
  with sources + merged_count.
- explode_recipe merged_count: duplicate ingredient lines (base + sub)
  sum into one row with merged_count > 1.
- Form renders the gray read-only panel (template markers).
"""

from __future__ import annotations

from tests.factories import ing_line, make_ingredient, make_recipe


def test_effective_ingredients_api_explodes_subrecipes(client, session_factory):
    with session_factory() as s:
        harina = make_ingredient(s, name="EffHarina UX", unit="kg")
        azucar = make_ingredient(s, name="EffAzucar UX", unit="kg")
        # Base recipe: masa madre uses harina + the sub-recipe "crema"
        crema = make_recipe(s, name="EffCrema UX", lines=[
            ing_line(ingredient=azucar, qty=0.5)])
        base = make_recipe(s, name="EffBase UX", lines=[
            ing_line(ingredient=harina, qty=1.0)])
        # add sub-recipe line directly (make_sub_line spec)
        from app.rms.models import RecipeLine
        s.add(RecipeLine(
            recipe_id=base.id, line_kind="sub_recipe", line_ref_id=crema.id,
            qty=1.0, line_unit="und",
        ))
        s.commit()
        rid = base.id

    r = client.get(f"/recetas/api/{rid}/effective-ingredients")
    assert r.status_code == 200
    data = r.json()
    names = {ln["name"]: ln for ln in data["lines"]}
    assert "EffHarina UX" in names
    az = names["EffAzucar UX"]
    # sub contributed: qty scaled by 1.0 / crema_yield
    assert az["sources"], "azucar should trace to the sub-recipe"
    assert any("EffCrema UX" in s for s in az["sources"])
    # base lines have no sources
    assert names["EffHarina UX"]["sources"] == []


def test_effective_ingredients_merges_duplicates(client, session_factory):
    with session_factory() as s:
        harina = make_ingredient(s, name="MergeHarina UX", unit="kg")
        sub = make_recipe(s, name="MergeSub UX", lines=[
            ing_line(ingredient=harina, qty=0.4)])
        base = make_recipe(s, name="MergeBase UX", lines=[
            ing_line(ingredient=harina, qty=1.0)])
        from app.rms.models import RecipeLine
        s.add(RecipeLine(
            recipe_id=base.id, line_kind="sub_recipe", line_ref_id=sub.id,
            qty=1.0, line_unit="und",
        ))
        s.commit()
        rid = base.id
    r = client.get(f"/recetas/api/{rid}/effective-ingredients")
    lines = r.json()["lines"]
    harina_rows = [ln for ln in lines if ln["name"] == "MergeHarina UX"]
    assert len(harina_rows) == 1, "duplicates merge into ONE row"
    row = harina_rows[0]
    assert row["merged_count"] >= 2, f"expected merged_count>=2, got {row}"
    assert row["qty"] > 1.0, "qty = base + sub contribution"


def test_effective_ingredients_unknown_recipe_empty(client):
    r = client.get("/recetas/api/999999/effective-ingredients")
    assert r.status_code == 200
    assert r.json()["lines"] == []


def test_form_renders_effective_panel(client, session_factory):
    with session_factory() as s:
        rec = make_recipe(s, name="EffPanel Recipe UX")
        s.commit()
        rid = rec.id
    r = client.get(f"/recetas/{rid}/editar")
    assert r.status_code == 200
    body = r.text
    assert "effective-ingredients-panel" in body
    assert "Ingredientes efectivos" in body
    assert "effective-ingredients" in body  # API URL in the JS


def test_detail_consolidada_shows_merged_badge(client, session_factory):
    with session_factory() as s:
        harina = make_ingredient(s, name="BadgeHarina UX", unit="kg")
        sub = make_recipe(s, name="BadgeSub UX", lines=[
            ing_line(ingredient=harina, qty=0.4)])
        base = make_recipe(s, name="BadgeBase UX", lines=[
            ing_line(ingredient=harina, qty=1.0)])
        from app.rms.models import RecipeLine
        s.add(RecipeLine(
            recipe_id=base.id, line_kind="sub_recipe", line_ref_id=sub.id,
            qty=1.0, line_unit="und",
        ))
        s.commit()
        rid = base.id
    r = client.get(f"/recetas/{rid}?vista=consolidada")
    assert r.status_code == 200
    assert "sumadas" in r.text
