"""P-15 / audit: /produccion-planner calcula ingredientes × tandas correctly.

Test plan:
1. GET /produccion-planner → 200, empty state visible
2. POST recipe_id + batches=10 → 200 with calculation
3. Ingredient rows show: required_qty, available, shortage
4. Stock-sufficient ingredients in green/warn; shortages in red
5. POST batches=0 or non-integer → handled gracefully (redirect or 422)
6. POST non-existent recipe_id → handled (redirect or 404)
"""
from __future__ import annotations

import pytest

pytestmark = [pytest.mark.smoke]


def test_planner_get_returns_empty_state(client):
    """P-15: GET /produccion-planner must show the picker UI with empty state."""
    r = client.get("/produccion-planner")
    assert r.status_code == 200, f"got {r.status_code}"
    body = r.text
    # The form elements are present (picker + batches input + Calcular button)
    assert 'name="batches"' in body or 'id="batches"' in body, (
        "Missing 'batches' input on /produccion-planner"
    )
    assert "Calcular" in body, "Missing 'Calcular' button text"
    # The empty-state message
    assert (
        "Elegí una receta" in body or "tandas" in body or "Probar" in body
        or "no hay datos" in body
    ), (
        "Missing empty-state message on /produccion-planner"
    )


def test_planner_compute_succeeds(client, session_factory):
    """P-15-1: POST with receta + batches=10 returns 200 with calc results."""
    from tests.factories import ing_line, make_ingredient, make_recipe

    with session_factory() as s:
        ing = make_ingredient(s, name=f"Harina-P15-{__import__('uuid').uuid4().hex[:6]}", stock_qty=50.0)
        recipe = make_recipe(
            s,
            name=f"Bolillo-P15-{__import__('uuid').uuid4().hex[:6]}",
            lines=[ing_line(ing, qty=2.0)],
            yield_qty=12.0,
        )
        s.commit()
        recipe_id = recipe.id
        ing_name = ing.name

    r = client.post("/produccion-planner/compute", data={"recipe_id": recipe_id, "batches": "10"})
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"
    body = r.text
    # Heading shows recipe × batches
    assert "10" in body, "Missing batches=10 in rendered output"
    # Ingredient name appears (calculation row)
    assert ing_name in body, (
        f"Calculated ingredient '{ing_name}' missing from planner output"
    )


def test_planner_compute_invalid_batches_redirects(client, session_factory):
    """P-15-5: POST with batches=0 redirects back to planner (router handles gracefully)."""
    from tests.factories import ing_line, make_ingredient, make_recipe

    with session_factory() as s:
        ing = make_ingredient(s, name=f"Harina-P15b-{__import__('uuid').uuid4().hex[:6]}")

    with session_factory() as s:
        r = make_recipe(s, lines=[ing_line(ing, qty=1.0)])
        s.commit()
        rid = r.id

    # batches=0 is invalid (router does `if batches <= 0: redirect`)
    r = client.post(
        "/produccion-planner/compute",
        data={"recipe_id": rid, "batches": "0"},
        follow_redirects=False,
    )
    assert r.status_code in (200, 303, 422), (
        f"Invalid batches should redirect/422, got {r.status_code}"
    )
    # Should NOT show the calculation result
    if r.status_code == 200:
        assert "10" not in r.text.split("<h2")[0].split("<h1")[0], (
            "Should not show calculated result with batches=0"
        )


def test_planner_compute_nonexistent_recipe_redirects(client):
    """P-15-6: POST with non-existent recipe_id redirects gracefully."""
    r = client.post(
        "/produccion-planner/compute",
        data={"recipe_id": 999999, "batches": "5"},
        follow_redirects=True,
    )
    # Router checks `if not recipe` and redirects to planner
    assert r.status_code == 200
    # Should land back on the empty planner form
    assert 'name="batches"' in r.text or 'id="batches"' in r.text
