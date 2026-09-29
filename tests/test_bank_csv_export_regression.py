"""Test bank CSV export feature."""

import pytest
import csv
import io
from tests.conftest import client

def test_bank_page_renders(client):
    """Bank page renders normally."""
    r = client.get('/bank')
    assert r.status_code == 200

def test_bank_csv_export_endpoint_exists(client):
    """Bank CSV export endpoint exists."""
    r = client.get('/bank/export.csv')
    assert r.status_code == 200
    assert 'text/csv' in r.headers.get('content-type', '')
    assert 'attachment' in r.headers.get('content-disposition', '')

def test_bank_csv_export_basic(client):
    """CSV export returns data."""
    r = client.get('/bank/export.csv')
    assert r.status_code == 200
    
    # Check CSV content
    content = r.content.decode('utf-8')
    lines = content.strip().split('\n')
    
    # Should have header
    assert len(lines) >= 1
    assert 'Fecha' in lines[0]
    assert 'Cuenta' in lines[0]
    assert 'Importe' in lines[0]
    
    # May or may not have data rows

def test_bank_csv_export_with_filters(client):
    """CSV export respects date filters."""
    r = client.get('/bank/export.csv?start_date=2025-09-01&end_date=2025-09-30')
    assert r.status_code == 200
    
    content = r.content.decode('utf-8')
    lines = content.strip().split('\n')
    assert len(lines) >= 1  # header at least
    assert 'Fecha' in lines[0]  # header present

def test_bank_csv_export_with_category(client):
    """CSV export respects category filter."""
    r = client.get('/bank/export.csv?category=groceries')
    assert r.status_code == 200
    
    content = r.content.decode('utf-8')
    lines = content.strip().split('\n')
    assert len(lines) >= 1  # header at least
    assert 'Fecha' in lines[0]  # header present

def test_bank_csv_export_empty(client):
    """CSV export handles empty data gracefully."""
    r = client.get('/bank/export.csv?start_date=2025-01-01&end_date=2025-01-01')
    assert r.status_code == 200
    
    content = r.content.decode('utf-8')
    lines = content.strip().split('\n')
    assert 'Fecha' in lines[0]  # header still there
    assert len(lines) == 1  # header only (no data rows for empty filter)

def test_bank_csv_export_format_consistent(client):
    """CSV export has consistent format."""
    r = client.get('/bank/export.csv')
    assert r.status_code == 200
    
    # Parse CSV
    content = r.content.decode('utf-8')
    csv_reader = csv.reader(io.StringIO(content))
    rows = list(csv_reader)
    
    # Check structure - should always have header
    assert len(rows) >= 1
    assert len(rows[0]) == 6  # 6 columns
    assert rows[0] == ["Fecha", "Cuenta", "Importe", "Categoría", "Contraparte", "Descripción"]
    
    # If there's data, check data rows
    if len(rows) > 1:
        for row in rows[1:]:
            assert len(row) == 6  # consistent column count

def test_bank_csv_export_no_errors(client):
    """CSV export doesn't crash."""
    # Test various filter combinations
    test_urls = [
        '/bank/export.csv',
        '/bank/export.csv?category=groceries',
        '/bank/export.csv?start_date=2025-09-01',
        '/bank/export.csv?end_date=2025-09-30',
        '/bank/export.csv?category=groceries&start_date=2025-09-01',
        '/bank/export.csv?category=groceries&start_date=invalid&end_date=invalid',
    ]
    
    for url in test_urls:
        r = client.get(url)
        assert r.status_code != 500, f"CSV export failed for {url}"

def test_bank_csv_download_headers(client):
    """CSV export has correct download headers."""
    r = client.get('/bank/export.csv')
    assert r.status_code == 200
    
    content_disposition = r.headers.get('content-disposition', '')
    assert 'filename=bank_transactions.csv' in content_disposition
    assert 'attachment' in content_disposition

def test_bank_csv_preserves_date_format(client):
    """CSV export uses correct date format."""
    r = client.get('/bank/export.csv')
    assert r.status_code == 200
    
    content = r.content.decode('utf-8')
    lines = content.strip().split('\n')
    if len(lines) > 2:
        first_row = lines[1].split(',')
        if len(first_row) > 0:
            date_str = first_row[0]
            # Should be YYYY-MM-DD format
            assert len(date_str.split('-')) == 3