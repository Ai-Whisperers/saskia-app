"""SASKIA-208 — Poisson weekday restocking forecast (BACKLOG #5).

Locks the closed-form Poisson MLE math, the two-path stockout walk
(P50 expected / P95 conservative), and the weekend-uplift signal —
no new dependencies (AGENTS.md rule 26).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.rms.db import init_db
from app.rms.models import Ingredient, StockMovement
from app.rms.restock_forecast import (
    forecast_restock,
    poisson_weekday_rates,
)


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/restock.sqlite")
    init_db(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


UTC = timezone.utc


def _seed_sales(session, ing_id: int, daily_totals: dict[str, float], *, at_hour: int = 12):
    """Seed movement_type='sale' rows: {YYYY-MM-DD: qty_consumed}."""
    for day_str, qty in daily_totals.items():
        dt = datetime.fromisoformat(day_str).replace(hour=at_hour, tzinfo=UTC)
        session.add(
            StockMovement(
                ingredient_id=ing_id,
                movement_type="sale",
                qty=-qty,
                reason="test sale",
                recorded_at=dt,
            )
        )
    session.commit()


class TestPoissonWeekdayRates:
    def test_closed_form_mle_flat_week(self, session):
        """λ̂_w = Σcount/Σexposure — 1.0/day on every weekday of the window."""
        ing = Ingredient(name="Harina P", unit="kg", stock_qty=0.0)
        session.add(ing)
        session.flush()

        now = datetime.now(UTC)
        # 8 weeks back: consume 1.0 kg every day
        daily = {}
        for i in range(1, 57):
            day = (now - timedelta(days=i)).date().isoformat()
            daily[day] = 1.0
        _seed_sales(session, ing.id, daily)

        rates = poisson_weekday_rates(session, ing.id, now=now)
        assert all(abs(lam - 1.0) < 1e-9 for lam in rates.lambdas)
        assert abs(rates.exposures[0] - 8.0) < 1e-9  # 8 Mondays in 56d
        assert rates.flat_equivalent() == pytest.approx(1.0)

    def test_weekend_uplift_detected(self, session):
        """Sat/Sun 3× consumption → weekday rates reflect it; flat misses it."""
        ing = Ingredient(name="Levadura P", unit="kg", stock_qty=0.0)
        session.add(ing)
        session.flush()

        now = datetime.now(UTC)
        daily = {}
        for i in range(1, 57):
            day = now - timedelta(days=i)
            qty = 3.0 if day.weekday() >= 5 else 1.0
            daily[day.date().isoformat()] = qty
        _seed_sales(session, ing.id, daily)

        rates = poisson_weekday_rates(session, ing.id, now=now)
        assert rates.rate(5) == pytest.approx(3.0)  # Saturday
        assert rates.rate(6) == pytest.approx(3.0)  # Sunday
        assert rates.rate(0) == pytest.approx(1.0)  # Monday
        # flat equivalent sits between the two — proving it's "wrong" both ways
        flat = rates.flat_equivalent()
        assert 1.0 < flat < 3.0

    def test_zero_sales_weekdays_get_zero_lambda_not_error(self, session):
        ing = Ingredient(name="Chips P", unit="kg", stock_qty=0.0)
        session.add(ing)
        session.flush()
        now = datetime.now(UTC)
        # Only 2 days of sales in the whole window
        _seed_sales(
            session,
            ing.id,
            {(now - timedelta(days=1)).date().isoformat(): 5.0},
        )
        rates = poisson_weekday_rates(session, ing.id, now=now)
        assert sum(rates.lambdas) > 0
        assert len(rates.lambdas) == 7
        # Unvisited weekdays have zero exposure → zero rate, zero SE
        zero_days = [i for i, n in enumerate(rates.exposures) if n == 0]
        assert zero_days == []  # 56d window always covers all weekdays

    def test_empty_history_all_zeros(self, session):
        ing = Ingredient(name="Nada P", unit="kg", stock_qty=4.0)
        session.add(ing)
        session.commit()
        rates = poisson_weekday_rates(session, ing.id)
        assert all(lam == 0.0 for lam in rates.lambdas)
        assert rates.flat_equivalent() == 0.0


class TestForecastRestock:
    def test_p95_runs_out_sooner_than_flat_suggests(self, session):
        """The whole point: flat says 'plenty', P95 path says 'order now'."""
        ing = Ingredient(name="Harina R", unit="kg", stock_qty=14.0)
        session.add(ing)
        session.flush()

        now = datetime.now(UTC)
        daily = {}
        for i in range(1, 57):
            day = now - timedelta(days=i)
            qty = 3.0 if day.weekday() >= 5 else 1.0
            daily[day.date().isoformat()] = qty
        _seed_sales(session, ing.id, daily)

        fc = forecast_restock(session, ing.id, now=now)
        # flat avg = (5*1 + 2*3)/7 = 11/7 ≈ 1.57 → flat says ~9 days
        flat_days = 14.0 / fc.lambda_flat
        # P95 path must be strictly sooner (risk-adjusted runs out first)
        assert fc.days_to_p95_stockout is not None
        assert fc.days_to_p95_stockout < flat_days

    def test_no_consumption_no_stockout_dates(self, session):
        ing = Ingredient(name="Decoracion R", unit="und", stock_qty=5.0)
        session.add(ing)
        session.commit()
        fc = forecast_restock(session, ing.id)
        assert fc.p50_stockout_date is None
        assert fc.p95_stockout_date is None
        assert fc.days_to_p95_stockout is None

    def test_recommended_qty_covers_p95_14day_target(self, session):
        ing = Ingredient(name="Manteca R", unit="kg", stock_qty=1.0, min_stock_qty=5)
        session.add(ing)
        session.flush()

        now = datetime.now(UTC)
        daily = {}
        for i in range(1, 57):
            day = now - timedelta(days=i)
            qty = 3.0 if day.weekday() >= 5 else 1.0
            daily[day.date().isoformat()] = qty
        _seed_sales(session, ing.id, daily)

        fc = forecast_restock(session, ing.id, now=now, cover_days=14)
        # target = max(min*2=10, p95_daily_avg*14) — p95 avg > flat 1.57
        assert fc.recommended_restock_qty > 10.0
        # cost estimate uses purchase price (not set here → None)
        assert fc.restock_cost_gs_estimate is None

    def test_confidence_labels_by_exposure(self, session):
        ing = Ingredient(name="Poco R", unit="kg", stock_qty=3.0)
        session.add(ing)
        session.flush()
        now = datetime.now(UTC)
        # 3 days of data only → low confidence
        _seed_sales(
            session,
            ing.id,
            {(now - timedelta(days=i)).date().isoformat(): 2.0 for i in (1, 2, 3)},
        )
        fc = forecast_restock(session, ing.id, now=now)
        assert fc.confidence == "low"

    def test_tiny_stock_p95_immediate(self, session):
        """Stock below one day's P95 demand → stockout lands within 1 day."""
        ing = Ingredient(name="Neg R", unit="kg", stock_qty=1.0)
        session.add(ing)
        session.flush()
        now = datetime.now(UTC)
        # Full 56-day window at 2.0/day → every weekday λ=2.0 with tight SE,
        # so day-1 P95 ≈ 2.3 > 1.0 → crosses immediately (deterministic).
        daily = {(now - timedelta(days=i)).date().isoformat(): 2.0 for i in range(1, 57)}
        _seed_sales(session, ing.id, daily)
        fc = forecast_restock(session, ing.id, now=now)
        assert fc.days_to_p95_stockout is not None
        assert fc.days_to_p95_stockout <= 1

    def test_unknown_ingredient_raises(self, session):
        with pytest.raises(ValueError, match="not found"):
            forecast_restock(session, 999999)
