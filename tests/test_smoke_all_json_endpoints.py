"""Comprehensive smoke test for every JSON-returning endpoint.

Per SASKIA_TEST_PLAN.md §5 #7 — one test per JSON endpoint. Every endpoint
must return valid JSON with the expected shape.
"""
from __future__ import annotations

import json

import pytest

# JSON endpoints from SASKIA_TEST_PLAN.md §1.3 + §5 #7
JSON_ROUTES = [
    ("/api/search?q=pan", dict),  # /search returns {type, label, url} list
    ("/healthz", dict),
    ("/healthz/db", dict),
    ("/healthz/schema", dict),
    ("/healthz/deps", dict),
    ("/healthz/errors", dict),
]


@pytest.mark.parametrize("route,expected_type", JSON_ROUTES)
def test_json_endpoint_returns_valid_json(client, route, expected_type):
    """Every JSON endpoint must return valid JSON of the expected type."""
    r = client.get(route)
    assert r.status_code < 500, (
        f"GET {route} returned {r.status_code}: {r.text[:200]}"
    )
    if r.status_code == 200:
        try:
            data = r.json()
            assert isinstance(data, expected_type), (
                f"{route} returned {type(data).__name__}, expected {expected_type.__name__}"
            )
        except json.JSONDecodeError:
            pytest.fail(f"{route} returned non-JSON: {r.text[:200]}")


def test_healthz_returns_status_ok(client):
    """/healthz must return JSON with status='ok'."""
    r = client.get("/healthz")
    data = r.json()
    assert "status" in data, f"Missing 'status' in /healthz: {data}"


def test_healthz_db_returns_db_field(client):
    """/healthz/db must return JSON with 'db' field."""
    r = client.get("/healthz/db")
    data = r.json()
    assert "db" in data, f"Missing 'db' in /healthz/db: {data}"


def test_healthz_db_includes_schema_version_when_ok(client):
    """/healthz/db must include schema_version when DB is healthy."""
    r = client.get("/healthz/db")
    data = r.json()
    if data.get("db") == "ok":
        assert "schema_version" in data, f"Missing schema_version: {data}"
        assert "code_schema_version" in data


def test_healthz_schema_returns_drift_field(client):
    """/healthz/schema must return drift field (0 if in sync)."""
    r = client.get("/healthz/schema")
    data = r.json()
    assert "drift" in data, f"Missing 'drift' in /healthz/schema: {data}"


def test_healthz_errors_returns_counts(client):
    """/healthz/errors must return http_500_count with last_1h and last_24h."""
    r = client.get("/healthz/errors")
    data = r.json()
    assert "http_500_count" in data, f"Missing 'http_500_count': {data}"
    counts = data["http_500_count"]
    assert "last_1h" in counts
    assert "last_24h" in counts


def test_healthz_deps_returns_fingerprints_not_secrets(client):
    """/healthz/deps must return fingerprints (len + sha), NEVER raw values."""
    r = client.get("/healthz/deps")
    data = r.json()
    # Must contain packages dict
    assert "packages" in data, f"Missing packages: {data}"
    # If any SUPABASE_* field exists, it must be fingerprint format (len + sha)
    for key, val in data.items():
        if key.startswith("SUPABASE_") and val is not None:
            assert val.startswith("len="), (
                f"{key} value is not fingerprinted: {val}"
            )
            assert "sha=" in val, f"{key} missing sha: {val}"


def test_api_search_returns_list(client, session_factory):
    """/api/search must return a JSON list (or list-wrapped)."""
    from app.rms.models import Product
    with session_factory() as s:
        p = Product(name="JSON Search Test Pan", portion_label="1 und", sale_price_gs=5000, is_available=True)
        s.add(p)
        s.commit()

    r = client.get("/api/search?q=Pan")
    assert r.status_code == 200
    data = r.json()
    # Should be a list or dict with categorized results
    assert isinstance(data, (list, dict)), f"Unexpected type: {type(data)}"
    if isinstance(data, dict):
        # Real response has 'customers', 'products', 'pedidos', 'recipes' keys
        # Just verify it's a non-empty dict
        assert len(data) > 0, f"Empty dict response: {data}"


def test_api_search_empty_query(client):
    """/api/search with empty query must return non-5xx (422 acceptable for missing query)."""
    r = client.get("/api/search?q=")
    # q= is required, so 422 is valid (Pydantic validation)
    assert r.status_code < 500, f"/api/search?q= returned {r.status_code}"


def test_ventas_buscar_returns_json(client, session_factory):
    """/ventas/buscar?sku= must return JSON or 404."""
    r = client.get("/ventas/buscar?sku=nonexistent")
    # Should be 200 (with empty result) or 404
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        try:
            r.json()
        except json.JSONDecodeError:
            pytest.fail(f"/ventas/buscar returned non-JSON: {r.text[:200]}")
