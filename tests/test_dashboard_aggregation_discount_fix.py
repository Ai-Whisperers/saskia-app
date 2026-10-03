"""Tests for the dashboard aggregation discount fix (Phase 14 #22).

Both `_build_hourly_sales_chart` and `_build_payment_methods_donut`
previously aggregated `qty × unit_price` (gross), silently overcounting
revenue for sales with `discount_gs > 0`. This test pins the post-fix
behavior: bucketing uses the post-discount line total so the dashboard
matches /recibo and /ventas.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.rms.models import Sale
from app.routers.dashboard import (
    _build_hourly_sales_chart,
    _build_payment_methods_donut,
)

ASUNCION = ZoneInfo("America/Asuncion")


def _sale(
    *,
    qty: float,
    unit_price_gs: int,
    discount_gs: int = 0,
    sold_at: datetime | None = None,
    payment_method: str = "efectivo",
    sale_id: int = 1,
) -> Sale:
    """Build a minimal Sale for the bucketing function (no DB required)."""
    return Sale(
        id=sale_id,
        product_id=1,
        qty=qty,
        unit_price_gs=unit_price_gs,
        discount_gs=discount_gs,
        sold_at=sold_at or datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc),
        payment_method=payment_method,
    )


def test_hourly_chart_buckets_discount_correctly():
    """A 5000 Gs. sale with 1000 Gs. discount must bucket 4000, not 5000.

    We put the two sales in DIFFERENT hours so each becomes its own
    bucket (max-bucket is the un-discounted one, the discounted one is
    the smaller bucket) — and we can verify the height ratio.
    """
    # 12:00 UTC = 09:00 Asunción (Paraguay observes UTC-3 in October DST)
    noon_utc = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    hour_later_utc = datetime(2026, 10, 1, 13, 0, tzinfo=timezone.utc)  # 10:00
    discounted = _sale(
        qty=1, unit_price_gs=5000, discount_gs=1000,
        sold_at=noon_utc, sale_id=1,
    )
    # Different hour so they get different buckets; same magnitude so
    # we can see the height difference between gross (5000) and
    # post-discount (4000) when normalized to the same max.
    full_price = _sale(
        qty=1, unit_price_gs=5000, discount_gs=0,
        sold_at=hour_later_utc, sale_id=2,
    )

    chart = _build_hourly_sales_chart([discounted, full_price], ASUNCION)
    # Both bars should be present (09h and 10h)
    assert "09h" in chart
    assert "10h" in chart
    # max=5000 (full_price), plot_h=132.
    # discounted bar height = 4000/5000 * 132 = 105.6 → "105.6"
    # gross would be 132.0 (full bar)
    assert 'height="105.6"' in chart, (
        f"discounted bar height should be 105.6 (4000/5000 * 132), "
        f"got: {chart[:300]}"
    )
    # Full-price bar should be the full height (132.0)
    assert 'height="132.0"' in chart


def test_hourly_chart_no_discount_uses_gross():
    """Without a discount, gross and post-discount are the same."""
    sale = _sale(qty=2, unit_price_gs=2500, discount_gs=0)
    chart = _build_hourly_sales_chart([sale], ASUNCION)
    # Single sale = max bucket = full height. plot_h = 132.
    assert 'height="132.0"' in chart


def test_hourly_chart_skips_sales_without_sold_at():
    """Sale rows with NULL sold_at must be silently skipped."""
    sale_no_time = Sale(
        id=1, product_id=1, qty=1, unit_price_gs=1000, discount_gs=0,
        sold_at=None, payment_method="efectivo",
    )
    chart = _build_hourly_sales_chart([sale_no_time], ASUNCION)
    assert "Sin ventas todavía" in chart


def test_hourly_chart_empty_list():
    """Empty sales list returns the empty-state message."""
    chart = _build_hourly_sales_chart([], ASUNCION)
    assert "Sin ventas todavía" in chart


def test_hourly_chart_all_zero_buckets_returns_empty_state():
    """Sales with NULL sold_at only → all-zero buckets → empty state."""
    sale_no_time = Sale(
        id=1, product_id=1, qty=1, unit_price_gs=1000, discount_gs=0,
        sold_at=None, payment_method="efectivo",
    )
    chart = _build_hourly_sales_chart([sale_no_time], ASUNCION)
    assert "Sin ventas todavía" in chart


def test_payment_methods_donut_respects_discount():
    """Donut chart sums post-discount line totals per payment method."""
    sales = [
        _sale(qty=1, unit_price_gs=10000, discount_gs=2000,
              payment_method="efectivo", sale_id=1),
        _sale(qty=1, unit_price_gs=5000, discount_gs=0,
              payment_method="tarjeta", sale_id=2),
        _sale(qty=2, unit_price_gs=3000, discount_gs=500,
              payment_method="efectivo", sale_id=3),
    ]
    # efectivo: (10000-2000) + (2*3000-500) = 8000 + 5500 = 13500
    # tarjeta: 5000
    donut = _build_payment_methods_donut(sales)
    # Donut SVG formats numbers with commas
    assert "13,500" in donut
    assert "5,000" in donut
    # Make sure the gross totals are NOT in the chart
    # (would be 16000 for efectivo, 5000 for tarjeta)
    assert "16,000" not in donut


def test_payment_methods_donut_handles_none_payment_method():
    """NULL payment_method must bucket as 'Sin especificar'."""
    sales = [
        Sale(
            id=1, product_id=1, qty=1, unit_price_gs=1000, discount_gs=0,
            sold_at=datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc),
            payment_method=None,
        ),
    ]
    donut = _build_payment_methods_donut(sales)
    assert "Sin especificar" in donut


def test_payment_methods_donut_empty():
    """No sales → empty-state message."""
    donut = _build_payment_methods_donut([])
    assert "Sin datos de pagos" in donut


def test_hourly_chart_clamped_at_zero_for_oversold_discount():
    """A discount larger than line total would yield negative; clamp to 0."""
    # edge case: discount exceeds line total (operator error). Should not
    # produce negative bar heights in the chart.
    sale = _sale(qty=1, unit_price_gs=1000, discount_gs=2000)
    chart = _build_hourly_sales_chart([sale], ASUNCION)
    # After clamp, bucket is 0 → empty state
    assert "Sin ventas todavía" in chart
