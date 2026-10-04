"""Regression: /recetas/<id> must render ingredient table + cost + instructions.

Guards against the 2026-09-29 production regression where every recipe
detail page returned a 200 with no ingredient table, no real cost, and
the placeholder "Secuencia Completa" — caused by `Recipe.instructions`
being added to the ORM (`app/rms/models_legacy.py`) without a matching
`ALTER TABLE recipe ADD COLUMN instructions TEXT` migration. Every
Recipe SELECT crashed; the route handler swallowed it and rendered empty
context.

The tests below seed the recipes/ingredients/recipe_lines/instructions
via the production seed helper, then assert the page renders the
ingredient table, a non-zero cost, and the seeded instructions phases.
The seed helper is invoked here (not via the script) so the test is
self-contained and doesn't depend on the live DB path.
"""

import json

import pytest

# --- Inline seed data: a 6-line apple pie with priced catalog rows ---

_INGREDIENT_FIXTURES = [
    # (id, name, unit, purchase_price_gs, allergens)
    (1, "harina", "kg", 4500, "gluten"),
    (2, "azúcar", "kg", 5200, ""),
    (11, "manteca", "kg", 32000, "dairy"),
    (15, "huevos", "und", 600, "eggs"),
    (20, "canela molida", "g", 50, ""),
    (27, "frutillas", "kg", 22000, ""),
]

_RECIPE_FIXTURE = {
    "id": 6,
    "name": "appeltaart",
    "yield_qty": 8.0,
    "yield_unit": "und",
    "prep_minutes": 40,
    "cook_minutes": 40,
    "difficulty": 2,
    "family": "pastelería",
    "dietary_tags": "",
    "notes": "Tarta de manzanas tradicional.",
    "instructions": json.dumps(
        [
            {
                "phase": "Sub-receta",
                "title": "Relleno de manzana",
                "steps": [
                    "Peyá y fileteá las manzanas en láminas finas.",
                    "Mezclá con azúcar, canela y unas gotas de limón.",
                    "Reservá 15 minutos para que largue jugo.",
                ],
            },
            {
                "phase": "Base",
                "title": "Masa brisée",
                "steps": [
                    "Mezclá la harina con la manteca fría hasta formar un arenado.",
                    "Agregá el azúcar y los huevos; uní sin trabajar de más.",
                ],
            },
            {
                "phase": "Ensamblaje",
                "title": "Tarta de manzanas",
                "steps": [
                    "Disponé las láminas de manzana sobre la masa en forma concéntrica.",
                    "Cubrí con tiras de masa formando un enrejado con el resto.",
                    "Horneá a 200 °C durante 35 a 40 minutos hasta dorar.",
                ],
            },
        ],
        ensure_ascii=False,
    ),
}

_RECIPE_LINE_FIXTURES = [
    # (line_id, recipe_id, line_kind, line_ref_id, qty, line_unit)
    (1, 6, "ingredient", 1, 0.4, "kg"),
    (2, 6, "ingredient", 11, 0.2, "kg"),
    (3, 6, "ingredient", 2, 0.25, "kg"),
    (4, 6, "ingredient", 15, 2.0, "und"),
    (5, 6, "ingredient", 20, 5.0, "g"),
    (6, 6, "ingredient", 27, 0.4, "kg"),
]


