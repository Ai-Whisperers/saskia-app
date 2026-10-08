"""# allow-hardcoded-dates: fixtures intentionally pin fixed dates (calendar edges, tz math, far-future sentinels); asserted relative to frozen or explicit anchors.
tests/test_plan_accuracy_properties_phase14_tier6.py — Phase 14 Tier 6.

Hypothesis property-based tests for app/rms/plan_accuracy.py invariants.

These tests target the pure-math invariants of the dataclasses (no DB):
  - DailyAccuracyRow.accuracy / under_baked / over_baked / demand_met
  - ProductAccuracySummary.total_accuracy
  - AccuracyReport.under_baked_pct
  - Conservation: completed = planned - under_baked + over_baked
    (this is the algebraic core — must hold for any non-negative planned
    and completed, in all branches of the per-row properties)

DB-bound code paths (compute_plan_accuracy, _daily_completions,
_daily_sales) are exercised by tests/test_plan_accuracy.py
(round-trip tests with real sessions).

What this catches going forward:
  - Off-by-one in property threshold logic (the <=0 vs <0 boundary)
  - Sign flips in under_baked vs over_baked
  - Division-by-zero regressions (planned_qty == 0)
  - Conservation regressions (subtle: someone might compute
    under_baked + over_baked and forget to subtract from planned)
  - Rounding artifacts in nested aggregations
"""

from __future__ import annotations

from datetime import date

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.rms.plan_accuracy import (
    AccuracyReport,
    DailyAccuracyRow,
    ProductAccuracySummary,
)

# --- strategies ---

# Non-negative floats, including 0 and small denormals.
_nonneg = st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False)

# Strategy for (planned, completed, sold), all >= 0.
_qty_triple = st.tuples(_nonneg, _nonneg, _nonneg)

_dates = st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31))
_pid = st.integers(min_value=1, max_value=10_000)


def _row(planned: float, completed: float, sold: float) -> DailyAccuracyRow:
    return DailyAccuracyRow(
        product_id=1,
        product_name="test",
        for_date=date(2026, 10, 2),
        planned_qty=planned,
        completed_qty=completed,
        sold_qty=sold,
    )


# --- DailyAccuracyRow properties ---


@given(_qty_triple)
@settings(max_examples=200)
def test_accuracy_returns_none_when_planned_zero(
    qt: tuple[float, float, float],
) -> None:
    """planned <= 0 → accuracy is None regardless of completed/sold."""
    planned, completed, _sold = qt
    if planned > 0:
        return  # strategy precondition doesn't apply
    row = _row(planned, completed, 0.0)
    assert row.accuracy is None


@given(planned=_nonneg, completed=_nonneg)
@settings(max_examples=200)
def test_accuracy_returns_completed_over_planned_when_planned_positive(
    planned: float,
    completed: float,
) -> None:
    """planned > 0 → accuracy == round(completed / planned, 4)."""
    if planned <= 0:
        return
    row = _row(planned, completed, 0.0)
    expected = round(completed / planned, 4)
    assert row.accuracy == pytest.approx(expected, abs=1e-9)


@given(_qty_triple)
@settings(max_examples=200)
def test_under_baked_never_negative(qt: tuple[float, float, float]) -> None:
    """under_baked is a clamped max — never below 0."""
    row = _row(*qt)
    assert row.under_baked >= 0.0


@given(_qty_triple)
@settings(max_examples=200)
def test_over_baked_never_negative(qt: tuple[float, float, float]) -> None:
    """over_baked is a clamped max — never below 0."""
    row = _row(*qt)
    assert row.over_baked >= 0.0


@given(planned=_nonneg, completed=_nonneg)
@settings(max_examples=200)
def test_under_baked_when_planned_exceeds_completed(
    planned: float,
    completed: float,
) -> None:
    """planned > completed → under_baked == planned - completed."""
    if planned <= completed:
        return
    row = _row(planned, completed, 0.0)
    assert row.under_baked == pytest.approx(planned - completed, abs=1e-9)
    assert row.over_baked == 0.0


@given(planned=_nonneg, completed=_nonneg)
@settings(max_examples=200)
def test_over_baked_when_completed_exceeds_planned(
    planned: float,
    completed: float,
) -> None:
    """completed > planned → over_baked == completed - planned."""
    if completed <= planned:
        return
    row = _row(planned, completed, 0.0)
    assert row.over_baked == pytest.approx(completed - planned, abs=1e-9)
    assert row.under_baked == 0.0


@given(_qty_triple)
@settings(max_examples=200)
def test_demand_met_returns_none_when_completed_zero(
    qt: tuple[float, float, float],
) -> None:
    """completed <= 0 → demand_met is None regardless of sold."""
    _planned, completed, sold = qt
    if completed > 0:
        return
    row = _row(0.0, completed, sold)
    assert row.demand_met is None


