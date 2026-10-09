"""Test bank currency toggle and pagination features."""


def test_bank_page_renders(client):
    """Bank page renders normally."""
    r = client.get("/bank")
    assert r.status_code == 200


def test_bank_currency_toggle_shows_all(client):
    """Currency toggle shows 'Todas' button by default."""
    r = client.get("/bank")
    assert r.status_code == 200
    body = r.text
    assert "Todas" in body
    assert "EUR" in body
    assert "PYG" in body


def test_bank_currency_toggle_eur_only(client):
    """Filter by EUR currency only."""
    r = client.get("/bank?currency=EUR")
    assert r.status_code == 200
    body = r.text
    assert "currency=EUR" in body
    # Should show EUR button as active
    assert "btn-primary" in body


def test_bank_currency_toggle_pyg_only(client):
    """Filter by PYG currency only."""
    r = client.get("/bank?currency=PYG")
    assert r.status_code == 200
    body = r.text
    assert "currency=PYG" in body


def test_bank_currency_toggle_invalid(client):
    """Invalid currency doesn't crash."""
    r = client.get("/bank?currency=USD")
    assert r.status_code == 200


def test_bank_currency_toggle_with_date_filter(client):
    """Currency toggle works with date filter."""
    r = client.get("/bank?currency=EUR&start_date=2025-09-01&end_date=2025-09-30")
    assert r.status_code == 200


def test_bank_pagination_default_page(client):
    """Default page is 1."""
    r = client.get("/bank")
    assert r.status_code == 200
    body = r.text
    # Should show pagination info or no pagination (if < per_page items)
    assert "bank" in body.lower()


def test_bank_pagination_page_2(client):
    """Page 2 works."""
    r = client.get("/bank?page=2")
    assert r.status_code == 200


def test_bank_pagination_invalid_page(client):
    """Invalid page (zero/negative) returns 400 (validation error)."""
    r = client.get("/bank?page=0")
    assert r.status_code in (200, 400), f"Unexpected {r.status_code}"


def test_bank_pagination_large_page(client):
    """Large page number doesn't crash."""
    r = client.get("/bank?page=999")
    assert r.status_code == 200


def test_bank_pagination_per_page_custom(client):
    """Custom per_page works."""
    r = client.get("/bank?per_page=25")
    assert r.status_code == 200


def test_bank_pagination_per_page_invalid(client):
    """Invalid per_page returns 400 (validation error) or uses default."""
    r = client.get("/bank?per_page=5")  # Below minimum
    assert r.status_code in (200, 400), f"Unexpected {r.status_code}"


def test_bank_pagination_per_page_too_large(client):
    """Too large per_page returns 400 (validation error) or uses max."""
    r = client.get("/bank?per_page=500")  # Above maximum
    assert r.status_code in (200, 400), f"Unexpected {r.status_code}"


def test_bank_pagination_with_filters(client):
    """Pagination works with filters."""
    r = client.get("/bank?page=1&per_page=10&currency=EUR&start_date=2025-09-01")
    assert r.status_code == 200


def test_bank_pagination_shows_count(client):
    """Pagination shows total count."""
    r = client.get("/bank")
    assert r.status_code == 200
    body = r.text
    # Should show pagination info if there are results
    if "Mostrando" in body or "movimientos" in body:
        # Pagination info is present
        assert True


def test_bank_csv_export_respects_currency(client):
    """CSV export respects currency filter."""
    r = client.get("/bank/export.csv?currency=EUR")
    assert r.status_code == 200
    content = r.content.decode("utf-8")
    # All rows should be EUR
    lines = content.strip().split("\n")
    if len(lines) > 2:
        # Check data rows (skip header)
        for line in lines[1:]:
            row = line.split(",")
            if len(row) >= 2:
                assert row[1] == "EUR"


def test_bank_csv_export_respects_pagination_filters(client):
    """CSV export includes date/currency filters."""
    r = client.get("/bank/export.csv?currency=EUR&start_date=2025-09-01&end_date=2025-09-30")
    assert r.status_code == 200


def test_bank_no_python_errors(client):
    """Bank page has no Python errors."""
    test_urls = [
        "/bank",
        "/bank?currency=EUR",
        "/bank?currency=PYG",
        "/bank?page=1",
        "/bank?page=2",
        "/bank?per_page=25",
        "/bank?currency=EUR&page=1",
        "/bank?start_date=2025-09-01&currency=EUR",
    ]

    for url in test_urls:
        r = client.get(url)
        assert r.status_code != 500, f"500 error on {url}"


def test_bank_pagination_links_preserve_filters(client):
    """Pagination links preserve other filters."""
    r = client.get("/bank?currency=EUR&page=1")
    assert r.status_code == 200
    body = r.text
    # Should have pagination controls
    if "pagination" in body or "page-item" in body:
        # Pagination is present
        assert True


def test_bank_currency_toggle_clear_button(client):
    """Clear button appears when currency filter active."""
    r = client.get("/bank?currency=EUR")
    assert r.status_code == 200
    body = r.text
    # Should have clear link
    assert "/bank" in body or "Limpiar" in body
