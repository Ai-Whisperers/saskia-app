"""tests/test_analisis_routes.py — SASKIA plan 1.

analisis router has 1 route (/analisis), 0 direct tests.

Per docs/plans/2026-10-11-plan-1-untested-routers.md.
"""

from __future__ import annotations

import pytest


def test_analisis_returns_200(authed_client):
    """GET /analisis → 200."""
    r = authed_client.get("/analisis")
    assert r.status_code == 200
