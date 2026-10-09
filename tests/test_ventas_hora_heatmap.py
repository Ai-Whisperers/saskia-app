"""Tests for BACKLOG #36: day-of-week × hour heatmap.

The original `/reportes/ventas-hora` page is a simple bar chart of
sales counts by hour-of-day. BACKLOG #36 wants a real heatmap:
day-of-week × hour matrix so operators can spot patterns like
"Friday 18-21h is the busiest slot".

This test pins the data shape returned by the new helper:
`sales_heatmap(session, since_days=N)` returns a 7×24 grid of counts.
We can then render the grid with CSS `background: hsl(... %)` cells.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.rms.config import ASUNCION_TZ
from app.rms.sales_intel import sales_heatmap


def test_sales_heatmap_returns_7_days_x_24_hours_grid(session_factory):
    """Output shape: 7 rows (Mon..Sun) × 24 cols (0..23 hours)."""
    with session_factory() as s:
        grid = sales_heatmap(s, since_days=90)
    assert len(grid) == 7
    for row in grid:
        assert len(row) == 24


def test_sales_heatmap_empty_database_returns_zeros(session_factory):
    """With no sales, the grid is all zeros."""
    with session_factory() as s:
        grid = sales_heatmap(s, since_days=90)
    for row in grid:
        for cell in row:
            assert cell == 0


def test_sales_heatmap_counts_sale_in_correct_cell(session_factory):
    """Insert a sale at a known local-time slot, verify the count lands.

    Day-of-week: Python's weekday() returns 0=Mon..6=Sun (local time).
    Hour: 0..23 (local time). The heatmap must bucket by LOCAL time
    because operators plan around Asunción local hours.
    """
    from app.rms.models import Product, Sale

    # Pick a stable local time: next Monday 14:30
    now_local = datetime.now(ASUNCION_TZ)
    days_to_mon = (0 - now_local.weekday()) % 7 or 7
    target = (now_local + timedelta(days=days_to_mon)).replace(
        hour=14, minute=30, second=0, microsecond=0
    )

    with session_factory() as s:
        # Need a product to satisfy the FK constraint.
        product = s.query(Product).first()
        if product is None:
            # Skip if seed didn't populate any products.
            pytest.skip("no products in seeded DB")
        s.add(
            Sale(
                product_id=product.id,
                qty=1.0,
                unit_price_gs=1000,
                sold_at=target,
            )
        )
        s.commit()

    with session_factory() as s:
        grid = sales_heatmap(s, since_days=90)
    # Find the cell we just incremented (Monday = row 0, hour 14 = col 14)
    assert grid[0][14] >= 1


def test_sales_heatmap_respects_since_days_window(session_factory):
    """Sales older than since_days are excluded from the heatmap."""
    from app.rms.models import Product, Sale

    old_time = (datetime.now(ASUNCION_TZ) - timedelta(days=120)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )

    with session_factory() as s:
        product = s.query(Product).first()
        if product is None:
            pytest.skip("no products in seeded DB")
        s.add(
            Sale(
                product_id=product.id,
                qty=1.0,
                unit_price_gs=500,
                sold_at=old_time,
            )
        )
        s.commit()

    with session_factory() as s:
        grid_30 = sales_heatmap(s, since_days=30)
        grid_180 = sales_heatmap(s, since_days=180)
    # 30-day window should not see the 120-day-old sale
    assert sum(sum(row) for row in grid_30) == 0
    # 180-day window should see it
    assert sum(sum(row) for row in grid_180) >= 1


def test_ventas_hora_page_renders_heatmap(client):
    """E4.S3 (BACKLOG #36): /reportes/ventas-hora renders the heatmap.

    Checks the response contains the heatmap CSS classes; full
    pixel-level render is the operator's job.
    """
    resp = client.get("/reportes/ventas-hora")
    assert resp.status_code == 200
    body = resp.text
    # Heatmap cell class is `heatmap-cell`
    assert "heatmap-cell" in body or "heatmap" in body.lower()
