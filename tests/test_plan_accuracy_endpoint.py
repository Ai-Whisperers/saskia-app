"""tests/test_plan_accuracy_endpoint.py — BACKLOG #29/#33 plan accuracy endpoint test."""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime, timezone

from fastapi.testclient import TestClient


def test_plan_accuracy_endpoint_empty(client: TestClient):
    """When no data, returns 0% accuracy."""
    response = client.get("/produccion/api/accuracy")
    assert response.status_code == 200
    data = response.json()
    assert data["completion_accuracy"] == 0.0
    assert data["completed_qty"] == 0.0
    assert data["planned_qty"] == 0.0
    assert data["n_products"] == 0
    assert data["worst_performers"] == []


def test_plan_accuracy_endpoint_with_data(client: TestClient, testdb):
    """With test data, returns correct accuracy."""
    from app.rms.models_legacy import Product, ProductionCompletion, ProductionPlan, Recipe

    today = Date(2026, 10, 1)
    with testdb() as s:
        # Create product with recipe
        r = Recipe(name="Torta", yield_qty=4.0)
        s.add(r)
        p = Product(name="Torta", recipe_id=r.id)
        s.add(p)
        s.flush()
        # Plan and complete half
        plan = ProductionPlan(
            recipe_id=r.id, batches_qty=2, status="planned", planned_at=datetime.now(timezone.utc)
        )
        s.add(plan)
        completion = ProductionCompletion(product_id=p.id, completed_qty=4, for_date=today)
        s.add(completion)
        s.commit()
    response = client.get("/produccion/api/accuracy")
    assert response.status_code == 200
    data = response.json()
    # Planned: 2 batches × 4 yield = 8; Completed: 4 → 50%
    assert data["completion_accuracy"] == 50.0
    assert data["completed_qty"] == 4.0
    assert data["planned_qty"] == 8.0
    assert data["n_products"] == 1
    assert len(data["worst_performers"]) == 1
