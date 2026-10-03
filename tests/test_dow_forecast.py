"""tests/test_dow_forecast.py — verify day-of-week-aware forecast (Phase 4 B2).

Decision 2026-10-01: when ``target_weekday`` is set, the forecast
averages ONLY historical sales on that weekday (Mon=0 ... Sun=6).
12-week lookback; falls back to all-DOW average when < 4 DOW weeks
exist. Powers /produccion/manana (per-product DOW breakdown) and
the /inicio headline forecast.

Covers:
- target_weekday aggregates only that DOW
- target_weekday=None preserves legacy flat 14-day avg
- Fallback to flat avg when < 4 DOW weeks exist
- 12-week vs 6-week window: longer window smooths recent shifts
- Voided sales are excluded
- plan_production(use_dow_forecast=True) wires through
- Empty DB returns 0
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.crud


def _make_sale(session_factory, product_id, qty, sold_at):
    """Helper: create a non-voided Sale row directly."""
    from app.rms.db import safe_commit
    from app.rms.models import Sale

    with session_factory() as s:
        sale = Sale(
            product_id=product_id,
            qty=qty,
            sold_at=sold_at,
            unit_price_gs=2500,
            notes=None,
            channel="mostrador",
        )
        s.add(sale)
        safe_commit(s)


def _last_dow(target_weekday: int) -> datetime:
    """Return the most recent datetime (in UTC, noon) that has the given
    Python weekday (Mon=0..Sun=6). Always lands in the past relative to today."""
    today = datetime.now(timezone.utc)
    days_since = (today.weekday() - target_weekday) % 7
    last = today - timedelta(days=days_since)
    return last.replace(hour=12, minute=0, second=0, microsecond=0)


def test_dow_forecast_aggregates_only_target_weekday(session_factory, qseed):
    """12 weeks of Tuesdays at 5 units + 12 weeks of Wednesdays at 0
    units → Tuesday forecast should be ~5, Wednesday should be ~0.5."""
    from app.rms.production import forecast_sales

    data = qseed("basic")
    prod_id = data["product"].id

    last_tue = _last_dow(1)  # most recent Tuesday at noon UTC
    for w in range(12):
        tue = last_tue - timedelta(days=w * 7)
        _make_sale(session_factory, prod_id, 5.0, tue)
        wed = tue + timedelta(days=1)
        _make_sale(session_factory, prod_id, 0.5, wed)

    with session_factory() as s:
        tue_pred = forecast_sales(
            s, product_id=prod_id, days_history=90, target_weekday=1
        )
        wed_pred = forecast_sales(
            s, product_id=prod_id, days_history=90, target_weekday=2
        )

    assert tue_pred == pytest.approx(5.0, abs=0.1), f"Tue should be 5, got {tue_pred}"
    assert wed_pred == pytest.approx(0.5, abs=0.1), f"Wed should be 0.5, got {wed_pred}"


def test_dow_forecast_none_preserves_legacy_flat_avg(session_factory, qseed):
    """When target_weekday=None, behavior is the original flat daily avg."""
    from app.rms.production import forecast_sales

    data = qseed("basic")
    prod_id = data["product"].id

    last_mon = _last_dow(0)
    last_sun = _last_dow(6)
    for w in range(10):
        mon = last_mon - timedelta(days=w * 7)
        sun = last_sun - timedelta(days=w * 7)
        _make_sale(session_factory, prod_id, 5.0, mon)
        _make_sale(session_factory, prod_id, 1.0, sun)

    with session_factory() as s:
        flat = forecast_sales(s, product_id=prod_id, days_history=80)
        mon_dow = forecast_sales(s, product_id=prod_id, days_history=80, target_weekday=0)
        sun_dow = forecast_sales(s, product_id=prod_id, days_history=80, target_weekday=6)

    assert flat == pytest.approx(0.75, abs=0.05), f"flat should be 0.75, got {flat}"
    assert mon_dow == pytest.approx(5.0, abs=0.1), f"Mon-only should be 5, got {mon_dow}"
    assert sun_dow == pytest.approx(1.0, abs=0.1), f"Sun-only should be 1, got {sun_dow}"


def test_dow_forecast_fallback_when_fewer_than_4_dow_weeks(session_factory, qseed):
    """Only 2 historical Mondays in 12-week window → fallback to flat avg."""
    from app.rms.production import forecast_sales

    data = qseed("basic")
    prod_id = data["product"].id

    last_mon = _last_dow(0)
    for w in [0, 1]:  # only 2 Mondays
        mon = last_mon - timedelta(days=w * 7)
        _make_sale(session_factory, prod_id, 100.0, mon)
    last_wed = _last_dow(2)
    for w in range(11):
        wed = last_wed - timedelta(days=w * 7)
        _make_sale(session_factory, prod_id, 2.0, wed)

    with session_factory() as s:
        mon_pred = forecast_sales(
            s, product_id=prod_id, days_history=90, target_weekday=0
        )

    # Fallback fires (2 < 4) → all-DOW avg over 90d ≈ 222/90 = 2.47
    # Without fallback it would be 200/2 = 100.
    assert mon_pred < 50, f"fallback should kick in (<50), got {mon_pred}"


def test_dow_forecast_empty_db_returns_zero(session_factory, qseed):
    """No sales at all → both DOW and flat return 0."""
    from app.rms.production import forecast_sales

    data = qseed("basic")
    prod_id = data["product"].id

    with session_factory() as s:
        flat = forecast_sales(s, product_id=prod_id, days_history=84)
        dow = forecast_sales(s, product_id=prod_id, days_history=84, target_weekday=2)

    assert flat == 0.0
    assert dow == 0.0


def test_plan_production_uses_dow_forecast_when_flag_set(session_factory, qseed):
    """plan_production with use_dow_forecast=True picks DOW-only forecast
    for auto-suggested products."""
    from app.rms.production import plan_production

    data = qseed("basic")
    prod_id = data["product"].id

    last_tue = _last_dow(1)
    for w in range(8):
        tue = last_tue - timedelta(days=w * 7)
        _make_sale(session_factory, prod_id, 10.0, tue)

    # Plan a Tuesday 7 days ahead so the 84-day window catches all 8 sales.
    tue_target = (last_tue + timedelta(days=7)).date()

    with session_factory() as s:
        plan_dow = plan_production(
            s, for_date=tue_target, days_history=84, use_dow_forecast=True
        )

    prod_row = next((r for r in plan_dow.rows if r.product_id == prod_id), None)
    assert prod_row is not None, "expected the basic product in the plan"
    # DOW forecast (8 Tuesdays × 10 / 8 weeks = 10) × seasonal mult (1.0).
    assert prod_row.qty_to_produce == pytest.approx(10.0, abs=0.5), (
        f"DOW forecast should give ~10 for Tuesday, got {prod_row.qty_to_produce}"
    )


def test_dow_forecast_12_week_window_smooths_recent_shift(session_factory, qseed):
    """12 weeks averages old+new; 6 weeks only sees the new regime."""
    from app.rms.production import forecast_sales

    data = qseed("basic")
    prod_id = data["product"].id

    last_tue = _last_dow(1)
    # w=0..5 (newest 6 weeks): qty=8
    # w=6..11 (oldest 6 weeks): qty=2
    for w in range(12):
        tue = last_tue - timedelta(days=w * 7)
        q = 8.0 if w < 6 else 2.0
        _make_sale(session_factory, prod_id, q, tue)

    with session_factory() as s:
        dow_12w = forecast_sales(s, product_id=prod_id, days_history=84, target_weekday=1)
        dow_6w = forecast_sales(s, product_id=prod_id, days_history=42, target_weekday=1)

    assert dow_12w == pytest.approx(5.0, abs=0.1), f"12w DOW should be 5, got {dow_12w}"
    assert dow_6w == pytest.approx(8.0, abs=0.1), f"6w DOW should be 8, got {dow_6w}"


def test_dow_forecast_does_not_count_voided_sales(session_factory, qseed):
    """Voided sales should not contribute to the DOW forecast."""
    from app.rms.db import safe_commit
    from app.rms.models import Sale
    from app.rms.production import forecast_sales

    data = qseed("basic")
    prod_id = data["product"].id

    last_tue = _last_dow(1)
    # Use 5 active + 5 voided over 10 weeks to ensure all land in 90d window.
    for w in range(10):
        tue = last_tue - timedelta(days=w * 7)
        if w < 5:
            _make_sale(session_factory, prod_id, 4.0, tue)
        else:
            with session_factory() as s:
                s.add(Sale(
                    product_id=prod_id, qty=99.0,
                    sold_at=tue,
                    unit_price_gs=2500, channel="mostrador",
                    voided_at=datetime.now(timezone.utc),
                ))
                safe_commit(s)

    with session_factory() as s:
        pred = forecast_sales(s, product_id=prod_id, days_history=90, target_weekday=1)

    # 5 active Tuesdays × 4 / 5 = 4.0 (voided excluded).
    assert pred == pytest.approx(4.0, abs=0.1), f"voided should be excluded, got {pred}"
