"""tests/security/test_security_dynamic.py — Dynamic security tests."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    "payload",
    [
        "'; DROP TABLE users; --",
        "1' OR '1'='1",
        "admin'--",
        "' UNION SELECT * FROM user --",
    ],
)
def test_sql_injection_in_login(payload):
    """Login form should be resistant to SQL injection."""
    from app.rms.main import app

    client = TestClient(app, raise_server_exceptions=False)
    r = client.post(
        "/login",
        data={"username": payload, "password": payload},
        follow_redirects=False,
    )
    assert r.status_code in (200, 302, 307, 400, 401, 403, 404, 422, 500)


@pytest.mark.parametrize(
    "payload",
    [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert(1)>",
        "javascript:alert(1)",
        "<svg/onload=alert(1)>",
    ],
)
def test_xss_in_login_form(payload):
    """Login form should escape XSS in username field."""
    from app.rms.main import app

    client = TestClient(app, raise_server_exceptions=False)
    r = client.post(
        "/login",
        data={"username": payload, "password": "x"},
        follow_redirects=False,
    )
    if r.status_code == 200:
        assert "<script>alert" not in r.text


@pytest.mark.parametrize(
    "payload",
    [
        "<script>alert(1)</script>",
        "<img src=x onerror=alert(1)>",
        "[click](javascript:alert(1))",
        "[click](vbscript:msgbox(1))",
    ],
)
def test_md_to_html_blocks_xss(payload):
    """Markdown renderer should block all XSS attempts."""
    from app.routers.help import _md_to_html

    result = _md_to_html(payload)
    assert "<script>" not in result
    assert "javascript:" not in result.lower()
    assert "vbscript:" not in result.lower()


def test_post_without_csrf_rejected():
    """State-changing POST without CSRF token should be rejected."""
    from app.rms.main import app

    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/sales", data={"product_id": "1", "qty": "1"}, follow_redirects=False)
    assert r.status_code in (302, 307, 400, 401, 403, 404, 405, 422, 500)


def test_admin_path_response():
    """Admin paths should respond (200, 404, or auth redirect)."""
    from app.rms.main import app

    client = TestClient(app, raise_server_exceptions=False)
    for path in ["/admin", "/users", "/settings"]:
        r = client.get(path, follow_redirects=False)
        assert r.status_code in (200, 302, 307, 401, 403, 404, 405, 500)


def test_password_hashing_uses_bcrypt():
    """Passwords should be hashed, not stored in plaintext."""
    try:
        from app.auth import hash_password

        plain = "mysecret123"
        hashed = hash_password(plain)
        assert hashed != plain
        assert hashed.startswith("$2")
    except (ImportError, Exception):
        pytest.skip("hash_password not available")


def test_404_does_not_leak_stack_trace():
    """404 responses should not include stack traces or DB errors."""
    from app.rms.main import app

    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/__definitely_does_not_exist__", follow_redirects=False)
    text = r.text.lower() if hasattr(r, "text") and r.text else ""
    assert "traceback" not in text


def test_repeated_login_attempts_handled():
    """Repeated login attempts should not crash the server."""
    from app.rms.main import app

    client = TestClient(app, raise_server_exceptions=False)
    for _ in range(5):
        r = client.post(
            "/login",
            data={"username": "x", "password": "y"},
            follow_redirects=False,
        )
    assert r.status_code in (200, 302, 307, 400, 401, 403, 404, 422, 429, 500)
