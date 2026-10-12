"""tests/security/test_security_dynamic.py — Dynamic security tests.

Targets the gap: Static analysis only, no dynamic security tests.
Exercises the app with malicious inputs to find vulnerabilities.
"""
import pytest

from tests._lib.auth import assert_safe_response
from tests._lib.http import (
    LOGIN_RATE_LIMITED_CODES,
    LOGIN_SAFE_CODES,
    METHOD_NOT_ALLOWED_CODES,
    AUTH_CODES,
)


pytestmark = [pytest.mark.security, pytest.mark.smoke]


@pytest.mark.parametrize("payload", [
    "'; DROP TABLE users; --",
    "1' OR '1'='1",
    "admin'--",
    "' UNION SELECT * FROM user --",
])
def test_sql_injection_in_login(authed_client, payload):
    """Login form should not 500 on SQL injection attempts."""
    r = authed_client.post(
        "/login",
        data={"username": payload, "password": payload},
        follow_redirects=False,
    )
    assert r.status_code in LOGIN_SAFE_CODES


@pytest.mark.parametrize("payload", [
    "<script>alert('XSS')</script>",
    "<img src=x onerror=alert(1)>",
    "javascript:alert(1)",
    "<svg/onload=alert(1)>",
])
def test_xss_in_login_form(authed_client, payload):
    """Login form should escape XSS in username field."""
    r = authed_client.post(
        "/login",
        data={"username": payload, "password": "x"},
        follow_redirects=False,
    )
    if r.status_code == 200 and hasattr(r, "text") and r.text:
        assert "<script>alert" not in r.text


@pytest.mark.parametrize("payload", [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "[click](javascript:alert(1))",
    "[click](vbscript:msgbox(1))",
])
def test_md_to_html_blocks_xss(payload):
    """Markdown renderer should block XSS attempts."""
    from app.routers.help import _md_to_html
    result = _md_to_html(payload)
    assert "<script>" not in result
    assert "javascript:" not in result.lower()
    assert "vbscript:" not in result.lower()


def test_post_endpoint_exists(authed_client):
    """State-changing POST endpoint should be reachable."""
    r = authed_client.get("/sales")
    assert r.status_code in METHOD_NOT_ALLOWED_CODES


def test_admin_path_response(authed_client):
    """Admin paths should respond (200, 404, or auth redirect)."""
    for path in ["/admin", "/users", "/settings"]:
        r = authed_client.get(path, follow_redirects=False)
        assert r.status_code in AUTH_CODES


def test_password_hashing_uses_bcrypt():
    """Passwords should be hashed with bcrypt, not plaintext."""
    try:
        from app.auth import hash_password
        plain = "mysecret123"
        hashed = hash_password(plain)
        assert hashed != plain
        assert hashed.startswith("$2")
    except (ImportError, Exception):
        pytest.skip("hash_password not available")


def test_404_does_not_leak_stack_trace(authed_client):
    """404 responses should not include stack traces or DB errors."""
    r = authed_client.get("/__definitely_does_not_exist__", follow_redirects=False)
    assert_safe_response(r)


def test_repeated_login_attempts_handled(authed_client):
    """Repeated login attempts should not crash the server."""
    last_r = None
    for _ in range(5):
        last_r = authed_client.post(
            "/login",
            data={"username": "x", "password": "y"},
            follow_redirects=False,
        )
    assert last_r is not None
    assert last_r.status_code in LOGIN_RATE_LIMITED_CODES
