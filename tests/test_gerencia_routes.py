"""tests/test_gerencia_routes.py — SASKIA plan 1.

gerencia router has 1 route (/gerencia), 0 tests.

Per docs/plans/2026-10-11-plan-1-untested-routers.md.
"""

from __future__ import annotations

import pytest


def test_gerencia_returns_200(authed_client):
    """GET /gerencia → 200."""
    r = authed_client.get("/gerencia")
    assert r.status_code == 200
