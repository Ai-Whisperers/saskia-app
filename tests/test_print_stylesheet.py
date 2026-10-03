"""Phase 22 — Print stylesheet verification.

print.css provides print-friendly layout for reports, batch sheets, and analytics,
hiding interactive elements, optimizing tables, and ensuring text readability.
"""
from __future__ import annotations

from pathlib import Path


PRINT_CSS = Path(__file__).parent.parent / "app" / "static" / "print.css"


def test_print_stylesheet_exists():
    """Should have a dedicated print stylesheet."""
    assert PRINT_CSS.exists()


def test_print_stylesheet_has_media_print():
    """Should use media='print' in base.html."""
    base_html = Path(__file__).parent.parent / "app" / "templates" / "base.html"
    text = base_html.read_text()
    assert 'media="print"' in text


def test_print_stylesheet_hides_interactive_elements():
    """Should hide non-printable interactive elements."""
    css = PRINT_CSS.read_text()
    # Core UI elements that shouldn't print
    assert '.modal-backdrop' in css and 'display: none' in css
    assert 'nav' in css and 'display: none' in css
    assert 'footer' in css and 'display: none' in css
    assert '.filter-toolbar' in css and 'display: none' in css
    assert '.kpi-strip' in css and 'display: none' in css
    assert '.progress-bar' in css and 'display: none' in css
    assert '.back-to-top' in css and 'display: none' in css


def test_print_stylesheet_optimizes_tables():
    """Should optimize table styling for print."""
    css = PRINT_CSS.read_text()
    # Table optimizations
    assert '.table' in css and 'border-collapse' in css
    assert '.table th' in css and 'border-bottom' in css
    assert '.table td' in css and 'border:' in css
    assert 'page-break-inside: avoid' in css


def test_print_stylesheet_has_page_breaks():
    """Should handle page breaks appropriately."""
    css = PRINT_CSS.read_text()
    # Page break rules
    assert '@page' in css
    assert 'margin: 2cm' in css
    assert 'page-break-after: avoid' in css
    assert 'page-break-inside: avoid' in css


def test_print_stylesheet_handles_links():
    """Should make links readable in print."""
    css = PRINT_CSS.read_text()
    assert 'a[href]:after' in css
    assert 'content: " (" attr(href) ")"' in css


def test_print_stylesheet_has_print_friendly_form_styling():
    """Should style forms for print readability."""
    css = PRINT_CSS.read_text()
    assert '.form-control' in css and 'border:' in css
    assert 'background: #fff !important' in css


def test_print_stylesheet_has_chart_optimization():
    """Should handle charts and images for print."""
    css = PRINT_CSS.read_text()
    assert '.chart-container' in css
    assert 'height: auto' in css
    assert 'max-width: 100%' in css


def test_print_stylesheet_handles_grids():
    """Should make responsive grids work in print."""
    css = PRINT_CSS.read_text()
    assert '.grid-2' in css
    assert 'width: 100%' in css
    assert 'clear: both' in css


def test_print_stylesheet_handles_tooltips():
    """Should make tooltips readable in print."""
    css = PRINT_CSS.read_text()
    assert '[data-tooltip]' in css
    assert 'content: attr(data-tooltip)' in css


def test_print_stylesheet_has_header_footer():
    """Should style report headers and add page numbers."""
    css = PRINT_CSS.read_text()
    assert '.report-header' in css
    assert '@bottom-right' in css
    assert 'counter(page)' in css


def test_print_stylesheet_uses_exact_color_adjustment():
    """Should use exact color adjustment for printed colors."""
    css = PRINT_CSS.read_text()
    assert '-webkit-print-color-adjust: exact' in css
    assert 'color-adjust: exact' in css


def test_print_stylesheet_handles_batches_overview():
    """Should optimize batches overview for print."""
    css = PRINT_CSS.read_text()
    assert '.batches-overview' in css
    assert 'page-break-inside: avoid' in css


def test_print_stylesheet_resets_shadows():
    """Should remove shadows for cleaner print output."""
    css = PRINT_CSS.read_text()
    assert 'box-shadow: none !important' in css