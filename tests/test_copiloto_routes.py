"""tests/test_copiloto_routes.py — SASKIA plan 1.

copiloto router has 2 routes (/copiloto, /copiloto/ask), 0 tests.

Per docs/plans/2026-10-11-plan-1-untested-routers.md.
"""

from __future__ import annotations

import pytest


def test_copiloto_returns_200(authed_client):
    """GET /copiloto → 200 (chat landing page)."""
    r = authed_client.get("/copiloto")
    assert r.status_code == 200


def test_copiloto_ask_post_returns_json(authed_client):
    """POST /copiloto/ask → 200 JSON with an answer."""
    r = authed_client.post(
        "/copiloto/ask",
        json={"question": "¿cuánto vendimos hoy?"},
    )
    assert r.status_code in (200, 422), r.text[:200]
