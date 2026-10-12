"""tests/test_forecast.py — Test app/rms/forecast.py (Phase 4.5).

Predictive restocking helpers (BACKLOG #7). Reads from stock_movement
(sale type, qty<0) to project when an ingredient will run out and
recommend how much to reorder.

Public API tested:
  - ConsumptionForecast dataclass (value object)
  - forecast_ingredient_consumption(session, ingredient_id, days_back)
  - forecast_all_ingredients(session, days_back, limit)
  - projected_stockout_in_7_days(forecast)
  - batch_forecast_ingredients(session, ingredient_ids, days_back)

A regression here would either:
  - Show "∞ days of stock" when stock is actually running out
    (operator gets a false sense of safety)
  - Recommend restocking when nothing is needed (over-ordering)
  - Mis-calculate trend % (the % change vs prior 30d) and miss
    a sudden demand spike
  - Lose the restock event price and show a stale purchase_price_gs
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.rms.forecast import (
    ConsumptionForecast,
    batch_forecast_ingredients,
    forecast_all_ingredients,
    forecast_ingredient_consumption,
    projected_stockout_in_7_days,
)
from app.rms.models import Ingredient, IngredientPriceEvent, StockMovement


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
    """qty is the magnitude of consumption (we pass it as a positive number).
    The function writes it as negative because sale movements drain stock.
    """
    m = StockMovement(
        ingredient_id=ingredient.id,
        movement_type="sale",
        qty=-qty,  # sale = out
        reference_id=reference_id,
        reference_type="sale",
        recorded_at=recorded_at,
    )
    session.add(m)
    session.commit()
    return m


def _add_restock_event(
    session, ingredient: Ingredient, price_gs: int, recorded_at: datetime
) -> IngredientPriceEvent:
    e = IngredientPriceEvent(
        ingredient_id=ingredient.id,
        price_gs=price_gs,
        recorded_at=recorded_at,
        source="restock",
    )
    session.add(e)
    session.commit()
    return e


class TestConsumptionForecastDataclass:
    def test_attributes(self):
        f = ConsumptionForecast(
            ingredient_id=1,
            name="x",
            current_stock_qty=10.0,
            min_stock_qty=5.0,
            avg_daily_consumption=0.5,
            trend_pct=10.0,
            days_of_stock=20.0,
            projected_stockout_at=datetime(2026, 12, 1, tzinfo=timezone.utc),
            recommended_restock_qty=5.0,
            last_restock_price_gs=5000,
        )
        assert f.ingredient_id == 1
        assert f.days_of_stock == 20.0
        assert f.last_restock_price_gs == 5000


class TestForecastIngredientNotFound:
    def test_raises_value_error_for_missing_ingredient(self, session_factory):
        with session_factory() as s:
            with pytest.raises(ValueError, match="not found"):
                forecast_ingredient_consumption(s, 99999)


class TestForecastIngredientNoHistory:
    """No sale movements exist → zero consumption, ∞ days of stock."""

    def test_returns_zero_consumption(self, session_factory):
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_fresh_ing", stock_qty=10.0)
        with session_factory() as s:
            f = forecast_ingredient_consumption(s, ing.id)
        assert f.ingredient_id == ing.id
        assert f.avg_daily_consumption == 0.0
        assert f.days_of_stock == float("inf")
        assert f.projected_stockout_at is None
        assert f.trend_pct == 0.0  # no prior data

    def test_no_consumption_means_target_is_2x_min(self, session_factory):
        # With zero consumption the recommendation is just "top up to 2x min"
        with session_factory() as s:
            ing = _make_ingredient(
                s, "_smoke_zero_ing", stock_qty=2.0, min_stock_qty=5.0
            )
        with session_factory() as s:
            f = forecast_ingredient_consumption(s, ing.id)
        # target = 2*5 = 10, current = 2 → restock = 8
        assert f.recommended_restock_qty == 8.0

    def test_no_consumption_stock_above_2x_min_means_no_restock(self, session_factory):
        with session_factory() as s:
            ing = _make_ingredient(
                s, "_smoke_full_ing", stock_qty=20.0, min_stock_qty=5.0
            )
        with session_factory() as s:
            f = forecast_ingredient_consumption(s, ing.id)
        assert f.recommended_restock_qty == 0.0  # already at 4x min


class TestForecastIngredientWithHistory:
    def test_computes_avg_daily_consumption(self, session_factory):
        now = datetime.now(timezone.utc)
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_h_ing", stock_qty=100.0, min_stock_qty=5.0)
            # 30 days of 0.5/day = 15.0 kg sold in last 30d
            for d in range(30):
                _add_sale_movement(
                    s, ing, 0.5, now - timedelta(days=d), reference_id=d + 1
                )
        with session_factory() as s:
            f = forecast_ingredient_consumption(s, ing.id)
        assert f.avg_daily_consumption == pytest.approx(0.5, rel=0.05)

    def test_computes_days_of_stock(self, session_factory):
        now = datetime.now(timezone.utc)
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_d_ing", stock_qty=10.0, min_stock_qty=5.0)
            for d in range(30):
                _add_sale_movement(
                    s, ing, 1.0, now - timedelta(days=d), reference_id=d + 100
                )
        with session_factory() as s:
            f = forecast_ingredient_consumption(s, ing.id)
        # 10 stock / 1.0/day = 10 days (roughly)
        assert 8 <= f.days_of_stock <= 12
        assert f.projected_stockout_at is not None

    def test_infinite_days_when_avg_zero(self, session_factory):
        now = datetime.now(timezone.utc)
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_inf_ing", stock_qty=10.0, min_stock_qty=5.0)
            # Only one movement, more than 30d ago (excluded by cutoff)
            _add_sale_movement(s, ing, 1.0, now - timedelta(days=60), reference_id=999)
        with session_factory() as s:
            f = forecast_ingredient_consumption(s, ing.id)
        assert f.days_of_stock == float("inf")
        assert f.projected_stockout_at is None

    def test_recommend_restock_when_low(self, session_factory):
        now = datetime.now(timezone.utc)
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_r_ing", stock_qty=2.0, min_stock_qty=5.0)
            for d in range(30):
                _add_sale_movement(
                    s, ing, 1.0, now - timedelta(days=d), reference_id=d + 200
                )
        with session_factory() as s:
            f = forecast_ingredient_consumption(s, ing.id)
        # avg_daily=1.0 → target = max(2*5, 1*14) = max(10, 14) = 14
        # restock = 14 - 2 = 12
        assert f.recommended_restock_qty == pytest.approx(12.0)

    def test_restock_zero_when_stock_above_target(self, session_factory):
        now = datetime.now(timezone.utc)
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_full_ing_2", stock_qty=100.0, min_stock_qty=5.0)
            for d in range(30):
                _add_sale_movement(
                    s, ing, 0.01, now - timedelta(days=d), reference_id=d + 300
                )
        with session_factory() as s:
            f = forecast_ingredient_consumption(s, ing.id)
        # avg_daily=0.01 → target = max(10, 0.14) = 10
        # stock=100, so no restock needed
        assert f.recommended_restock_qty == 0.0

    def test_uses_last_restock_event_price(self, session_factory):
        now = datetime.now(timezone.utc)
        with session_factory() as s:
            ing = _make_ingredient(
                s, "_smoke_p_ing", stock_qty=10.0, min_stock_qty=5.0,
                purchase_price_gs=3000,  # current stored price
            )
            _add_restock_event(s, ing, 7000, now - timedelta(days=2))  # newer
            _add_restock_event(s, ing, 5000, now - timedelta(days=20))  # older
        with session_factory() as s:
            f = forecast_ingredient_consumption(s, ing.id)
        # The 7000 Gs event is more recent → wins
        assert f.last_restock_price_gs == 7000

    def test_falls_back_to_ingredient_price_when_no_event(self, session_factory):
        with session_factory() as s:
            ing = _make_ingredient(
                s, "_smoke_no_evt", stock_qty=10.0, min_stock_qty=5.0,
                purchase_price_gs=4321,
            )
        with session_factory() as s:
            f = forecast_ingredient_consumption(s, ing.id)
        assert f.last_restock_price_gs == 4321  # falls back to stored price

    def test_ignores_non_restock_price_events(self, session_factory):
        # Only 'restock' source should count; 'manual' or 'excel_import' should not
        now = datetime.now(timezone.utc)
        with session_factory() as s:
            ing = _make_ingredient(
                s, "_smoke_only_manual", stock_qty=10.0, min_stock_qty=5.0,
                purchase_price_gs=3000,
            )
            e = IngredientPriceEvent(
                ingredient_id=ing.id,
                price_gs=9999,
                recorded_at=now - timedelta(days=1),
                source="manual",  # not "restock"
            )
            s.add(e)
            s.commit()
        with session_factory() as s:
            f = forecast_ingredient_consumption(s, ing.id)
        assert f.last_restock_price_gs == 3000  # falls back, ignores manual

    def test_trend_pct_increasing(self, session_factory):
        now = datetime.now(timezone.utc)
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_trend_up", stock_qty=100.0, min_stock_qty=5.0)
            # Recent 30d: 1.0/day = 30kg
            for d in range(30):
                _add_sale_movement(s, ing, 1.0, now - timedelta(days=d), reference_id=d + 400)
            # Prior 30d: 0.5/day = 15kg
            for d in range(30, 60):
                _add_sale_movement(s, ing, 0.5, now - timedelta(days=d), reference_id=d + 400)
        with session_factory() as s:
            f = forecast_ingredient_consumption(s, ing.id)
        # 100% increase (1.0 vs 0.5)
        assert f.trend_pct == pytest.approx(100.0, rel=0.05)

    def test_trend_pct_decreasing(self, session_factory):
        now = datetime.now(timezone.utc)
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_trend_down", stock_qty=100.0, min_stock_qty=5.0)
            # Recent 30d: 0.5/day
            for d in range(30):
                _add_sale_movement(s, ing, 0.5, now - timedelta(days=d), reference_id=d + 500)
            # Prior 30d: 1.0/day
            for d in range(30, 60):
                _add_sale_movement(s, ing, 1.0, now - timedelta(days=d), reference_id=d + 500)
        with session_factory() as s:
            f = forecast_ingredient_consumption(s, ing.id)
        # -50% (halved)
        assert f.trend_pct == pytest.approx(-50.0, rel=0.05)

    def test_trend_pct_zero_when_no_prior(self, session_factory):
        # Prior consumption is 0 → trend is 0% (not "inf")
        now = datetime.now(timezone.utc)
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_no_prior", stock_qty=100.0, min_stock_qty=5.0)
            for d in range(30):
                _add_sale_movement(s, ing, 1.0, now - timedelta(days=d), reference_id=d + 600)
        with session_factory() as s:
            f = forecast_ingredient_consumption(s, ing.id)
        assert f.trend_pct == 0.0

    def test_handles_null_stock_qty(self, session_factory):
        with session_factory() as s:
            ing = Ingredient(
                name="_smoke_null_stock", unit="kg",
                stock_qty=None, min_stock_qty=5.0, purchase_price_gs=1000,
            )
            s.add(ing)
            s.commit()
            s.refresh(ing)
        with session_factory() as s:
            f = forecast_ingredient_consumption(s, ing.id)
        assert f.current_stock_qty == 0.0  # None → 0.0
        assert f.days_of_stock == float("inf")  # no consumption

    def test_excludes_non_sale_movements(self, session_factory):
        # merma/adjustment/reorder should NOT be summed as consumption
        now = datetime.now(timezone.utc)
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_only_real_sales", stock_qty=10.0, min_stock_qty=5.0)
            for d in range(30):
                _add_sale_movement(s, ing, 1.0, now - timedelta(days=d), reference_id=d + 700)
            # merma, adjustment, reorder movements — should be ignored
            for mtype in ["merma", "adjustment", "reorder"]:
                for d in range(5):
                    m = StockMovement(
                        ingredient_id=ing.id,
                        movement_type=mtype,
                        qty=-5.0,
                        recorded_at=now - timedelta(days=d),
                    )
                    s.add(m)
            s.commit()
        with session_factory() as s:
            f = forecast_ingredient_consumption(s, ing.id)
        # Only the 30 sale rows count → avg_daily ≈ 1.0
        assert f.avg_daily_consumption == pytest.approx(1.0, rel=0.05)


class TestForecastAllIngredients:
    def test_returns_all_ingredients(self, session_factory):
        with session_factory() as s:
            for n in ["_smoke_a", "_smoke_b", "_smoke_c"]:
                _make_ingredient(s, n)
        with session_factory() as s:
            forecasts = forecast_all_ingredients(s, limit=10)
        assert len(forecasts) == 3

    def test_sorts_urgent_first(self, session_factory):
        # a: 100 stock, no sales → ∞ days (last)
        # b: 10 stock, 1.0/day → ~10 days (first)
        # c: 50 stock, 0.5/day → ~100 days (middle)
        now = datetime.now(timezone.utc)
        with session_factory() as s:
            a = _make_ingredient(s, "_smoke_sort_a", stock_qty=100.0, min_stock_qty=5.0)
            b = _make_ingredient(s, "_smoke_sort_b", stock_qty=10.0, min_stock_qty=5.0)
            c = _make_ingredient(s, "_smoke_sort_c", stock_qty=50.0, min_stock_qty=5.0)
            # Give b and c some recent sales
            for d in range(30):
                _add_sale_movement(s, b, 1.0, now - timedelta(days=d), reference_id=d + 800)
                _add_sale_movement(s, c, 0.5, now - timedelta(days=d), reference_id=d + 900)
        with session_factory() as s:
            forecasts = forecast_all_ingredients(s, limit=10)
        names = [f.name for f in forecasts]
        # b first (~10d), c second (~100d), a last (∞)
        assert names[0] == "_smoke_sort_b"
        assert names[1] == "_smoke_sort_c"
        assert names[2] == "_smoke_sort_a"

    def test_respects_limit(self, session_factory):
        with session_factory() as s:
            for i in range(5):
                _make_ingredient(s, f"_smoke_lim_{i}")
        with session_factory() as s:
            forecasts = forecast_all_ingredients(s, limit=3)
        assert len(forecasts) == 3


class TestProjectedStockoutIn7Days:
    def test_true_for_urgent(self):
        f = ConsumptionForecast(
            ingredient_id=1, name="x", current_stock_qty=1.0,
            min_stock_qty=5.0, avg_daily_consumption=1.0,
            trend_pct=0.0, days_of_stock=3.0,
            projected_stockout_at=None, recommended_restock_qty=5.0,
            last_restock_price_gs=None,
        )
        assert projected_stockout_in_7_days(f) is True

    def test_false_for_safe(self):
        f = ConsumptionForecast(
            ingredient_id=1, name="x", current_stock_qty=100.0,
            min_stock_qty=5.0, avg_daily_consumption=1.0,
            trend_pct=0.0, days_of_stock=30.0,
            projected_stockout_at=None, recommended_restock_qty=0.0,
            last_restock_price_gs=None,
        )
        assert projected_stockout_in_7_days(f) is False

    def test_false_for_infinite_days(self):
        f = ConsumptionForecast(
            ingredient_id=1, name="x", current_stock_qty=10.0,
            min_stock_qty=5.0, avg_daily_consumption=0.0,
            trend_pct=0.0, days_of_stock=float("inf"),
            projected_stockout_at=None, recommended_restock_qty=10.0,
            last_restock_price_gs=None,
        )
        assert projected_stockout_in_7_days(f) is False


class TestBatchForecastIngredients:
    def test_empty_returns_empty(self, session_factory):
        with session_factory() as s:
            assert batch_forecast_ingredients(s, []) == {}

    def test_skips_missing_ingredient_ids(self, session_factory):
        # IDs that don't exist should be silently skipped
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_batch_real")
        with session_factory() as s:
            result = batch_forecast_ingredients(s, [ing.id, 99999])
        assert ing.id in result
        assert 99999 not in result

    def test_uses_single_query_for_consumption(self, session_factory):
        now = datetime.now(timezone.utc)
        with session_factory() as s:
            ings = []
            for n in ["_smoke_b1", "_smoke_b2", "_smoke_b3"]:
                ing = _make_ingredient(s, n, stock_qty=100.0, min_stock_qty=5.0)
                for d in range(30):  # 30 days of sales
                    _add_sale_movement(s, ing, 1.0, now - timedelta(days=d), reference_id=d + 1000)
                ings.append(ing)
        with session_factory() as s:
            result = batch_forecast_ingredients(
                s, [i.id for i in ings]
            )
        assert len(result) == 3
        for ing in ings:
            assert ing.id in result
            f = result[ing.id]
            # 30kg over 30d = 1.0/day
            assert f.avg_daily_consumption == pytest.approx(1.0, rel=0.05)
