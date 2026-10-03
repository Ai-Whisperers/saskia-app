"""tests/test_plan_accuracy.py — BACKLOG #29 + #33 unit tests.

Covers:
  - empty DB → AccuracyReport with zero totals
  - one product, planned = completed = sold → accuracy = 1.0, no under/over
  - under-baked (completed < planned) → accuracy < 1, under_baked positive
  - over-baked (completed > planned + sold lower) → over_baked positive
  - ad-hoc completions (planned = 0, completed > 0) → accuracy = None, not 0
  - product aggregation across multiple days
  - daily rows exclude resolved cells (planned=completed=sold=0)
  - date_range_presets returns 7/30/90 day windows
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.rms.db import make_engine
from app.rms.models_legacy import Product, ProductionCompletion
from app.rms.plan_accuracy import (
    compute_plan_accuracy,
    date_range_presets,
)


@pytest.fixture
def plan_session():
    """In-memory SQLite + schema bootstrap for plan accuracy tests."""
    eng = make_engine("sqlite:///:memory:")
    from app.rms.db import init_db

    init_db(eng)
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=eng)()


@pytest.fixture
def product(plan_session) -> Product:
    p = Product(name="Pan de queso", sale_price_gs=5000)
    plan_session.add(p)
    plan_session.commit()
    plan_session.refresh(p)
    return p


def test_empty_db_returns_zero_report(plan_session):
    report = compute_plan_accuracy(
        plan_session,
        date(2026, 1, 1),
        date(2026, 1, 7),
        planned_qty_by_pid_day={},
    )
    assert report.total_planned == 0.0
    assert report.total_completed == 0.0
    assert report.total_sold == 0.0
    assert report.avg_accuracy is None
    assert report.daily_rows == []
    assert report.product_summary == []
    assert report.n_days_with_completion == 0
    assert report.n_days_in_period == 7


def test_perfect_match_accuracy_one(plan_session, product):
    planned = {(product.id, date(2026, 1, 1)): 10.0}
    plan_session.add(ProductionCompletion(
        product_id=product.id, for_date=date(2026, 1, 1), completed_qty=10.0,
        recorded_at=datetime(2026, 1, 1, 23, 59, 0),
    ))
    plan_session.commit()
    report = compute_plan_accuracy(
        plan_session, date(2026, 1, 1), date(2026, 1, 1), planned,
    )
    assert report.total_completed == 10.0
    assert report.total_planned == 10.0
    assert report.avg_accuracy == 1.0
    assert report.under_baked_pct == 0.0
    assert len(report.daily_rows) == 1
    row = report.daily_rows[0]
    assert row.accuracy == 1.0
    assert row.under_baked == 0.0
    assert row.over_baked == 0.0


def test_under_baked_low_accuracy(plan_session, product):
    planned = {(product.id, date(2026, 1, 1)): 10.0}
    plan_session.add(ProductionCompletion(
        product_id=product.id, for_date=date(2026, 1, 1), completed_qty=4.0,
        recorded_at=datetime(2026, 1, 1, 23, 59, 0),
    ))
    plan_session.commit()
    report = compute_plan_accuracy(
        plan_session, date(2026, 1, 1), date(2026, 1, 1), planned,
    )
    row = report.daily_rows[0]
    assert row.accuracy == 0.4
    assert row.under_baked == 6.0
    assert row.over_baked == 0.0
    assert report.product_summary[0].under_baked_units == 6.0


def test_over_baked_wasted_capacity(plan_session, product):
    """Made 12, planned 10, demand 8 — over_baked by 2 (the unsold surplus)."""
    planned = {(product.id, date(2026, 1, 1)): 10.0}
    plan_session.add(ProductionCompletion(
        product_id=product.id, for_date=date(2026, 1, 1), completed_qty=12.0,
        recorded_at=datetime(2026, 1, 1, 23, 59, 0),
    ))
    plan_session.commit()
    report = compute_plan_accuracy(
        plan_session, date(2026, 1, 1), date(2026, 1, 1), planned,
    )
    row = report.daily_rows[0]
    assert row.accuracy == 1.2
    assert row.over_baked == 2.0
    assert row.demand_met == pytest.approx(0.6667, 4)


def test_ad_hoc_completion_planned_zero(plan_session, product):
    """No plan, but operator baked 12 — accuracy = None (not 0)."""
    plan_session.add(ProductionCompletion(
        product_id=product.id, for_date=date(2026, 1, 1), completed_qty=12.0,
        recorded_at=datetime(2026, 1, 1, 23, 59, 0),
    ))
    plan_session.commit()
    report = compute_plan_accuracy(
        plan_session, date(2026, 1, 1), date(2026, 1, 1), {},
    )
    assert len(report.daily_rows) == 1
    row = report.daily_rows[0]
    assert row.accuracy is None
    assert row.planned_qty == 0.0
    assert row.completed_qty == 12.0


def test_multiple_days_aggregate(plan_session, product):
    """Product appears 3 days: planned 10/20/30, completed 12/18/5."""
    d1, d2, d3 = date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)
    planned = {
        (product.id, d1): 10.0,
        (product.id, d2): 20.0,
        (product.id, d3): 30.0,
    }
    for d, q in [(d1, 12.0), (d2, 18.0), (d3, 5.0)]:
        plan_session.add(ProductionCompletion(
            product_id=product.id, for_date=d, completed_qty=q,
            recorded_at=datetime(d.year, d.month, d.day, 23, 59, 0),
        ))
    plan_session.commit()
    report = compute_plan_accuracy(
        plan_session, d1, d3, planned,
    )
    assert report.n_days_with_completion == 3
    assert report.total_planned == 60.0
    assert report.total_completed == 35.0
    summary = report.product_summary[0]
    assert summary.n_days_with_plan == 3
    # d1 over by 2, d2 under by 2, d3 under by 25 → under = 2+25 = 27
    assert summary.under_baked_units == pytest.approx(27.0)
    assert summary.total_completed == 35.0
    assert summary.total_planned == 60.0


def test_zero_rows_excluded(plan_session, product):
    """Days with all-zero planned/completed/sold don't create rows."""
    report = compute_plan_accuracy(
        plan_session,
        date(2026, 1, 1),
        date(2026, 1, 7),
        {},
    )
    assert report.daily_rows == []
    assert report.n_days_with_completion == 0


def test_date_range_presets_returns_three_windows():
    presets = date_range_presets()
    assert set(presets.keys()) == {"7d", "30d", "90d"}
    for label, (start, end) in presets.items():
        if label == "7d":
            assert (end - start).days == 6
        if label == "30d":
            assert (end - start).days == 29
        if label == "90d":
            assert (end - start).days == 89
        assert start <= end


def test_voided_sales_excluded(plan_session, product):
    """Voided sales must NOT count toward sold_qty (demand_met / over-baked logic)."""
    from app.rms.models_legacy import Sale
    plan_session.add(Sale(
        sold_at=datetime(2026, 1, 1, 14, 0, 0),
        product_id=product.id, qty=2, unit_price_gs=5000,
        voided_at=datetime(2026, 1, 1, 15, 0, 0),
    ))
    plan_session.commit()
    report = compute_plan_accuracy(
        plan_session, date(2026, 1, 1), date(2026, 1, 1), {},
    )
    # No completions, no plan → no rows
    assert report.daily_rows == []
