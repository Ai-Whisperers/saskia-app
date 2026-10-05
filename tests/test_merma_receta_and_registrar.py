"""Merma (waste) and produccion (production) endpoint tests."""

from __future__ import annotations


def test_merma_page_loads(authed_client):
    """GET /merma must return 200."""
    r = authed_client.get("/merma")
    assert r.status_code == 200


def test_merma_registrar_post_no_500(authed_client, session_factory):
    """POST /merma/registrar must not 500."""
    from app.rms.models import Ingredient

    with session_factory() as s:
        ing = Ingredient(name="Merma Test Ing", unit="kg", stock_qty=10.0, min_stock_qty=1.0)
        s.add(ing)
        s.commit()
        ing_id = ing.id

    r = authed_client.post(
        "/merma/registrar",
        data={"ingredient_id": str(ing_id), "qty": "1.0", "reason": "test"},
    )
    assert r.status_code < 500, f"/merma/registrar returned {r.status_code}: {r.text[:200]}"


def test_merma_receta_post_no_500(authed_client, session_factory):
    """POST /merma/receta must not 500 (waste from recipe)."""
    from app.rms.models import Recipe

    with session_factory() as s:
        recipe = Recipe(name="Merma Receta Test", yield_qty=10.0)
        s.add(recipe)
        s.commit()
        recipe_id = recipe.id

    r = authed_client.post(
        "/merma/receta",
        data={"recipe_id": str(recipe_id), "qty": "1.0"},
    )
    assert r.status_code < 500, f"/merma/receta returned {r.status_code}: {r.text[:200]}"


def test_produccion_page_loads(authed_client):
    """GET /produccion must return 200."""
    r = authed_client.get("/produccion")
    assert r.status_code == 200


def test_produccion_override_no_500(authed_client, session_factory):
    """POST /produccion/override must not 500."""

    r = authed_client.post(
        "/produccion/override",
        data={"recipe_id": "1", "qty": "5"},
    )
    assert r.status_code < 500, f"/produccion/override returned {r.status_code}: {r.text[:200]}"


def test_reorder_page_loads(authed_client):
    """GET /reorder must return 200."""
    r = authed_client.get("/reorder")
    assert r.status_code == 200


def test_reorder_registrar_no_500(authed_client, session_factory):
    """POST /reorder/registrar must not 500."""
    from app.rms.models import Ingredient

    with session_factory() as s:
        ing = Ingredient(name="Reorder Test Ing", unit="kg", stock_qty=5.0, min_stock_qty=10.0)
        s.add(ing)
        s.commit()
        ing_id = ing.id

    r = authed_client.post(
        "/reorder/registrar",
        data={"ingredient_id": str(ing_id), "qty": "20"},
    )
    assert r.status_code < 500, f"/reorder/registrar returned {r.status_code}: {r.text[:200]}"


def test_reorder_generate_po_no_500(authed_client):
    """POST /reorder/generate-po must not 500."""
    r = authed_client.post("/reorder/generate-po")
    assert r.status_code < 500, f"/reorder/generate-po returned {r.status_code}: {r.text[:200]}"


def test_auditoria_filters_loads(authed_client):
    """GET /auditoria with filters must return 200."""
    r = authed_client.get("/auditoria?action_filter=http.500")
    assert r.status_code == 200, f"/auditoria filter returned {r.status_code}"


def test_auditoria_prune_post_no_500(authed_client):
    """POST /auditoria/prune must not 500."""
    r = authed_client.post("/auditoria/prune", data={"days": "30"})
    assert r.status_code < 500, f"/auditoria/prune returned {r.status_code}: {r.text[:200]}"
