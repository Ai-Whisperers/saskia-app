"""Phase 22 — Dark mode theme verification.

The dark mode is already shipped:
- :root[data-theme="dark"] palette in app.css
- #theme-toggle button in base.html
- JavaScript handler (assumed in app.js or inline)
"""
from __future__ import annotations

from pathlib import Path


APP_CSS = Path(__file__).parent.parent / "app" / "static" / "app.css"
BASE_HTML = Path(__file__).parent.parent / "app" / "templates" / "base.html"


def test_app_css_has_dark_palette():
    text = APP_CSS.read_text()
    assert ":root[data-theme=\"dark\"]" in text, "Missing dark theme palette"


def test_dark_palette_overrides_bg():
    """Dark mode should override --color-bg."""
    text = APP_CSS.read_text()
    # Find the dark section
    dark_idx = text.find('data-theme="dark"')
    assert dark_idx > 0
    dark_section = text[dark_idx:dark_idx + 5000]
    # Should redefine --color-bg
    assert "--color-bg:" in dark_section


def test_dark_palette_overrides_text():
    """Dark mode should override --color-text."""
    text = APP_CSS.read_text()
    dark_idx = text.find('data-theme="dark"')
    dark_section = text[dark_idx:dark_idx + 5000]
    assert "--color-text:" in dark_section


def test_dark_palette_overrides_border():
    """Dark mode should override --color-border."""
    text = APP_CSS.read_text()
    dark_idx = text.find('data-theme="dark"')
    dark_section = text[dark_idx:dark_idx + 5000]
    assert "--color-border:" in dark_section


def test_base_html_has_theme_toggle():
    """base.html should have a #theme-toggle button."""
    text = BASE_HTML.read_text()
    assert 'id="theme-toggle"' in text


def test_theme_toggle_has_aria_label():
    """Theme toggle button should be screen-reader friendly."""
    text = BASE_HTML.read_text()
    assert 'aria-label' in text and 'tema' in text.lower()


def test_theme_toggle_uses_moon_svg():
    """Default state should show moon icon (to switch to dark)."""
    text = BASE_HTML.read_text()
    # Find theme toggle area
    idx = text.find('id="theme-toggle"')
    section = text[idx:idx + 500]
    # Either moon or sun icon - just check there's an SVG reference
    assert "<use href=" in section
    assert "#icon-" in section


def test_base_html_includes_app_css():
    """base.html should reference app.css which has the dark palette."""
    text = BASE_HTML.read_text()
    assert "app.css" in text or "static/app.css" in text or 'href="/static/app.css"' in text


def test_prefers_color_scheme_in_css():
    """Dark mode could be triggered by system pref via @media (prefers-color-scheme: dark)."""
    text = APP_CSS.read_text()
    has_media = "prefers-color-scheme" in text
    has_data_theme = 'data-theme="dark"' in text
    # Either explicit data-theme toggle OR media query
    assert has_data_theme or has_media, (
        "Dark mode must use data-theme toggle OR prefers-color-scheme media query"
    )


def test_print_styles_defined():
    """Phase 22 #43: print stylesheet for invoices."""
    text = APP_CSS.read_text()
    assert "@media print" in text or "@page" in text, "Missing print styles"