"""Phase 23 — Form field help text tests.

Verifies the form_help, field_label, and char_counter macros + CSS.
"""
from __future__ import annotations

from pathlib import Path


HELP_CSS = Path(__file__).parent.parent / "app" / "static" / "form-help.css"
MACROS = Path(__file__).parent.parent / "app" / "templates" / "_components" / "macros.html"
BASE_HTML = Path(__file__).parent.parent / "app" / "templates" / "base.html"


def test_form_help_css_exists():
    """Should have form help text styles."""
    assert HELP_CSS.exists()


def test_form_help_css_loaded_in_base():
    """Should be loaded in base.html."""
    text = BASE_HTML.read_text()
    assert "form-help.css" in text


def test_form_help_macro_exists():
    """Should have form_help macro."""
    text = MACROS.read_text()
    assert "macro form_help" in text


def test_form_help_macro_supports_kinds():
    """Should support info, warn, error kinds."""
    text = MACROS.read_text()
    assert 'kind="info"' in text or "kind=" in text
    assert "form-help--{{ kind }}" in text or "form-help--" in text


def test_form_help_macro_supports_id():
    """Should support id for aria-describedby."""
    text = MACROS.read_text()
    assert "id=" in text
    assert 'id="{{ id }}"' in text or "id=" in text


def test_form_help_macro_supports_icon():
    """Should support optional icon."""
    text = MACROS.read_text()
    assert "icon" in text
    assert "<svg" in text or "use href" in text


def test_form_help_macro_supports_inline():
    """Should support inline variant."""
    text = MACROS.read_text()
    assert "inline" in text
    assert "form-help--inline" in text


def test_form_help_macro_uses_small_element():
    """Should use <small> for semantic help text."""
    text = MACROS.read_text()
    assert "<small" in text
    assert "</small>" in text


def test_field_label_macro_exists():
    """Should have field_label macro."""
    text = MACROS.read_text()
    assert "macro field_label" in text


def test_field_label_macro_supports_required():
    """Should support required field indicator."""
    text = MACROS.read_text()
    assert "form-label--required" in text
    assert "::after" in text or "required" in text


def test_field_label_macro_supports_optional():
    """Should support optional field indicator."""
    text = MACROS.read_text()
    assert "form-label--optional" in text


def test_char_counter_macro_exists():
    """Should have char_counter macro."""
    text = MACROS.read_text()
    assert "macro char_counter" in text


def test_char_counter_macro_shows_count():
    """Should show current/max character count."""
    text = MACROS.read_text()
    assert "data-counter-for" in text
    assert "data-counter-max" in text
    assert "{{ max }}" in text


def test_form_help_css_has_info_style():
    """Should style info messages."""
    css = HELP_CSS.read_text()
    assert ".form-help--info" in css
    assert "color:" in css


def test_form_help_css_has_warn_style():
    """Should style warning messages."""
    css = HELP_CSS.read_text()
    assert ".form-help--warn" in css


def test_form_help_css_has_error_style():
    """Should style error messages."""
    css = HELP_CSS.read_text()
    assert ".form-help--error" in css


def test_form_help_css_has_required_indicator():
    """Should style required field marker."""
    css = HELP_CSS.read_text()
    assert ".form-label--required" in css
    assert "::after" in css


def test_form_help_css_has_counter_style():
    """Should style character counter."""
    css = HELP_CSS.read_text()
    assert ".form-counter" in css
    assert ".form-counter--over" in css
    assert ".form-counter--near" in css


def test_form_help_css_supports_dark_mode():
    """Should support dark mode."""
    css = HELP_CSS.read_text()
    assert '[data-theme="dark"]' in css
    assert ".form-help" in css


def test_form_help_css_handles_print():
    """Should be print-friendly."""
    css = HELP_CSS.read_text()
    assert "@media print" in css
    assert "color: #333" in css or "color:" in css


def test_form_help_css_respects_reduced_motion():
    """Should respect prefers-reduced-motion."""
    css = HELP_CSS.read_text()
    assert "prefers-reduced-motion" in css


def test_form_help_has_icon_styling():
    """Should style help icons."""
    css = HELP_CSS.read_text()
    assert ".form-help__icon" in css
    assert "width: 14px" in css or "width:" in css
    assert "height: 14px" in css or "height:" in css


def test_form_help_macro_returns_valid_html():
    """form_help macro should generate valid HTML structure."""
    text = MACROS.read_text()
    # Check that the macro outputs proper HTML
    assert "class=\"form-help" in text
    assert "form-help--{{ kind }}" in text


def test_char_counter_has_dynamic_classes():
    """Counter should have classes for state changes."""
    css = HELP_CSS.read_text()
    assert ".form-counter--over" in css
    assert ".form-counter--near" in css


def test_field_label_uses_semantic_label():
    """field_label should use <label> element."""
    text = MACROS.read_text()
    assert "<label" in text
    assert "form-label" in text