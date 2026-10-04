"""tests/e2e/test_strict_auth.py — the prod auth path with auth ENABLED.

The whole suite runs with SASKIA_TEST_AUTH_DISABLED=1. Since prod flipped
to real bcrypt auth (2026-09-24), nothing tested the enabled path E2E:
wrong password rejected, right password accepted, session cookie honored,
protected routes 401/redirect without it.

Uses its OWN TestClient (not the shared `client` fixture) because the
bypass env var is read at import/request time and the shared client's
fixtures re-set it.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def strict_client(session_factory, monkeypatch, tmp_db_path):
    """TestClient with the auth bypass OFF and a known admin password.

    Seeds the admin user via the same bootstrap prod uses
    (SASKIA_ADMIN_PASSWORD → bcrypt hash).
    """

    monkeypatch.delenv("SASKIA_TEST_AUTH_DISABLED", raising=False)
    monkeypatch.setenv("SASKIA_ADMIN_PASSWORD", "pytest-admin-pw-123")

    from app.rms import main as main_module
    from app.rms.bootstrap import run_password_sync

    test_engine = session_factory.kw["bind"]

    def _make_engine_for_test(url=None, *, for_tests=False):
        return test_engine

    monkeypatch.setattr(main_module, "make_engine_dialect", _make_engine_for_test)

    run_password_sync(session_factory())

    from fastapi.testclient import TestClient

    # https base_url: the session cookie is Secure-flagged by default
    # (HTTPS_ONLY defaults true) and httpx won't replay Secure cookies over
    # http — the login would "work" but the session would never stick.
    with TestClient(
        main_module.app, raise_server_exceptions=False, base_url="https://testserver"
    ) as c:
        main_module.app.state.engine = test_engine
        main_module.app.state.session_factory = session_factory
        yield c


def test_wrong_password_rejected(strict_client):
    r = strict_client.post(
        "/login",
        data={
            "username": "admin",
            "password": "definitely-wrong",
        },
        follow_redirects=False,
    )
    # Local backend redirects to /login?...error=credenciales+invalidas
    # on bad credentials — the success case redirects to `next` instead.
    assert r.status_code == 303
    loc = r.headers.get("location", "")
    assert "error=" in loc, f"bad password must bounce back to /login: {loc}"
    assert "inv" in loc.lower()


def test_right_password_gets_session(strict_client):
    r = strict_client.post(
        "/login",
        data={
            "username": "admin",
            "password": "pytest-admin-pw-123",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303, f"login failed: {r.status_code} {r.text[:200]}"


def test_protected_route_redirects_anonymous(strict_client):
    r = strict_client.get("/dashboard", follow_redirects=False)
    assert r.status_code in (303, 401)
    if r.status_code == 303:
        assert "/login" in (r.headers.get("location") or "")


def test_logged_in_session_reaches_dashboard(strict_client):
    strict_client.post(
        "/login",
        data={
            "username": "admin",
            "password": "pytest-admin-pw-123",
        },
        follow_redirects=False,
    )
    r = strict_client.get("/dashboard")
    assert r.status_code == 200
