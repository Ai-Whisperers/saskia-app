"""Phase 25 — Advanced filter bar tests.

Verifies the filter_bar_advanced macro and CSS.
"""
from __future__ import annotations

from pathlib import Path


FILTER_CSS = Path(__file__).parent.parent / "app" / "static" / "filter-bar-advanced.css"
MACROS = Path(__file__).parent.parent / "app" / "templates" / "_components" / "macros.html"
BASE_HTML = Path(__file__).parent.parent / "app" / "templates" / "base.html"


def test_filter_bar_css_exists():
    """Should have filter bar styles."""
    assert FILTER_CSS.exists()


def test_filter_bar_css_loaded_in_base():
    """Should be loaded in base.html."""
    text = BASE_HTML.read_text()
    assert "filter-bar-advanced.css" in text


def test_filter_bar_macro_exists():
    """Should have filter_bar_advanced macro."""
    text = MACROS.read_text()
    assert "macro filter_bar_advanced" in text


def test_filter_bar_macro_supports_search():
    """Should support search input."""
    text = MACROS.read_text()
    assert "search=" in text
    assert 'type="search"' in text
    assert 'name="q"' in text


def test_filter_bar_macro_supports_placeholder():
    """Should support custom placeholder."""
    text = MACROS.read_text()
    assert "search_placeholder" in text
    assert "placeholder=" in text


def test_filter_bar_macro_uses_search_icon():
    """Should display search icon."""
    text = MACROS.read_text()
    assert "icon-search" in text
    assert "filter-bar-advanced__search-icon" in text


def test_filter_bar_macro_supports_results_count():
    """Should show results count."""
    text = MACROS.read_text()
    assert "results_count" in text
    assert "resultado" in text
    assert "aria-live" in text


def test_filter_bar_macro_supports_clear():
    """Should support clear button."""
    text = MACROS.read_text()
    assert "show_clear" in text
    assert "Limpiar" in text
    assert "filter-bar-advanced__clear" in text


def test_filter_bar_macro_supports_form_action():
    """Should support custom form action."""
    text = MACROS.read_text()
    assert "form_action" in text
    assert "action=" in text


def test_filter_bar_macro_supports_saved_filters():
    """Should support saved filter presets."""
    text = MACROS.read_text()
    assert "saved_filters" in text
    assert "Filtros guardados" in text


def test_filter_bar_macro_uses_form():
    """Should render as a form."""
    text = MACROS.read_text()
    assert "<form" in text
    assert 'role="search"' in text
    assert 'aria-label="Filtros"' in text


def test_filter_bar_macro_has_submit_button():
    """Should have submit button."""
    text = MACROS.read_text()
    assert "type=\"submit\"" in text
    assert "Aplicar" in text


def test_filter_bar_macro_supports_search_target():
    """Should integrate with search-highlight via data attribute."""
    text = MACROS.read_text()
    assert "search_target" in text
    assert "data-search-highlight" in text


def test_filter_bar_css_has_search_styling():
    """Should style search input."""
    css = FILTER_CSS.read_text()
    assert ".filter-bar-advanced__search" in css
    assert ".filter-bar-advanced__search input" in css
    assert "padding:" in css


def test_filter_bar_css_has_focus_styles():
    """Should have focus styles."""
    css = FILTER_CSS.read_text()
    assert ":focus" in css
    assert "box-shadow" in css
    assert "border-color" in css


def test_filter_bar_css_has_clear_button():
    """Should style clear button."""
    css = FILTER_CSS.read_text()
    assert ".filter-bar-advanced__clear" in css
    assert "color: var(--color-danger" in css


def test_filter_bar_css_has_count_badge():
    """Should style count badge."""
    css = FILTER_CSS.read_text()
    assert ".filter-bar-advanced__count" in css
    assert "filter-bar-advanced__badge" in css


def test_filter_bar_css_supports_dark_mode():
    """Should support dark mode."""
    css = FILTER_CSS.read_text()
    assert '[data-theme="dark"]' in css
    assert ".filter-bar-advanced" in css


def test_filter_bar_css_responsive():
    """Should be mobile responsive."""
    css = FILTER_CSS.read_text()
    assert "@media (max-width: 768px)" in css
    assert "flex-direction: column" in css


def test_filter_bar_css_handles_print():
    """Should hide in print."""
    css = FILTER_CSS.read_text()
    assert "@media print" in css
    assert "display: none" in css


def test_filter_bar_css_respects_reduced_motion():
    """Should respect prefers-reduced-motion."""
    css = FILTER_CSS.read_text()
    assert "prefers-reduced-motion" in css


def test_filter_bar_css_has_icon_positioning():
    """Should position search icon correctly."""
    css = FILTER_CSS.read_text()
    assert "position: absolute" in css
    assert "left: 12px" in css


def test_filter_bar_macro_pluralizes_results():
    """Should pluralize results count."""
    text = MACROS.read_text()
    assert "if results_count != 1" in text or "results_count != 1" in text


def test_filter_bar_macro_conditional_clear():
    """Should only show clear when there's something to clear."""
    text = MACROS.read_text()
    assert "if show_clear and (search or saved_filters)" in text


def test_filter_bar_css_has_saved_filter_styling():
    """Should style saved filter dropdown."""
    css = FILTER_CSS.read_text()
    assert ".filter-bar-advanced__saved" in css
    assert ".filter-bar-advanced__saved select" in css


def test_filter_bar_macro_uses_aria_live():
    """Should use aria-live for dynamic count updates."""
    text = MACROS.read_text()
    assert "aria-live=\"polite\"" in text


def test_filter_bar_macro_supports_form_method():
    """Should support custom form method."""
    text = MACROS.read_text()
    assert "form_method" in text
    assert 'method="{{' in text or 'method=\"{{' in text