"""Sprint Week 1 — Search highlight utility tests.

Verifies the search-highlight.js utility for client-side result highlighting.
"""

from __future__ import annotations

from pathlib import Path

SEARCH_JS = Path(__file__).parent.parent / "app" / "static" / "search-highlight.js"
SEARCH_CSS = Path(__file__).parent.parent / "app" / "static" / "search-highlight.css"
BASE_HTML = Path(__file__).parent.parent / "app" / "templates" / "base.html"


def test_search_highlight_js_exists():
    """Should have a dedicated search highlight script."""
    assert SEARCH_JS.exists()


def test_search_highlight_css_exists():
    """Should have highlight styles."""
    assert SEARCH_CSS.exists()


def test_search_highlight_loaded_in_base():
    """Should be loaded in base.html."""
    text = BASE_HTML.read_text()
    assert "search-highlight.js" in text
    assert "search-highlight.css" in text


def test_search_highlight_uses_mark_element():
    """Should use <mark> for semantic highlighting."""
    js = SEARCH_JS.read_text()
    assert "createElement('mark')" in js
    assert "search-highlight" in js


def test_search_highlight_escapes_regex():
    """Should escape regex special characters in query."""
    js = SEARCH_JS.read_text()
    assert "replace(/[.*+?^" in js or "replace(/\\\\.\\*\\+\\?" in js
    assert "RegExp" in js


def test_search_highlight_walks_text_nodes():
    """Should walk text nodes only, skipping scripts/styles."""
    js = SEARCH_JS.read_text()
    assert "createTreeWalker" in js
    assert "NodeFilter.SHOW_TEXT" in js
    assert "SCRIPT" in js
    assert "STYLE" in js


def test_search_highlight_supports_clear():
    """Should support clearing highlights."""
    js = SEARCH_JS.read_text()
    assert "clear" in js
    assert "querySelectorAll('mark" in js
    assert "normalize" in js


def test_search_highlight_handles_min_length():
    """Should require minimum query length."""
    js = SEARCH_JS.read_text()
    assert "query.length < 2" in js or "length < 2" in js


def test_search_highlight_uses_data_attribute():
    """Should auto-attach via data-search-highlight attribute."""
    js = SEARCH_JS.read_text()
    assert "data-search-highlight" in js
    assert "querySelectorAll" in js


def test_search_highlight_supports_escape():
    """Should clear on Escape key."""
    js = SEARCH_JS.read_text()
    assert "Escape" in js
    assert "keydown" in js


def test_search_highlight_debounces():
    """Should debounce input to avoid excessive updates."""
    js = SEARCH_JS.read_text()
    assert "debounce" in js.lower() or "setTimeout" in js


def test_search_highlight_handles_case_insensitive():
    """Should be case-insensitive."""
    js = SEARCH_JS.read_text()
    assert "'gi'" in js or "flags: 'gi'" in js


def test_search_highlight_preserves_html():
    """Should not break HTML structure (only text nodes)."""
    js = SEARCH_JS.read_text()
    assert "text node" in js.lower() or "textNode" in js or "SHOW_TEXT" in js


def test_search_highlight_handles_no_results():
    """Should gracefully handle no matches."""
    js = SEARCH_JS.read_text()
    assert "test(text)" in js or "regex.test" in js


def test_search_highlight_css_visible():
    """Highlight should be visually distinct."""
    css = SEARCH_CSS.read_text()
    assert "background:" in css
    assert "color:" in css


def test_search_highlight_css_dark_mode():
    """Should support dark mode."""
    css = SEARCH_CSS.read_text()
    assert '[data-theme="dark"]' in css


def test_search_highlight_css_print():
    """Should handle print styles."""
    css = SEARCH_CSS.read_text()
    assert "@media print" in css


def test_search_highlight_css_reduced_motion():
    """Should respect reduced motion."""
    css = SEARCH_CSS.read_text()
    assert "prefers-reduced-motion" in css


def test_search_highlight_pedidos_integration():
    """Pedidos search should have data-search-highlight."""
    text = Path(__file__).parent.parent / "app" / "templates" / "pedidos.html"
    html = text.read_text()
    assert "data-search-highlight=" in html
    assert "#pedidos-tbody" in html


def test_search_highlight_exposes_global():
    """Should expose SearchHighlight globally."""
    js = SEARCH_JS.read_text()
    assert "window.SearchHighlight" in js
    assert "highlight" in js
    assert "clear" in js
