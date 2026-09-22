"""tests/test_csrf.py — CSRF middleware tests."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.security


def _clean_client(client):
    """Helper: make a fresh TestClient without the conftest's primed cookie."""
    from starlette.testclient import TestClient

    from app.rms.main import app
    return TestClient(app, raise_server_exceptions=False)


def test_get_sets_csrf_cookie(client):
    """GET / should set a csrf_token cookie.

    Use a fresh client (no primed cookie from conftest) so we test the
    middleware's actual priming behavior, not the autouse priming.
    """
    fresh = _clean_client(client)
    resp = fresh.get("/")
    assert resp.status_code in (200, 303, 401)  # any in-flight response
    cookie = resp.cookies.get("csrf_token")
    assert cookie is not None
    assert len(cookie) > 16


def test_post_without_csrf_cookie_rejected(client):
    """POST without csrf cookie → 403 from CSRF middleware.

    Use a fresh client with no cookies to verify CSRF rejects bare POSTs.
    """
    fresh = _clean_client(client)
    resp = fresh.post("/ventas/nueva", data={"product_id": "1", "qty": "1"})
    assert resp.status_code == 403, (
        f"Expected 403 from CSRF guard, got {resp.status_code}"
    )


def test_post_with_valid_csrf_cookie_proceeds_to_route(client):
    """POST with a signed csrf cookie reaches the route (may 400 because of bad product)."""
    fresh = _clean_client(client)
    r1 = fresh.get("/")
    csrf = r1.cookies.get("csrf_token")
    assert csrf is not None
    fresh.cookies.set("csrf_token", csrf)
    resp = fresh.post("/ventas/nueva", data={"product_id": "999999", "qty": "1"})
    assert resp.status_code != 403


def test_login_exempt_from_csrf(client):
    """POST /login must NOT require csrf (first-time login has no cookie yet)."""
    fresh = _clean_client(client)
    resp = fresh.post("/login", data={"username": "nobody", "password": "x"})
    assert resp.status_code != 403


def test_healthz_exempt_from_csrf(client):
    """/healthz endpoints are exempt (no cookies, monitored externally)."""
    fresh = _clean_client(client)
    for path in ("/healthz", "/healthz/db", "/healthz/deps"):
        resp = fresh.get(path)
        assert resp.status_code != 403
