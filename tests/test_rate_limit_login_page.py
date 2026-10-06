"""TDD: rate-limited login must show a styled page with retry countdown
+ button, not a raw 429 JSON blob.

Why this test exists:
- 2026-10-06 the user hit "Demasiados intentos. Intenta nuevamente en
  unos minutos." and the only option was to wait 5 minutes. There was no
  "try now" link. The 429 was JSON, not styled.
- The fix: redirect back to /login?error=...&retry_after=N which renders
  the existing login template with a countdown + retry button.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest


AUTH_PY = Path(__file__).resolve().parents[1] / "app" / "routers" / "auth.py"
LOGIN_HTML = Path(__file__).resolve().parents[1] / "app" / "templates" / "login.html"


def test_auth_redirects_on_rate_limit():
    text = AUTH_PY.read_text()
    assert "RedirectResponse" in text, "rate-limited login must redirect"
    assert "retry_after" in text, "must pass retry_after to /login"


def test_login_template_renders_retry_button():
    text = LOGIN_HTML.read_text()
    assert "retry_after" in text, "template must accept retry_after"
    assert 'id="retry-btn"' in text, "template must render a retry button"
    assert 'id="retry-countdown"' in text, "template must show countdown"


def test_login_template_countdown_decrements():
    text = LOGIN_HTML.read_text()
    # Verify the tick() function exists and decrements remaining
    assert "function tick" in text
    assert "remaining -= 1" in text
    assert "btn.disabled = false" in text, "button must enable at 0"


def test_rate_limit_redirect_url():
    """The redirect URL must include both error and retry_after query params."""
    text = AUTH_PY.read_text()
    assert "/login?error=" in text
    assert "&retry_after=" in text


def test_login_form_accepts_retry_after_param():
    """The GET handler must accept retry_after so the redirect lands."""
    text = AUTH_PY.read_text()
    assert "retry_after: int | None = None" in text
    assert '"retry_after": retry_after' in text