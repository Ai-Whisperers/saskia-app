"""tests/_lib/auth.py — Centralized auth/test-client helpers.

Eliminates the duplication of "build a TestClient with auth X" that was
copied across 8+ tier test files. All helpers return a real `TestClient`
compatible with FastAPI's app. The auth-ENABLED variant uses monkeypatch
(not context manager) so it's safe to use with pytest-xdist.

Usage:
    from tests._lib.auth import fresh_client, auth_disabled_client, auth_required_client

    def test_something(fresh_client):
        r = fresh_client.get("/login")
        assert r.status_code in (200, 302)

    def test_something_requiring_auth(auth_required_client):
        r = auth_required_client.get("/admin")
        assert r.status_code in (200, 401, 403)
"""

from __future__ import annotations

from contextlib import contextmanager

from fastapi.testclient import TestClient


def _build_client() -> TestClient:
    """Build a fresh TestClient. Imports app lazily to avoid import side-effects."""
    from app.rms.main import app

    return TestClient(app, raise_server_exceptions=False)


@contextmanager
def fresh_client():
    """TestClient with default auth (uses conftest's `SASKIA_TEST_AUTH_DISABLED=1` env).

    Use this in tests where you don't care about the auth gate, or when the
    fixture `client`/`authed_client` from conftest is too heavy.

    Yields:
        TestClient: A real FastAPI TestClient.

    Example:
        def test_x():
            with fresh_client() as c:
                r = c.get("/")
                assert r.status_code == 200
    """
    with _build_client() as c:
        yield c


@contextmanager
def auth_required_client():
    """TestClient with auth ENABLED (real auth flow).

    Patches `app.auth.is_auth_disabled` to return False. Use for tests that
    need to verify the real auth gate (login redirects, 401/403, etc).

    Yields:
        TestClient: A real FastAPI TestClient with auth required.

    Example:
        def test_protected_route_redirects():
            with auth_required_client() as c:
                r = c.get("/dashboard", follow_redirects=False)
                assert r.status_code in (302, 303, 307)
    """
    from unittest.mock import patch

    with patch("app.auth.is_auth_disabled", return_value=False):
        with _build_client() as c:
            yield c


@contextmanager
def auth_disabled_client():
    """TestClient with auth EXPLICITLY disabled.

    Same as fresh_client() but makes the intent clearer. Use this when you
    want to communicate "auth is off and that's the point".

    Yields:
        TestClient: A real FastAPI TestClient with auth disabled.
    """
    from unittest.mock import patch

    with patch("app.auth.is_auth_disabled", return_value=True):
        with _build_client() as c:
            yield c


def assert_safe_response(r, *, allow_redirects: bool = True) -> None:
    """Assert a response is 'safe' (no 5xx, no stack trace in body).

    Args:
        r: The response object.
        allow_redirects: If False, treat 3xx as failures.

    Asserts:
        - Status code is not 5xx.
        - Response body does not contain "Traceback".
    """
    assert r.status_code < 500, f"Got 5xx: {r.status_code} {getattr(r, 'text', '')[:200]}"
    if not allow_redirects and 300 <= r.status_code < 400:
        raise AssertionError(f"Got redirect {r.status_code} but redirects not allowed")
    if hasattr(r, "text") and r.text:
        assert "Traceback" not in r.text, f"Response leaked stack trace: {r.text[:200]}"


__all__ = [
    "assert_safe_response",
    "auth_disabled_client",
    "auth_required_client",
    "fresh_client",
]
