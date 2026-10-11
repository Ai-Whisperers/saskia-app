"""tests/test_photo_credits_routes.py — SASKIA plan 1.

photo_credits router has 1 route (/creditos), 0 tests.

Per docs/plans/2026-10-11-plan-1-untested-routers.md.
"""

from __future__ import annotations

import pytest


def test_creditos_returns_200(authed_client):
    """GET /creditos → 200 (photo credits page)."""
    r = authed_client.get("/creditos")
    assert r.status_code == 200
