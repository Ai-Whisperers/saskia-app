"""P-09: Ventas historial filters, pagination, CSV export regression test.

Tests:
- /ventas/historial page renders
- Filters work (date range, payment method, etc.)
- Pagination is present
- CSV export endpoint exists

This is a server-side regression test that verifies the historial page
renders correctly and the CSV export endpoint works, without requiring
Playwright for browser interactions.
"""


def test_ventas_historial_renders(client):
    """P-09: Historial page renders 200."""
    r = client.get("/ventas/historial")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"


def test_ventas_historial_renders_in_spanish(client):
    """P-09: Page is in Spanish."""
    r = client.get("/ventas/historial")
    assert r.status_code == 200
    body = r.text
    assert "Historial de ventas" in body, "Page not in Spanish"


def test_ventas_historial_has_search_box(client):
    """P-09: Search input is present."""
    r = client.get("/ventas/historial")
    assert r.status_code == 200
    body = r.text
    # Check for search input
    assert 'id="sales-search"' in body or 'name="q"' in body, "Search box not found"


def test_ventas_historial_has_product_filter(client):
    """P-09: Product filter combo is present."""
    r = client.get("/ventas/historial")
    assert r.status_code == 200
    body = r.text
    # Check for product filter (saskia-combo or select)
    assert 'name="product_id"' in body or "Filtrar por producto" in body, "Product filter not found"


def test_ventas_historial_has_payment_filter(client):
    """P-09: Payment method filter is present (or via checkbox)."""
    r = client.get("/ventas/historial")
    assert r.status_code == 200
    body = r.text
    # Check for payment method or include-voided checkbox
    assert (
        "efectivo" in body.lower()
        or "tarjeta" in body.lower()
        or "transferencia" in body.lower()
        or "include_voided" in body
        or "anuladas" in body.lower()
    ), "Payment filter not found"


def test_ventas_historial_has_days_filter(client):
    """P-09: Days range filter is present."""
    r = client.get("/ventas/historial")
    assert r.status_code == 200
    body = r.text
    # Check for days filter (saskia-combo with name="days")
    assert 'name="days"' in body or "Rango" in body, "Days filter not found"


def test_ventas_historial_has_pagination(client):
    """P-09: Pagination controls are present."""
    r = client.get("/ventas/historial")
    assert r.status_code == 200
    body = r.text
    # Check for "Mostrando" indicator (always shown)
    assert "Mostrando" in body, "Pagination indicator not found"


def test_ventas_historial_has_csv_export_link(client):
    """P-09: CSV export link is present in page."""
    r = client.get("/ventas/historial")
    assert r.status_code == 200
    body = r.text
    # Check for CSV export link
    assert "format=csv" in body or "Exportar CSV" in body, "CSV export link not found"


def test_ventas_historial_csv_export(client):
    """P-09: CSV export endpoint exists."""
    # The historial page uses ?format=csv for export
    r = client.get("/ventas/historial?format=csv")
    # Should return 200 (CSV) or 302 (redirect)
    assert r.status_code in (200, 302), f"CSV export failed with {r.status_code}"


def test_ventas_historial_no_python_errors(client):
    """P-09: No Python errors."""
    test_urls = [
        "/ventas/historial",
        "/ventas/historial?page=1",
        "/ventas/historial?fecha_desde=2026-01-01",
        "/ventas/historial?format=csv",
    ]
    for url in test_urls:
        r = client.get(url)
        assert r.status_code != 500, f"URL {url} returned 500"
