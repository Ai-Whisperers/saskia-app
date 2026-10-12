"""SASKIA-212: recipe.instructions field on ORM + structured editor on the form.

The Recipe model in `app/rms/models_legacy.py` (the one the route uses)
declares `instructions` as a TEXT column for JSON phase storage. The
form template, however, had no editor for it — so every recipe fell
through to the placeholder "Secuencia Completa" text. Operators had
no way to write the real procedure.

SASKIA-212 adds:
1. Parsing the `instructions` field on POST (route + form helpers).
2. Persisting it in `_update_recipe_fields` and `_create_recipe_record`.
3. A free-form textarea in the form template, preloaded from
   `r.instructions` if present.
4. The detail template already renders `_parse_recipe_phases` when
   present, so the data flows through automatically.
"""

import json
from decimal import Decimal

from app.rms.models import Ingredient, Recipe, RecipeLine

# ── 1. Model has the instructions field ─────────────────────────────


def test_recipe_model_has_instructions_field():
    """The Recipe ORM model must expose an `instructions` attribute."""
    from sqlalchemy import inspect

    mapper = inspect(Recipe)
    cols = {c.key for c in mapper.columns}
    assert "instructions" in cols, (
        f"Recipe model missing 'instructions' field. columns: {sorted(cols)}"
    )


# ── 2. Form parses + persists + renders instructions JSON ───────────


_RECIPE_EDIT_FORM_FIXTURE = {
    "name": "SASKIA-212 fixture__rec_X",
    "yield_qty": "10",
    "yield_unit": "und",
    "notes": "",
    "prep_minutes": "20",
    "cook_minutes": "15",
    "difficulty": "2",
    "family": "",
    "menu_tags": "",
    "dietary_tags": "",
    # One ingredient line so _count_valid_lines returns >= 1. The route
    # expects the line_kind / line_target_id / line_qty fields to be
    # POSTed as multi-value form fields (getlist), so the seed function
    # below patches these in with the real ingredient id.
    "line_kind": "__INGREDIENT_ID__",
    "line_target_id": "__INGREDIENT_ID__",
    "line_qty": "500",
    "line_unit": "g",
    "instructions": json.dumps(
        [
            {
                "phase": "Masa",
                "title": "Base",
                "steps": ["Paso 1", "Paso 2"],
            },
            {
                "phase": "Horneado",
                "title": "Cocción",
                "steps": ["Paso A"],
            },
        ]
    ),
}


def _build_payload(session_factory, name: str, instructions: str) -> dict:
    """Build a POST payload with a real ingredient id in the line."""
    from app.rms.models import Ingredient as Ing

    ing_name = f"Harina 000 SASKIA-212 {name}"
    with session_factory() as s:
        ing = s.query(Ing).filter_by(name=ing_name).one()
        ing_id = str(ing.id)
    payload = dict(_RECIPE_EDIT_FORM_FIXTURE)
    payload["name"] = name
    payload["line_kind"] = "ingredient"
    payload["line_target_id"] = ing_id
    payload["line_qty"] = "500"
    payload["instructions"] = instructions
    return payload


_seed_name_map: dict[str, str] = {}


def _find_recipe_seed_name(recipe_name: str) -> str:
    return _seed_name_map.get(recipe_name, recipe_name)


def _seed_minimal_recipe(session_factory, name: str) -> int:
    """Insert a minimal Recipe row + one ingredient line so POST validates."""
    with session_factory() as s:
        ing = Ingredient(
            name=f"Harina 000 SASKIA-212 {name}",
            unit="g",
            purchase_price_gs=8500,
        )
        s.add(ing)
        s.flush()
        r = Recipe(name=name, yield_qty=10.0, yield_unit="und")
        s.add(r)
        s.flush()
        line = RecipeLine(
            recipe_id=r.id,
            line_kind="ingredient",
            line_ref_id=ing.id,
            qty=Decimal("500"),
            line_unit="g",
        )
        s.add(line)
        s.commit()
        return r.id


