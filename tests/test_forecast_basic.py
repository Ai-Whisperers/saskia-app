"""Tests for app/rms/forecast.py — predictive restocking."""

from datetime import datetime, timedelta, timezone


def test_forecast_zero_consumption_via_apply_sale(qseed):
    """When sales happen through apply_sale, forecast sees real consumption."""
    from app.rms.costing import apply_sale
    from app.rms.forecast import forecast_ingredient_consumption

    data = qseed("basic")
    ing_id = data["ingredient"].id
    prod_id = data["product"].id
    sf = qseed.session_factory

    # Make 10 sales over the last 10 days → 10 units consumed at qty=1 each
    with sf() as s:
        # Use apply_sale directly. Note: q=1, recipe has 0.3 kg per batch
        # so each sale consumes 0.3 kg of flour.
        now = datetime.now(timezone.utc)
        for i in range(10):
            apply_sale(
                s, product_id=prod_id, qty=1.0,
                sold_at=now - timedelta(days=i),
                payment_method="efectivo", channel="Mostrador",
                notes=None, customer_id=None, discount_gs=0,
            )
        s.commit()

    with sf() as s:
        f = forecast_ingredient_consumption(s, ing_id, days_back=30)
    # At least 1.0 days of avg_daily_consumption = positive number
    # Exact value: 10 sales × 0.3 kg = 3 kg consumed
    assert f.avg_daily_consumption > 0
    assert f.recommended_restock_qty >= 0
    # 30d default → 3kg / 30 = 0.1 kg/day
    # current stock started at 10, minus 3kg = 7kg
    # 7 / 0.1 = 70 days
    assert f.days_of_stock > 0
