"""tests/test_produccion_route.py — /produccion route tests."""
from __future__ import annotations


def test_produccion_renders_empty(client):
    """GET /produccion returns 200 even with no data."""
    resp = client.get("/produccion")
    assert resp.status_code == 200
    body = resp.text
    assert "Producción" in body or "Plan de producción" in body
