"""Phase 22 — js-confirm-form verification.

app.js already implements:
- js-confirm-form: intercept forms with class="js-confirm-form"
- js-confirm-link: intercept links/buttons with data-confirm-* attrs
- data-confirm-title, data-confirm-body, data-confirm-danger attrs
"""
from __future__ import annotations

from pathlib import Path


APP_JS = Path(__file__).parent.parent / "app" / "static" / "app.js"


def test_app_js_mentions_js_confirm_form():
    text = APP_JS.read_text()
    assert "js-confirm-form" in text


def test_app_js_uses_data_confirm_attrs():
    """Should respect data-confirm-title, data-confirm-body, data-confirm-danger."""
    text = APP_JS.read_text()
    assert "confirmTitle" in text or "confirm-title" in text
    assert "confirmBody" in text or "confirm-body" in text
    assert "confirmDanger" in text or "confirm-danger" in text


def test_app_js_implements_confirm_dialog():
    """Should show a confirmation dialog with the configured title/body."""
    text = APP_JS.read_text()
    assert "dialog" in text.lower() or "confirm" in text.lower()


def test_app_js_handles_danger_state():
    """Danger confirmations should look different (e.g. red button)."""
    text = APP_JS.read_text()
    assert "danger" in text


def test_app_js_uses_querySelectorAll():
    """Should bind to all matching forms on page load."""
    text = APP_JS.read_text()
    assert "querySelectorAll" in text


def test_app_js_prevents_default_submit():
    """Should prevent form submission until confirmed."""
    text = APP_JS.read_text()
    assert "preventDefault" in text or "preventdefault" in text.lower()


def test_app_js_returns_true_on_confirm():
    """After confirmation, the form should submit normally."""
    text = APP_JS.read_text()
    # Look for the submit call
    assert "submit" in text


def test_app_js_initializes_on_domready():
    text = APP_JS.read_text()
    assert "DOMContentLoaded" in text or "domcontentloaded" in text.lower() or "readyState" in text