"""tests/test_accounting.py — verify app/rms/accounting.py (E17).

Per docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md E17.

Covers:
- extract_iva with tax_mode="included" (gross=11k, base=10k, iva=1k)
- extract_iva with tax_mode="excluded" (gross=10k, base=10k, iva=1k)
- extract_iva raises on unknown mode
- monthly_iva_breakdown buckets by (year, month)
- libro_ventas returns chronological rows
- daily_summary computes one day's metrics
- product_margin_summary aggregates by product
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.analytics

from datetime import datetime, timedelta, timezone

from app.rms.accounting import (
    PARAGUAY_IVA_RATE,
    daily_summary,
    extract_iva,
    libro_ventas,
    monthly_iva_breakdown,
    product_margin_summary,
)
from app.rms.models import Customer, Product, Sale


def test_extract_iva_included_mode():
    """When price includes IVA: 11_000 -> base=10_000, iva=1_000."""
    calc = extract_iva(11_000, tax_mode="included")
    assert calc.gross_gs == 11_000
    assert calc.base_gs == 10_000
    assert calc.iva_gs == 1_000


def test_extract_iva_included_mode_one_million():
    """Big amount: 1_100_000 -> base=1_000_000, iva=100_000."""
    calc = extract_iva(1_100_000, tax_mode="included")
    assert calc.base_gs == 1_000_000
    assert calc.iva_gs == 100_000


def test_extract_iva_excluded_mode():
    """When price excludes IVA: 10_000 net + 1_000 IVA = 11_000 gross."""
    calc = extract_iva(10_000, tax_mode="excluded")
    assert calc.base_gs == 10_000
    assert calc.iva_gs == 1_000


def test_extract_iva_unknown_mode_raises():
    with pytest.raises(ValueError, match="Unknown tax_mode"):
        extract_iva(1000, tax_mode="bogus")


def test_paraguay_iva_rate_is_10_percent():
    """PY IVA = 10% (E17)."""
    from decimal import Decimal
    assert abs(PARAGUAY_IVA_RATE - Decimal("0.10")) < Decimal("1e-9")


def test_monthly_iva_breakdown_buckets_by_month(session_factory):
    """monthly_iva_breakdown aggregates per (year, month)."""
    s = session_factory()
    try:
        prod = Product(name="Muffin", sale_price_gs=1100)
        s.add(prod)
        s.flush()
        now = datetime.now(timezone.utc)
        s.add_all([
            # March: 3 sales
            Sale(sold_at=datetime(now.year, 3, 5), product_id=prod.id, qty=1, unit_price_gs=1100),
            Sale(sold_at=datetime(now.year, 3, 10), product_id=prod.id, qty=1, unit_price_gs=1100),
            Sale(sold_at=datetime(now.year, 3, 15), product_id=prod.id, qty=1, unit_price_gs=1100),
            # April: 1 sale
            Sale(sold_at=datetime(now.year, 4, 5), product_id=prod.id, qty=1, unit_price_gs=1100),
        ])
        s.commit()

        start = datetime(now.year, 1, 1, tzinfo=timezone.utc)
        end = datetime(now.year, 12, 31, tzinfo=timezone.utc)
        months = monthly_iva_breakdown(s, start_date=start, end_date=end)

        march = next((m for m in months if m.month == 3), None)
        assert march is not None
        assert march.n_sales == 3
        assert march.total_gross_gs == 3300
        # 3300 / 1.1 = 3000
        assert march.total_base_gs == 3000
        assert march.total_iva_gs == 300

        april = next((m for m in months if m.month == 4), None)
        assert april is not None
        assert april.n_sales == 1
    finally:
        s.close()


def test_monthly_iva_excludes_voided(session_factory):
    s = session_factory()
    try:
        prod = Product(name="Muffin", sale_price_gs=1100)
        s.add(prod)
        s.flush()
        now = datetime.now(timezone.utc)
        s.add_all([
            Sale(sold_at=datetime(now.year, 3, 5), product_id=prod.id, qty=1, unit_price_gs=1100),
            Sale(
                sold_at=datetime(now.year, 3, 10),
                product_id=prod.id,
                qty=1,
                unit_price_gs=1100,
                voided_at=datetime.now(timezone.utc),
            ),
        ])
        s.commit()

        start = datetime(now.year, 1, 1, tzinfo=timezone.utc)
        end = datetime(now.year, 12, 31, tzinfo=timezone.utc)
        months = monthly_iva_breakdown(s, start_date=start, end_date=end)
        march = next((m for m in months if m.month == 3), None)
        assert march is not None
        assert march.n_sales == 1  # voided excluded
    finally:
        s.close()


def test_libro_ventas_chronological_with_customer_name(session_factory):
    """libro_ventas returns chronological rows + resolves customer name."""
    s = session_factory()
    try:
        prod = Product(name="Docena muffins", sale_price_gs=25000)
        s.add(prod)
        s.flush()
        cust = Customer(name="María", phone="+595981000099")
        s.add(cust)
        s.flush()
        now = datetime.now(timezone.utc)
        s.add_all([
            Sale(sold_at=now - timedelta(days=3), product_id=prod.id, qty=1, unit_price_gs=25000, customer_id=cust.id),
            Sale(sold_at=now - timedelta(days=2), product_id=prod.id, qty=1, unit_price_gs=25000),
        ])
        s.commit()

        rows = libro_ventas(
            s,
            start_date=now - timedelta(days=10),
            end_date=now + timedelta(days=1),
        )
        assert len(rows) == 2
        assert rows[0].sold_at < rows[1].sold_at  # chronological
        # Customer name resolved for first
        assert rows[0].customer_name == "María"
        # Anon for second
        assert rows[1].customer_name is None
        # IVA extracted: 25000 * 10% / 110% = 2272.72... → truncated to 2272
        assert rows[0].total_gross_gs == 25000
        assert rows[0].iva_gs == 2272
    finally:
        s.close()


def test_daily_summary_for_one_day(session_factory):
    """daily_summary computes revenue + iva for a single day."""
    s = session_factory()
    try:
        prod = Product(name="Muffin", sale_price_gs=1100)
        s.add(prod)
        s.flush()
        day = datetime(2026, 3, 15)
        for hour in (9, 10, 11):
            s.add(Sale(
                sold_at=datetime(2026, 3, 15, hour, 0, tzinfo=timezone.utc),
                product_id=prod.id,
                qty=1,
                unit_price_gs=1100,
            ))
        s.commit()

        summary = daily_summary(s, day)
        assert summary.n_sales == 3
        assert summary.revenue_gross_gs == 3300
        assert summary.iva_gs == 300
        assert summary.margin_gs >= 0  # cogs may be 0 in test
    finally:
        s.close()


def test_product_margin_summary_per_product(session_factory):
    """product_margin_summary aggregates by product."""
    s = session_factory()
    try:
        p1 = Product(name="Muffin", sale_price_gs=2500)
        p2 = Product(name="Cheesecake", sale_price_gs=35000)
        s.add_all([p1, p2])
        s.flush()
        now = datetime.now(timezone.utc)
        # 4 muffins + 2 cheesecakes
        for _ in range(4):
            s.add(Sale(sold_at=now - timedelta(days=1), product_id=p1.id, qty=1, unit_price_gs=2500))
        for _ in range(2):
            s.add(Sale(sold_at=now - timedelta(days=1), product_id=p2.id, qty=1, unit_price_gs=35000))
        s.commit()

        margins = product_margin_summary(
            s,
            start_date=now - timedelta(days=2),
            end_date=now + timedelta(days=1),
        )
        assert len(margins) == 2
        # Sorted by product_id (deterministic); but revenue differs
        muff = next(m for m in margins if m.product_name == "Muffin")
        chee = next(m for m in margins if m.product_name == "Cheesecake")
        assert muff.n_sold == 4
        assert muff.revenue_gs == 10000
        assert chee.n_sold == 2
        assert chee.revenue_gs == 70000
    finally:
        s.close()


def test_accounting_handles_empty_db(session_factory):
    """Reports must return empty / 0 on fresh DB, no exceptions."""
    s = session_factory()
    try:
        assert monthly_iva_breakdown(s) == []
        assert libro_ventas(
            s,
            start_date=datetime.now(timezone.utc) - timedelta(days=10),
            end_date=datetime.now(timezone.utc),
        ) == []
        # daily_summary on empty DB
        ds = daily_summary(s, datetime.now(timezone.utc))
        assert ds.n_sales == 0
        assert ds.revenue_gross_gs == 0
        assert product_margin_summary(
            s,
            start_date=datetime.now(timezone.utc) - timedelta(days=10),
            end_date=datetime.now(timezone.utc),
        ) == []
    finally:
        s.close()
