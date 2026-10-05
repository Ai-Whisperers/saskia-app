"""tests/test_day_hour_heatmap.py — BACKLOG #36 day-of-week × hour-of-day grid.

Verifies the 7×24 heatmap bucket assignment, TZ conversion, empty-cells
fallback, and color-scaling max.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def hh_engine():
    from app.rms.db import init_db, make_engine
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    yield engine


@pytest.fixture()
def hh_session(hh_engine):
    SessionLocal = sessionmaker(bind=hh_engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _seed_sale(s, *, sold_at: datetime, qty=1, unit_price_gs=10_000,
               discount_gs=0, product_id=1):
    from app.rms.models_legacy import Product, Sale
    if s.execute(__import__("sqlalchemy").text("SELECT id FROM product WHERE id=1")).first() is None:
        s.add(Product(id=1, name="Test", sale_price_gs=10_000, portion_label="unit"))
        s.flush()
    sale = Sale(
        product_id=product_id,
        qty=qty,
        unit_price_gs=unit_price_gs,
        discount_gs=discount_gs,
        sold_at=sold_at,
        payment_method="efectivo",
        channel="mostrador",
        invoice_type="none",
        tz="America/Asuncion",
    )
    s.add(sale)
    s.flush()
    return sale


# ─── day_hour_heatmap ────────────────────────────────────────────────────────


def test_day_hour_heatmap_returns_168_cells(hh_session):
    """Every (weekday, hour) cell is materialized, even empty ones."""
    from app.rms.analytics import day_hour_heatmap

    hm = day_hour_heatmap(hh_session, days=7)
    assert len(hm.cells) == 7 * 24
    # All cells have valid weekday/hour
    seen = set()
    for c in hm.cells:
        assert 0 <= c.weekday < 7
        assert 0 <= c.hour < 24
        seen.add((c.weekday, c.hour))
    assert len(seen) == 168


def test_day_hour_heatmap_empty_period(hh_session):
    """No sales → all-zero cells, max_sales_gs=0, totals=0."""
    from app.rms.analytics import day_hour_heatmap

    hm = day_hour_heatmap(hh_session, days=30)
    assert hm.max_sales_gs == 0
    assert hm.total_sales_gs == 0
    assert hm.total_n_sales == 0
    for c in hm.cells:
        assert c.sales_gs == 0
        assert c.n_sales == 0


def test_day_hour_heatmap_buckets_by_asuncion_local(hh_session):
    """A sale at 12:00 UTC lands at 09:00 Asuncion local (UTC-3).

    Without TZ conversion, we'd bucket at 12:00 — operators would see
    a peak shifted 3 hours off their wall clock.
    """
    from app.rms.analytics import day_hour_heatmap

    # 2026-10-05 12:00 UTC = 2026-10-05 09:00 -03:00 (Monday)
    sale_at = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc).replace(tzinfo=None)
    _seed_sale(hh_session, sold_at=sale_at, unit_price_gs=1000)

    hm = day_hour_heatmap(hh_session, days=10)
    # Monday 09:00 (Asuncion) should have the sale
    cell = next(
        c for c in hm.cells
        if c.weekday == 0 and c.hour == 9
    )
    assert cell.sales_gs == 1000
    assert cell.n_sales == 1
    # Monday 12:00 should NOT (UTC bucket)
    cell_wrong = next(
        c for c in hm.cells
        if c.weekday == 0 and c.hour == 12
    )
    assert cell_wrong.sales_gs == 0


def test_day_hour_heatmap_discount_subtracted(hh_session):
    """Post-discount line total: unit_price × qty − discount_gs.

    Matches the Tier-4 #22 fix on dashboard hourly chart — the operator
    sees net revenue, not the over-counted gross.
    """
    from app.rms.analytics import day_hour_heatmap

    sale_at = datetime(2026, 10, 5, 14, 0, tzinfo=timezone.utc).replace(tzinfo=None)
    _seed_sale(hh_session, sold_at=sale_at, qty=2,
               unit_price_gs=5_000, discount_gs=3_000)
    # 2 × 5000 − 3000 = 7000

    hm = day_hour_heatmap(hh_session, days=10)
    cell = next(
        c for c in hm.cells
        if c.weekday == 0 and c.hour == 11
    )
    assert cell.sales_gs == 7_000


def test_day_hour_heatmap_multiple_sales_stack(hh_session):
    """Same cell, multiple sales → sum + count both increment."""
    from app.rms.analytics import day_hour_heatmap

    sale_at = datetime(2026, 10, 5, 15, 0, tzinfo=timezone.utc).replace(tzinfo=None)
    for _ in range(3):
        _seed_sale(hh_session, sold_at=sale_at, unit_price_gs=1_000)

    hm = day_hour_heatmap(hh_session, days=10)
    cell = next(c for c in hm.cells if c.weekday == 0 and c.hour == 12)
    assert cell.sales_gs == 3_000
    assert cell.n_sales == 3


def test_day_hour_heatmap_voided_excluded(hh_session):
    """Voided sales don't appear in the heatmap."""
    from app.rms.analytics import day_hour_heatmap
    from app.rms.models_legacy import Sale

    sale_at = datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc).replace(tzinfo=None)
    sale = _seed_sale(hh_session, sold_at=sale_at, unit_price_gs=2_000)
    sale.voided_at = datetime.now(timezone.utc)
    hh_session.flush()

    hm = day_hour_heatmap(hh_session, days=10)
    cell = next(c for c in hm.cells if c.weekday == 0 and c.hour == 7)
    assert cell.sales_gs == 0
    assert hm.total_n_sales == 0


