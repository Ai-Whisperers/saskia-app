"""Phase 32 — Inline form validator tests.

Verifies the HTML5 constraint validation auto-applied to forms.
"""
from __future__ import annotations

from pathlib import Path


FV_JS = Path(__file__).parent.parent / "app" / "static" / "form-validator.js"
FV_CSS = Path(__file__).parent.parent / "app" / "static" / "form-validator.css"
BASE_HTML = Path(__file__).parent.parent / "app" / "templates" / "base.html"


def test_form_validator_js_exists():
    """Should have form validator script."""
    assert FV_JS.exists()


def test_form_validator_css_exists():
    """Should have validator styles."""
    assert FV_CSS.exists()


def test_form_validator_loaded_in_base():
    """Should be loaded in base.html."""
    text = BASE_HTML.read_text()
    assert "form-validator.js" in text
    assert "form-validator.css" in text


def test_form_validator_exposes_global():
    """Should expose FormValidator globally."""
    js = FV_JS.read_text()
    assert "window.FormValidator" in js


def test_form_validator_uses_iife():
    """Should be wrapped in IIFE."""
    js = FV_JS.read_text()
    assert "(function()" in js
    assert "'use strict'" in js


def test_form_validator_uses_data_attribute():
    """Should use data-validate attribute on forms."""
    js = FV_JS.read_text()
    assert "data-validate" in js
    assert "form[data-validate" in js


def test_form_validator_uses_checkvalidity():
    """Should use native checkValidity API."""
    js = FV_JS.read_text()
    assert "checkValidity" in js


def test_form_validator_uses_validation_message():
    """Should use validationMessage for error text."""
    js = FV_JS.read_text()
    assert "validationMessage" in js


def test_form_validator_marks_invalid():
    """Should add is-invalid class and aria-invalid=true."""
    js = FV_JS.read_text()
    assert "is-invalid" in js
    assert 'aria-invalid' in js
    assert "'true'" in js


def test_form_validator_marks_valid():
    """Should add is-valid class and aria-invalid=false."""
    js = FV_JS.read_text()
    assert "is-valid" in js
    assert "'false'" in js


def test_form_validator_uses_blur():
    """Should validate on blur for early feedback."""
    js = FV_JS.read_text()
    assert "'blur'" in js


def test_form_validator_uses_input():
    """Should re-validate on input for live correction."""
    js = FV_JS.read_text()
    assert "'input'" in js


def test_form_validator_uses_submit():
    """Should validate on submit."""
    js = FV_JS.read_text()
    assert "'submit'" in js


def test_form_validator_uses_capture():
    """Should use capture phase for blur to catch all blurs."""
    js = FV_JS.read_text()
    assert "true)" in js  # capture flag


def test_form_validator_handles_disabled():
    """Should skip disabled/readOnly fields."""
    js = FV_JS.read_text()
    assert "el.disabled" in js
    assert "el.readOnly" in js


def test_form_validator_handles_saskia_combo():
    """Should work with saskia-combo components."""
    js = FV_JS.read_text()
    assert "select, textarea" in js or "select" in js


def test_form_validator_has_invalid_feedback():
    """Should show invalid-feedback message."""
    js = FV_JS.read_text()
    assert "invalid-feedback" in js
    assert "data-for" in js


def test_form_validator_hides_feedback_when_valid():
    """Should hide feedback when field becomes valid."""
    js = FV_JS.read_text()
    assert "display = 'none'" in js


def test_form_validator_revalidates_on_input_after_error():
    """Should re-validate on input only after an error."""
    js = FV_JS.read_text()
    assert "is-invalid" in js
    assert "if (field.classList.contains" in js


def test_form_validator_public_validate():
    """Should expose public validate method."""
    js = FV_JS.read_text()
    assert "validate(form)" in js
    assert "return true" in js
    assert "return valid" in js or "valid = false" in js


def test_form_validator_event_handlers_bound():
    """Should bind event handlers in init."""
    js = FV_JS.read_text()
    assert "bind(this)" in js


def test_form_validator_iterates_forms():
    """Should iterate all matching forms."""
    js = FV_JS.read_text()
    assert "forEach" in js
    assert "querySelectorAll" in js


def test_form_validator_dom_ready():
    """Should wait for DOM ready."""
    js = FV_JS.read_text()
    assert "readyState" in js
    assert "DOMContentLoaded" in js


def test_form_validator_checks_parents():
    """Should find feedback in parent element."""
    js = FV_JS.read_text()
    assert "parentElement" in js


def test_form_validator_iterates_fields():
    """Should iterate all form fields."""
    js = FV_JS.read_text()
    assert "input, select, textarea" in js


def test_form_validator_uses_matches():
    """Should use matches() for field type check."""
    js = FV_JS.read_text()
    assert ".matches(" in js


def test_form_validator_css_is_invalid_styling():
    """CSS should style is-invalid fields red."""
    css = FV_CSS.read_text()
    assert ".is-invalid" in css
    assert "border-color-danger" in css.replace(" ", "") or "var(--color-danger" in css


def test_form_validator_css_is_valid_styling():
    """CSS should style is-valid fields green."""
    css = FV_CSS.read_text()
    assert ".is-valid" in css
    assert "var(--color-success" in css


def test_form_validator_css_invalid_feedback():
    """CSS should style invalid-feedback messages."""
    css = FV_CSS.read_text()
    assert ".invalid-feedback" in css
    assert "color: var(--color-danger" in css


def test_form_validator_css_focus_shadow():
    """CSS should have focus shadow for invalid fields."""
    css = FV_CSS.read_text()
    assert "focus" in css
    assert "box-shadow" in css


def test_form_validator_css_dark_mode():
    """CSS should support dark mode."""
    css = FV_CSS.read_text()
    assert '[data-theme="dark"]' in css


def test_form_validator_css_background_svg():
    """CSS should use SVG background icon for invalid fields."""
    css = FV_CSS.read_text()
    assert "background-image" in css
    assert "data:image/svg+xml" in css


def test_form_validator_css_uses_important():
    """CSS should use !important for override styles."""
    css = FV_CSS.read_text()
    assert "!important" in css


def test_form_validator_css_responsive_padding():
    """CSS should add padding for icon space."""
    css = FV_CSS.read_text()
    assert "padding-right" in css