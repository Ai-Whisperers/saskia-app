"""Tests for /produccion/accuracy Top-5 worst days widget.

Sazon-Improvement v2 (2026-10-06) Phase E step 5: the /accuracy
dashboard now surfaces the top 5 days with the biggest plan-vs-actual
delta (under-baked + over-baked). Operators glance at this to see
"which day did I screw up the worst?" without reading 30 rows of
the daily table.

The widget is rendered as a 2-column section above the product table:
  - Left: Top 5 worst days (most delta in absolute units)
  - Right: Top 5 best days (highest accuracy, planned > 0)

The data is computed in app.rms.plan_accuracy.compute_plan_accuracy()
and exposed as two new fields on AccuracyReport:
  - worst_days: list of (date, total_delta, total_planned, total_completed)
  - best_days:  same shape, ordered by avg_accuracy desc
"""
from __future__ import annotations

from datetime import date

from app.rms.plan_accuracy import (
    AccuracyReport,
    DailyAccuracyRow,
    compute_plan_accuracy,
)


def test_accuracy_report_has_worst_days_field():
    """AccuracyReport must expose worst_days as a list of (date, ...) tuples."""
    report = AccuracyReport()
    assert hasattr(report, "worst_days")
    assert isinstance(report.worst_days, list)


def test_accuracy_report_has_best_days_field():
    """AccuracyReport must expose best_days as a list of (date, ...) tuples."""
    report = AccuracyReport()
    assert hasattr(report, "best_days")
    assert isinstance(report.best_days, list)


def test_empty_period_has_no_worst_or_best_days():
    """When no data exists, both lists are empty (not None, not crash)."""
    report = AccuracyReport()
    assert report.worst_days == []
    assert report.best_days == []


def test_daily_delta_aggregation():
    """Per-day total = sum(planned) + sum(completed) across products."""
    from app.rms.plan_accuracy import _aggregate_daily_totals

    # Synthetic data: 2 days, 1 product each, 1 day under-baked + 1 over-baked
    rows = [
        DailyAccuracyRow(
            product_id=1, product_name="Pan", for_date=date(2026, 10, 5),
            planned_qty=10.0, completed_qty=8.0, sold_qty=7.0,
        ),
        DailyAccuracyRow(
            product_id=2, product_name="Chipa", for_date=date(2026, 10, 5),
            planned_qty=5.0, completed_qty=4.0, sold_qty=3.0,
        ),
        DailyAccuracyRow(
            product_id=1, product_name="Pan", for_date=date(2026, 10, 6),
            planned_qty=20.0, completed_qty=25.0, sold_qty=18.0,
        ),
    ]
    totals = _aggregate_daily_totals(rows)
    # 10-05: 15 planned, 12 completed → delta=3 (under)
    assert totals[date(2026, 10, 5)]["planned"] == 15.0
    assert totals[date(2026, 10, 5)]["completed"] == 12.0
    assert totals[date(2026, 10, 5)]["delta"] == 3.0
    assert totals[date(2026, 10, 5)]["accuracy"] == 0.8
    # 10-06: 20 planned, 25 completed → delta=5 (over, accuracy 1.25)
    assert totals[date(2026, 10, 6)]["planned"] == 20.0
    assert totals[date(2026, 10, 6)]["completed"] == 25.0
    assert totals[date(2026, 10, 6)]["delta"] == 5.0
    assert totals[date(2026, 10, 6)]["accuracy"] == 1.25


def test_worst_days_sorted_by_delta_desc():
    """worst_days returns up to 5 days, ordered by |delta| descending."""
    from app.rms.plan_accuracy import _top_worst_days, _aggregate_daily_totals

    rows = [
        DailyAccuracyRow(
            product_id=1, product_name="A", for_date=date(2026, 10, 1),
            planned_qty=10.0, completed_qty=10.0, sold_qty=10.0,
        ),
        DailyAccuracyRow(
            product_id=1, product_name="A", for_date=date(2026, 10, 2),
            planned_qty=10.0, completed_qty=2.0, sold_qty=2.0,
        ),
        DailyAccuracyRow(
            product_id=1, product_name="A", for_date=date(2026, 10, 3),
            planned_qty=10.0, completed_qty=0.0, sold_qty=0.0,
        ),
    ]
    totals = _aggregate_daily_totals(rows)
    worst = _top_worst_days(totals, n=5)
    # 10-03: delta=10 (worst), 10-02: delta=8, 10-01: delta=0
    assert [d[0] for d in worst] == [
        date(2026, 10, 3), date(2026, 10, 2), date(2026, 10, 1)
    ]
    # 10-01 has delta=0 but is included (no under-bake or over-bake);
    # the cook might want to see "good days" too.
    assert worst[0][1] == 10.0
    assert worst[1][1] == 8.0


def test_best_days_sorted_by_accuracy_desc():
    """best_days returns up to 5 days with planned > 0, ordered by accuracy desc."""
    from app.rms.plan_accuracy import _top_best_days, _aggregate_daily_totals

    rows = [
        DailyAccuracyRow(
            product_id=1, product_name="A", for_date=date(2026, 10, 1),
            planned_qty=10.0, completed_qty=10.0, sold_qty=10.0,
        ),
        DailyAccuracyRow(
            product_id=1, product_name="A", for_date=date(2026, 10, 2),
            planned_qty=10.0, completed_qty=8.0, sold_qty=7.0,
        ),
        # No plan for 10-03 → should NOT appear in best_days
        DailyAccuracyRow(
            product_id=1, product_name="A", for_date=date(2026, 10, 3),
            planned_qty=0.0, completed_qty=5.0, sold_qty=3.0,
        ),
    ]
    totals = _aggregate_daily_totals(rows)
    best = _top_best_days(totals, n=5)
    # 10-01 accuracy 1.0 (best), 10-02 accuracy 0.8, 10-03 excluded
    assert [d[0] for d in best] == [date(2026, 10, 1), date(2026, 10, 2)]
    assert best[0][2] == 1.0
    assert best[1][2] == 0.8


def test_top_n_returns_at_most_n():
    """If there are more than N days, the lists are capped at N."""
    from app.rms.plan_accuracy import _top_worst_days, _aggregate_daily_totals

    rows = [
        DailyAccuracyRow(
            product_id=1, product_name="A", for_date=date(2026, 10, i),
            planned_qty=10.0, completed_qty=float(i % 5), sold_qty=0.0,
        )
        for i in range(1, 11)  # 10 days
    ]
    totals = _aggregate_daily_totals(rows)
    worst = _top_worst_days(totals, n=5)
    assert len(worst) == 5
