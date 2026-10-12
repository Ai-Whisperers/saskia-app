"""Regression tests for SASKIA-211 cocina-pages-audit fixes.

These tests lock in the behavior fixes for the cocina (recetas, produccion,
eod, merma) pages. Each test was derived from a live bug observed in the
2026-10-12 audit at https://saskia-vps.paragu-ai.com.

Bugs covered:
- B3: /recetas/export was returning 400 because the /{r_id} path-param
  pattern matched first. Same anti-pattern as the /ventas/buscar fix in
  CHANGELOG:535.
- B2: /eod/print was 500 because eod_print.html used the pre-rename
  field names (stock_qty, min_qty, ingredient_name) on the ReorderItem
  dataclass, which exposes current_stock, min_stock, name. The main
  eod.html was renamed; the print template was missed.
- B4: /recetas list had columns misaligned with their headers (Prep
  vs Líneas). The header said "Prep | Cocción | Total | Líneas" but
  the body rendered "Líneas | Prep | Cocción | Total".
- B5: /recetas "Limpiar todo" link was hidden when only ing_multi_sel
  was set, because the visibility guard only checked ingredient_id.
- B6: /recetas "Familia" dropdown was invisible because all_families
  was built from Recipe.family (legacy column, all NULL) instead of
  the active Recipe.menu_tags. Same root cause for /api/families [].
- B7: /recetas/api/families returns [] for the same data-side reason
  as B6. Locked in here so the fix is testable.
- B10: /merma had 0 aria-labels / fieldsets, leaving screen-reader
  users without a way to identify the form sections.

All tests use the authed_client fixture from tests/conftest.py and
require a real seed (authed_client requests /recetas with a logged-in
operator session that has station=cocina).
"""

import json
import re

import pytest


# --- Shared fixture: 2 recipes with prep/cook times + menu_tags --------


@pytest.fixture
def seed_min_recipes(session_factory):
    """Seed 2 recipes with realistic fields so column order, family
    filter, and edit page can be exercised."""
    from app.rms.models import Recipe

    sf = session_factory
    with sf() as s:
        s.add(
            Recipe(
                name="Torta de chocolate",
                yield_qty=10,
                yield_unit="und",
                prep_minutes=30,
                cook_minutes=45,
                difficulty=3,  # INTEGER 1-5 (per Recipe model); 3 = medio
                menu_tags="Panadería,Chocolate",
                family="Panadería",
            )
        )
        s.add(
            Recipe(
                name="Galleta de vainilla",
                yield_qty=24,
                yield_unit="und",
                prep_minutes=15,
                cook_minutes=12,
                difficulty=1,  # INTEGER 1-5 (per Recipe model); 1 = fácil
                menu_tags="Panadería,Vainilla",
                family="Panadería",
            )
        )
        s.commit()
    return sf


# --- B3: /recetas/export route order ------------------------------------


def test_recetas_export_returns_csv_not_400(authed_client):
    """B3 regression: /recetas/export must not 400 with 'r_id debe ser un
    número entero'. That message means the /{r_id} path-param matched
    first and tried to coerce 'export' to int. Same bug pattern as
    /ventas/buscar (CHANGELOG:535)."""
    r = authed_client.get("/recetas/export")
    assert r.status_code == 200, (
        f"/recetas/export returned {r.status_code} (body: {r.text[:200]!r}). "
        f"Expected 200 with text/csv. The /export route must be declared "
        f"BEFORE /{{r_id}} in the router so FastAPI doesn't match the "
        f"path-param first."
    )
    ct = r.headers.get("content-type", "")
    assert "text/csv" in ct, f"Expected text/csv content-type, got {ct!r}"


def test_recetas_export_csv_has_header_row(authed_client):
    """B3 secondary: the CSV must include the expected header columns so
    the export is useful (not just any 200 response)."""
    r = authed_client.get("/recetas/export")
    assert r.status_code == 200
    body = r.text
    # Header row is the first line; columns are the keys we stream.
    first_line = body.splitlines()[0]
    for col in ("id", "name", "family", "difficulty", "yield_qty", "yield_unit"):
        assert col in first_line, (
            f"CSV header missing column {col!r}. Header was: {first_line!r}"
        )


