"""tests/test_sales_intel.py — E30 sales intelligence tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.rms.models import Product, Sale
from app.rms.sales_intel import (
    churning_products,
    peak_day_of_week,
    peak_hour,
    product_affinity,
    rising_products,
    sales_by_day_of_week,
    sales_by_hour,
    sales_by_month,
    sales_summary,
    top_pairs,
)


def _make_sale(session, sold_at, product_id, qty=1, unit_price=1000):
    s = Sale(sold_at=sold_at, product_id=product_id, qty=qty,
             unit_price_gs=unit_price)
    session.add(s)
    return s


# ---------------------------------------------------------------------------
# Time patterns
# ---------------------------------------------------------------------------

def test_sales_by_hour_empty(session_factory):
    with session_factory() as s:
        result = sales_by_hour(s)
        assert len(result) == 24
        assert sum(result.values()) == 0


def test_sales_by_hour_distributes(session_factory):
    with session_factory() as s:
        p = Product(name="p_hour_xyz", portion_label="und",
                    sale_price_gs=1000)
        s.add(p)
        s.flush()
        now = datetime.now(timezone.utc)
        for _ in range(3):
            _make_sale(s, now.replace(hour=9, minute=0), p.id)
        for _ in range(5):
            _make_sale(s, now.replace(hour=14, minute=0), p.id)
        for _ in range(2):
            _make_sale(s, now.replace(hour=20, minute=0), p.id)
        s.commit()
        result = sales_by_hour(s)
        assert result[9] == 3
        assert result[14] == 5
        assert result[20] == 2
        assert result[0] == 0


def test_sales_by_dow(session_factory):
    with session_factory() as s:
        p = Product(name="p_dow_xyz", portion_label="und",
                    sale_price_gs=1000)
        s.add(p)
        s.flush()
        wed = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
        _make_sale(s, wed, p.id)
        s.commit()
        result = sales_by_day_of_week(s)
        assert result[2] == 1


def test_sales_by_month(session_factory):
    with session_factory() as s:
        p = Product(name="p_m_xyz", portion_label="und",
                    sale_price_gs=1000)
        s.add(p)
        s.flush()
        s1 = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
        s2 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
        _make_sale(s, s1, p.id)
        _make_sale(s, s2, p.id)
        s.commit()
        result = sales_by_month(s)
        assert "2026-09" in result
        assert "2026-10" in result
        assert result["2026-09"] == 1


def test_peak_hour(session_factory):
    with session_factory() as s:
        p = Product(name="p_pk_xyz", portion_label="und",
                    sale_price_gs=1000)
        s.add(p)
        s.flush()
        now = datetime.now(timezone.utc)
        for _ in range(5):
            _make_sale(s, now.replace(hour=8), p.id)
        for _ in range(10):
            _make_sale(s, now.replace(hour=12), p.id)
        for _ in range(3):
            _make_sale(s, now.replace(hour=18), p.id)
        s.commit()
        assert peak_hour(s) == 12


def test_peak_hour_no_sales_returns_neg_one(session_factory):
    with session_factory() as s:
        assert peak_hour(s) == -1


def test_peak_dow(session_factory):
    with session_factory() as s:
        p = Product(name="p_pkd_xyz", portion_label="und",
                    sale_price_gs=1000)
        s.add(p)
        s.flush()
        sat = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)
        _make_sale(s, sat, p.id)
        s.commit()
        assert peak_day_of_week(s) == 5


def test_sales_summary_shape(session_factory):
    with session_factory() as s:
        result = sales_summary(s)
        assert "by_hour" in result
        assert "by_dow" in result
        assert "by_month" in result
        assert "peak_hour" in result
        assert "peak_dow" in result


# ---------------------------------------------------------------------------
# Product affinity
# ---------------------------------------------------------------------------

def test_product_affinity_empty(session_factory):
    with session_factory() as s:
        assert product_affinity(s) == {}


def test_product_affinity_pair_bought_together(session_factory):
    with session_factory() as s:
        p1 = Product(name="aff_a_xyz", portion_label="und",
                     sale_price_gs=1000)
        p2 = Product(name="aff_b_xyz", portion_label="und",
                     sale_price_gs=1000)
        s.add_all([p1, p2])
        s.flush()
        now = datetime.now(timezone.utc)
        for day_offset in range(3):
            t = now - timedelta(days=day_offset, hours=10)
            _make_sale(s, t, p1.id)
            _make_sale(s, t + timedelta(minutes=30), p2.id)
        s.commit()
        pairs = product_affinity(s, min_cooccurrence=1)
        key = (min(p1.id, p2.id), max(p1.id, p2.id))
        assert pairs[key] == 3


def test_product_affinity_min_cooccurrence_filter(session_factory):
    with session_factory() as s:
        p1 = Product(name="min_a_xyz", portion_label="und",
                     sale_price_gs=1000)
        p2 = Product(name="min_b_xyz", portion_label="und",
                     sale_price_gs=1000)
        s.add_all([p1, p2])
        s.flush()
        now = datetime.now(timezone.utc)
        _make_sale(s, now, p1.id)
        _make_sale(s, now + timedelta(minutes=10), p2.id)
        s.commit()
        assert product_affinity(s, min_cooccurrence=2) == {}


def test_top_pairs_returns_n(session_factory):
    with session_factory() as s:
        p1 = Product(name="tp_a_xyz", portion_label="und",
                     sale_price_gs=1000)
        p2 = Product(name="tp_b_xyz", portion_label="und",
                     sale_price_gs=1000)
        s.add_all([p1, p2])
        s.flush()
        now = datetime.now(timezone.utc)
        for day in range(5):
            t = now - timedelta(days=day, hours=10)
            _make_sale(s, t, p1.id)
            _make_sale(s, t + timedelta(minutes=15), p2.id)
        s.commit()
        result = top_pairs(s, n=3)
        assert len(result) == 1
        assert result[0]["count"] == 5
        assert result[0]["product_a_name"] == "tp_a_xyz"


def test_top_pairs_includes_names(session_factory):
    with session_factory() as s:
        p1 = Product(name="named_a_xyz", portion_label="und",
                     sale_price_gs=1000)
        p2 = Product(name="named_b_xyz", portion_label="und",
                     sale_price_gs=1000)
        s.add_all([p1, p2])
        s.flush()
        now = datetime.now(timezone.utc)
        _make_sale(s, now, p1.id)
        _make_sale(s, now + timedelta(minutes=5), p2.id)
        s.commit()
        result = top_pairs(s)
        names = {result[0]["product_a_name"], result[0]["product_b_name"]}
        assert "named_a_xyz" in names
        assert "named_b_xyz" in names


# ---------------------------------------------------------------------------
# Churn + rising
# ---------------------------------------------------------------------------

def test_churning_products_detects_decline(session_factory):
    with session_factory() as s:
        p = Product(name="churn_xyz", portion_label="und",
                    sale_price_gs=1000)
        s.add(p)
        s.flush()
        now = datetime.now(timezone.utc)
        for i in range(30):
            t = now - timedelta(days=15 + i)
            _make_sale(s, t, p.id)
        for i in range(2):
            t = now - timedelta(days=14 - i)
            _make_sale(s, t, p.id)
        s.commit()
        churn = churning_products(s, threshold_pct=0.3, window_days=14)
        assert any(c.product_id == p.id for c in churn)


def test_rising_products_detects_growth(session_factory):
    with session_factory() as s:
        p = Product(name="rise_xyz", portion_label="und",
                    sale_price_gs=1000)
        s.add(p)
        s.flush()
        now = datetime.now(timezone.utc)
        for i in range(2):
            t = now - timedelta(days=20 + i)
            _make_sale(s, t, p.id)
        for i in range(30):
            t = now - timedelta(days=14 - i % 14)
            _make_sale(s, t, p.id)
        s.commit()
        rising = rising_products(s, threshold_pct=0.3, window_days=14)
        assert any(r.product_id == p.id for r in rising)


def test_churning_excludes_stable(session_factory):
    with session_factory() as s:
        p = Product(name="stable_xyz", portion_label="und",
                    sale_price_gs=1000)
        s.add(p)
        s.flush()
        now = datetime.now(timezone.utc)
        for i in range(10):
            _make_sale(s, now - timedelta(days=10 + i), p.id)
        for i in range(10):
            _make_sale(s, now - timedelta(days=10 - i), p.id)
        s.commit()
        churn = churning_products(s, threshold_pct=0.3, window_days=14)
        assert not any(c.product_id == p.id for c in churn)
