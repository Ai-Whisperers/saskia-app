"""Phase 26 — Keyboard shortcut badge tests.

Verifies the shortcut_badge macro and CSS.
"""
from __future__ import annotations

from pathlib import Path


SHORTCUT_CSS = Path(__file__).parent.parent / "app" / "static" / "shortcut-badge.css"
MACROS = Path(__file__).parent.parent / "app" / "templates" / "_components" / "macros.html"
BASE_HTML = Path(__file__).parent.parent / "app" / "templates" / "base.html"


def test_shortcut_badge_css_exists():
    """Should have shortcut badge styles."""
    assert SHORTCUT_CSS.exists()


def test_shortcut_badge_css_loaded_in_base():
    """Should be loaded in base.html."""
    text = BASE_HTML.read_text()
    assert "shortcut-badge.css" in text


def test_shortcut_badge_macro_exists():
    """Should have shortcut_badge macro."""
    text = MACROS.read_text()
    assert "macro shortcut_badge" in text


def test_shortcut_badge_uses_varargs():
    """Should accept variable number of keys."""
    text = MACROS.read_text()
    assert "*keys" in text
    assert "for k in keys" in text


def test_shortcut_badge_renders_kbd():
    """Should render keys as <kbd> elements."""
    text = MACROS.read_text()
    assert "<kbd>" in text
    assert "{{ k }}" in text


def test_shortcut_badge_has_aria_label():
    """Should have aria-label for accessibility."""
    text = MACROS.read_text()
    assert "aria-label" in text
    assert "Atajo" in text
    assert "join(' + ')" in text


def test_shortcut_badge_uses_span():
    """Should use <span> for inline display."""
    text = MACROS.read_text()
    assert "<span" in text
    assert "</span>" in text


def test_shortcut_badge_uses_class():
    """Should use shortcut-badge class."""
    text = MACROS.read_text()
    assert 'class="shortcut-badge"' in text


def test_shortcut_badge_handles_separators():
    """Should add space between keys (not after last)."""
    text = MACROS.read_text()
    assert "if not loop.last" in text
    assert " {% endif" in text


def test_shortcut_badge_css_has_kbd_styling():
    """Should style kbd elements like keys."""
    css = SHORTCUT_CSS.read_text()
    assert ".shortcut-badge kbd" in css
    assert "font-family: monospace" in css
    assert "border:" in css
    assert "box-shadow" in css


def test_shortcut_badge_css_inline_with_button():
    """Should style badge inline with buttons."""
    css = SHORTCUT_CSS.read_text()
    assert ".btn .shortcut-badge" in css
    assert "rgba(255, 255, 255" in css


def test_shortcut_badge_css_supports_dark_mode():
    """Should support dark mode."""
    css = SHORTCUT_CSS.read_text()
    assert '[data-theme="dark"]' in css
    assert ".shortcut-badge" in css


def test_shortcut_badge_css_handles_print():
    """Should hide in print."""
    css = SHORTCUT_CSS.read_text()
    assert "@media print" in css
    assert "display: none" in css


def test_shortcut_badge_css_has_vertical_align():
    """Should align inline with text."""
    css = SHORTCUT_CSS.read_text()
    assert "vertical-align: middle" in css


def test_shortcut_badge_css_uses_border_radius():
    """Should have proper border radius."""
    css = SHORTCUT_CSS.read_text()
    assert "border-radius:" in css


def test_shortcut_badge_css_has_line_height():
    """Should have proper line height."""
    css = SHORTCUT_CSS.read_text()
    assert "line-height:" in css


def test_shortcut_badge_macro_compact():
    """Should be visually compact."""
    css = SHORTCUT_CSS.read_text()
    assert "padding: 2px 6px" in css or "padding:" in css
    assert "font-size: 0.75rem" in css or "font-size:" in css


def test_shortcut_badge_macro_supports_single_key():
    """Should work with just one key."""
    text = MACROS.read_text()
    # Varargs means it works with 1+ args
    assert "*keys" in text


def test_shortcut_badge_macro_supports_multiple_keys():
    """Should work with multiple keys separated by space."""
    text = MACROS.read_text()
    assert "for k in keys" in text
    assert "loop.last" in text


def test_shortcut_badge_macro_uses_join():
    """Should join keys with ' + ' in aria-label."""
    text = MACROS.read_text()
    assert "join(' + ')" in text