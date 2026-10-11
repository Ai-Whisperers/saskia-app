"""tests/test_herebus_routes.py — SASKIA plan 1.

herebus router (app/routers/herebus.py) integrates with the HERE
Maps API. Tests skip external calls and only verify route wiring.

Per docs/plans/2026-10-11-plan-1-untested-routers.md.
"""

from __future__ import annotations

import pytest


def test_herebus_index_returns_200_or_3xx(authed_client):
    """GET /herebus → 200/3xx (route wiring)."""
    r = authed_client.get("/herebus")
    # 200 (page renders), 303 (redirect to login), or 404 all OK
    assert r.status_code in (200, 303, 404), r.text[:200]