@given(completed=_nonneg, sold=_nonneg)
@settings(max_examples=200)
def test_demand_met_when_completed_positive(
    completed: float,
    sold: float,
) -> None:
    """completed > 0 → demand_met == round(sold / completed, 4)."""
    if completed <= 0:
        return
    row = _row(0.0, completed, sold)
    expected = round(sold / completed, 4)
    assert row.demand_met == pytest.approx(expected, abs=1e-9)


# --- THE conservation invariant ---


@given(planned=_nonneg, completed=_nonneg)
@settings(max_examples=200)
def test_conservation_invariant_completed_equals_planned_minus_under_plus_over(
    planned: float,
    completed: float,
) -> None:
    """THE invariant: completed = planned - under_baked + over_baked.

    This must hold for any non-negative planned, completed — it's the
    algebraic identity that proves under_baked and over_baked correctly
    partition the gap between planned and completed.
    """
    row = _row(planned, completed, 0.0)
    assert row.completed_qty == pytest.approx(
        row.planned_qty - row.under_baked + row.over_baked,
        abs=1e-9,
    )


@given(planned=_nonneg, completed=_nonneg, sold=_nonneg)
@settings(max_examples=200)
def test_conservation_under_plus_over_equals_abs_gap(
    planned: float,
    completed: float,
    sold: float,
) -> None:
    """under_baked + over_baked == |completed - planned|.

    Both are zero when plans met exactly. Otherwise exactly one is
    non-zero (mutually exclusive branches).
    """
    row = _row(planned, completed, sold)
    gap = abs(completed - planned)
    assert row.under_baked + row.over_baked == pytest.approx(gap, abs=1e-9)
    if planned != completed:
        # Exactly one branch is non-zero.
        assert (row.under_baked > 0) != (row.over_baked > 0)


# --- ProductAccuracySummary.total_accuracy ---


@given(planned=_nonneg, completed=_nonneg)
@settings(max_examples=200)
def test_product_summary_total_accuracy_matches_completed_over_planned(
    planned: float,
    completed: float,
) -> None:
    """Same property as row.accuracy, at the product-aggregate level."""
    summary = ProductAccuracySummary(
        product_id=1,
        product_name="t",
        n_days_with_plan=1,
        n_days_completed=1,
        avg_accuracy=None,
        under_baked_units=max(planned - completed, 0.0),
        over_baked_units=max(completed - planned, 0.0),
        total_planned=planned,
        total_completed=completed,
        total_sold=0.0,
    )
    if planned <= 0:
        assert summary.total_accuracy is None
    else:
        assert summary.total_accuracy == pytest.approx(
            round(completed / planned, 4),
            abs=1e-9,
        )


# --- AccuracyReport.under_baked_pct ---


@given(planned=_nonneg, completed=_nonneg)
@settings(max_examples=200)
def test_report_under_baked_pct_none_when_total_planned_zero(
    planned: float,
    completed: float,
) -> None:
    """total_planned <= 0 → under_baked_pct is None."""
    if planned > 0:
        return
    report = AccuracyReport(
        daily_rows=[],
        product_summary=[],
        n_days_in_period=1,
        total_planned=planned,
        total_completed=completed,
        total_sold=0.0,
    )
    assert report.under_baked_pct is None


@given(planned=_nonneg, completed=_nonneg)
@settings(max_examples=200)
def test_report_under_baked_pct_in_unit_interval(
    planned: float,
    completed: float,
) -> None:
    """under_baked_pct is in [0, 1] when planned > 0."""
    if planned <= 0:
        return
    report = AccuracyReport(
        daily_rows=[],
        product_summary=[],
        n_days_in_period=1,
        total_planned=planned,
        total_completed=completed,
        total_sold=0.0,
    )
    pct = report.under_baked_pct
    assert pct is not None
    assert 0.0 <= pct <= 1.0


@given(planned=_nonneg, completed=_nonneg)
@settings(max_examples=200)
def test_report_under_baked_pct_zero_when_overbaked(
    planned: float,
    completed: float,
) -> None:
    """When over-baked (completed >= planned), under_baked_pct is 0."""
    if planned <= 0 or completed < planned:
        return
    report = AccuracyReport(
        total_planned=planned,
        total_completed=completed,
    )
    assert report.under_baked_pct == pytest.approx(0.0, abs=1e-9)


# --- date_range_presets smoke ---


def test_date_range_presets_returns_3_keys() -> None:
    """Three presets: 7d / 30d / 90d."""
    from app.rms.plan_accuracy import date_range_presets

    presets = date_range_presets()
    assert set(presets.keys()) == {"7d", "30d", "90d"}


@given(_dates)
def test_date_range_presets_window_length_matches_label(_unused: date) -> None:
    """Each preset's window length (inclusive) is label-1 + 1.

    7d → 7 days, 30d → 30 days, 90d → 90 days (start = today - (n-1),
    end = today, inclusive count = n).
    """
    from app.rms.plan_accuracy import date_range_presets

    presets = date_range_presets()
    for label, expected_days in [("7d", 7), ("30d", 30), ("90d", 90)]:
        start, end = presets[label]
        assert (end - start).days + 1 == expected_days