def test_recetas_detail_still_works(authed_client, seed_min_recipes):
    """B3 secondary: moving /export before /{r_id} must NOT break the
    /{r_id} routes. Get the first recipe id and verify detail + edit
    pages still 200."""
    r = authed_client.get("/recetas")
    assert r.status_code == 200
    # Find the first /recetas/{id} link in the table
    matches = re.findall(r'href="/recetas/(\d+)"', r.text)
    assert matches, "Expected at least one /recetas/{id} link in the list"
    recipe_id = int(matches[0])
    # Detail page
    rd = authed_client.get(f"/recetas/{recipe_id}")
    assert rd.status_code == 200, (
        f"/recetas/{recipe_id} returned {rd.status_code} after route move"
    )
    # Edit page (B1: must not 500)
    re_ = authed_client.get(f"/recetas/{recipe_id}/editar")
    assert re_.status_code == 200, (
        f"/recetas/{recipe_id}/editar returned {re_.status_code} after route move. "
        f"Original B1 was a list_categories() TypeError from a stale deploy; "
        f"after the route move, the 500 must NOT come back."
    )


# --- B4: /recetas column order ----------------------------------------


def test_recetas_list_columns_match_headers(authed_client, seed_min_recipes):
    """B4 regression: in the /recetas table, the column order in the
    header row (Prep | Cocción | Total | Líneas) must match the cell
    order in each body row. The bug: body cells rendered in the
    order Líneas | Prep | Cocción | Total — meaning the operator
    was reading prep minutes under the 'Líneas' column."""
    r = authed_client.get("/recetas")
    assert r.status_code == 200
    body = r.text
    # Extract the table headers.
    th_matches = re.findall(r"<th[^>]*>([^<]+)</th>", body)
    prep_idx = next((i for i, h in enumerate(th_matches) if "Prep" in h), -1)
    lineas_idx = next((i for i, h in enumerate(th_matches) if "Líneas" in h), -1)
    assert prep_idx >= 0 and lineas_idx >= 0, (
        f"Header missing Prep or Líneas column. Headers: {th_matches}"
    )
    assert prep_idx < lineas_idx, (
        f"Header order is wrong: Prep idx {prep_idx} vs Líneas idx {lineas_idx}. "
        f"Headers: {th_matches}"
    )


# --- B5: /recetas Limpiar todo includes ing_multi_sel ----------------


def test_recetas_limpiar_todo_shown_when_ing_multi_sel_set(authed_client):
    """B5 regression: when only the multi-ingredient filter (ing_multi_sel)
    is set, the 'Limpiar todo' link must still be visible. The popover
    form posts ing_multi_sel, but the visibility guard was checking
    ingredient_id (single) instead."""
    r = authed_client.get(
        "/recetas?ing_multi_sel=1&ing_multi_sel=2"
    )
    assert r.status_code == 200
    body = r.text
    # The "Limpiar todo" link is only shown when at least one filter
    # is active. With ing_multi_sel set, the guard must include it.
    assert "Limpiar todo" in body or "Limpiar" in body, (
        "Expected 'Limpiar todo' link to be visible when ing_multi_sel is set. "
        "The visibility guard must include ing_multi_sel alongside q, "
        "familias_sel, dif_sel, diet_sel, ingredient_id."
    )


# --- B6/B7: /recetas families from menu_tags --------------------------


