"""Phase 30 — Clipboard utility tests.

Verifies the data-copy and data-copy-from click-to-copy utility.
"""

from __future__ import annotations

from pathlib import Path

CLIPBOARD_JS = Path(__file__).parent.parent / "app" / "static" / "clipboard.js"
CLIPBOARD_CSS = Path(__file__).parent.parent / "app" / "static" / "clipboard.css"
BASE_HTML = Path(__file__).parent.parent / "app" / "templates" / "base.html"


def test_clipboard_js_exists():
    """Should have a clipboard script."""
    assert CLIPBOARD_JS.exists()


def test_clipboard_css_exists():
    """Should have feedback styles."""
    assert CLIPBOARD_CSS.exists()


def test_clipboard_loaded_in_base():
    """Should be loaded in base.html."""
    text = BASE_HTML.read_text()
    assert "clipboard.js" in text
    assert "clipboard.css" in text


def test_clipboard_exposes_global():
    """Should expose Clipboard globally."""
    js = CLIPBOARD_JS.read_text()
    assert "window.Clipboard" in js


def test_clipboard_uses_iife():
    """Should be wrapped in IIFE."""
    js = CLIPBOARD_JS.read_text()
    assert "(function()" in js
    assert "'use strict'" in js


def test_clipboard_uses_data_copy():
    """Should support data-copy attribute for static text."""
    js = CLIPBOARD_JS.read_text()
    assert "data-copy" in js
    assert "data-copy-from" in js


def test_clipboard_uses_modern_api():
    """Should use modern navigator.clipboard API."""
    js = CLIPBOARD_JS.read_text()
    assert "navigator.clipboard" in js
    assert "writeText" in js


def test_clipboard_has_fallback():
    """Should have execCommand fallback for older browsers."""
    js = CLIPBOARD_JS.read_text()
    assert "_fallback" in js
    assert "execCommand" in js
    assert "textarea" in js


def test_clipboard_shows_feedback():
    """Should show visual feedback on copy."""
    js = CLIPBOARD_JS.read_text()
    assert "_showFeedback" in js
    assert "copy-success" in js
    assert "copy-error" in js


def test_clipboard_supports_custom_messages():
    """Should support custom success/error messages via data attributes."""
    js = CLIPBOARD_JS.read_text()
    assert "data-copy-success" in js
    assert "data-copy-error" in js
    assert "Copiado" in js


def test_clipboard_event_delegation():
    """Should use event delegation for performance."""
    js = CLIPBOARD_JS.read_text()
    assert "addEventListener('click'" in js
    assert "closest(" in js


def test_clipboard_resets_after_timeout():
    """Should restore original button state after timeout."""
    js = CLIPBOARD_JS.read_text()
    assert "setTimeout" in js
    assert "1500" in js


def test_clipboard_aria_live():
    """Should announce result to screen readers."""
    js = CLIPBOARD_JS.read_text()
    assert "aria-live" in js
    assert "polite" in js


def test_clipboard_logs_errors():
    """Should log errors to console."""
    js = CLIPBOARD_JS.read_text()
    assert "console.error" in js
    assert "Copy failed" in js


def test_clipboard_finds_target():
    """Should find target via data-copy-from selector."""
    js = CLIPBOARD_JS.read_text()
    assert "querySelector" in js
    assert "textContent" in js
    assert ".value" in js


def test_clipboard_handles_missing_target():
    """Should handle missing target gracefully."""
    js = CLIPBOARD_JS.read_text()
    assert "if (!target) return" in js or "if (!target)" in js


def test_clipboard_handles_empty_text():
    """Should handle empty text gracefully."""
    js = CLIPBOARD_JS.read_text()
    assert "if (!text) return" in js or "if (!text)" in js


def test_clipboard_prevents_default():
    """Should preventDefault to avoid form submission."""
    js = CLIPBOARD_JS.read_text()
    assert "preventDefault" in js


def test_clipboard_dom_ready():
    """Should wait for DOM ready if needed."""
    js = CLIPBOARD_JS.read_text()
    assert "readyState" in js
    assert "DOMContentLoaded" in js


def test_clipboard_css_has_success_class():
    """CSS should style copy-success."""
    css = CLIPBOARD_CSS.read_text()
    assert ".copy-success" in css
    assert "color: white" in css or "color: white" in css.replace(" ", "")


def test_clipboard_css_has_error_class():
    """CSS should style copy-error."""
    css = CLIPBOARD_CSS.read_text()
    assert ".copy-error" in css


def test_clipboard_css_uses_css_vars():
    """CSS should use CSS variables for colors."""
    css = CLIPBOARD_CSS.read_text()
    assert "var(--color-success" in css
    assert "var(--color-danger" in css


def test_clipboard_css_transition():
    """CSS should have smooth transitions."""
    css = CLIPBOARD_CSS.read_text()
    assert "transition" in css


def test_clipboard_css_respects_reduced_motion():
    """CSS should respect prefers-reduced-motion."""
    css = CLIPBOARD_CSS.read_text()
    assert "prefers-reduced-motion" in css


def test_clipboard_css_uses_important():
    """CSS should use !important to override button styles during feedback."""
    css = CLIPBOARD_CSS.read_text()
    assert "!important" in css


def test_clipboard_css_targets_data_attributes():
    """CSS should target the data-copy/data-copy-from attributes."""
    css = CLIPBOARD_CSS.read_text()
    assert "[data-copy]" in css
    assert "[data-copy-from]" in css