def test_recipe_form_persists_instructions(client, session_factory):
    """POSTing instructions via /recetas/{id}/editar must persist them."""
    rid = _seed_minimal_recipe(session_factory, "SASKIA-212 a__rec_X")
    payload = _build_payload(
        session_factory,
        "SASKIA-212 a__rec_X",
        _RECIPE_EDIT_FORM_FIXTURE["instructions"],
    )
    r = client.post(f"/recetas/{rid}/editar", data=payload, follow_redirects=True)
    assert r.status_code == 200, f"POST failed: {r.status_code} {r.text[:200]}"
    # Verify the row now has the instructions
    with session_factory() as s:
        row = s.get(Recipe, rid)
        assert row.instructions is not None, "instructions not persisted"
        phases = json.loads(row.instructions)
        assert len(phases) == 2
        assert phases[0]["title"] == "Base"
        assert phases[0]["steps"] == ["Paso 1", "Paso 2"]


def test_recipe_form_persists_freeform_instructions(client, session_factory):
    """Free-form text is wrapped into a single phase and persisted."""
    rid = _seed_minimal_recipe(session_factory, "SASKIA-212 a2__rec_X")
    payload = _build_payload(
        session_factory,
        "SASKIA-212 a2__rec_X",
        "Paso uno: mezclar.\nPaso dos: hornear.",
    )
    r = client.post(f"/recetas/{rid}/editar", data=payload, follow_redirects=True)
    assert r.status_code == 200, f"POST failed: {r.status_code} {r.text[:200]}"
    with session_factory() as s:
        row = s.get(Recipe, rid)
        assert row.instructions is not None
        phases = json.loads(row.instructions)
        assert len(phases) >= 1
        assert "Paso uno" in phases[0]["steps"][0]


def test_recipe_detail_renders_instructions(client, session_factory):
    """/recetas/{id} must render the steps from recipe.instructions."""
    rid = _seed_minimal_recipe(session_factory, "SASKIA-212 b__rec_X")
    # Persist instructions via the route
    payload = _build_payload(
        session_factory,
        "SASKIA-212 b__rec_X",
        _RECIPE_EDIT_FORM_FIXTURE["instructions"],
    )
    r = client.post(f"/recetas/{rid}/editar", data=payload, follow_redirects=True)
    assert r.status_code == 200
    # Now fetch the detail
    r = client.get(f"/recetas/{rid}")
    assert r.status_code == 200
    body = r.text
    # The detail template renders phase.title as the section heading.
    assert "Base" in body, "phase title 'Base' not in detail page"
    assert "Cocci" in body, "phase title 'Cocción' not in detail page"
    assert "Paso 1" in body, "first step text not in detail page"
    assert "Paso A" in body, "second phase step not in detail page"


# ── 3. Form GET exposes the editor ──────────────────────────────────


def test_recipe_form_renders_instructions_editor(client, session_factory):
    """The edit form must include a steps editor (textarea + preloaded text)."""
    rid = _seed_minimal_recipe(session_factory, "SASKIA-212 c__rec_X")
    # Pre-seed some instructions
    with session_factory() as s:
        row = s.get(Recipe, rid)
        row.instructions = json.dumps(
            [{"phase": "P1", "title": "T1", "steps": ["s1", "s2"]}], ensure_ascii=False
        )
        s.commit()
    r = client.get(f"/recetas/{rid}/editar")
    assert r.status_code == 200
    body = r.text
    # The new "Pasos / Procedimiento" section is present.
    assert "Pasos / Procedimiento" in body, (
        f"recipe form missing Pasos / Procedimiento section. body sample: {body[:3000]}"
    )
    # The seeded instructions are preloaded as free-form text (one step
    # per line) in the textarea — not as raw JSON.
    assert "s1" in body and "s2" in body, (
        "seeded instructions not preloaded into the form's steps editor"
    )


# ── 4. Empty instructions still renders the page (no 500) ──────────


def test_recipe_detail_handles_null_instructions(client, session_factory):
    """A recipe with NULL instructions must still render (the placeholder)."""
    rid = _seed_minimal_recipe(session_factory, "SASKIA-212 d__rec_X")
    r = client.get(f"/recetas/{rid}")
    assert r.status_code == 200


# ── 5. All live recipes render without 500 ─────────────────────────


def test_all_recipes_render_200(client, session_factory):
    """Every recipe in the DB must render /recetas/{id} with 200."""
    with session_factory() as s:
        ids = [row[0] for row in s.query(Recipe.id).all()]
    for rid in ids:
        r = client.get(f"/recetas/{rid}")
        assert r.status_code == 200, f"recipe {rid} returned {r.status_code}"
