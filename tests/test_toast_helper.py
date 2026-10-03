"""Sprint Week 1 — Toast helper tests.

Verifies the Toast notification helper that wraps saskia-toast.
"""
from __future__ import annotations

from pathlib import Path


TOAST_JS = Path(__file__).parent.parent / "app" / "static" / "toast-helper.js"
BASE_HTML = Path(__file__).parent.parent / "app" / "templates" / "base.html"


def test_toast_helper_exists():
    """Should have a dedicated toast helper."""
    assert TOAST_JS.exists()


def test_toast_helper_loaded_in_base():
    """Should be loaded in base.html."""
    text = BASE_HTML.read_text()
    assert "toast-helper.js" in text


def test_toast_helper_has_success():
    """Should support success notifications."""
    js = TOAST_JS.read_text()
    assert "success:" in js
    assert "'success'" in js


def test_toast_helper_has_error():
    """Should support error notifications."""
    js = TOAST_JS.read_text()
    assert "error:" in js
    assert "'error'" in js


def test_toast_helper_has_warning():
    """Should support warning notifications."""
    js = TOAST_JS.read_text()
    assert "warning:" in js
    assert "'warning'" in js


def test_toast_helper_has_info():
    """Should support info notifications."""
    js = TOAST_JS.read_text()
    assert "info:" in js
    assert "'info'" in js


def test_toast_helper_uses_saskia_toast():
    """Should use saskia-toast Web Component."""
    js = TOAST_JS.read_text()
    assert "saskia-toast" in js
    assert "saskia-toast-stack" in js


def test_toast_helper_supports_duration():
    """Should support custom duration."""
    js = TOAST_JS.read_text()
    assert "duration" in js


def test_toast_helper_has_confirm():
    """Should support confirmation toasts with actions."""
    js = TOAST_JS.read_text()
    assert "confirm:" in js
    assert "onConfirm" in js
    assert "onCancel" in js


def test_toast_helper_auto_removes():
    """Should auto-remove after duration."""
    js = TOAST_JS.read_text()
    assert "setTimeout" in js
    assert "remove" in js


def test_toast_helper_uses_iife():
    """Should be wrapped in IIFE."""
    js = TOAST_JS.read_text()
    assert "(function()" in js
    assert "'use strict'" in js


def test_toast_helper_exposes_global():
    """Should expose Toast globally."""
    js = TOAST_JS.read_text()
    assert "window.Toast" in js


def test_toast_helper_has_default_durations():
    """Should have appropriate default durations for each type."""
    js = TOAST_JS.read_text()
    # Error should last longer than success
    assert "6000" in js  # error default
    assert "4000" in js  # success default


def test_toast_helper_handles_missing_stack():
    """Should gracefully handle missing toast stack."""
    js = TOAST_JS.read_text()
    assert "console.warn" in js
    assert "not found" in js


def test_toast_helper_creates_dom_element():
    """Should create DOM elements dynamically."""
    js = TOAST_JS.read_text()
    assert "createElement" in js
    assert "appendChild" in js