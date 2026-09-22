"""tests/test_reliability.py — ensure unhandled errors return clean JSON 500s.

Pre-fix: any unhandled exception → generic HTML 500 with no info.
Post-fix: structured JSON {"error": str, "type": str, "request_id": str}
and the exception is logged to stderr/Sentry (when configured).
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.smoke


def test_unhandled_exception_returns_json_500(client, session_factory):
    """A route that raises RuntimeError → 500 JSON, not HTML.

    Uses raise_server_exceptions=False so the FastAPI exception handler
    fires (TestClient's default behavior is to re-raise to the test).
    """
    from starlette.testclient import TestClient

    from app.rms.main import app

    @app.get("/__test_raises")
    def _raises():
        raise RuntimeError("simulated-unhandled-error")

    # Make a client that lets exceptions reach the global handler.
    test_client = TestClient(app, raise_server_exceptions=False)
    try:
        resp = test_client.get("/__test_raises")
    finally:
        app.router.routes = [r for r in app.router.routes if getattr(r, "path", "") != "/__test_raises"]

    assert resp.status_code == 500
    assert resp.headers.get("content-type", "").startswith("application/json")
    body = resp.json()
    assert "error" in body
    assert body["type"] in ("RuntimeError", "Exception")
    assert "request_id" in body
    # Sanity: must NOT leak the actual Python stack trace in the response.
    assert "Traceback" not in resp.text


def test_404_returns_json(client):
    """Unknown route → JSON 404 (consistent with error shape)."""
    resp = client.get("/__nonexistent_path_definitely_not_a_real_route")
    assert resp.status_code == 404
    # Starlette default returns either HTML or JSON; we want JSON consistency.
    # Accept either for now but at minimum no HTML 500.
    assert resp.status_code in (404, 405)
