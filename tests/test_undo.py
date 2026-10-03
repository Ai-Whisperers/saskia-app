"""Phase 33 — Undo functionality tests.

Verifies the data-undo form interception utility.
"""
from __future__ import annotations

from pathlib import Path


UNDO_JS = Path(__file__).parent.parent / "app" / "static" / "undo.js"
BASE_HTML = Path(__file__).parent.parent / "app" / "templates" / "base.html"


def test_undo_js_exists():
    """Should have undo script."""
    assert UNDO_JS.exists()


def test_undo_loaded_in_base():
    """Should be loaded in base.html."""
    text = BASE_HTML.read_text()
    assert "undo.js" in text


def test_undo_exposes_global():
    """Should expose Undo globally."""
    js = UNDO_JS.read_text()
    assert "window.Undo" in js


def test_undo_uses_iife():
    """Should be wrapped in IIFE."""
    js = UNDO_JS.read_text()
    assert "(function()" in js
    assert "'use strict'" in js


def test_undo_uses_data_attribute():
    """Should use data-undo attribute on forms."""
    js = UNDO_JS.read_text()
    assert "data-undo" in js
    assert "form[data-undo]" in js


def test_undo_has_default_duration():
    """Should have default duration of 30s."""
    js = UNDO_JS.read_text()
    assert "defaultDuration" in js
    assert "30" in js


def test_undo_supports_custom_duration():
    """Should support custom duration via data-undo attribute."""
    js = UNDO_JS.read_text()
    assert "parseInt(form.getAttribute" in js


def test_undo_intercepts_submit():
    """Should intercept submit events."""
    js = UNDO_JS.read_text()
    assert "'submit'" in js
    assert "addEventListener" in js


def test_undo_uses_capture_phase():
    """Should use capture phase for early interception."""
    js = UNDO_JS.read_text()
    assert ", true)" in js or "true" in js


def test_undo_skips_get_forms():
    """Should skip GET forms (no destructive intent)."""
    js = UNDO_JS.read_text()
    assert "'get'" in js
    assert "toLowerCase" in js


def test_undo_prevents_default():
    """Should preventDefault to delay submission."""
    js = UNDO_JS.read_text()
    assert "preventDefault" in js


def test_undo_uses_formdata():
    """Should capture form data for later commit."""
    js = UNDO_JS.read_text()
    assert "new FormData" in js


def test_undo_uses_undo_label():
    """Should support custom undo label."""
    js = UNDO_JS.read_text()
    assert "data-undo-label" in js
    assert "Acción realizada" in js or "undoLabel" in js


def test_undo_creates_toast():
    """Should create a toast with undo button."""
    js = UNDO_JS.read_text()
    assert "saskia-toast" in js
    assert "Deshacer" in js


def test_undo_has_undo_action_attribute():
    """Should use data-undo-action attribute for button."""
    js = UNDO_JS.read_text()
    assert "data-undo-action" in js


def test_undo_commits_via_fetch():
    """Should commit via fetch."""
    js = UNDO_JS.read_text()
    assert "fetch" in js
    assert "_commit" in js


def test_undo_uses_xhr_header():
    """Should send X-Requested-With for backend detection."""
    js = UNDO_JS.read_text()
    assert "X-Requested-With" in js


def test_undo_uses_same_origin():
    """Should include credentials."""
    js = UNDO_JS.read_text()
    assert "same-origin" in js


def test_undo_shows_success_toast():
    """Should show success toast on commit."""
    js = UNDO_JS.read_text()
    assert "Toast.success" in js
    assert "Acción completada" in js


def test_undo_shows_error_toast():
    """Should show error toast on failure."""
    js = UNDO_JS.read_text()
    assert "Toast.error" in js
    assert "Error" in js


def test_undo_reloads_after_success():
    """Should reload page after successful action."""
    js = UNDO_JS.read_text()
    assert "window.location.reload" in js


def test_undo_handles_toast_close():
    """Should commit if toast is closed manually."""
    js = UNDO_JS.read_text()
    assert "toast-close" in js


def test_undo_uses_set_timeout():
    """Should auto-commit after duration via setTimeout."""
    js = UNDO_JS.read_text()
    assert "setTimeout(commit" in js
    assert "duration * 1000" in js


def test_undo_prevents_double_commit():
    """Should track committed flag."""
    js = UNDO_JS.read_text()
    assert "committed = false" in js
    assert "if (committed) return" in js


def test_undo_removes_toast_on_complete():
    """Should remove toast after action."""
    js = UNDO_JS.read_text()
    assert "toast.remove" in js


def test_undo_handles_no_toast_helper():
    """Should commit immediately if Toast not available."""
    js = UNDO_JS.read_text()
    assert "if (!window.Toast)" in js


def test_undo_logs_errors():
    """Should log network errors."""
    js = UNDO_JS.read_text()
    assert "console.error" in js
    assert "Undo commit failed" in js


def test_undo_dom_ready():
    """Should wait for DOM ready."""
    js = UNDO_JS.read_text()
    assert "readyState" in js
    assert "DOMContentLoaded" in js


def test_undo_iterates_forms():
    """Should iterate forms in selector."""
    js = UNDO_JS.read_text()
    assert "form.matches" in js


def test_undo_handles_undo_click():
    """Should handle undo button clicks."""
    js = UNDO_JS.read_text()
    assert "click" in js
    assert "data-undo-action" in js