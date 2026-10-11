"""tests/test_insights_derived_routes.py — SASKIA audit (round 5).

The insights_derived router (app/routers/insights_derived.py) had 0 direct
route tests. The engines (forecast_demand, theoretical_vs_actual, etc.)
are tested elsewhere, but the HTTP-level wiring was unverified.

These tests are smoke-level: each route returns 200 with the right
shape. They would catch a future regression that broke the route
wiring (e.g., a typo in the path, a missing import, a template rename).
"""

from __future__ import annotations

import pytest


@pytest.fixture
def _seed_ingredient(session_factory):
    """Seed one ingredient so price-impact has a real target."""
    from tests.factories import make_ingredient

    s = session_factory()
    try:
        ing = make_ingredient(s, name="Harina Test", unit="kg", stock_qty=10.0)
        s.commit()
        return ing.id
    finally:
        s.close()


def test_reportes_food_cost_variance_returns_200(client):
    """GET /reportes/food-cost-variance → 200 (route wiring)."""
    r = client.get("/reportes/food-cost-variance")
    assert r.status_code == 200


def test_reportes_demand_returns_200(client):
    """GET /reportes/demand → 200 (route wiring)."""
    r = client.get("/reportes/demand")
    assert r.status_code == 200
    # The page renders the demand header (or empty-state).
    body = r.text
    assert "Demanda" in body or "Previsto" in body or "unidades" in body


def test_reportes_freshness_returns_200(client):
    """GET /reportes/freshness → 200 (route wiring)."""
    r = client.get("/reportes/freshness")
    assert r.status_code == 200
    body = r.text
    # Page shows freshness flags (use-first or cook-today)
    assert "Frescura" in body or "vencimiento" in body.lower() or "cocinar" in body.lower() or "sin ingredientes" in body.lower()


def test_reportes_price_impact_returns_200(client, _seed_ingredient):
    """GET /reportes/price-impact/{id} → 200 for a real ingredient."""
    ing_id = _seed_ingredient
    r = client.get(f"/reportes/price-impact/{ing_id}", params={"new_price": 5000})
    assert r.status_code == 200
    body = r.text
    # Page should reference the ingredient and the impact concept
    assert "Impacto" in body or "precio" in body.lower() or "Harina" in body


def test_reportes_api_allergen_check_returns_json(client):
    """GET /reportes/api/allergen-check?product_id=X → JSON with allergens info."""
    r = client.get("/reportes/api/allergen-check", params={"customer_id": 999999, "product_id": 999999})
    # 200 with empty list (no product) is fine
    assert r.status_code == 200
    import json
    data = json.loads(r.text)
    assert isinstance(data, (list, dict))
