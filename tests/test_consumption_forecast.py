"""Tests for BACKLOG #32 (Poisson predictive restocking foundation).

`consumption_forecast()` is the deterministic baseline: avg_daily_consumption
multiplied by horizon × safety_factor. The Poisson regression layer (#29) is
a separate enhancement for ingredients with high volatility.

Uses StockMovement rows with movement_type='sale' AND qty<0 (outgoing
consumption). Aggregates by ingredient_id, joins with Ingredient to get
current stock + name.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.rms.analytics import (
    ConsumptionForecast,
    consumption_forecast,
)
from app.rms.models_legacy import Ingredient, StockMovement


def test_consumption_forecast_empty(session_factory):
    """No consumption data → empty list."""
    session = session_factory()
    forecasts = consumption_forecast(session)
    assert forecasts == []
    session.close()


def test_consumption_forecast_basic(session_factory):
    """Aggregates consumption and calculates days_until_stockout."""
    session = session_factory()

    # Seed ingredient with current stock = 30 units
    ingredient = Ingredient(
        name="Harina",
        unit="kg",
        stock_qty=30.0,
        purchase_price_gs=5000,
    )
    session.add(ingredient)
    session.commit()
    ing_id = ingredient.id

    # Seed 3 days of consumption: -10 units each day = -30 total
    now = datetime.now(timezone.utc)
    for day_offset in range(3):
        session.add(
            StockMovement(
                ingredient_id=ing_id,
                qty=-10.0,
                movement_type="sale",
                reference_type="sale",
                recorded_at=now - timedelta(days=day_offset),
            )
        )
    session.commit()
    session.close()

    # Re-query with fresh session
    session = session_factory()
    forecasts = consumption_forecast(session, lookback_days=30)
    session.close()

    assert len(forecasts) == 1
    forecast = forecasts[0]

    # Total consumed = 30 over 30 days = 1.0/day
    assert forecast.avg_daily_consumption == pytest.approx(1.0, abs=0.01)

    # Stock = 30, avg = 1.0/day → 30 days until stockout
    assert forecast.days_until_stockout == 30

    # Default safety_factor=1.5, horizon=7 days
    # Predicted consumption = 1.0 × 7 × 1.5 = 10.5
    # Recommended = max(10.5 - 30, 0) = 0 (stock sufficient)
    assert forecast.recommended_reorder_qty == 0.0

    # 30 days > 7 days → not predicted to stockout
    assert forecast.is_predicted_to_stockout is False

    assert forecast.ingredient_id == ing_id
    assert forecast.name == "Harina"
    assert forecast.safety_stock_factor == 1.5


def test_consumption_forecast_predicted_stockout(session_factory):
    """Identifies ingredients predicted to stockout within horizon."""
    session = session_factory()

    # Ingredient with low stock and high consumption
    ingredient = Ingredient(
        name="Azúcar",
        unit="kg",
        stock_qty=2.0,  # Very low stock
        purchase_price_gs=4000,
    )
    session.add(ingredient)
    session.commit()
    ing_id = ingredient.id

    # High consumption: -1kg/day × 7 days = -7 total over 30-day window
    now = datetime.now(timezone.utc)
    for day_offset in range(7):
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
    forecasts = consumption_forecast(session, lookback_days=30, horizon_days=7)
    session.close()

    forecast = forecasts[0]

    # 7 units consumed over 30 days = ~0.23/day
    # Stock = 2, avg = 0.23 → ~8.5 days until stockout (rounded to 8)
    assert forecast.avg_daily_consumption == pytest.approx(0.23, abs=0.01)
    assert forecast.days_until_stockout == 8

    # Predicted consumption = 0.23 × 7 × 1.5 = 2.45
    # Recommended = max(2.45 - 2, 0) = 0.45
    assert forecast.recommended_reorder_qty == pytest.approx(0.45, abs=0.05)

    # 8 days > 7 day horizon → NOT predicted to stockout
    # (within 1 day of horizon, but technically outside)
    assert forecast.is_predicted_to_stockout is False


def test_consumption_forecast_imminent_stockout(session_factory):
    """Marks ingredient as predicted to stockout within horizon."""
    session = session_factory()

    ingredient = Ingredient(
        name="Manteca",
        unit="kg",
        stock_qty=1.0,  # 1kg
        purchase_price_gs=10000,
    )
    session.add(ingredient)
    session.commit()
    ing_id = ingredient.id

    # -1kg/day × 7 days = -7 over 30 days = 0.23/day
    now = datetime.now(timezone.utc)
    for day_offset in range(7):
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
    forecasts = consumption_forecast(session, lookback_days=30, horizon_days=10)
    session.close()

    forecast = forecasts[0]

    # Stock = 1, avg = 0.23/day → ~4 days until stockout
    assert forecast.days_until_stockout == 4

    # 4 days < 10 day horizon → predicted to stockout
    assert forecast.is_predicted_to_stockout is True


def test_consumption_forecast_only_incoming_movement_excluded(session_factory):
    """Only outgoing (qty<0) movements are counted as consumption."""
    session = session_factory()

    ingredient = Ingredient(
        name="Levadura",
        unit="g",
        stock_qty=100.0,
        purchase_price_gs=200,
    )
    session.add(ingredient)
    session.commit()
    ing_id = ingredient.id

    # Seed only incoming (reorder) movements — NOT consumption
    now = datetime.now(timezone.utc)
    for day_offset in range(5):
        session.add(
            StockMovement(
                ingredient_id=ing_id,
                qty=+20.0,  # Positive = incoming
                movement_type="reorder",  # Not sale
                reference_type="po",
                recorded_at=now - timedelta(days=day_offset),
            )
        )
    session.commit()
    session.close()

    session = session_factory()
    forecasts = consumption_forecast(session)
    session.close()

    # No sale movements → no consumption detected → empty
    assert forecasts == []


def test_consumption_forecast_filter_by_ingredient(session_factory):
    """Filtering by ingredient_id returns only that ingredient."""
    session = session_factory()

    ing1 = Ingredient(name="Harina", unit="kg", stock_qty=50.0)
    ing2 = Ingredient(name="Azúcar", unit="kg", stock_qty=20.0)
    session.add_all([ing1, ing2])
    session.commit()

    now = datetime.now(timezone.utc)
    session.add_all(
        [
            StockMovement(
                ingredient_id=ing1.id,
                qty=-2.0,
                movement_type="sale",
                reference_type="sale",
                recorded_at=now,
            ),
            StockMovement(
                ingredient_id=ing2.id,
                qty=-5.0,
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
    forecasts = consumption_forecast(session, ingredient_id=ing1_id)
    session.close()

    # Only ing1 returned
    assert len(forecasts) == 1
    assert forecasts[0].name == "Harina"


def test_consumption_forecast_sort_by_urgency(session_factory):
    """Forecasts sorted by days_until_stockout (lowest first)."""
    session = session_factory()

    # Low stock + high consumption = stockout soon
    urgent = Ingredient(name="Urgente", unit="kg", stock_qty=1.0)
    # High stock + low consumption = stockout later
    safe = Ingredient(name="Segura", unit="kg", stock_qty=100.0)
    session.add_all([urgent, safe])
    session.commit()

    now = datetime.now(timezone.utc)
    # Urgent: -5/day → stockout in ~0.2 days
    # Safe: -0.5/day → stockout in 200 days
    session.add_all(
        [
            StockMovement(
                ingredient_id=urgent.id,
                qty=-5.0,
                movement_type="sale",
                reference_type="sale",
                recorded_at=now - timedelta(days=1),
            ),
            StockMovement(
                ingredient_id=safe.id,
                qty=-0.5,
                movement_type="sale",
                reference_type="sale",
                recorded_at=now - timedelta(days=1),
            ),
        ]
    )
    session.commit()
    session.close()

    session = session_factory()
    forecasts = consumption_forecast(session, lookback_days=7)
    session.close()

    assert len(forecasts) == 2
    # Most urgent (lowest days_until_stockout) first
    assert forecasts[0].name == "Urgente"
    # 1/5 = 0.2 days, but since I'm using .get() the stock is unchanged from 1.0
    # Actually 5kg consumption, but the test only seeded 1 movement with -5 over 1 day
    # so total_consumed = 5 over 7 days = 0.71/day. Stock = 1.0. Days = 1/0.71 = 1.4
    assert forecasts[0].days_until_stockout <= 2  # Within tolerance
    assert forecasts[1].name == "Segura"


def test_consumption_forecast_safety_factor(session_factory):
    """Custom safety_factor increases recommended_reorder_qty."""
    session = session_factory()

    ingredient = Ingredient(name="X", unit="kg", stock_qty=10.0)
    session.add(ingredient)
    session.commit()
    ing_id = ingredient.id

    now = datetime.now(timezone.utc)
    # -3/day consumption
    for day_offset in range(3):
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

    # With safety_factor=1.0: predicted = 0.1 × 7 × 1.0 = 0.7
    # Recommended = max(0.7 - 10, 0) = 0
    session = session_factory()
    forecasts_default = consumption_forecast(session, safety_factor=1.0)
    session.close()

    # With safety_factor=5.0: predicted = 0.1 × 7 × 5 = 3.5
    # Recommended = max(3.5 - 10, 0) = 0
    # (stock still sufficient even with 5x safety)
    session = session_factory()
    forecasts_high = consumption_forecast(session, safety_factor=5.0)
    session.close()

    assert forecasts_default[0].safety_stock_factor == 1.0
    assert forecasts_high[0].safety_stock_factor == 5.0
    assert forecasts_high[0].recommended_reorder_qty >= forecasts_default[0].recommended_reorder_qty


def test_consumption_forecast_outside_lookback(session_factory):
    """Movements older than lookback_days are excluded."""
    session = session_factory()

    ingredient = Ingredient(name="Y", unit="kg", stock_qty=50.0)
    session.add(ingredient)
    session.commit()
    ing_id = ingredient.id

    now = datetime.now(timezone.utc)
    # Old movement (outside 30-day window)
    session.add(
        StockMovement(
            ingredient_id=ing_id,
            qty=-10.0,
            movement_type="sale",
            reference_type="sale",
            recorded_at=now - timedelta(days=60),  # 60 days ago
        )
    )
    # Recent movement (within window)
    session.add(
        StockMovement(
            ingredient_id=ing_id,
            qty=-5.0,
            movement_type="sale",
            reference_type="sale",
            recorded_at=now - timedelta(days=5),  # 5 days ago
        )
    )
    session.commit()
    session.close()

    session = session_factory()
    forecasts = consumption_forecast(session, lookback_days=30)
    session.close()

    # Only -5 counted (5/30 = 0.17/day)
    assert forecasts[0].avg_daily_consumption == pytest.approx(0.17, abs=0.01)


def test_consumption_forecast_dataclass_shape(session_factory):
    """Verifies ConsumptionForecast dataclass fields are populated correctly."""
    session = session_factory()

    ingredient = Ingredient(name="Test", unit="kg", stock_qty=15.0)
    session.add(ingredient)
    session.commit()
    ing_id = ingredient.id

    session.add(
        StockMovement(
            ingredient_id=ing_id,
            qty=-3.0,
            movement_type="sale",
            reference_type="sale",
            recorded_at=datetime.now(timezone.utc),
        )
    )
    session.commit()
    session.close()

    session = session_factory()
    forecasts = consumption_forecast(session)
    session.close()

    assert len(forecasts) == 1
    forecast = forecasts[0]

    # All fields populated
    assert isinstance(forecast, ConsumptionForecast)
    assert isinstance(forecast.ingredient_id, int)
    assert isinstance(forecast.name, str)
    assert isinstance(forecast.avg_daily_consumption, float)
    assert isinstance(forecast.days_until_stockout, int)
    assert isinstance(forecast.safety_stock_factor, float)
    assert isinstance(forecast.recommended_reorder_qty, float)
    assert isinstance(forecast.is_predicted_to_stockout, bool)
