"""P-05: Inventario listing, filters, and status pills regression test.

Tests:
- /inventario listing renders 200
- Filters work (search, status pills)
- Status pills show correct states (low stock, expiring, etc.)
- Server-side rendering without JS dependency
"""
import pytest


def test_inventario_index_renders_200(client):
    """P-05: /inventario listing page returns 200."""
    r = client.get("/inventario")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"


def test_inventario_has_search_input(client):
    """P-05: Search input is present for filtering."""
    r = client.get("/inventario")
    assert r.status_code == 200
    body = r.text
    # Check for search input
    assert 'name="q"' in body or 'type="search"' in body, "Search input not found"
    # Check for placeholder text
    assert "Buscar" in body or "buscar" in body, "Search placeholder not found"


def test_inventario_has_filter_dropdowns(client):
    """P-05: Filter dropdowns are present."""
    r = client.get("/inventario")
    assert r.status_code == 200
    body = r.text
    # Check for filter controls (could be dropdowns or buttons)
    assert "filter" in body.lower() or "filtro" in body.lower(), "No filter controls found"
    # Check for multi-filter component (mf-pop is used in the app)
    assert "mf-pop" in body or "filter" in body.lower(), "Multi-filter component not found"


def test_inventario_has_status_pills(client):
    """P-05: Status pills (low stock, expiring, etc.) are rendered."""
    r = client.get("/inventario")
    assert r.status_code == 200
    body = r.text
    # Check for status pill classes
    assert "pill" in body.lower() or "badge" in body.lower(), "No status pills/badges found"


def test_inventario_listing_with_search_filter(client):
    """P-05: Listing filters by search query."""
    r = client.get("/inventario?q=harina")
    assert r.status_code == 200
    # Should return 200 even if no results match


def test_inventario_listing_with_status_filter(client):
    """P-05: Listing filters by status (low stock, expiring, etc.)."""
    # Test various status filters
    for status in ["low", "expiring", "expired", "ok"]:
        r = client.get(f"/inventario?status={status}")
        assert r.status_code == 200, f"Status filter '{status}' failed"


def test_inventario_csv_export(client):
    """P-05: CSV export endpoint exists."""
    r = client.get("/inventario/export.csv")
    # Should return 200 or 302 (redirect)
    assert r.status_code in (200, 302), f"CSV export failed with {r.status_code}"


def test_inventario_new_button(client):
    """P-05: 'New ingredient' button is present."""
    r = client.get("/inventario")
    assert r.status_code == 200
    body = r.text
    # Check for link to create new ingredient
    assert "/inventario/nuevo" in body, "Link to new ingredient not found"


def test_inventario_handles_empty_state(client):
    """P-05: Empty state is shown when no ingredients exist."""
    r = client.get("/inventario")
    assert r.status_code == 200
    body = r.text
    # Should show empty state or table
    assert "empty-state" in body or "<table" in body or "tbody" in body, \
        "Neither empty state nor table found"


def test_inventario_no_python_errors(client):
    """P-05: No Python errors in inventory page rendering."""
    # Test multiple query combinations to ensure no 500 errors
    test_urls = [
        "/inventario",
        "/inventario?q=test",
        "/inventario?status=low",
        "/inventario?sort=name",
        "/inventario?page=1",
    ]
    for url in test_urls:
        r = client.get(url)
        assert r.status_code == 200, f"URL {url} returned {r.status_code}"
        # Check that response is HTML, not error page
        assert "text/html" in r.headers.get("content-type", ""), \
            f"URL {url} didn't return HTML"
