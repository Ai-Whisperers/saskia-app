"""Phase 36 — Number input stepper tests.

Verifies the data-stepper enhanced number input.
"""
from __future__ import annotations

from pathlib import Path


STEPPER_JS = Path(__file__).parent.parent / "app" / "static" / "stepper.js"
STEPPER_CSS = Path(__file__).parent.parent / "app" / "static" / "stepper.css"
BASE_HTML = Path(__file__).parent.parent / "app" / "templates" / "base.html"


def test_stepper_js_exists():
    """Should have stepper script."""
    assert STEPPER_JS.exists()


def test_stepper_css_exists():
    """Should have stepper styles."""
    assert STEPPER_CSS.exists()


def test_stepper_loaded_in_base():
    """Should be loaded in base.html."""
    text = BASE_HTML.read_text()
    assert "stepper.js" in text
    assert "stepper.css" in text


def test_stepper_exposes_global():
    """Should expose Stepper globally."""
    js = STEPPER_JS.read_text()
    assert "window.Stepper" in js


def test_stepper_uses_iife():
    """Should be wrapped in IIFE."""
    js = STEPPER_JS.read_text()
    assert "(function()" in js
    assert "'use strict'" in js


def test_stepper_uses_data_attribute():
    """Should use data-stepper attribute."""
    js = STEPPER_JS.read_text()
    assert "data-stepper" in js


def test_stepper_creates_wrapper():
    """Should create wrapper element."""
    js = STEPPER_JS.read_text()
    assert "createElement('div')" in js
    assert "stepper" in js


def test_stepper_creates_buttons():
    """Should create +/- buttons."""
    js = STEPPER_JS.read_text()
    assert "_createButton" in js
    assert "'+'" in js or "'-'" in js
    assert "Aumentar" in js or "Disminuir" in js


def test_stepper_handles_min_max():
    """Should respect min/max bounds."""
    js = STEPPER_JS.read_text()
    assert "parseFloat(input.min)" in js
    assert "parseFloat(input.max)" in js
    assert "input.max)" in js


def test_stepper_handles_step():
    """Should use step attribute."""
    js = STEPPER_JS.read_text()
    assert "parseFloat(input.step)" in js


def test_stepper_aligns_to_step():
    """Should align values to step grid."""
    js = STEPPER_JS.read_text()
    assert "Math.round" in js
    assert "toFixed" in js


def test_stepper_decimal_precision():
    """Should preserve step decimal precision."""
    js = STEPPER_JS.read_text()
    assert "decimals" in js
    assert ".split('.')[1]" in js


def test_stepper_dispatches_events():
    """Should dispatch input and change events."""
    js = STEPPER_JS.read_text()
    assert "new Event('input'" in js
    assert "new Event('change'" in js


def test_stepper_handles_any_step():
    """Should handle step='any'."""
    js = STEPPER_JS.read_text()
    assert "'any'" in js


def test_stepper_updates_button_state():
    """Should disable buttons at bounds."""
    js = STEPPER_JS.read_text()
    assert ".disabled" in js
    assert "_updateButtons" in js


def test_stepper_prevents_double_init():
    """Should not re-enhance same input."""
    js = STEPPER_JS.read_text()
    assert "stepperReady" in js


def test_stepper_dom_ready():
    """Should wait for DOM ready."""
    js = STEPPER_JS.read_text()
    assert "readyState" in js
    assert "DOMContentLoaded" in js


def test_stepper_iterates_inputs():
    """Should iterate all matching inputs."""
    js = STEPPER_JS.read_text()
    assert "querySelectorAll" in js
    assert "forEach" in js


def test_stepper_handles_no_min_max():
    """Should handle inputs without min/max."""
    js = STEPPER_JS.read_text()
    assert "isNaN" in js


def test_stepper_has_aria_label():
    """Should have aria-labels on buttons."""
    js = STEPPER_JS.read_text()
    assert "aria-label" in js


def test_stepper_handles_clamp():
    """Should clamp to bounds."""
    js = STEPPER_JS.read_text()
    assert "newValue < min" in js
    assert "newValue > max" in js


def test_stepper_css_flex():
    """CSS should use flex layout."""
    css = STEPPER_CSS.read_text()
    assert ".stepper" in css
    assert "display: inline-flex" in css or "display: inline-flex;" in css


def test_stepper_css_button_styling():
    """CSS should style buttons."""
    css = STEPPER_CSS.read_text()
    assert ".stepper__btn" in css
    assert "width: 32px" in css
    assert "height: 32px" in css


def test_stepper_css_disabled_state():
    """CSS should style disabled state."""
    css = STEPPER_CSS.read_text()
    assert ":disabled" in css
    assert "opacity:" in css


def test_stepper_css_touch_targets():
    """CSS should have 44px min for mobile."""
    css = STEPPER_CSS.read_text()
    assert "@media (max-width: 768px)" in css
    assert "width: 44px" in css


def test_stepper_css_dark_mode():
    """CSS should support dark mode."""
    css = STEPPER_CSS.read_text()
    assert '[data-theme="dark"]' in css


def test_stepper_css_input_centered():
    """CSS should center input text."""
    css = STEPPER_CSS.read_text()
    assert "text-align: center" in css


def test_stepper_css_no_radius():
    """CSS should remove input border-radius."""
    css = STEPPER_CSS.read_text()
    assert "border-radius: 0" in css