"""tests/test_accounting_refunds.py — refund subtraction in accounting reports.

M1 (2026-10-02): the daily summary and the payment-method breakdown now
subtract refunds from gross so operators see NET revenue (not gross).

This file tests:
  - daily_summary returns NET revenue (= gross - refunds)
  - daily_summary exposes refunds_total_gs + refunds_count
  - sales_by_payment_method returns refunds_gs + n_refunds + net_total_gs
  - Refund rows that pre-date the sale's date (e.g. refunded yesterday for a
    sale made today) DON'T subtract from today's totals — they subtract from
    the day the refund was issued (recorded_at), per fiscal practice.
  - Daily summary stays correct on days with no refunds (regression guard)

What's NOT covered here (deferred):
  - libro_ventas refund section (fiscal report — needs separate design)
  - CSV export column ordering (deferred to librobased testing)
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("SASKIA_ENV", "test")
os.environ.setdefault("SASKIA_TEST_AUTH_DISABLED", "1")


@pytest.fixture()
def acc_engine():
    from app.rms.db import init_db, make_engine
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    yield engine


@pytest.fixture()
def acc_session(acc_engine):
    SessionLocal = sessionmaker(bind=acc_engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _make_sale(s, *, total_gs=10_000, payment_method="efectivo",
               customer_id=None, sold_at=None, voided=False):
    from app.rms.models_legacy import Product, Sale
    if s.execute(__import__("sqlalchemy").text("SELECT id FROM product WHERE id=1")).first() is None:
        s.add(Product(id=1, name="Test", sale_price_gs=total_gs, portion_label="unit"))
        s.flush()
    sale = Sale(
        product_id=1,
        qty=1.0,
        unit_price_gs=total_gs,
        sold_at=sold_at or datetime.now(timezone.utc),
        payment_method=payment_method,
        customer_id=customer_id,
        discount_gs=0,
        channel="mostrador",
        invoice_type="none",
        tz="America/Asuncion",
    )
    if voided:
        sale.voided_at = datetime.now(timezone.utc)
    s.add(sale)
    s.flush()
    return sale


def _make_refund(s, *, target_type, target_id, amount_gs,
                 payment_method="efectivo", recorded_at=None, restock_qty=False,
                 target_amount_gs=None):
    from app.rms.models_legacy import Refund
    r = Refund(
        target_type=target_type,
        target_id=target_id,
        # Default: target_amount_gs is generous (1_000_000) so tests can
        # stack multiple refunds without hitting the cap trigger. Override
        # explicitly when testing the cap itself.
        target_amount_gs=target_amount_gs if target_amount_gs is not None else 1_000_000,
        amount_gs=amount_gs,
        payment_method=payment_method,
        restock_qty=restock_qty,
        restocked_qty=0.0,
        recorded_at=recorded_at or datetime.now(timezone.utc),
        recorded_by="op",
        loyalty_reversed=0,
    )
    s.add(r)
    s.flush()
    return r


# ─── daily_summary ─────────────────────────────────────────────────────────


def test_daily_summary_subtracts_refunds(acc_session):
    """One sale + one full refund = NET revenue 0, not gross."""
    from app.rms.accounting import daily_summary
    from datetime import date

    sale = _make_sale(acc_session, total_gs=10_000)
    _make_refund(acc_session, target_type="sale", target_id=sale.id, amount_gs=10_000)

    summary = daily_summary(acc_session, day=datetime.now(timezone.utc))
    assert summary.refunds_total_gs == 10_000
    assert summary.refunds_count == 1
    # NET: 10_000 (gross) - 10_000 (refund) = 0
    assert summary.revenue_gross_gs == 0
    assert summary.iva_gs == 0


def test_daily_summary_partial_refund(acc_session):
    """Half-refund: gross 10k, refund 4k → net 6k."""
    from app.rms.accounting import daily_summary

    sale = _make_sale(acc_session, total_gs=10_000)
    _make_refund(acc_session, target_type="sale", target_id=sale.id, amount_gs=4_000)

    summary = daily_summary(acc_session, day=datetime.now(timezone.utc))
    assert summary.refunds_total_gs == 4_000
    assert summary.revenue_gross_gs == 6_000
    # IVA on 6k gross: 6000 / 1.1 = 5454 base, 546 iva
    assert 540 < summary.iva_gs < 560  # rounding tolerance


def test_daily_summary_no_refunds_unchanged(acc_session):
    """Regression: days with no refunds look exactly like before M1."""
    from app.rms.accounting import daily_summary

    _make_sale(acc_session, total_gs=10_000)
    _make_sale(acc_session, total_gs=5_000)

    summary = daily_summary(acc_session, day=datetime.now(timezone.utc))
    assert summary.refunds_total_gs == 0
    assert summary.refunds_count == 0
    # NET = gross (no refunds)
    assert summary.revenue_gross_gs == 15_000
    assert summary.n_sales == 2


def test_daily_summary_refund_on_different_day_doesnt_affect_today(acc_session):
    """A refund issued today but recorded yesterday must NOT subtract from
    today's totals — the refund's recorded_at is the only thing we filter on.

    Fiscal practice: the day of the refund is when money actually left, so
    that's the day's revenue-impacting event.
    """
    from app.rms.accounting import daily_summary
    from datetime import timedelta

    yesterday = datetime.now(timezone.utc) - timedelta(days=2)
    sale = _make_sale(acc_session, total_gs=10_000, sold_at=yesterday)
    _make_refund(
        acc_session, target_type="sale", target_id=sale.id,
        amount_gs=10_000,
        recorded_at=yesterday + timedelta(hours=1),  # refund was on the same day as sale
    )

    # Today's summary (no refunds today)
    summary_today = daily_summary(acc_session, day=datetime.now(timezone.utc))
    assert summary_today.refunds_total_gs == 0

    # Yesterday's summary (refund WAS on that day)
    summary_yesterday = daily_summary(acc_session, day=yesterday)
    assert summary_yesterday.refunds_total_gs == 10_000


# ─── sales_by_payment_method ──────────────────────────────────────────────


def test_payment_method_subtracts_refunds(acc_session):
    """Refund in same payment_method bucket subtracts from gross → net."""
    from app.rms.accounting import sales_by_payment_method

    _make_sale(acc_session, total_gs=10_000, payment_method="efectivo")
    _make_refund(
        acc_session, target_type="sale", target_id=1,
        amount_gs=3_000, payment_method="efectivo",
    )

    out = sales_by_payment_method(acc_session)
    assert "efectivo" in out
    bucket = out["efectivo"]
    assert bucket["total_gs"] == 10_000
    assert bucket["refunds_gs"] == 3_000
    assert bucket["net_total_gs"] == 7_000
    assert bucket["n_sales"] == 1
    assert bucket["n_refunds"] == 1


def test_payment_method_refund_without_sale(acc_session):
    """Edge case: refund exists but original sale doesn't (deleted) — bucket still shows up."""
    from app.rms.accounting import sales_by_payment_method

    _make_refund(
        acc_session, target_type="sale", target_id=99_999,
        amount_gs=2_000, payment_method="tarjeta",
    )

    out = sales_by_payment_method(acc_session)
    assert "tarjeta" in out
    bucket = out["tarjeta"]
    assert bucket["n_sales"] == 0
    assert bucket["total_gs"] == 0
    assert bucket["refunds_gs"] == 2_000
    assert bucket["net_total_gs"] == -2_000