def test_day_hour_heatmap_max_for_color_scale(hh_session):
    """max_sales_gs is the largest single cell, used by template to
    color-scale (e.g., intensity = cell.sales / max)."""
    from app.rms.analytics import day_hour_heatmap

    # Big sale on Mon 10:00, smaller on Wed 14:00
    _seed_sale(
        hh_session,
        sold_at=datetime(2026, 10, 5, 13, 0, tzinfo=timezone.utc).replace(tzinfo=None),
        unit_price_gs=10_000,
    )
    _seed_sale(
        hh_session,
        sold_at=datetime(2026, 10, 7, 17, 0, tzinfo=timezone.utc).replace(tzinfo=None),
        unit_price_gs=4_000,
    )
    hm = day_hour_heatmap(hh_session, days=10)
    assert hm.max_sales_gs == 10_000


def test_day_hour_heatmap_out_of_window_excluded(hh_session):
    """Sales older than `days` don't appear."""
    from app.rms.analytics import day_hour_heatmap

    old = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc).replace(tzinfo=None)
    _seed_sale(hh_session, sold_at=old, unit_price_gs=5_000)

    hm = day_hour_heatmap(hh_session, days=30)
    assert hm.total_sales_gs == 0
    assert hm.max_sales_gs == 0


def test_day_hour_heatmap_days_clamped(hh_session):
    """days < 1 clamped to 1, days > 365 clamped to 365."""
    from app.rms.analytics import day_hour_heatmap

    hm = day_hour_heatmap(hh_session, days=0)
    assert hm.days == 1
    hm = day_hour_heatmap(hh_session, days=9999)
    assert hm.days == 365


def test_day_hour_heatmap_total_equals_sum(hh_session):
    """Invariant: total_sales_gs == sum(cell.sales_gs for all cells)."""
    from app.rms.analytics import day_hour_heatmap

    _seed_sale(hh_session,
               sold_at=datetime(2026, 10, 5, 13, 0, tzinfo=timezone.utc).replace(tzinfo=None),
               unit_price_gs=3_000)
    _seed_sale(hh_session,
               sold_at=datetime(2026, 10, 7, 17, 0, tzinfo=timezone.utc).replace(tzinfo=None),
               unit_price_gs=7_000)
    hm = day_hour_heatmap(hh_session, days=10)
    assert hm.total_sales_gs == sum(c.sales_gs for c in hm.cells)
    assert hm.total_n_sales == sum(c.n_sales for c in hm.cells)