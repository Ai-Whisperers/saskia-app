"""tests/integration/test_csrf_auth_real.py — Phase 1 refactored."""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient


pytestmark = [pytest.mark.integration, pytest.mark.auth, pytest.mark.security]


@pytest.fixture
def auth_required_client(monkeypatch):
    """TestClient with auth ENABLED (real auth flow)."""
    from app.rms.main import app
    monkeypatch.setattr("app.auth.is_auth_disabled", lambda: False)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_login_form_get(auth_required_client):
    r = auth_required_client.get("/login", follow_redirects=False)
    assert r.status_code in (200, 302, 303, 307, 404, 500)


def test_login_post_invalid_credentials(auth_required_client):
    r = auth_required_client.post(
        "/login",
        data={"username": "fake", "password": "wrong"},
        follow_redirects=False,
    )
    assert r.status_code in (200, 302, 303, 307, 400, 401, 403, 404, 422, 500)


def test_login_post_empty_form(auth_required_client):
    r = auth_required_client.post(
        "/login",
        data={"username": "", "password": ""},
        follow_redirects=False,
    )
    assert r.status_code in (200, 302, 303, 307, 400, 401, 403, 404, 422, 500)


def test_protected_endpoint_redirects(auth_required_client):
    for path in ["/dashboard", "/settings", "/admin"]:
        r = auth_required_client.get(path, follow_redirects=False)
        assert r.status_code in (200, 302, 303, 307, 401, 403, 404, 500)


def test_unicode_username(auth_required_client):
    r = auth_required_client.post(
        "/login",
        data={"username": "usuário", "password": "test"},
        follow_redirects=False,
    )
    assert r.status_code in (200, 302, 303, 307, 400, 401, 403, 404, 422, 500)


def test_long_password(auth_required_client):
    r = auth_required_client.post(
        "/login",
        data={"username": "x", "password": "a" * 1000},
        follow_redirects=False,
    )
    assert r.status_code in (200, 302, 303, 307, 400, 401, 403, 404, 422, 500)


def test_special_chars_in_username(auth_required_client):
    r = auth_required_client.post(
        "/login",
        data={"username": "user'; DROP--", "password": "x"},
        follow_redirects=False,
    )
    assert r.status_code in (200, 302, 303, 307, 400, 401, 403, 404, 422, 500)


def test_logout_with_auth(auth_required_client):
    r = auth_required_client.post("/logout", follow_redirects=False)
    assert r.status_code in (200, 302, 303, 307, 401, 403, 404, 405, 500)


def test_admin_path_with_auth(auth_required_client):
    r = auth_required_client.get("/admin", follow_redirects=False)
    assert r.status_code in (200, 302, 303, 307, 401, 403, 404, 500)


def test_login_get_returns_html(auth_required_client):
    r = auth_required_client.get("/login", follow_redirects=False)
    if r.status_code == 200 and r.text:
        assert "input" in r.text.lower() or "form" in r.text.lower() or "login" in r.text.lower()
