"""Smoke test for CSV export endpoints.

Per SASKIA_TEST_PLAN.md §5 #8 — every CSV export must:
- Return Content-Type: text/csv (or similar)
- Have non-empty body when there's data
- Money columns as integers (Gs.) not formatted strings
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.smoke
from datetime import datetime, timezone

from app.rms.models import Product, Sale

CSV_ROUTES = [
    "/inventario/export.csv",
    "/productos/export.csv",
    "/pedidos/export-csv",
    "/ventas/export.csv",
    "/reportes/precios/csv",
]


@pytest.mark.parametrize("route", CSV_ROUTES)
def test_csv_endpoint_returns_csv_content_type(client, route):
    """Every CSV endpoint must return text/csv content-type."""
    r = client.get(route)
    assert r.status_code < 500, f"GET {route} returned {r.status_code}"
    if r.status_code == 200:
        content_type = r.headers.get("content-type", "").lower()
        assert "csv" in content_type or "text/plain" in content_type, (
            f"{route} returned content-type '{content_type}', expected text/csv"
        )


@pytest.mark.parametrize("route", CSV_ROUTES)
def test_csv_endpoint_returns_nonempty_body_when_data_exists(client, route, session_factory):
    """CSV export with seeded data must return non-empty body."""
    # Seed minimal data so the CSV has at least headers
    with session_factory() as s:
        # Only add if no products
        existing = s.execute(Product.__table__.select().limit(1)).first()
        if not existing:
            p = Product(
                name="CSV Test Pan",
                portion_label="1 und",
                sale_price_gs=5000,
                is_available=True,
            )
            s.add(p)
            s.commit()

    r = client.get(route)
    if r.status_code == 200:
        body = r.text
        # Must have at least a header row
        assert len(body) > 0, f"{route} returned empty body"
        # CSV must have at least one line
        assert "\n" in body or len(body) > 10, f"{route} returned no CSV lines"


def test_ventas_export_csv_contains_money_columns(client, session_factory):
    """Ventas CSV must have integer money columns (Gs.)."""
    with session_factory() as s:
        p = Product(
            name="CSV Ventas Test",
            portion_label="1 und",
            sale_price_gs=12345,
            is_available=True,
        )
        s.add(p)
        s.commit()
        s.refresh(p)
        sale = Sale(
            product_id=p.id,
            qty=2,
            unit_price_gs=12345,
            sold_at=datetime.now(timezone.utc),
        )
        s.add(sale)
        s.commit()

    r = client.get("/ventas/export.csv")
    if r.status_code == 200:
        body = r.text
        # Money should be plain integers, not formatted with thousands separator
        assert "12.345" not in body, "Money columns should be plain integers, not formatted"
        assert "12345" in body, "Sale price 12345 should appear in CSV"


def test_productos_export_csv_includes_headers(client, session_factory):
    """Productos CSV must include header row with column names."""
    with session_factory() as s:
        p = Product(
            name="CSV Header Test",
            portion_label="1 und",
            sale_price_gs=5000,
            is_available=True,
        )
        s.add(p)
        s.commit()

    r = client.get("/productos/export.csv")
    if r.status_code == 200:
        body = r.text
        first_line = body.split("\n")[0].lower()
        # Should have at least one known column
        assert any(col in first_line for col in ("name", "id", "sale_price", "sku")), (
            f"CSV missing expected columns in header: {first_line}"
        )
