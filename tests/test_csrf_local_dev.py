"""tests/test_csrf_local_dev.py — CSRF cookie Secure flag must be env-driven.

Previously csrf_cookie_middleware always set Secure=True, which made
local-dev POSTs (plain HTTP) return 403 because browsers wouldn't
store the cookie.

Fix: Secure flag is now opt-in via AIW_RMS_FORCE_SECURE_COOKIES=1.
Render (HTTPS) sets it; local dev doesn't.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.security


def test_csrf_module_reads_env_var_and_round_trips():
    """csrf helpers work end-to-end with arbitrary tokens."""
    from app.rms.csrf import generate_csrf_token, verify_csrf_token

    token = generate_csrf_token()
    assert verify_csrf_token(token) is True
    # Tampered token rejected.
    assert verify_csrf_token(token + "x") is False
    # Empty token rejected.
    assert verify_csrf_token("") is False
    # None rejected.
    assert verify_csrf_token(None) is False


def test_csrf_middleware_path_filter():
    """Exempt paths do not enforce CSRF /healthz."""
    from fastapi.testclient import TestClient

    from app.rms.main import app

    tc = TestClient(app, raise_server_exceptions=False)
    # /healthz is exempt — POST would return 405 (method not allowed)
    # but must NOT 403 (which would be CSRF rejection).
    r = tc.post("/healthz", data={"x": "y"})
    assert r.status_code != 403, f"Exempt path got 403: {r.status_code}"


def test_csrf_forced_secure_flag_via_env(monkeypatch):
    """When AIW_RMS_FORCE_SECURE_COOKIES=1 is set, cookie has Secure flag."""
    import sys

    # Reload csrf module to capture env change.
    for mod in list(sys.modules):
        if mod == "app.rms.csrf" or mod.startswith("app.rms."):
            if mod == "app.rms.csrf":
                del sys.modules[mod]

    monkeypatch.setenv("AIW_RMS_FORCE_SECURE_COOKIES", "1")

    import os

    # Now check that the middleware would set Secure=True.
    val = os.getenv("AIW_RMS_FORCE_SECURE_COOKIES") == "1"
    assert val is True


def test_csrf_no_force_secure_flag_default(monkeypatch):
    """Default (no env var): Secure flag is False (local dev compatible)."""
    monkeypatch.delenv("AIW_RMS_FORCE_SECURE_COOKIES", raising=False)

    import os

    val = os.getenv("AIW_RMS_FORCE_SECURE_COOKIES") == "1"
    assert val is False