@pytest.fixture
def seeded_recipe_6(session_factory):
    """Seed recipe 6 + its 6 ingredients + recipe_lines + instructions JSON."""
    from app.rms.models import Ingredient, Recipe, RecipeLine, TagLink
    from app.rms.tags import ensure_tag

    with session_factory() as s:
        for iid, iname, iunit, iprice, iallergens in _INGREDIENT_FIXTURES:
            s.add(
                Ingredient(
                    id=iid,
                    name=iname,
                    unit=iunit,
                    purchase_price_gs=iprice,
                    allergens=(iallergens or None),
                    stock_qty=10.0,
                    min_stock_qty=1.0,
                )
            )
        s.add(Recipe(**_RECIPE_FIXTURE))
        for lid, rid, lkind, lref, lqty, lunit in _RECIPE_LINE_FIXTURES:
            s.add(
                RecipeLine(
                    id=lid,
                    recipe_id=rid,
                    line_kind=lkind,
                    line_ref_id=lref,
                    qty=lqty,
                    line_unit=lunit,
                )
            )
        s.commit()

        # Seed tag_link rows so derived_tags has a non-empty intersection
        # target — otherwise the detail page renders all-✅ vacuously.
        gluten_tag = ensure_tag(s, "alergeno-gluten", "ingredient", "#ff6f00")
        dairy_tag = ensure_tag(s, "alergeno-lactosa", "ingredient", "#ff6f00")
        eggs_tag = ensure_tag(s, "con-huevo", "ingredient", "#ff6f00")
        # harina → gluten, manteca → dairy, huevos → eggs
        s.add_all(
            [
                TagLink(tag_id=gluten_tag.id, target_kind="ingredient", target_id=1),
                TagLink(tag_id=dairy_tag.id, target_kind="ingredient", target_id=11),
                TagLink(tag_id=eggs_tag.id, target_kind="ingredient", target_id=15),
            ]
        )
        # Recipe 6 inherits: gluten, dairy, eggs
        s.add_all(
            [
                TagLink(tag_id=gluten_tag.id, target_kind="recipe", target_id=6),
                TagLink(tag_id=dairy_tag.id, target_kind="recipe", target_id=6),
                TagLink(tag_id=eggs_tag.id, target_kind="recipe", target_id=6),
            ]
        )
        s.commit()

        # Run cascade_refresh so recipe.allergens/derived_dietary_tags caches populate
        from app.rms.tag_algebra import cascade_refresh

        try:
            cascade_refresh(s, recipe_id=6)
            s.commit()
        except Exception:
            s.rollback()

    return {"recipe_id": 6}


# --- Tests ---


def test_receta_6_renders_200(client, seeded_recipe_6):
    """Sanity: page is reachable and returns HTML."""
    r = client.get("/recetas/6")
    assert r.status_code == 200
    assert (
        "appeltaart" in r.text.lower()
        or "apple pie" in r.text.lower()
        or "receta" in r.text.lower()
    )


def test_receta_6_shows_ingredient_table(client, seeded_recipe_6):
    """The 'Ingredientes y sub-recetas' card must be present (was missing)."""
    body = client.get("/recetas/6").text
    assert "Ingredientes y sub-recetas" in body


def test_receta_6_lists_all_six_ingredients(client, seeded_recipe_6):
    """Each ingredient from recipe 6 must appear in the rendered HTML."""
    body = client.get("/recetas/6").text
    for ing in ("harina", "manteca", "azúcar", "huevos", "canela molida", "frutillas"):
        assert ing in body, f"missing ingredient: {ing}"


def test_receta_6_cost_is_non_zero(client, seeded_recipe_6):
    """Costo del lote must be a real number, not Gs. 0 (price engine works)."""
    import re

    body = client.get("/recetas/6").text
    i = body.find("Costo del lote")
    assert i > 0, "Costo del lote label not found"
    snippet = body[i : i + 400]
    m = re.search(r'class="metric-value">\s*([^<]+?)\s*</div>', snippet)
    assert m is not None, "Costo del lote metric-value not found"
    val = m.group(1).strip()
    assert val.startswith("Gs."), f"unexpected format: {val!r}"
    assert val != "Gs. 0", f"cost is zero — ingredient prices missing: {val!r}"


def test_receta_6_instructions_section_renders(client, seeded_recipe_6):
    """Secuencia Completa must be present (was showing placeholder before)."""
    body = client.get("/recetas/6").text
    assert "Secuencia Completa de Preparación" in body


def test_receta_6_instructions_have_phases(client, seeded_recipe_6):
    """The seeded JSON phases (sub-receta → base → ensamble) must render."""
    body = client.get("/recetas/6").text
    assert "Relleno de manzana" in body, "Sub-receta phase title not rendered"
    assert "Masa brisée" in body, "Base phase title not rendered"
    assert "Tarta de manzanas" in body, "Ensamblaje phase title not rendered"


def test_receta_6_derived_tags_present(client, seeded_recipe_6):
    """Derived dietary tags must be computed (no longer all-✅ vacuous)."""
    body = client.get("/recetas/6").text
    assert "Etiquetas derivadas" in body
    # With tag_links seeded, derivation lists the actual blocking ingredients
    assert "bloqueada por" in body


def test_receta_6_no_internal_errors_in_html(client, seeded_recipe_6):
    """The error-handler-rendered 200 must not leak stack traces."""
    body = client.get("/recetas/6").text
    assert "OperationalError" not in body
    assert "no such column" not in body
    assert "Traceback" not in body


def test_recipe_pages_no_500(client, seeded_recipe_6):
    """The detail route must NEVER return 500, even if data is sparse."""
    r = client.get("/recetas/6")
    assert r.status_code != 500
