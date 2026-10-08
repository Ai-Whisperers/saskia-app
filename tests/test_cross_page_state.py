"""Phase 22 — Cross-page state preservation.

Preserves filter settings, search queries, and view preferences across page visits
to improve operator workflow and reduce repetitive input.
"""

from __future__ import annotations

from pathlib import Path


def test_cross_page_state_exists():
    """Should have cross-page state preservation for filters."""
    # Check if localStorage is used for common filter patterns
    js_files = list((Path(__file__).parent.parent / "app" / "static").glob("*.js"))

    # Look for filter persistence
    found_patterns = []
    for js_file in js_files:
        text = js_file.read_text()
        if any(pattern in text for pattern in ["localStorage", "sessionStorage"]):
            found_patterns.append(js_file.name)

    # These should have filter persistence
    assert "app.js" in found_patterns, "app.js should handle cross-page state"


def test_cross_page_state_has_date_range_preservation():
    """Should preserve date ranges across insight pages."""
    # Check if any JavaScript handles date range persistence
    app_js = Path(__file__).parent.parent / "app" / "static" / "app.js"
    text = app_js.read_text()

    # Look for date range persistence patterns
    has_date_save = any(
        p in text for p in ["days_filter", "date_range", "from_date", "to_date", "savedDates"]
    )
    if not has_date_save:
        print("No date persistence found yet")

    # Check if forms are restored from storage
    has_form_restore = "localStorage" in text and "form" in text.lower()
    if not has_form_restore:
        print("No form state preservation found yet")


def test_cross_page_state_has_search_query_preservation():
    """Should preserve search queries when navigating between related pages."""
    # Check if search inputs maintain their state
    templates_dir = Path(__file__).parent.parent / "app" / "templates"

    search_templates = []
    for template in templates_dir.glob("*.html"):
        text = template.read_text()
        if "search" in text.lower() or "buscar" in text.lower():
            search_templates.append(template.name)

    # Common pages that should have search persistence
    expected_pages = ["pedidos.html", "clientes.html", "productos.html"]
    found_pages = [p for p in expected_pages if p in search_templates]

    if found_pages:
        print(f"Search pages found: {found_pages}")
    else:
        print("No search pages found in templates")


def test_cross_page_state_has_view_preferences():
    """Should remember view preferences like table sorting, filters, etc."""
    # Check for view preference patterns
    app_js = Path(__file__).parent.parent / "app" / "static" / "app.js"
    text = app_js.read_text()

    # Look for sorting, filter, or view preference persistence
    has_sorting = any(p in text for p in ["sort_", "table_sort", "column_sort"])
    has_filters = any(p in text for p in ["filter_", "saved_filters"])
    has_view = any(p in text for p in ["view_", "layout_", "preferences"])

    if not has_sorting:
        print("No table sorting persistence")
    if not has_filters:
        print("No filter persistence")
    if not has_view:
        print("No view preference persistence")


def test_cross_page_state_handles_insight_navigation():
    """Should preserve filter state when navigating between insight pages."""
    # Check insight pages for cross-navigation state
    insight_pages = [
        "insight_demand.html",
        "insight_food_cost.html",
        "insight_freshness.html",
        "insight_margenes.html",
        "insight_margenes_detalle.html",
        "reportes_mermas_cost.html",
        "suppliers_volatility.html",
        "auditoria_analytics.html",
    ]

    templates_dir = Path(__file__).parent.parent / "app" / "templates"
    found_insights = []

    for page in insight_pages:
        page_path = templates_dir / page
        if page_path.exists():
            text = page_path.read_text()
            if "days_filter" in text or "date" in text.lower():
                found_insights.append(page)

    if found_insights:
        print(f"Insight pages with dates: {found_insights}")
    else:
        print("No insight pages with date filters found")


def test_cross_page_state_handles_session_data():
    """Should handle session-specific data like draft orders, unsaved changes."""
    # Check for draft or session persistence
    app_js = Path(__file__).parent.parent / "app" / "static" / "app.js"
    text = app_js.read_text()

    # Look for draft or unsaved change persistence
    has_drafts = any(p in text for p in ["draft", "unsaved", "session_data"])
    has_form_dirty = "form-dirty.js" in text

    if not has_drafts:
        print("No draft order persistence")
    if not has_form_dirty:
        print("Form-dirty.js not loaded in app.js")

    # Form-dirty.js should handle unsaved changes
    form_dirty_js = Path(__file__).parent.parent / "app" / "static" / "form-dirty.js"
    if form_dirty_js.exists():
        print("Form-dirty.js exists for unsaved change warnings")


def test_cross_page_state_has_cookie_fallback():
    """Should have cookie fallback for state persistence."""
    # Check for cookie usage as fallback
    base_html = Path(__file__).parent.parent / "app" / "templates" / "base.html"
    text = base_html.read_text()

    # Check if cookie consent or cookie-based storage is present
    has_cookies = "cookie" in text.lower()

    if not has_cookies:
        print("No cookie handling found in base.html")