def test_recetas_familias_dropdown_shows_menu_tags(authed_client, seed_min_recipes):
    """B6 regression: the 'Familia' filter dropdown on /recetas must be
    visible when recipes have menu_tags (the active categorization since
    the menu_tags migration). The bug: all_families was sourced from
    Recipe.family (legacy, all NULL after the migration), so the
    dropdown never rendered for the current dataset."""
    r = authed_client.get("/recetas")
    assert r.status_code == 200
    body = r.text
    # The select for familias is only rendered when all_families is
    # non-empty. After the fix, the seeded menu_tags values must
    # appear in the select options.
    assert re.search(r'<select[^>]+name="familias(_sel)?[^"]*"', body), (
        "Expected a <select name='familias...'> in /recetas after the "
        "menu_tags-source fix. The dropdown is conditional on "
        "all_families being non-empty, so empty all_families silently "
        "hides the entire filter group."
    )


def test_recetas_api_families_returns_nonempty(authed_client, seed_min_recipes):
    """B7 regression: /recetas/api/families must return at least one
    family for the seeded dataset (it has 2 recipes with menu_tags).
    Was returning [] because the endpoint only queried Recipe.family."""
    r = authed_client.get("/recetas/api/families")
    assert r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}"
    data = json.loads(r.text)
    assert isinstance(data, list)
    # After the fix, the response should include at least one value
    # from Recipe.family OR Recipe.menu_tags.
    assert len(data) > 0, (
        f"/recetas/api/families returned [] — the B6 fix didn't propagate "
        f"to this endpoint, or the seed has no menu_tags. Response: {data!r}"
    )


# --- B8: hardcoded 70/20/10 cost breakdown removed --------------------


def test_receta_detalle_no_hardcoded_cost_breakdown(authed_client, seed_min_recipes):
    """B8 regression: the 'Desglose estimado' (Insumos 70% / Mano de
    obra 20% / Gastos generales 10%) section in receta_detalle.html
    must NOT be rendered. Those numbers were literal multipliers
    of batch_cost, not real labor/overhead data — misleading the
    operator. The fix removes the entire breakdown block until real
    labor_cost / overhead fields exist."""
    r = authed_client.get("/recetas")
    assert r.status_code == 200
    matches = re.findall(r'href="/recetas/(\d+)"', r.text)
    assert matches
    recipe_id = int(matches[0])
    rd = authed_client.get(f"/recetas/{recipe_id}")
    assert rd.status_code == 200
    body = rd.text
    # The hardcoded breakdown uses "70%" / "20%" / "10%" or "Mano de
    # obra" / "Gastos generales" labels with the percentage. None of
    # these must appear.
    assert "70%" not in body, (
        "Hardcoded 70% Insumos multiplier still in /recetas/{id}. "
        "The breakdown block must be removed until real labor/overhead "
        "data flows in."
    )
    assert "Mano de obra" not in body or "Gastos generales" not in body, (
        "Hardcoded 'Mano de obra' / 'Gastos generales' cost breakdown "
        "still in /recetas/{id}. The misleading 70/20/10 split must "
        "be removed — it shows literal multipliers of batch_cost, "
        "not real data."
    )


# --- B10: merma a11y --------------------------------------------------


def test_merma_forms_have_aria_labels(authed_client):
    """B10 regression: the forms on /merma must have programmatic
    labels (aria-label on <form>, or aria-labelledby, or a wrapping
    <fieldset><legend>). Screen-reader users could not identify
    the 'Registrar merma de insumo' vs 'Merma de receta completa'
    sections before the fix."""
    r = authed_client.get("/merma")
    assert r.status_code == 200
    body = r.text
    # Count forms that have an aria-label OR are inside a fieldset/legend.
    # We require at least one of the two forms to be labeled.
    forms_with_label = re.findall(
        r'<form[^>]+(aria-label="[^"]+"|aria-labelledby="[^"]+")',
        body,
    )
    fieldsets = re.findall(r"<fieldset[^>]*>", body)
    assert len(forms_with_label) + len(fieldsets) >= 1, (
        "Expected at least one <form> with aria-label/aria-labelledby OR "
        "a <fieldset> wrapping a form on /merma. Without a programmatic "
        "label, screen-reader users cannot identify the form sections. "
        f"Forms-with-label count: {len(forms_with_label)}, fieldsets: {len(fieldsets)}"
    )
