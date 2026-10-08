"""Tests for BACKLOG #29 probabilistic (Poisson) consumption forecast.

`probabilistic_consumption_forecast()` is the rule-based approximation
of Poisson regression. Uses avg_daily_consumption as the rate parameter
λ, computes P(stockout within horizon) = 1 - Poisson_cdf(stock, λ × horizon),
and 95th-percentile safety stock.

This is the deterministic baseline that future Poisson regression would
extend with hourly buckets, day-of-week, and seasonality features.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.rms.analytics import (
    ProbabilisticForecast,
    probabilistic_consumption_forecast,
)
from app.rms.models_legacy import Ingredient, StockMovement


def test_probabilistic_forecast_empty(session_factory):
    """No consumption → empty list."""
    session = session_factory()
    forecasts = probabilistic_consumption_forecast(session)
    assert forecasts == []
    session.close()


def test_probabilistic_forecast_basic(session_factory):
    """Returns expected fields with reasonable magnitudes."""
    ingredient = Ingredient(
        name="Harina",
        unit="kg",
        stock_qty=10.0,
        purchase_price_gs=5000,
    )
    session = session_factory()
    session.add(ingredient)
    session.commit()
    ing_id = ingredient.id

    # -1/day over 30 days → avg_daily = 1.0
    now = datetime.now(timezone.utc)
    for day_offset in range(30):
        session.add(
            StockMovement(
                ingredient_id=ing_id,
                qty=-1.0,
                movement_type="sale",
                reference_type="sale",
                recorded_at=now - timedelta(days=day_offset),
            )
        )
    session.commit()
    session.close()

    session = session_factory()
    forecasts = probabilistic_consumption_forecast(session, lookback_days=30, horizon_days=7)
    session.close()

    assert len(forecasts) == 1
    f = forecasts[0]

    # λ = 1.0 (avg_daily_consumption)
    assert f.avg_daily_consumption == pytest.approx(1.0, abs=0.01)

    # Expected horizon = 1.0 × 7 = 7.0
    assert f.expected_horizon_consumption == pytest.approx(7.0, abs=0.01)

    # Stock = 10, expected = 7.0 → moderate stockout probability
    # P(X > 10 | Poisson(7)) is non-zero but not high
    assert 0.0 <= f.p_stockout_within_horizon <= 1.0

    # P(X = 0 | 7) ≈ exp(-7) ≈ 0.0009
    assert f.p_zero_consumption < 0.01
    assert f.p_any_consumption > 0.99


def test_probabilistic_high_stockout_probability(session_factory):
    """Stock below expected → high stockout probability."""
    ingredient = Ingredient(
        name="Azúcar",
        unit="kg",
        stock_qty=2.0,  # Very low
        purchase_price_gs=4000,
    )
    session = session_factory()
    session.add(ingredient)
    session.commit()
    ing_id = ingredient.id

    # High consumption: -1/day × 30 days = -30 total → λ = 1.0
    now = datetime.now(timezone.utc)
    for day_offset in range(30):
        session.add(
            StockMovement(
                ingredient_id=ing_id,
                qty=-1.0,
                movement_type="sale",
                reference_type="sale",
                recorded_at=now - timedelta(days=day_offset),
            )
        )
    session.commit()
    session.close()

    session = session_factory()
    forecasts = probabilistic_consumption_forecast(session, lookback_days=30, horizon_days=7)
    session.close()

    f = forecasts[0]

    # Stock = 2, expected = 7 → very high stockout probability
    # P(X > 2 | Poisson(7)) ≈ 0.92
    assert f.p_stockout_within_horizon > 0.8


def test_probabilistic_low_stockout_probability(session_factory):
    """Stock well above expected → low stockout probability."""
    ingredient = Ingredient(
        name="Manteca",
        unit="kg",
        stock_qty=100.0,  # Very high
        purchase_price_gs=10000,
    )
    session = session_factory()
    session.add(ingredient)
    session.commit()
    ing_id = ingredient.id

    # Low consumption: -1/day × 30 days → λ = 1.0
    now = datetime.now(timezone.utc)
    for day_offset in range(30):
        session.add(
            StockMovement(
                ingredient_id=ing_id,
                qty=-1.0,
                movement_type="sale",
                reference_type="sale",
                recorded_at=now - timedelta(days=day_offset),
            )
        )
    session.commit()
    session.close()

    session = session_factory()
    forecasts = probabilistic_consumption_forecast(session, lookback_days=30, horizon_days=7)
    session.close()

    f = forecasts[0]

    # Stock = 100, expected = 7 → very low stockout probability
    # P(X > 100 | Poisson(7)) ≈ 0 (essentially impossible)
    assert f.p_stockout_within_horizon < 0.01


def test_probabilistic_safety_stock_95pct(session_factory):
    """95th percentile is higher than expected consumption."""
    ingredient = Ingredient(
        name="X",
        unit="kg",
        stock_qty=50.0,
    )
    session = session_factory()
    session.add(ingredient)
    session.commit()
    ing_id = ingredient.id

    # -1/day × 30 days → λ = 1.0
    now = datetime.now(timezone.utc)
    for day_offset in range(30):
        session.add(
            StockMovement(
                ingredient_id=ing_id,
                qty=-1.0,
                movement_type="sale",
                reference_type="sale",
                recorded_at=now - timedelta(days=day_offset),
            )
        )
    session.commit()
    session.close()

    session = session_factory()
    forecasts = probabilistic_consumption_forecast(session, lookback_days=30, horizon_days=7)
    session.close()

    f = forecasts[0]

    # Expected = 7, σ = sqrt(7) ≈ 2.65
    # 95th percentile = 7 + 1.645 × 2.65 ≈ 11.36
    expected = f.expected_horizon_consumption
    safety = f.safety_stock_95pct

    assert safety > expected  # Safety stock > expected consumption
    assert safety - expected < expected  # Within reasonable margin (less than 100% of expected)


def test_probabilistic_sort_by_urgency(session_factory):
    """Sorted by stockout probability (highest first)."""
    session = session_factory()

    # High risk: low stock + consumption
    high_risk = Ingredient(name="Critical", unit="kg", stock_qty=1.0)
    # Low risk: high stock + consumption
    low_risk = Ingredient(name="Safe", unit="kg", stock_qty=500.0)
    session.add_all([high_risk, low_risk])
    session.commit()

    now = datetime.now(timezone.utc)
    session.add_all(
        [
            StockMovement(
                ingredient_id=high_risk.id,
                qty=-1.0,
                movement_type="sale",
                reference_type="sale",
                recorded_at=now - timedelta(days=1),
            ),
            StockMovement(
                ingredient_id=low_risk.id,
                qty=-1.0,
                movement_type="sale",
                reference_type="sale",
                recorded_at=now - timedelta(days=1),
            ),
        ]
    )
    session.commit()
    session.close()

    session = session_factory()
    forecasts = probabilistic_consumption_forecast(session, lookback_days=30, horizon_days=7)
    session.close()

    assert len(forecasts) == 2
    # Highest stockout probability first
    assert forecasts[0].name == "Critical"
    assert forecasts[0].p_stockout_within_horizon > forecasts[1].p_stockout_within_horizon


def test_probabilistic_filter_by_ingredient(session_factory):
    """ingredient_id filter returns only that ingredient."""
    session = session_factory()

    ing1 = Ingredient(name="A", unit="kg", stock_qty=10.0)
    ing2 = Ingredient(name="B", unit="kg", stock_qty=20.0)
    session.add_all([ing1, ing2])
    session.commit()

    now = datetime.now(timezone.utc)
    session.add_all(
        [
            StockMovement(
                ingredient_id=ing1.id,
                qty=-1.0,
                movement_type="sale",
                reference_type="sale",
                recorded_at=now,
            ),
            StockMovement(
                ingredient_id=ing2.id,
                qty=-1.0,
                movement_type="sale",
                reference_type="sale",
                recorded_at=now,
            ),
        ]
    )
    session.commit()
    ing1_id = ing1.id
    session.close()

    session = session_factory()
    forecasts = probabilistic_consumption_forecast(session, ingredient_id=ing1_id)
    session.close()

    assert len(forecasts) == 1
    assert forecasts[0].name == "A"


def test_probabilistic_horizon_days_param(session_factory):
    """Different horizons give different stockout probabilities."""
    ingredient = Ingredient(name="Z", unit="kg", stock_qty=10.0)
    session = session_factory()
    session.add(ingredient)
    session.commit()
    ing_id = ingredient.id

    now = datetime.now(timezone.utc)
    for day_offset in range(30):
        session.add(
            StockMovement(
                ingredient_id=ing_id,
                qty=-1.0,
                movement_type="sale",
                reference_type="sale",
                recorded_at=now - timedelta(days=day_offset),
            )
        )
    session.commit()
    session.close()

    session = session_factory()
    fc_7 = probabilistic_consumption_forecast(session, horizon_days=7)
    session.close()

    session = session_factory()
    fc_30 = probabilistic_consumption_forecast(session, horizon_days=30)
    session.close()

    # λ=1, stock=10
    # 7-day: expected=7, P(X>10|7) ~ 0.27
    # 30-day: expected=30, P(X>10|30) ~ ~1.0
    assert fc_7[0].expected_horizon_consumption < fc_30[0].expected_horizon_consumption
    assert fc_7[0].p_stockout_within_horizon < fc_30[0].p_stockout_within_horizon


def test_probabilistic_dataclass_shape(session_factory):
    """Verifies ProbabilisticForecast has correct field shapes."""
    ingredient = Ingredient(name="W", unit="kg", stock_qty=10.0)
    session = session_factory()
    session.add(ingredient)
    session.commit()
    ing_id = ingredient.id

    session.add(
        StockMovement(
            ingredient_id=ing_id,
            qty=-1.0,
            movement_type="sale",
            reference_type="sale",
            recorded_at=datetime.now(timezone.utc),
        )
    )
    session.commit()
    session.close()

    session = session_factory()
    forecasts = probabilistic_consumption_forecast(session)
    session.close()

    assert len(forecasts) == 1
    f = forecasts[0]

    assert isinstance(f, ProbabilisticForecast)
    assert isinstance(f.ingredient_id, int)
    assert isinstance(f.name, str)
    assert isinstance(f.avg_daily_consumption, float)
    assert isinstance(f.current_stock, float)
    assert isinstance(f.horizon_days, int)
    assert isinstance(f.expected_horizon_consumption, float)
    assert isinstance(f.p_zero_consumption, float)
    assert isinstance(f.p_any_consumption, float)
    assert isinstance(f.p_stockout_within_horizon, float)
    assert isinstance(f.safety_stock_95pct, float)

    # Probabilities in valid range
    assert 0.0 <= f.p_zero_consumption <= 1.0
    assert 0.0 <= f.p_any_consumption <= 1.0
    assert 0.0 <= f.p_stockout_within_horizon <= 1.0

    # p_zero + p_any = 1.0 (within float precision)
    assert abs((f.p_zero_consumption + f.p_any_consumption) - 1.0) < 1e-10


def test_probabilistic_no_stock_consumption(session_factory):
    """Ingredient with stock=0 should have very high stockout probability."""
    ingredient = Ingredient(name="Empty", unit="kg", stock_qty=0.0)
    session = session_factory()
    session.add(ingredient)
    session.commit()
    ing_id = ingredient.id

    # Lots of consumption → very high stockout probability
    now = datetime.now(timezone.utc)
    for day_offset in range(30):
        session.add(
            StockMovement(
                ingredient_id=ing_id,
                qty=-1.0,
                movement_type="sale",
                reference_type="sale",
                recorded_at=now - timedelta(days=day_offset),
            )
        )
    session.commit()
    session.close()

    session = session_factory()
    forecasts = probabilistic_consumption_forecast(session)
    session.close()

    f = forecasts[0]
    # Stock = 0, λ = 1.0, expected = 7.0
    # P(X > 0 | Poisson(7)) = 1 - exp(-7) ≈ 0.999
    assert f.p_stockout_within_horizon > 0.9
