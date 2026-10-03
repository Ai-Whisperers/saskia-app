"""Phase 24 — Pagination component tests.

Verifies the pagination macro and CSS.
"""
from __future__ import annotations

from pathlib import Path


PAGINATION_CSS = Path(__file__).parent.parent / "app" / "static" / "pagination.css"
MACROS = Path(__file__).parent.parent / "app" / "templates" / "_components" / "macros.html"
BASE_HTML = Path(__file__).parent.parent / "app" / "templates" / "base.html"


def test_pagination_css_exists():
    """Should have pagination styles."""
    assert PAGINATION_CSS.exists()


def test_pagination_css_loaded_in_base():
    """Should be loaded in base.html."""
    text = BASE_HTML.read_text()
    assert "pagination.css" in text


def test_pagination_macro_exists():
    """Should have pagination macro."""
    text = MACROS.read_text()
    assert "macro pagination" in text


def test_pagination_macro_required_params():
    """Macro should require page, total_pages, base_url."""
    text = MACROS.read_text()
    assert "page," in text
    assert "total_pages," in text
    assert "base_url" in text


def test_pagination_macro_supports_extra_qs():
    """Should support extra query string params."""
    text = MACROS.read_text()
    assert "extra_qs" in text


def test_pagination_macro_supports_compact():
    """Should support compact variant."""
    text = MACROS.read_text()
    assert "compact" in text
    assert "pagination--compact" in text


def test_pagination_macro_renders_nav():
    """Should render <nav> element with aria-label."""
    text = MACROS.read_text()
    assert "<nav" in text
    assert 'aria-label="Paginación"' in text


def test_pagination_macro_has_previous_link():
    """Should have previous page link."""
    text = MACROS.read_text()
    assert "Página anterior" in text
    assert "chevron-left" in text


def test_pagination_macro_has_next_link():
    """Should have next page link."""
    text = MACROS.read_text()
    assert "Página siguiente" in text
    assert "chevron-right" in text


def test_pagination_macro_marks_current_page():
    """Should mark current page with aria-current."""
    text = MACROS.read_text()
    assert 'aria-current="page"' in text
    assert "pagination__item--current" in text


def test_pagination_macro_has_ellipsis():
    """Should show ellipsis for gaps in page numbers."""
    text = MACROS.read_text()
    assert "pagination__ellipsis" in text
    assert "…" in text


def test_pagination_macro_handles_single_page():
    """Should not render when only 1 page."""
    text = MACROS.read_text()
    assert "if total_pages > 1" in text


def test_pagination_macro_has_info_text():
    """Should show page info text."""
    text = MACROS.read_text()
    assert "Página" in text
    assert "pagination__info" in text
    assert "aria-live=\"polite\"" in text


def test_pagination_css_has_hover():
    """Should have hover styles."""
    css = PAGINATION_CSS.read_text()
    assert ":hover" in css
    assert "background:" in css


def test_pagination_css_has_focus():
    """Should have focus styles for keyboard nav."""
    css = PAGINATION_CSS.read_text()
    assert ":focus" in css
    assert "outline:" in css


def test_pagination_css_has_current_style():
    """Should style current page differently."""
    css = PAGINATION_CSS.read_text()
    assert ".pagination__item--current" in css
    assert "background:" in css


def test_pagination_css_has_disabled_style():
    """Should style disabled state."""
    css = PAGINATION_CSS.read_text()
    assert ".pagination__item--disabled" in css
    assert "opacity:" in css
    assert "pointer-events: none" in css


def test_pagination_css_has_gap_style():
    """Should style gap (ellipsis container)."""
    css = PAGINATION_CSS.read_text()
    assert ".pagination__item--gap" in css or "pagination__ellipsis" in css


def test_pagination_css_has_compact_variant():
    """Should have compact variant."""
    css = PAGINATION_CSS.read_text()
    assert ".pagination--compact" in css
    assert "min-width: 32px" in css


def test_pagination_css_supports_dark_mode():
    """Should support dark mode."""
    css = PAGINATION_CSS.read_text()
    assert '[data-theme="dark"]' in css
    assert ".pagination__item" in css


def test_pagination_css_handles_print():
    """Should be print-friendly."""
    css = PAGINATION_CSS.read_text()
    assert "@media print" in css
    assert ".pagination__info" in css
    assert "display: none" in css


def test_pagination_css_respects_reduced_motion():
    """Should respect prefers-reduced-motion."""
    css = PAGINATION_CSS.read_text()
    assert "prefers-reduced-motion" in css


def test_pagination_macro_preserves_query_string():
    """Should preserve extra query string params."""
    text = MACROS.read_text()
    assert "{{ qp }}" in text
    assert "extra_qs" in text


def test_pagination_macro_has_accessible_icons():
    """Icons should be aria-hidden."""
    text = MACROS.read_text()
    assert 'aria-hidden="true"' in text
    assert "pagination__icon" in text


def test_pagination_css_has_icon_styling():
    """Should style icons properly."""
    css = PAGINATION_CSS.read_text()
    assert ".pagination__icon" in css
    assert "width: 16px" in css
    assert "height: 16px" in css