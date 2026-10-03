"""Phase 22 — Touch targets and tooltip component tests.

Verifies WCAG 2.5.5 compliance (44px min) and the saskia-tooltip Web Component.
"""
from __future__ import annotations

from pathlib import Path


TOUCH_CSS = Path(__file__).parent.parent / "app" / "static" / "touch-targets.css"
TOOLTIP_JS = Path(__file__).parent.parent / "app" / "static" / "saskia-tooltip.js"
TOOLTIP_CSS = Path(__file__).parent.parent / "app" / "static" / "saskia-tooltip.css"
BASE_HTML = Path(__file__).parent.parent / "app" / "templates" / "base.html"


def test_touch_targets_css_exists():
    """Should have touch target enforcement CSS."""
    assert TOUCH_CSS.exists()


def test_touch_targets_loaded_in_base():
    """Should be loaded in base.html."""
    text = BASE_HTML.read_text()
    assert "touch-targets.css" in text


def test_touch_targets_44px_minimum():
    """All interactive elements should be at least 44px (WCAG 2.5.5)."""
    css = TOUCH_CSS.read_text()
    assert "min-height: 44px" in css
    assert "min-width: 44px" in css


def test_touch_targets_covers_buttons():
    """Should cover .btn and button elements."""
    css = TOUCH_CSS.read_text()
    assert ".btn" in css
    assert "button:" in css


def test_touch_targets_covers_form_inputs():
    """Should cover form controls and inputs."""
    css = TOUCH_CSS.read_text()
    assert ".form-control" in css
    assert "input[type=" in css


def test_touch_targets_covers_combo():
    """Should cover saskia-combo and combo rows."""
    css = TOUCH_CSS.read_text()
    assert "saskia-combo" in css
    assert ".combo-row" in css
    assert ".combo-toggle" in css


def test_touch_targets_covers_navigation():
    """Should cover nav links and tabs."""
    css = TOUCH_CSS.read_text()
    assert ".nav-link" in css
    assert ".tab" in css


def test_touch_targets_mobile_only():
    """Should only apply on mobile (≤768px)."""
    css = TOUCH_CSS.read_text()
    assert "@media (max-width: 768px)" in css


def test_touch_targets_prevents_ios_zoom():
    """Should use 16px font to prevent iOS zoom on focus."""
    css = TOUCH_CSS.read_text()
    assert "font-size: 16px" in css


def test_touch_targets_handles_coarse_pointer():
    """Should handle coarse pointer (touch) specifically."""
    css = TOUCH_CSS.read_text()
    assert "pointer: coarse" in css


def test_touch_targets_extends_icon_buttons():
    """Should extend icon button tap area."""
    css = TOUCH_CSS.read_text()
    assert ".btn-icon" in css
    assert "padding: 10px" in css


def test_touch_targets_table_rows():
    """Should make table rows tappable."""
    css = TOUCH_CSS.read_text()
    assert ".table tbody tr" in css
    assert "min-height: 48px" in css


def test_touch_targets_checkbox_radio():
    """Should scale checkbox/radio for better tap area."""
    css = TOUCH_CSS.read_text()
    assert "input[type=\"checkbox\"]" in css
    assert "input[type=\"radio\"]" in css
    assert "transform: scale(1.3)" in css


# Tooltip tests

def test_tooltip_js_exists():
    """Should have a tooltip Web Component."""
    assert TOOLTIP_JS.exists()


def test_tooltip_css_exists():
    """Should have tooltip styles."""
    assert TOOLTIP_CSS.exists()


def test_tooltip_loaded_in_base():
    """Should be loaded in base.html."""
    text = BASE_HTML.read_text()
    assert "saskia-tooltip.js" in text
    assert "saskia-tooltip.css" in text


def test_tooltip_registers_web_component():
    """Should register a custom element."""
    js = TOOLTIP_JS.read_text()
    assert "class SaskiaTooltip" in js
    assert "customElements.define" in js
    assert "'saskia-tooltip'" in js or "\"saskia-tooltip\"" in js


def test_tooltip_supports_text_attribute():
    """Should support text attribute for tooltip content."""
    js = TOOLTIP_JS.read_text()
    assert "text" in js
    assert "getAttribute" in js


def test_tooltip_supports_position_attribute():
    """Should support position (top, bottom, left, right)."""
    js = TOOLTIP_JS.read_text()
    assert "position" in js
    assert "'top'" in js
    assert "'bottom'" in js
    assert "'left'" in js
    assert "'right'" in js


def test_tooltip_supports_delay():
    """Should support custom show delay."""
    js = TOOLTIP_JS.read_text()
    assert "delay" in js
    assert "setTimeout" in js


def test_tooltip_is_keyboard_accessible():
    """Should support keyboard (focus/blur)."""
    js = TOOLTIP_JS.read_text()
    assert "focus" in js
    assert "blur" in js
    assert "tabindex" in js


def test_tooltip_has_aria_role():
    """Should have proper ARIA role."""
    js = TOOLTIP_JS.read_text()
    assert "role" in js
    assert "tooltip" in js


def test_tooltip_handles_mouse_events():
    """Should handle mouseenter/mouseleave."""
    js = TOOLTIP_JS.read_text()
    assert "mouseenter" in js
    assert "mouseleave" in js


def test_tooltip_handles_viewport_collision():
    """Should handle viewport collision detection."""
    js = TOOLTIP_JS.read_text()
    assert "viewportWidth" in js
    assert "margin" in js


def test_tooltip_auto_attaches():
    """Should auto-attach to elements with saskia-tooltip attribute."""
    js = TOOLTIP_JS.read_text()
    assert "DOMContentLoaded" in js
    assert "saskia-tooltip" in js
    assert "querySelectorAll" in js


def test_tooltip_css_has_arrow():
    """Should have CSS arrows for tooltips."""
    css = TOOLTIP_CSS.read_text()
    assert ".saskia-tooltip--top::after" in css
    assert ".saskia-tooltip--bottom::after" in css
    assert ".saskia-tooltip--left::after" in css
    assert ".saskia-tooltip--right::after" in css


def test_tooltip_css_has_animation():
    """Should have show/hide animation."""
    css = TOOLTIP_CSS.read_text()
    assert "transition:" in css
    assert "saskia-tooltip--visible" in css


def test_tooltip_css_handles_dark_mode():
    """Should support dark mode."""
    css = TOOLTIP_CSS.read_text()
    assert '[data-theme="dark"]' in css


def test_tooltip_css_handles_print():
    """Should hide in print."""
    css = TOOLTIP_CSS.read_text()
    assert "@media print" in css
    assert "display: none" in css


def test_tooltip_css_respects_reduced_motion():
    """Should respect prefers-reduced-motion."""
    css = TOOLTIP_CSS.read_text()
    assert "prefers-reduced-motion" in css