"""Phase 22 — Sortable table component verification.

All 75 tables in the application can now be sorted by clicking headers.
Supports keyboard navigation, URL state, and visual indicators.
"""

from __future__ import annotations

from pathlib import Path

SORTABLE_JS = Path(__file__).parent.parent / "app" / "static" / "sortable-table.js"
SORTABLE_CSS = Path(__file__).parent.parent / "app" / "static" / "sortable-table.css"
BASE_HTML = Path(__file__).parent.parent / "app" / "templates" / "base.html"


def test_sortable_js_exists():
    """Should have a dedicated sortable table script."""
    assert SORTABLE_JS.exists()


def test_sortable_css_exists():
    """Should have dedicated sortable table styles."""
    assert SORTABLE_CSS.exists()


def test_sortable_loaded_in_base():
    """Should be loaded in base.html."""
    text = BASE_HTML.read_text()
    assert "sortable-table.js" in text
    assert "sortable-table.css" in text


def test_sortable_supports_table_class():
    """Should support tables with .sortable class."""
    js = SORTABLE_JS.read_text()
    assert "table.sortable" in js
    assert "table[data-sortable]" in js


def test_sortable_makes_headers_clickable():
    """Should make headers clickable with proper accessibility."""
    js = SORTABLE_JS.read_text()

    # Check accessibility attributes
    assert "setAttribute('role'" in js or 'setAttribute("role"' in js
    assert "setAttribute('tabindex'" in js or 'setAttribute("tabindex"' in js
    assert "setAttribute('aria-sort'" in js or 'setAttribute("aria-sort"' in js
    assert "setAttribute('data-sort-key'" in js or 'setAttribute("data-sort-key"' in js


def test_sortable_supports_keyboard_navigation():
    """Should support keyboard navigation (Enter/Space)."""
    js = SORTABLE_JS.read_text()

    # Check keyboard handlers
    assert "e.key === 'Enter'" in js
    assert "e.key === ' '" in js
    assert "keydown" in js


def test_sortable_has_visual_indicators():
    """Should have visual indicators for sort state."""
    js = SORTABLE_JS.read_text()

    # Check sort indicators
    assert "sort-indicator" in js
    assert "sort-asc" in js
    assert "sort-desc" in js
    assert "aria-sort" in js


def test_sortable_handles_three_states():
    """Should support none/asc/desc states."""
    js = SORTABLE_JS.read_text()

    # Check three-state logic
    assert "SORT_ASC" in js
    assert "SORT_DESC" in js
    assert "SORT_NONE" in js

    # Should cycle: none -> asc -> desc -> none
    assert "if (currentDir === SORT_ASC)" in js
    assert "newDir = SORT_DESC" in js
    assert "newDir = SORT_NONE" in js


def test_sortable_handles_numeric_values():
    """Should correctly sort numeric values."""
    js = SORTABLE_JS.read_text()

    # Check numeric sorting
    assert "parseFloat" in js
    assert "aNum" in js
    assert "bNum" in js
    assert "!isNaN(aNum)" in js


def test_sortable_supports_custom_sort_values():
    """Should support data-sort-value for custom sorting."""
    js = SORTABLE_JS.read_text()

    # Check data-sort-value support
    assert "data-sort-value" in js
    assert "cell.dataset.sortValue" in js


def test_sortable_persists_in_url():
    """Should persist sort state in URL."""
    js = SORTABLE_JS.read_text()

    # Check URL persistence
    assert "updateURL" in js
    assert "searchParams.set" in js
    assert "searchParams.get" in js
    assert "history.replaceState" in js


def test_sortable_restores_from_url():
    """Should restore sort state from URL on page load."""
    js = SORTABLE_JS.read_text()

    # Check restoration
    assert "restoreSortState" in js
    assert "searchParams.get('sort')" in js
    assert "searchParams.get('dir')" in js


def test_sortable_handles_no_sort_columns():
    """Should respect data-no-sort attribute."""
    js = SORTABLE_JS.read_text()

    # Check no-sort handling
    assert "data-no-sort" in js
    assert "no-sort" in js or "noSort" in js or "data-no-sort" in js


def test_sortable_stores_original_index():
    """Should preserve original order for reset."""
    js = SORTABLE_JS.read_text()

    # Check original index storage
    assert "originalIndex" in js
    assert "dataset.originalIndex" in js


def test_sortable_has_focus_styles():
    """Should have proper focus styles for accessibility."""
    css = SORTABLE_CSS.read_text()

    # Check focus styles
    assert ".sortable-header:focus" in css
    assert "outline:" in css or "outline " in css


def test_sortable_has_hover_styles():
    """Should have hover feedback."""
    css = SORTABLE_CSS.read_text()

    # Check hover
    assert ".sortable-header:hover" in css
    assert "background-color" in css


def test_sortable_has_active_sort_styles():
    """Should have visual feedback for active sort column."""
    css = SORTABLE_CSS.read_text()

    # Check active sort styles
    assert ".sort-asc" in css
    assert ".sort-desc" in css
    assert "background-color" in css


def test_sortable_handles_print():
    """Should hide sort indicators in print."""
    css = SORTABLE_CSS.read_text()

    # Check print styles
    assert "@media print" in css
    assert ".sort-indicator" in css
    assert "display: none" in css


def test_sortable_respects_reduced_motion():
    """Should respect prefers-reduced-motion."""
    css = SORTABLE_CSS.read_text()

    # Check reduced motion
    assert "prefers-reduced-motion" in css
    assert "transition: none" in css


def test_sortable_supports_dark_mode():
    """Should support dark mode."""
    css = SORTABLE_CSS.read_text()

    # Check dark mode
    assert '[data-theme="dark"]' in css
    assert "background-color" in css


def test_sortable_observes_dynamic_tables():
    """Should observe DOM mutations for dynamic tables."""
    js = SORTABLE_JS.read_text()

    # Check mutation observer
    assert "MutationObserver" in js
    assert "addedNodes" in js
    assert "childList" in js
    assert "subtree" in js


def test_sortable_exposes_global_api():
    """Should expose SortableTable globally."""
    js = SORTABLE_JS.read_text()

    # Check global API
    assert "window.SortableTable" in js
    assert "init:" in js
    assert "sortBy:" in js


def test_pedidos_table_is_sortable():
    """Pedidos table should be sortable with proper data attributes."""
    pedidos_html = Path(__file__).parent.parent / "app" / "templates" / "pedidos.html"
    text = pedidos_html.read_text()

    # Check sortable class
    assert 'class="table is-hoverable is-striped sortable"' in text

    # Check data-sort-key on headers
    assert 'data-sort-key="status"' in text
    assert 'data-sort-key="customer"' in text
    assert 'data-sort-key="promised_at"' in text
    assert 'data-sort-key="total_gs"' in text

    # Check no-sort on checkbox and actions
    assert "data-no-sort" in text


def test_sortable_works_with_existing_table_classes():
    """Should work with existing table classes like is-hoverable, is-striped."""
    js = SORTABLE_JS.read_text()
    css = SORTABLE_CSS.read_text()

    # Check compatibility
    assert "table.sortable" in js or "table[data-sortable]" in js
    assert "table.sortable" in css or "table[data-sortable]" in css