def test_payment_method_per_method_refund_split(acc_session):
    """Refund in tarjeta doesn't subtract from efectivo."""
    from app.rms.accounting import sales_by_payment_method

    _make_sale(acc_session, total_gs=10_000, payment_method="efectivo")
    _make_sale(acc_session, total_gs=10_000, payment_method="tarjeta")
    # Refund tarjeta sale
    _make_refund(
        acc_session, target_type="sale", target_id=2,
        amount_gs=4_000, payment_method="tarjeta",
    )

    out = sales_by_payment_method(acc_session)
    assert out["efectivo"]["refunds_gs"] == 0
    assert out["tarjeta"]["refunds_gs"] == 4_000
    assert out["efectivo"]["net_total_gs"] == 10_000
    assert out["tarjeta"]["net_total_gs"] == 6_000


def test_payment_method_no_refunds_unchanged(acc_session):
    """Regression: no refunds → identical to pre-M1 output."""
    from app.rms.accounting import sales_by_payment_method

    _make_sale(acc_session, total_gs=5_000, payment_method="efectivo")
    _make_sale(acc_session, total_gs=7_000, payment_method="tarjeta")

    out = sales_by_payment_method(acc_session)
    assert out["efectivo"]["total_gs"] == 5_000
    assert out["efectivo"]["refunds_gs"] == 0
    assert out["efectivo"]["net_total_gs"] == 5_000
    assert out["tarjeta"]["total_gs"] == 7_000
    assert out["tarjeta"]["net_total_gs"] == 7_000


# ─── n_sales: NOT changed (refunds are not new sales) ─────────────────────


def test_daily_summary_n_sales_does_not_include_refunds(acc_session):
    """n_sales counts Sale rows only, not refunds."""
    from app.rms.accounting import daily_summary

    sale = _make_sale(acc_session, total_gs=10_000)
    _make_refund(acc_session, target_type="sale", target_id=sale.id, amount_gs=5_000)
    _make_refund(acc_session, target_type="sale", target_id=sale.id, amount_gs=2_000)

    summary = daily_summary(acc_session, day=datetime.now(timezone.utc))
    assert summary.n_sales == 1
    assert summary.refunds_count == 2
    assert summary.refunds_total_gs == 7_000
    # NET = 10k - 7k = 3k
    assert summary.revenue_gross_gs == 3_000
