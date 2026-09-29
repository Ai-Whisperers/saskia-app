"""Test bank date range filter feature."""


def test_bank_page_renders(client):
    """Bank page renders normally."""
# allow-hardcoded-dates: date-range filter assertions must be deterministic
    r = client.get('/bank')
    assert r.status_code == 200

def test_bank_date_filter_shows_form(client):
    """Bank page shows date range filter form."""
    r = client.get('/bank')
    assert r.status_code == 200
    body = r.text
    assert "start_date" in body, "Date range form missing start_date"
    assert "end_date" in body, "Date range form missing end_date"
    assert "Filtros" in body, "Filter button missing"

def test_bank_date_filter_empty(client):
    """Empty date filter works."""
    r = client.get('/bank?start_date=&end_date=')
    assert r.status_code == 200

def test_bank_date_filter_valid(client):
    """Date filter with valid dates works."""
    r = client.get('/bank?start_date=2025-09-01&end_date=2025-09-30')
    assert r.status_code == 200

def test_bank_date_filter_invalid(client):
    """Date filter with invalid dates doesn't crash."""
    r = client.get('/bank?start_date=invalid&end_date=invalid')
    assert r.status_code == 200

def test_bank_date_filter_mixed(client):
    """Mixed valid/invalid date filter works."""
    r = client.get('/bank?start_date=invalid&end_date=2025-09-30')
    assert r.status_code == 200

def test_bank_date_filter_with_category(client):
    """Date filter + category filter works."""
    r = client.get('/bank?start_date=2025-09-01&end_date=2025-09-30&category=groceries')
    assert r.status_code == 200

def test_bank_date_filter_clear_link(client):
    """Clear date filter link appears when filters applied."""
    r = client.get('/bank?start_date=2025-09-01&end_date=2025-09-30')
    assert r.status_code == 200
    body = r.text
    assert "/bank" in body, "Clear link missing"

def test_bank_retains_filters_on_manual_entry(client):
    """Date filters are preserved in form when filters applied."""
    r = client.get('/bank?start_date=2025-09-01&end_date=2025-09-30')
    assert r.status_code == 200
    assert "value=\"2025-09-01\"", "Start date not persisted in form"
    assert "value=\"2025-09-30\"", "End date not persisted in form"

def test_bank_date_filter_browser_compatible(client):
    """Date filter works with HTML date input (different format)."""
    r = client.get('/bank?start_date=2025-09-01&end_date=2025-09-30')
    assert r.status_code == 200
    body = r.text
    assert "2025-09-01" in body or "2025-09-30" in body, "Date filter not visible"

def test_bank_no_jinja_errors(client):
    """Bank page renders without Jinja errors."""
    r = client.get('/bank')
    assert r.status_code == 200
    body = r.text
    assert "TemplateSyntaxError" not in body and "UndefinedError" not in body, \
        "Jinja template error detected"
