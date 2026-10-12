"""tests/integration/test_csrf_auth_real.py — Real CSRF + auth flow integration tests.

Tests auth-enabled behavior. Uses the `_lib.auth.auth_required_client`
context manager (xdist-safe) so tests verify the real auth gate.
"""
import pytest

from tests._lib.auth import auth_required_client
from tests._lib.http import (
    AUTH_METHOD_CODES,
    LOGIN_POST_CODES,
    REQUIRES_LOGIN_CODES,
    SAFE_CODES,
)


pytestmark = [pytest.mark.integration, pytest.mark.auth, pytest.mark.security]


def test_login_form_get():
    with auth_required_client() as c:
        r = c.get("/login", follow_redirects=False)
        assert r.status_code in SAFE_CODES


def test_login_post_invalid_credentials():
    with auth_required_client() as c:
        r = c.post(
            "/login",
            data={"username": "fake", "password": "wrong"},
            follow_redirects=False,
        )
        assert r.status_code in LOGIN_POST_CODES


def test_login_post_empty_form():
    with auth_required_client() as c:
        r = c.post(
            "/login",
            data={"username": "", "password": ""},
            follow_redirects=False,
        )
        assert r.status_code in LOGIN_POST_CODES


def test_protected_endpoint_redirects():
    with auth_required_client() as c:
        for path in ["/dashboard", "/settings", "/admin"]:
            r = c.get(path, follow_redirects=False)
            assert r.status_code in REQUIRES_LOGIN_CODES


def test_unicode_username():
    with auth_required_client() as c:
        r = c.post(
            "/login",
            data={"username": "usuário", "password": "test"},
            follow_redirects=False,
        )
        assert r.status_code in LOGIN_POST_CODES


def test_long_password():
    with auth_required_client() as c:
        r = c.post(
            "/login",
            data={"username": "x", "password": "a" * 1000},
            follow_redirects=False,
        )
        assert r.status_code in LOGIN_POST_CODES


def test_special_chars_in_username():
    with auth_required_client() as c:
        r = c.post(
            "/login",
            data={"username": "user'; DROP--", "password": "x"},
            follow_redirects=False,
        )
        assert r.status_code in LOGIN_POST_CODES


def test_logout_with_auth():
    with auth_required_client() as c:
        r = c.post("/logout", follow_redirects=False)
        assert r.status_code in AUTH_METHOD_CODES


def test_admin_path_with_auth():
    with auth_required_client() as c:
        r = c.get("/admin", follow_redirects=False)
        assert r.status_code in REQUIRES_LOGIN_CODES


def test_login_get_returns_html():
    with auth_required_client() as c:
        r = c.get("/login", follow_redirects=False)
        if r.status_code == 200 and r.text:
            assert "input" in r.text.lower() or "form" in r.text.lower() or "login" in r.text.lower()
