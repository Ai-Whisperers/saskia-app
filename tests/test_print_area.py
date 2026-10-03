"""Phase 31 — Print area utility tests.

Verifies the data-print and target-area print utility.
"""
from __future__ import annotations

from pathlib import Path


PRINT_JS = Path(__file__).parent.parent / "app" / "static" / "print-area.js"
BASE_HTML = Path(__file__).parent.parent / "app" / "templates" / "base.html"


def test_print_area_js_exists():
    """Should have a print area script."""
    assert PRINT_JS.exists()


def test_print_area_loaded_in_base():
    """Should be loaded in base.html."""
    text = BASE_HTML.read_text()
    assert "print-area.js" in text


def test_print_area_exposes_global():
    """Should expose PrintArea globally."""
    js = PRINT_JS.read_text()
    assert "window.PrintArea" in js


def test_print_area_uses_iife():
    """Should be wrapped in IIFE."""
    js = PRINT_JS.read_text()
    assert "(function()" in js
    assert "'use strict'" in js


def test_print_area_uses_data_attribute():
    """Should use data-print attribute."""
    js = PRINT_JS.read_text()
    assert "data-print" in js
    assert "data-print-hide" in js
    assert "data-print-title" in js


def test_print_area_event_delegation():
    """Should use event delegation."""
    js = PRINT_JS.read_text()
    assert "addEventListener('click'" in js
    assert "closest(" in js


def test_print_area_prevents_default():
    """Should preventDefault for buttons."""
    js = PRINT_JS.read_text()
    assert "preventDefault" in js


def test_print_area_uses_iframe():
    """Should use hidden iframe for clean printing."""
    js = PRINT_JS.read_text()
    assert "iframe" in js
    assert "createElement('iframe')" in js


def test_print_area_hides_iframe():
    """Should position iframe off-screen."""
    js = PRINT_JS.read_text()
    assert "right = '-10000px'" in js
    assert "position = 'fixed'" in js


def test_print_area_writes_iframe_doc():
    """Should write iframe document."""
    js = PRINT_JS.read_text()
    assert "doc.write" in js or "contentDocument.write" in js
    assert "doc.open" in js
    assert "doc.close" in js


def test_print_area_clones_styles():
    """Should clone stylesheets for accurate rendering."""
    js = PRINT_JS.read_text()
    assert "styleSheets" in js
    assert "cssRules" in js
    assert "_buildHtml" in js


def test_print_area_handles_cors():
    """Should handle cross-origin stylesheet errors."""
    js = PRINT_JS.read_text()
    assert "catch (e)" in js
    assert "return ''" in js


def test_print_area_uses_window_print():
    """Should use contentWindow.print() for iframe."""
    js = PRINT_JS.read_text()
    assert "contentWindow.print" in js
    assert "window.print" in js


def test_print_area_falls_back_to_window_print():
    """Should fall back to window.print() if no target."""
    js = PRINT_JS.read_text()
    assert "window.print()" in js


def test_print_area_removes_iframe():
    """Should clean up iframe after print."""
    js = PRINT_JS.read_text()
    assert "removeChild(iframe)" in js or "removeChild" in js


def test_print_area_uses_timeout():
    """Should use setTimeout for render delay."""
    js = PRINT_JS.read_text()
    assert "setTimeout" in js


def test_print_area_escapes_title():
    """Should HTML-escape the title."""
    js = PRINT_JS.read_text()
    assert "_escape" in js
    assert "textContent" in js


def test_print_area_supports_custom_title():
    """Should accept custom title."""
    js = PRINT_JS.read_text()
    assert "data-print-title" in js
    assert "customTitle" in js


def test_print_area_supports_hide():
    """Should support hiding selectors."""
    js = PRINT_JS.read_text()
    assert "data-print-hide" in js
    assert "hideSelector" in js


def test_print_area_handles_missing_target():
    """Should warn if target not found."""
    js = PRINT_JS.read_text()
    assert "console.warn" in js
    assert "Print target not found" in js


def test_print_area_logs_errors():
    """Should log errors."""
    js = PRINT_JS.read_text()
    assert "console.error" in js
    assert "Print failed" in js


def test_print_area_dom_ready():
    """Should wait for DOM ready."""
    js = PRINT_JS.read_text()
    assert "readyState" in js
    assert "DOMContentLoaded" in js


def test_print_area_sets_title():
    """Should update document title for print."""
    js = PRINT_JS.read_text()
    assert "document.title" in js


def test_print_area_html_structure():
    """Should generate proper HTML structure."""
    js = PRINT_JS.read_text()
    assert "<!DOCTYPE html>" in js
    assert "<html lang=\"es\">" in js
    assert "<head>" in js
    assert "<body>" in js
    assert "@page" in js