"""tests/e2e/test_settings_runtime_crud.py — the 37-route dark cluster.

settings_runtime is the operator-config surface (branding, tax, margin
tiers, pricing markup, categories, channels, payment methods, storage
types, date presets) that costing and reports read downstream. Before
this file: only the static-content audit touched it — an entire router
with zero behavioral coverage (found by the 2026-09-25 gap analysis).

JSON-body API routes (BaseModel payloads), unlike the form-POST flows.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.crud]


def _crud_roundtrip(client, path: str, payload: dict, update: dict,
                    *, list_key: str | None = None, id_key: str = "id"):
    """Generic create → read → update → delete sweep for one entity type.

    Returns the created entity's id.
    """
    # create
    r = client.post(f"/api/{path}", json=payload)
    assert r.status_code in (200, 201), f"create {path}: {r.status_code} {r.text[:200]}"
    created = r.json()
    eid = created[id_key]

    # read (list) — must contain what we created
    r = client.get(f"/api/{path}")
    assert r.status_code == 200, f"list {path}: {r.status_code}"
    items = r.json() if isinstance(r.json(), list) else r.json().get(list_key or "items", [])
    assert any(it[id_key] == eid for it in items), f"created {path} not in list"

    # update
    r = client.post(f"/api/{path}/{eid}/update", json=update)
    assert r.status_code == 200, f"update {path}/{eid}: {r.status_code} {r.text[:200]}"

    # delete
    r = client.post(f"/api/{path}/{eid}/delete")
    assert r.status_code in (200, 204, 303), f"delete {path}/{eid}: {r.status_code}"
    return eid


def test_channel_crud_roundtrip(client):
    _crud_roundtrip(client, "channels",
                    {"code": "test-ch", "label": "Canal test", "sort_order": 10},
                    {"label": "Canal editado"})


def test_payment_method_crud_roundtrip(client):
    _crud_roundtrip(client, "payment-methods",
                    {"code": "test-pm", "label": "Transferencia test", "fee_pct": 1.5},
                    {"label": "Transferencia editada"})


def test_storage_type_crud_roundtrip(client):
    _crud_roundtrip(client, "storage-types",
                    {"code": "test-st", "label": "Freezer test", "requires_temp_min": True},
                    {"label": "Freezer editado"})


def test_date_preset_crud_roundtrip(client):
    _crud_roundtrip(client, "date-presets",
                    {"code": "test-dp", "label": "Últimos 3 días test", "days": 3},
                    {"label": "Últimos 3 días editado"})


def test_category_crud_roundtrip(client):
    """Categories are scoped: create needs scope, list needs ?scope=."""
    r = client.post("/api/categories", json={"name": "Cat test", "scope": "product"})
    assert r.status_code in (200, 201), r.text[:200]
    cid = r.json()["id"]

    r = client.get("/api/categories?scope=product")
    assert r.status_code == 200
    assert any(c["id"] == cid for c in r.json())

    r = client.post(f"/api/categories/{cid}/update", json={"name": "Cat editada"})
    assert r.status_code == 200

    r = client.post(f"/api/categories/{cid}/delete")
    assert r.status_code in (200, 204, 303)


def test_category_scope_validation_rejected(client):
    r = client.post("/api/categories", json={"name": "X", "scope": "bogus"})
    assert r.status_code in (400, 422)


def test_categories_list_requires_scope(client):
    r = client.get("/api/categories")
    assert r.status_code in (400, 422)


def test_update_unknown_category_404(client):
    r = client.post("/api/categories/999999/update", json={"name": "n"})
    assert r.status_code == 404


def test_date_preset_days_bounds(client):
    r = client.post("/api/date-presets", json={"code": "x", "label": "x", "days": 0})
    assert r.status_code in (400, 422)
    r2 = client.post("/api/date-presets", json={"code": "x", "label": "x", "days": 9999})
    assert r2.status_code in (400, 422)


def test_payment_method_fee_bounds(client):
    r = client.post("/api/payment-methods", json={"code": "x", "label": "x", "fee_pct": 150})
    assert r.status_code in (400, 422)


def test_iva_rates_endpoint_loads(client):
    r = client.get("/api/iva-rates")
    assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"


def test_stock_status_config_endpoints(client):
    """GET list + update/delete on a config row (id from the list)."""
    r = client.get("/api/stock-status-config")
    assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
    items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    if not items:
        pytest.skip("no stock-status configs seeded")
    cid = items[0]["id"]
    r2 = client.post(f"/api/stock-status-config/{cid}/update", json={})
    assert r2.status_code == 200, f"{r2.status_code} {r2.text[:200]}"
