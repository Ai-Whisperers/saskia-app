"""Tests for BACKLOG #35: per-customer reorder rate.

A "reorder" = a returning customer making a 2nd+ purchase. The
existing `customer_retention()` only counts new vs returning; BACKLOG
#35 wants the **rate** of repeat purchase + the average gap between
orders. This is the core signal for "is this customer loyal?".

The helper returns:
- total_customers (distinct in window)
- customers_with_2plus_orders (distinct who reordered)
- reorder_rate (fraction of customers who reordered)
- avg_days_between_orders (mean gap across all consecutive-order pairs)
- median_days_between_orders (typical gap)
- top_repeaters (top N customers by total_orders)

All bucketing must use Asunción local time since that's the unit
operators reason about ("Saskia usually orders on Saturdays").
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.rms.config import ASUNCION_TZ
from app.rms.sales_intel import customer_reorder_rates
from tests.factories import make_customer, make_product, make_sale


def test_customer_reorder_rates_returns_expected_keys(session_factory):
    """Output shape: keys match the docstring contract."""
    with session_factory() as s:
        out = customer_reorder_rates(s, since_days=180)
    assert set(out.keys()) >= {
        "total_customers",
        "customers_with_2plus_orders",
        "reorder_rate",
        "avg_days_between_orders",
        "median_days_between_orders",
        "top_repeaters",
    }


def test_customer_reorder_rates_empty_db_returns_zeros(session_factory):
    """With no sales, the rates are zero and lists are empty."""
    with session_factory() as s:
        out = customer_reorder_rates(s, since_days=180)
    assert out["total_customers"] == 0
    assert out["customers_with_2plus_orders"] == 0
    assert out["reorder_rate"] == 0.0
    assert out["avg_days_between_orders"] == 0.0
    assert out["median_days_between_orders"] == 0.0
    assert out["top_repeaters"] == []


def test_customer_reorder_rate_counts_repeats(session_factory):
    """Customer with 3 orders in the window is a 'repeater' (1)."""
    with session_factory() as s:
        product = make_product(s, name="p_reorder_xyz")
        customer = make_customer(s, name="TEST_REORDER_3")
        s.commit()
        cid = customer.id

        now = datetime.now(ASUNCION_TZ)
        # 3 orders spaced 7 days apart
        for i in range(3):
            t = (now - timedelta(days=14) + i * timedelta(days=7))
            make_sale(
                s,
                product=product,
                qty=1.0,
                unit_price_gs=1000,
                at=t,
            )
            # set customer_id post-hoc (make_sale doesn't take it)
            s.query(type(customer)).filter_by(id=cid).first()
        # Re-fetch and tag the sales with customer_id
        from app.rms.models import Sale
        sales = (
            s.query(Sale)
            .filter(Sale.product_id == product.id)
            .order_by(Sale.sold_at)
            .all()
        )
        for sale in sales:
            sale.customer_id = cid
        s.commit()

    with session_factory() as s:
        out = customer_reorder_rates(s, since_days=180)

    assert out["customers_with_2plus_orders"] >= 1
    assert out["reorder_rate"] > 0.0
    # Avg gap ≈ 7 days (slight slack for sub-second rounding at commit time)
    assert out["avg_days_between_orders"] == pytest.approx(7.0, rel=0.05)


def test_customer_reorder_rates_top_repeaters_sorted_desc(session_factory):
    """top_repeaters list is sorted by total_orders (highest first)."""
    with session_factory() as s:
        product = make_product(s, name="p_toprep_xyz")

        a = make_customer(s, name="TEST_REORDER_A")
        b = make_customer(s, name="TEST_REORDER_B")
        s.commit()

        now = datetime.now(ASUNCION_TZ)
        # Customer A: 5 orders
        for i in range(5):
            sale = make_sale(
                s,
                product=product,
                qty=1.0,
                unit_price_gs=1000,
                at=now - timedelta(days=10 - i),
            )
            sale.customer_id = a.id
        # Customer B: 2 orders
        for i in range(2):
            sale = make_sale(
                s,
                product=product,
                qty=1.0,
                unit_price_gs=1000,
                at=now - timedelta(days=5 - i),
            )
            sale.customer_id = b.id
        s.commit()

    with session_factory() as s:
        out = customer_reorder_rates(s, since_days=180, top_n=20)

    names = [c["customer_name"] for c in out["top_repeaters"]]
    assert "TEST_REORDER_A" in names
    assert "TEST_REORDER_B" in names
    if "TEST_REORDER_A" in names and "TEST_REORDER_B" in names:
        # A has 5 orders, B has 2 — A should appear before B
        assert names.index("TEST_REORDER_A") < names.index("TEST_REORDER_B")


def test_customer_reorder_rates_excludes_voided_sales(session_factory):
    """Voided sales don't count toward reorder stats."""
    with session_factory() as s:
        product = make_product(s, name="p_voided_xyz")
        customer = make_customer(s, name="TEST_VOIDED")
        s.commit()
        cid = customer.id

        now = datetime.now(ASUNCION_TZ)
        # 1 valid sale (not a reorder); 1 voided sale (doesn't count)
        s1 = make_sale(
            s,
            product=product,
            qty=1.0,
            unit_price_gs=1000,
            at=now - timedelta(days=10),
        )
        s1.customer_id = cid
        s2 = make_sale(
            s,
            product=product,
            qty=1.0,
            unit_price_gs=1000,
            at=now - timedelta(days=5),
        )
        s2.customer_id = cid
        s2.voided_at = now  # void the second one
        s.commit()

    with session_factory() as s:
        out = customer_reorder_rates(s, since_days=180)

    # Only 1 valid order → customer should not appear in top_repeaters
    names = [c["customer_name"] for c in out["top_repeaters"]]
    assert "TEST_VOIDED" not in names


def test_customer_reorder_rates_respects_since_days(session_factory):
    """Orders older than since_days are excluded."""
    with session_factory() as s:
        product = make_product(s, name="p_old_xyz")
        customer = make_customer(s, name="TEST_OLD")
        s.commit()
        cid = customer.id

        old = datetime.now(ASUNCION_TZ) - timedelta(days=200)
        # 2 orders both outside the 90-day window
        for i in range(2):
            sale = make_sale(
                s,
                product=product,
                qty=1.0,
                unit_price_gs=1000,
                at=old + timedelta(days=i),
            )
            sale.customer_id = cid
        s.commit()

    with session_factory() as s:
        out_90 = customer_reorder_rates(s, since_days=90)
        out_365 = customer_reorder_rates(s, since_days=365)

    names_90 = [c["customer_name"] for c in out_90["top_repeaters"]]
    names_365 = [c["customer_name"] for c in out_365["top_repeaters"]]
    assert "TEST_OLD" not in names_90
    assert "TEST_OLD" in names_365


def test_ops_status_renders_reorder_stats(client):
    """E4.S4 (BACKLOG #35): /ops/status surfaces reorder stats.

    Renders the reorder_stats block even when there are no customers
    (degrades gracefully — reorder_rate=0.0, top_repeaters=[]).
    """
    resp = client.get("/ops/status")
    assert resp.status_code == 200
    body = resp.text
    # The page surfaces reorder stats under these text labels.
    assert "Reorder" in body or "reorder" in body.lower()
    # The stats block shows reorder rate as percent or fraction
    assert "rate" in body.lower() or "%" in body