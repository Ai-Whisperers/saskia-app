"""Dashboard KPI end-to-end tests."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.smoke
from datetime import datetime, timezone

from app.rms.models import Product, Sale


def test_dashboard_loads_empty(client):
    """GET / must return 200 even with no data."""
    r = client.get("/")
    assert r.status_code == 200, f"/ returned {r.status_code}: {r.text[:200]}"


def test_dashboard_loads_with_sales(client, session_factory):
    """GET / must return 200 with sales data."""

    with session_factory() as s:
        product = Product(
            name="KPI Test Product",
            portion_label="1 und",
            sale_price_gs=10000,
            is_available=True,
        )
        s.add(product)
        s.commit()
        s.refresh(product)

        sale = Sale(
            product_id=product.id,
            qty=2,
            unit_price_gs=10000,
            sold_at=datetime.now(timezone.utc),
        )
        s.add(sale)
        s.commit()

    r = client.get("/")
    assert r.status_code == 200, f"/ with sales returned {r.status_code}"


def test_dashboard_loads_with_voided_sales(client, session_factory):
    """GET / must handle voided sales correctly."""

    with session_factory() as s:
        product = Product(
            name="Void Test Product",
            portion_label="1 und",
            sale_price_gs=5000,
            is_available=True,
        )
        s.add(product)
        s.commit()
        s.refresh(product)

        # One normal, one voided
        s.add(
            Sale(
                product_id=product.id,
                qty=1,
                unit_price_gs=5000,
                sold_at=datetime.now(timezone.utc),
            )
        )
        s.add(
            Sale(
                product_id=product.id,
                qty=1,
                unit_price_gs=5000,
                sold_at=datetime.now(timezone.utc),
                voided_at=datetime.now(timezone.utc),
            )
        )
        s.commit()

    r = client.get("/")
    assert r.status_code == 200, f"/ with voided returned {r.status_code}"


def test_dashboard_filter_today(client):
    """GET /?period=today must return 200."""
    r = client.get("/?period=today")
    assert r.status_code == 200


def test_dashboard_filter_week(client):
    """GET /?period=week must return 200."""
    r = client.get("/?period=week")
    assert r.status_code == 200


def test_dashboard_filter_month(client):
    """GET /?period=month must return 200."""
    r = client.get("/?period=month")
    assert r.status_code == 200


def test_dashboard_filter_custom_with_dates(client):
    """GET /?period=custom with start/end must return 200."""
    r = client.get("/?period=custom&start=2026-01-01&end=2026-01-31")
    assert r.status_code == 200, f"/?period=custom with dates returned {r.status_code}"


def test_dashboard_filter_custom_no_dates_falls_back_to_today(client):
    """GET /?period=custom without start/end falls back to today's window.

    Regression test for SASKIA-213. The bug was that _period_window raised
    ValueError("Unknown period: custom") and the route returned 500. The fix
    is in app/routers/dashboard.py:_resolve_period_window, which routes the
    no-dates case through _period_window("custom") where the "custom" branch
    returns today's window (see lines 71-74 of that file).
    """
    r = client.get("/?period=custom")
    assert r.status_code == 200, f"Expected 200 fallback, got {r.status_code}"
