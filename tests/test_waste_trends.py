"""Tests for BACKLOG #34 — Waste ROI per ingredient + price trend.

The `waste_impact_with_trends()` function joins WasteLog (cost
denormalized at insert time) with IngredientPriceEvent (append-only
history of purchase-price changes) to compute, per ingredient:

  - Total waste cost in the window
  - Average price in the recent half
  - Average price in the prior half
  - Percentage change recent vs prior

This unlocks the operator-facing question: "I'm wasting Harina, is
its price also rising?" If yes, the waste is becoming more
expensive and should be prioritized.

Coverage:
- Empty warehouse → empty list (no crash, no divide-by-zero)
- Waste only, no price history → trend_pct = None
- Price flat → trend_pct ≈ 0
- Price rising → trend_pct > 0, falls in amplified set
- Price falling → trend_pct < 0, NOT in amplified set
- Multiple ingredients → sorted by cost desc
- amplified_waste_ingredients() filters correctly
- 60-day floor (functions clamp `days` to 60 minimum)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.rms.models import (
    IngredientPriceEvent,
    WasteLog,
)
from app.rms.waste import (
    WasteIngredientTrend,
    amplified_waste_ingredients,
    waste_impact_with_trends,
)
from tests.factories import make_ingredient

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def _seed_ingredient(s, *, name, price_gs, stock_qty=10.0, unit="kg"):
    return make_ingredient(s, name=name, unit=unit, stock_qty=stock_qty, purchase_price_gs=price_gs)


def _seed_price_event(s, *, ingredient_id, price_gs, days_ago):
    s.add(
        IngredientPriceEvent(
            ingredient_id=ingredient_id,
            price_gs=price_gs,
            recorded_at=NOW - timedelta(days=days_ago),
            source="manual",
        )
    )


def test_empty_returns_empty_list(session_factory):
    """No waste + no price events → empty list, no crash."""
    s = session_factory()
    try:
        rows = waste_impact_with_trends(s, days=60, now=NOW)
        assert rows == []
    finally:
        s.close()


def test_waste_only_no_price_history_trend_is_none(session_factory):
    """Waste logged but no price events in either window → trend_pct=None."""
    s = session_factory()
    try:
        ing = _seed_ingredient(s, name="harina", price_gs=5000)
        s.flush()
        # Waste event 30 days ago
        s.add(
            WasteLog(
                ingredient_id=ing.id,
                qty=1.0,
                reason="vencida",
                cost_gs=5000,
                recorded_at=NOW - timedelta(days=30),
            )
        )
        s.flush()

        rows = waste_impact_with_trends(s, days=60, now=NOW)
        assert len(rows) == 1
        assert rows[0].ingredient_name == "harina"
        assert rows[0].cost_gs == 5000
        assert rows[0].trend_pct is None, "no price events → no trend"
        assert rows[0].avg_price_recent_gs is None
        assert rows[0].avg_price_prior_gs is None
    finally:
        s.close()


def test_flat_price_trend_is_zero(session_factory):
    """Price stable across the window → trend_pct ≈ 0.0."""
    s = session_factory()
    try:
        ing = _seed_ingredient(s, name="harina", price_gs=5000)
        s.flush()
        # Price events 50, 40, 30, 20, 10 days ago — all at 5000.
        for d in (50, 40, 30, 20, 10):
            _seed_price_event(s, ingredient_id=ing.id, price_gs=5000, days_ago=d)
        # Waste event 5 days ago
        s.add(
            WasteLog(
                ingredient_id=ing.id,
                qty=1.0,
                reason="vencida",
                cost_gs=5000,
                recorded_at=NOW - timedelta(days=5),
            )
        )
        s.flush()

        rows = waste_impact_with_trends(s, days=60, now=NOW)
        assert len(rows) == 1
        assert rows[0].trend_pct == 0.0, f"expected 0.0, got {rows[0].trend_pct}"
    finally:
        s.close()


def test_rising_price_positive_trend(session_factory):
    """Price rising → trend_pct > 0 → falls in amplified set."""
    s = session_factory()
    try:
        ing = _seed_ingredient(s, name="harina", price_gs=5000)
        s.flush()
        # Prior half (30-50 days): all at 4000
        for d in (50, 45, 40, 35):
            _seed_price_event(s, ingredient_id=ing.id, price_gs=4000, days_ago=d)
        # Recent half (5-25 days): all at 5000 → +25%
        for d in (25, 20, 15, 10, 5):
            _seed_price_event(s, ingredient_id=ing.id, price_gs=5000, days_ago=d)
        # Waste event 1 day ago
        s.add(
            WasteLog(
                ingredient_id=ing.id,
                qty=1.0,
                reason="vencida",
                cost_gs=5000,
                recorded_at=NOW - timedelta(days=1),
            )
        )
        s.flush()

        rows = waste_impact_with_trends(s, days=60, now=NOW)
        assert len(rows) == 1
        assert rows[0].avg_price_recent_gs == 5000
        assert rows[0].avg_price_prior_gs == 4000
        assert rows[0].trend_pct == 25.0, f"expected 25.0, got {rows[0].trend_pct}"
        # 25% > 5% threshold → amplified
        amplified = amplified_waste_ingredients(rows)
        assert len(amplified) == 1
        assert amplified[0].ingredient_name == "harina"
    finally:
        s.close()


def test_falling_price_negative_trend_not_amplified(session_factory):
    """Price falling → trend_pct < 0 → NOT in amplified set (default 5%)."""
    s = session_factory()
    try:
        ing = _seed_ingredient(s, name="azúcar", price_gs=5000)
        s.flush()
        # Prior half: 6000
        for d in (50, 45, 40, 35):
            _seed_price_event(s, ingredient_id=ing.id, price_gs=6000, days_ago=d)
        # Recent half: 5000 → -16.67%
        for d in (25, 20, 15, 10, 5):
            _seed_price_event(s, ingredient_id=ing.id, price_gs=5000, days_ago=d)
        # Waste
        s.add(
            WasteLog(
                ingredient_id=ing.id,
                qty=1.0,
                reason="vencida",
                cost_gs=5000,
                recorded_at=NOW - timedelta(days=1),
            )
        )
        s.flush()

        rows = waste_impact_with_trends(s, days=60, now=NOW)
        assert len(rows) == 1
        assert rows[0].trend_pct < 0
        assert rows[0].trend_pct == pytest.approx(-16.67, abs=0.01)
        # Negative trend → filtered out by default 5% threshold
        assert amplified_waste_ingredients(rows) == []
    finally:
        s.close()


def test_multiple_ingredients_sorted_by_cost_desc(session_factory):
    """3 ingredients with different costs → returned cost desc."""
    s = session_factory()
    try:
        cheap = _seed_ingredient(s, name="cheap", price_gs=1000)
        mid = _seed_ingredient(s, name="mid", price_gs=3000)
        expensive = _seed_ingredient(s, name="expensive", price_gs=10000)
        s.flush()
        for ing, qty, cost in [
            (cheap, 1.0, 1000),
            (mid, 2.0, 6000),
            (expensive, 1.0, 10000),
        ]:
            s.add(
                WasteLog(
                    ingredient_id=ing.id,
                    qty=qty,
                    reason="vencida",
                    cost_gs=cost,
                    recorded_at=NOW - timedelta(days=5),
                )
            )
        s.flush()

        rows = waste_impact_with_trends(s, days=60, now=NOW)
        assert len(rows) == 3
        names = [r.ingredient_name for r in rows]
        assert names == ["expensive", "mid", "cheap"]
        # Costs in same order
        costs = [r.cost_gs for r in rows]
        assert costs == [10000, 6000, 1000]
    finally:
        s.close()


def test_amplified_filters_by_threshold(session_factory):
    """amplified_waste_ingredients() respects trend_threshold_pct."""
    s = session_factory()
    try:
        mild = _seed_ingredient(s, name="mild", price_gs=5000)
        hot = _seed_ingredient(s, name="hot", price_gs=5000)
        s.flush()
        # mild: prior 5000, recent 5100 → +2% (below 5% threshold)
        for d in (50, 40):
            _seed_price_event(s, ingredient_id=mild.id, price_gs=5000, days_ago=d)
        for d in (20, 10):
            _seed_price_event(s, ingredient_id=mild.id, price_gs=5100, days_ago=d)
        # hot: prior 5000, recent 6000 → +20% (well above)
        for d in (50, 40):
            _seed_price_event(s, ingredient_id=hot.id, price_gs=5000, days_ago=d)
        for d in (20, 10):
            _seed_price_event(s, ingredient_id=hot.id, price_gs=6000, days_ago=d)
        # Both have waste
        for ing in (mild, hot):
            s.add(
                WasteLog(
                    ingredient_id=ing.id,
                    qty=1.0,
                    reason="vencida",
                    cost_gs=5000,
                    recorded_at=NOW - timedelta(days=5),
                )
            )
        s.flush()

        rows = waste_impact_with_trends(s, days=60, now=NOW)
        # Both rows present.
        assert len(rows) == 2
        # Default threshold 5%: only "hot" qualifies.
        amplified = amplified_waste_ingredients(rows)
        assert len(amplified) == 1
        assert amplified[0].ingredient_name == "hot"

        # Custom threshold 1%: both qualify.
        amplified_1pct = amplified_waste_ingredients(rows, trend_threshold_pct=1.0)
        assert len(amplified_1pct) == 2
    finally:
        s.close()


def test_only_recent_prices_no_prior_no_trend(session_factory):
    """Price events ONLY in recent half (no prior) → trend_pct = None.

    You can't compute a % change without a baseline.
    """
    s = session_factory()
    try:
        ing = _seed_ingredient(s, name="harina", price_gs=5000)
        s.flush()
        # Only recent events
        for d in (20, 10, 5):
            _seed_price_event(s, ingredient_id=ing.id, price_gs=5000, days_ago=d)
        s.add(
            WasteLog(
                ingredient_id=ing.id,
                qty=1.0,
                reason="vencida",
                cost_gs=5000,
                recorded_at=NOW - timedelta(days=2),
            )
        )
        s.flush()

        rows = waste_impact_with_trends(s, days=60, now=NOW)
        assert len(rows) == 1
        assert rows[0].avg_price_recent_gs == 5000
        assert rows[0].avg_price_prior_gs is None
        assert rows[0].trend_pct is None
    finally:
        s.close()


def test_only_prior_prices_no_recent_no_trend(session_factory):
    """Price events ONLY in prior half (no recent) → trend_pct = None."""
    s = session_factory()
    try:
        ing = _seed_ingredient(s, name="harina", price_gs=5000)
        s.flush()
        # Only prior events
        for d in (50, 45, 40):
            _seed_price_event(s, ingredient_id=ing.id, price_gs=4000, days_ago=d)
        s.add(
            WasteLog(
                ingredient_id=ing.id,
                qty=1.0,
                reason="vencida",
                cost_gs=5000,
                recorded_at=NOW - timedelta(days=2),
            )
        )
        s.flush()

        rows = waste_impact_with_trends(s, days=60, now=NOW)
        assert len(rows) == 1
        assert rows[0].avg_price_recent_gs is None
        assert rows[0].avg_price_prior_gs == 4000
        assert rows[0].trend_pct is None
    finally:
        s.close()


def test_days_param_clamped_minimum_60(session_factory):
    """Passing days=7 should still use 60 (the floor)."""
    s = session_factory()
    try:
        ing = _seed_ingredient(s, name="harina", price_gs=5000)
        s.flush()
        # 60-day-old price event
        _seed_price_event(s, ingredient_id=ing.id, price_gs=4000, days_ago=55)
        # 7-day-old price event
        _seed_price_event(s, ingredient_id=ing.id, price_gs=5000, days_ago=7)
        s.add(
            WasteLog(
                ingredient_id=ing.id,
                qty=1.0,
                reason="vencida",
                cost_gs=5000,
                recorded_at=NOW - timedelta(days=2),
            )
        )
        s.flush()

        # days=7 should still surface both halves correctly because
        # the function clamps to 60.
        rows = waste_impact_with_trends(s, days=7, now=NOW)
        assert len(rows) == 1
        assert rows[0].trend_pct is not None
        assert rows[0].trend_pct > 0  # price went 4000 -> 5000
    finally:
        s.close()


def test_waste_outside_window_ignored(session_factory):
    """Waste events older than `days` should not appear."""
    s = session_factory()
    try:
        ing = _seed_ingredient(s, name="harina", price_gs=5000)
        s.flush()
        # Waste 200 days ago → outside 60-day window
        s.add(
            WasteLog(
                ingredient_id=ing.id,
                qty=1.0,
                reason="vencida",
                cost_gs=5000,
                recorded_at=NOW - timedelta(days=200),
            )
        )
        s.flush()

        rows = waste_impact_with_trends(s, days=60, now=NOW)
        assert rows == []
    finally:
        s.close()


def test_waste_ingredient_trend_is_dataclass():
    """Smoke: the dataclass holds the expected fields with correct types."""
    row = WasteIngredientTrend(
        ingredient_id=1,
        ingredient_name="harina",
        cost_gs=5000,
        qty=1.0,
        avg_price_recent_gs=5000,
        avg_price_prior_gs=4000,
        trend_pct=25.0,
    )
    assert row.ingredient_id == 1
    assert row.ingredient_name == "harina"
    assert row.trend_pct == 25.0
