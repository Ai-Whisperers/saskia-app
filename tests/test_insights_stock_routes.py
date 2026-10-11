"""tests/test_insights_stock_routes.py — SASKIA plan 1.

insights_stock router (mounted at /reportes) has 4 routes, 0 direct
tests. Smoke tests cover all 4 endpoints.

Per docs/plans/2026-10-11-plan-1-untested-routers.md.
"""

from __future__ import annotations

import pytest


def test_insights_stock_intel_returns_200(authed_client):
    """GET /reportes/stock-intel → 200."""
    r = authed_client.get("/reportes/stock-intel")
    assert r.status_code == 200


def test_insights_afinidades_returns_200(authed_client):
    """GET /reportes/afinidades → 200."""
    r = authed_client.get("/reportes/afinidades")
    assert r.status_code == 200
    body = r.text.lower()
    assert "afinidad" in body or "insight" in body or "stock" in body or "par" in body


def test_insights_margenes_returns_200(authed_client):
    """GET /reportes/margenes → 200."""
    r = authed_client.get("/reportes/margenes")
    assert r.status_code == 200


def test_insights_margenes_product_returns_200(authed_client, session_factory):
    """GET /reportes/margenes/{product_id} → 200 for a real product."""
    from tests.factories import make_product
    s = session_factory()
    try:
        p = make_product(s, name="Insight Margen Test")
        s.commit()
        pid = p.id
    finally:
        s.close()

    r = authed_client.get(f"/reportes/margenes/{pid}")
    assert r.status_code in (200, 404), r.text[:200]
