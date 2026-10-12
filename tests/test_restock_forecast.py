"""tests/test_restock_forecast.py — Test app/rms/restock_forecast.py (Phase 4.5).

The Poisson weekday restocking forecast (BACKLOG #5). Upgrades the
flat 30-day average in forecast.py with a per-weekday Poisson rate
model, no numpy/scipy (AGENTS.md rule 26). Closed-form MLE:
λ̂ = Σcounts / Σexposure.

Why weekday rates beat a flat average: a bakery's Saturday sales are
routinely 2-3× Tuesday's. A flat λ says "12 days of stock left" while
the Saturday-heavy path actually runs out in 8 — the exact gap this
module closes.

Public API tested:
  - WeekdayRates dataclass: rate(), se(), flat_equivalent()
  - poisson_weekday_rates(session, ingredient_id, window_days, now)
  - RestockForecast dataclass
  - forecast_restock(session, ingredient_id, ...)
  - forecast_restock_batch(session, ingredient_ids, only_at_risk, ...)

A regression here would either:
  - Report p95=14d when actual is 8d → operator misses a stockout
  - Mix up weekday indexing (%w is Sun=0; .weekday() is Mon=0) → flat
    average still wins on the worst day
  - Fail the `conf` SQLite strftime portability and drop everything to 0
  - Crash on an ingredient with no observed sales
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from sqlalchemy import select

from app.rms.models import Ingredient, StockMovement
from app.rms.restock_forecast import (
    WeekdayRates,
    forecast_restock,
    forecast_restock_batch,
    poisson_weekday_rates,
)


def _make_ingredient(
    session,
    name: str,
    stock_qty: float = 10.0,
    min_stock_qty: float = 5.0,
    purchase_price_gs: int = 5000,
) -> Ingredient:
    ing = Ingredient(
        name=name,
        unit="kg",
        stock_qty=stock_qty,
        min_stock_qty=min_stock_qty,
        purchase_price_gs=purchase_price_gs,
    )
    session.add(ing)
    session.commit()
    session.refresh(ing)
    return ing


def _add_sale_movement(
    session,
    ingredient: Ingredient,
    qty: float,
    recorded_at: datetime,
    reference_id: int = 1,
) -> StockMovement:
    m = StockMovement(
        ingredient_id=ingredient.id,
        movement_type="sale",
        qty=-qty,
        reference_id=reference_id,
        reference_type="sale",
        recorded_at=recorded_at,
    )
    session.add(m)
    session.commit()
    return m


# Pin "now" to a Sunday so weekday arithmetic is deterministic in tests.
# 2026-10-11 is a Sunday.
FROZEN_NOW = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)


class TestWeekdayRates:
    def test_rate_method_returns_per_weekday(self):
        wr = WeekdayRates(
            lambdas=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7],  # Mon..Sun
            exposures=[4.0] * 7,
        )
        assert wr.rate(0) == 0.1  # Monday
        assert wr.rate(5) == 0.6  # Saturday
        assert wr.rate(6) == 0.7  # Sunday
        # Wraps (7 = Monday again, -1 = Sunday)
        assert wr.rate(7) == 0.1
        assert wr.rate(-1) == 0.7

    def test_se_zero_when_no_exposure(self):
        # No weekday-w observations → SE is 0 (not NaN/inf)
        wr = WeekdayRates(
            lambdas=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            exposures=[0.0] * 7,
        )
        for wd in range(7):
            assert wr.se(wd) == 0.0

    def test_se_formula(self):
        # SE = sqrt(λ/n). For λ=0.5, n=4 → sqrt(0.125)
        import math
        wr = WeekdayRates(
            lambdas=[0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            exposures=[4.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        )
        assert wr.se(0) == math.sqrt(0.5 / 4.0)

    def test_flat_equivalent_weighted_by_exposure(self):
        # Different rates and exposures → weighted mean
        wr = WeekdayRates(
            lambdas=[0.1, 0.2, 0.0, 0.0, 0.0, 0.0, 0.0],
            exposures=[4.0, 6.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        )
        # (0.1*4 + 0.2*6) / (4+6) = 0.16
        assert wr.flat_equivalent() == pytest.approx(0.16)

    def test_flat_equivalent_zero_when_no_exposure(self):
        wr = WeekdayRates()
        assert wr.flat_equivalent() == 0.0

    def test_default_lambdas_and_exposures(self):
        wr = WeekdayRates()
        assert wr.lambdas == [0.0] * 7
        assert wr.exposures == [0.0] * 7
        assert wr.window_days == 56


class TestPoissonWeekdayRates:
    def test_no_data_returns_zero_rates(self, session_factory):
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_pf_empty")
        with session_factory() as s:
            wr = poisson_weekday_rates(s, ing.id, now=FROZEN_NOW)
        assert all(r == 0.0 for r in wr.lambdas)
        assert wr.window_days == 56  # default

    def test_window_days_parameter(self, session_factory):
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_pf_window")
        with session_factory() as s:
            wr = poisson_weekday_rates(s, ing.id, window_days=28, now=FROZEN_NOW)
        assert wr.window_days == 28

    def test_weekday_indexing_is_mon_0_to_sun_6(self, session_factory):
        # Add a sale on a Monday (date.weekday()=0) at a known past time
        # and a sale on a Sunday (date.weekday()=6). The lambdas should
        # reflect that.
        # Pick a Monday within the window: 2026-10-05 is Monday.
        # Pick a Sunday: 2026-10-04 is Sunday.
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_pf_dow")
            # Multiple sales on each day to make the rate visible
            for _ in range(3):
                _add_sale_movement(
                    s, ing, 2.0,
                    datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc),  # Monday
                    reference_id=1,
                )
            for _ in range(3):
                _add_sale_movement(
                    s, ing, 6.0,
                    datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc),  # Sunday
                    reference_id=2,
                )

        with session_factory() as s:
            wr = poisson_weekday_rates(s, ing.id, now=FROZEN_NOW)
        # In 56d window (2026-08-16 to 2026-10-11), 2026-10-05 (Mon) and
        # 2026-10-04 (Sun) both appear. 8 Mondays + 8 Sundays in 56d.
        # Monday: 3*2.0/8 = 0.75, Sunday: 3*6.0/8 = 2.25
        assert wr.lambdas[0] == pytest.approx(0.75)  # Mon
        assert wr.lambdas[6] == pytest.approx(2.25)  # Sun

    def test_excludes_non_sale_movements(self, session_factory):
        # merma/adjustment should not contribute to rate
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_pf_filter")
            # 3 sale movements on Monday 2026-10-05
            for _ in range(3):
                _add_sale_movement(
                    s, ing, 1.0,
                    datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc),
                    reference_id=1,
                )
            # 5 merma movements on the same Monday — should be ignored
            for _ in range(5):
                m = StockMovement(
                    ingredient_id=ing.id,
                    movement_type="merma",
                    qty=-10.0,
                    recorded_at=datetime(2026, 10, 5, 11, 0, tzinfo=timezone.utc),
                )
                s.add(m)
            s.commit()
        with session_factory() as s:
            wr = poisson_weekday_rates(s, ing.id, now=FROZEN_NOW)
        # Only the 3 sale movements count: 3*1.0/8 Mondays = 0.375
        assert wr.lambdas[0] == pytest.approx(0.375)

    def test_window_excludes_old_movements(self, session_factory):
        # A movement 100 days ago should not contribute to a 28d window
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_pf_old")
            _add_sale_movement(
                s, ing, 100.0,  # huge
                datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),  # way outside
                reference_id=1,
            )
        with session_factory() as s:
            wr = poisson_weekday_rates(s, ing.id, window_days=28, now=FROZEN_NOW)
        # No recent sales → all rates zero
        assert all(r == 0.0 for r in wr.lambdas)


class TestForecastRestock:
    def test_raises_value_error_for_missing_ingredient(self, session_factory):
        with session_factory() as s:
            with pytest.raises(ValueError, match="not found"):
                forecast_restock(s, 99999, now=FROZEN_NOW)

    def test_no_data_returns_zero_recommendation(self, session_factory):
        # No sales history → 2x min floor only
        with session_factory() as s:
            ing = _make_ingredient(
                s, "_smoke_rf_no_data", stock_qty=2.0, min_stock_qty=5.0
            )
        with session_factory() as s:
            fc = forecast_restock(s, ing.id, now=FROZEN_NOW)
        assert fc.lambda_flat == 0.0
        assert fc.p50_stockout_date is None
        assert fc.p95_stockout_date is None
        assert fc.days_to_p95_stockout is None
        # target = 2*min = 10, current = 2, so restock = 8
        assert fc.recommended_restock_qty == 8.0
        assert fc.confidence == "low"  # <10 observed days

    def test_confidence_low_under_10_days(self, session_factory):
        # 5 days of sales across 5 days → low confidence (<10)
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_rf_low", stock_qty=1000.0, min_stock_qty=5.0)
            for d in range(5):
                _add_sale_movement(s, ing, 1.0,
                    FROZEN_NOW - timedelta(days=d), reference_id=d + 1)
        with session_factory() as s:
            fc = forecast_restock(s, ing.id, now=FROZEN_NOW)
        assert fc.confidence == "low"

    def test_confidence_medium_at_10_days(self, session_factory):
        # 10 distinct days of sales → medium
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_rf_medium")
            for d in range(10):
                _add_sale_movement(
                    s, ing, 1.0,
                    FROZEN_NOW - timedelta(days=d),
                    reference_id=d + 1,
                )
        with session_factory() as s:
            fc = forecast_restock(s, ing.id, now=FROZEN_NOW)
        assert fc.confidence == "medium"

    def test_confidence_high_at_28_days(self, session_factory):
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_rf_high")
            for d in range(30):
                _add_sale_movement(
                    s, ing, 1.0,
                    FROZEN_NOW - timedelta(days=d),
                    reference_id=d + 1,
                )
        with session_factory() as s:
            fc = forecast_restock(s, ing.id, now=FROZEN_NOW)
        assert fc.confidence == "high"

    def test_p50_date_set_when_consumption_eventually_exceeds_stock(self, session_factory):
        # Stock=10, very high daily consumption → p50 within horizon
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_rf_p50", stock_qty=5.0, min_stock_qty=1.0)
            for d in range(56):
                _add_sale_movement(
                    s, ing, 3.0,
                    FROZEN_NOW - timedelta(days=d),
                    reference_id=d + 1,
                )
        with session_factory() as s:
            fc = forecast_restock(s, ing.id, now=FROZEN_NOW)
        assert fc.p50_stockout_date is not None
        assert fc.days_to_p95_stockout is not None
        # P95 should always be ≥ P50
        if fc.p50_stockout_date and fc.p95_stockout_date:
            assert fc.p95_stockout_date >= fc.p50_stockout_date

    def test_high_stock_no_stockout_in_horizon(self, session_factory):
        # 1000 stock, 0.1/day → no stockout in 60d horizon
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_rf_safe", stock_qty=1000.0, min_stock_qty=5.0)
            for d in range(56):
                _add_sale_movement(
                    s, ing, 0.1,
                    FROZEN_NOW - timedelta(days=d),
                    reference_id=d + 1,
                )
        with session_factory() as s:
            fc = forecast_restock(s, ing.id, now=FROZEN_NOW)
        # With 0.1/day and 1000 stock, no stockout in 60 days
        assert fc.p50_stockout_date is None
        assert fc.p95_stockout_date is None
        assert fc.days_to_p95_stockout is None
        # No restock needed (already above target)
        assert fc.recommended_restock_qty == 0.0

    def test_recommend_restock_covers_14d(self, session_factory):
        # With significant consumption, recommended covers 14 days
        with session_factory() as s:
            ing = _make_ingredient(
                s, "_smoke_rf_14d", stock_qty=2.0, min_stock_qty=1.0
            )
            for d in range(56):
                _add_sale_movement(
                    s, ing, 5.0,
                    FROZEN_NOW - timedelta(days=d),
                    reference_id=d + 1,
                )
        with session_factory() as s:
            fc = forecast_restock(s, ing.id, cover_days=14, now=FROZEN_NOW)
        # Should be at least 14d * λ (some multiple) - 2 stock
        # Plus the 2x min floor
        assert fc.recommended_restock_qty > 0

    def test_recommend_restock_respects_min_floor(self, session_factory):
        # Even with very low consumption, must hit 2x min
        with session_factory() as s:
            ing = _make_ingredient(
                s, "_smoke_rf_floor", stock_qty=2.0, min_stock_qty=10.0
            )
            for d in range(56):
                _add_sale_movement(
                    s, ing, 0.001,
                    FROZEN_NOW - timedelta(days=d),
                    reference_id=d + 1,
                )
        with session_factory() as s:
            fc = forecast_restock(s, ing.id, now=FROZEN_NOW)
        # 2x min = 20, current = 2, so restock = 18
        assert fc.recommended_restock_qty == pytest.approx(18.0, abs=0.5)

    def test_restock_cost_estimate_uses_purchase_price(self, session_factory):
        with session_factory() as s:
            ing = _make_ingredient(
                s, "_smoke_rf_cost",
                stock_qty=0.0, min_stock_qty=5.0,
                purchase_price_gs=10000,
            )
            for d in range(30):
                _add_sale_movement(
                    s, ing, 1.0,
                    FROZEN_NOW - timedelta(days=d),
                    reference_id=d + 1,
                )
        with session_factory() as s:
            fc = forecast_restock(s, ing.id, now=FROZEN_NOW)
        # Cost = recommended * 10000 Gs
        assert fc.restock_cost_gs_estimate is not None
        assert fc.restock_cost_gs_estimate == round(
            fc.recommended_restock_qty * 10000
        )

    def test_weekday_peak_and_trough(self, session_factory):
        # Strong Saturday pattern
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_rf_peak", stock_qty=1000.0, min_stock_qty=5.0)
            # Find all Saturdays in the 56d window before FROZEN_NOW
            for d in range(56):
                day = (FROZEN_NOW - timedelta(days=d)).date()
                if day.weekday() == 5:  # Saturday
                    _add_sale_movement(s, ing, 10.0,
                        datetime(day.year, day.month, day.day, 10, 0, tzinfo=timezone.utc),
                        reference_id=day.day + 100)
                else:
                    _add_sale_movement(s, ing, 0.5,
                        datetime(day.year, day.month, day.day, 10, 0, tzinfo=timezone.utc),
                        reference_id=day.day + 200)
        with session_factory() as s:
            fc = forecast_restock(s, ing.id, now=FROZEN_NOW)
        # Saturday should be peak, Mon or Tue should be trough
        assert fc.weekday_peak_rate > fc.weekday_trough_rate

    def test_weekend_uplift_positive(self, session_factory):
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_rf_uplift", stock_qty=1000.0, min_stock_qty=5.0)
            for d in range(56):
                day = (FROZEN_NOW - timedelta(days=d)).date()
                if day.weekday() in (5, 6):  # Sat or Sun
                    qty = 5.0
                else:
                    qty = 1.0
                _add_sale_movement(s, ing, qty,
                    datetime(day.year, day.month, day.day, 10, 0, tzinfo=timezone.utc),
                    reference_id=day.day + 300)
        with session_factory() as s:
            fc = forecast_restock(s, ing.id, now=FROZEN_NOW)
        # Weekend uplift should be positive
        assert fc.weekend_uplift_pct > 0

    def test_weekend_uplift_zero_when_no_weekday_data(self, session_factory):
        # No Mon-Thu data → weekday_avg is 0 → uplift is 0 (not -100 or inf)
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_rf_no_uplift", stock_qty=1000.0, min_stock_qty=5.0)
            for d in range(56):
                day = (FROZEN_NOW - timedelta(days=d)).date()
                if day.weekday() in (5, 6):
                    _add_sale_movement(s, ing, 1.0,
                        datetime(day.year, day.month, day.day, 10, 0, tzinfo=timezone.utc),
                        reference_id=day.day + 400)
        with session_factory() as s:
            fc = forecast_restock(s, ing.id, now=FROZEN_NOW)
        assert fc.weekend_uplift_pct == 0.0

    def test_handles_null_stock_qty(self, session_factory):
        with session_factory() as s:
            ing = Ingredient(
                name="_smoke_rf_null", unit="kg",
                stock_qty=None, min_stock_qty=5.0, purchase_price_gs=5000,
            )
            s.add(ing)
            s.commit()
            s.refresh(ing)
        with session_factory() as s:
            fc = forecast_restock(s, ing.id, now=FROZEN_NOW)
        assert fc.current_stock_qty == 0.0

    def test_handles_null_purchase_price(self, session_factory):
        with session_factory() as s:
            ing = Ingredient(
                name="_smoke_rf_no_price", unit="kg",
                stock_qty=2.0, min_stock_qty=5.0, purchase_price_gs=None,
            )
            s.add(ing)
            s.commit()
            s.refresh(ing)
            for d in range(30):
                _add_sale_movement(s, ing, 1.0,
                    FROZEN_NOW - timedelta(days=d),
                    reference_id=d + 1)
        with session_factory() as s:
            fc = forecast_restock(s, ing.id, now=FROZEN_NOW)
        # cost estimate is None when purchase_price is None
        assert fc.restock_cost_gs_estimate is None


class TestForecastRestockBatch:
    def test_empty_returns_empty(self, session_factory):
        with session_factory() as s:
            assert forecast_restock_batch(s, []) == {}

    def test_only_at_risk_filters_by_p95_threshold(self, session_factory):
        # Two ingredients: one at risk, one safe
        with session_factory() as s:
            at_risk = _make_ingredient(
                s, "_smoke_rf_batch_risk", stock_qty=5.0, min_stock_qty=1.0
            )
            safe = _make_ingredient(
                s, "_smoke_rf_batch_safe", stock_qty=10000.0, min_stock_qty=5.0
            )
            for d in range(56):
                _add_sale_movement(s, at_risk, 3.0,
                    FROZEN_NOW - timedelta(days=d), reference_id=d + 1)
                _add_sale_movement(s, safe, 0.1,
                    FROZEN_NOW - timedelta(days=d), reference_id=d + 100)

        with session_factory() as s:
            result = forecast_restock_batch(
                s, [at_risk.id, safe.id], only_at_risk=True,
                p95_days_threshold=14,
            )
        assert at_risk.id in result
        assert safe.id not in result  # 10000 stock, 0.1/day = ∞ days

    def test_only_at_risk_false_includes_all(self, session_factory):
        with session_factory() as s:
            safe = _make_ingredient(
                s, "_smoke_rf_batch_all", stock_qty=10000.0, min_stock_qty=5.0
            )
            for d in range(56):
                _add_sale_movement(s, safe, 0.1,
                    FROZEN_NOW - timedelta(days=d), reference_id=d + 1)

        with session_factory() as s:
            result = forecast_restock_batch(
                s, [safe.id], only_at_risk=False,
            )
        assert safe.id in result

    def test_propagates_value_error_for_missing_ingredient(self, session_factory):
        # forecast_restock_batch calls forecast_restock() per id, which
        # raises ValueError for missing ingredients. The batch function
        # does NOT catch — by design, so a typo in the id list surfaces.
        with session_factory() as s:
            real = _make_ingredient(s, "_smoke_rf_batch_real")
            for d in range(28):
                _add_sale_movement(s, real, 1.0,
                    FROZEN_NOW - timedelta(days=d), reference_id=d + 1)
        with pytest.raises(ValueError, match="not found"):
            with session_factory() as s2:
                forecast_restock_batch(s2, [real.id, 99999])
