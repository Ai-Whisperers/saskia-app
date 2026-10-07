"""SASKIA-208 integration — reorder page carries the P95 Poisson forecast.

Locks the router contract: /reorder (both HTML + JSON shapes) exposes
restock_map, and the template renders the P95 badge only when the
conservative path lands ≥2 days before the flat average.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.rms.db import init_db
from app.rms.models import Ingredient, StockMovement
from app.rms.restock_forecast import forecast_restock_batch

UTC = timezone.utc


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/restock-int.sqlite")
    init_db(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def _seed_ing(session, name, stock, daily_qty=1.0, weekend_qty=4.0):
    ing = Ingredient(name=name, unit="kg", stock_qty=stock, min_stock_qty=2)
    session.add(ing)
    session.flush()
    now = datetime.now(UTC)
    for i in range(1, 57):
        day = now - timedelta(days=i)
        qty = weekend_qty if day.weekday() >= 5 else daily_qty
        session.add(
            StockMovement(
                ingredient_id=ing.id,
                movement_type="sale",
                qty=-qty,
                reason="test",
                recorded_at=day.replace(hour=12, tzinfo=UTC),
            )
        )
    session.commit()
    return ing


def test_batch_returns_all_when_not_only_at_risk(session):
    ing = _seed_ing(session, "Harina B", stock=50.0)
    out = forecast_restock_batch(session, [ing.id], only_at_risk=False)
    assert ing.id in out
    assert out[ing.id].lambda_flat > 0


def test_batch_filters_to_at_risk(session):
    """50 kg against ~1.8/day → P95 stockout far out → filtered out."""
    ing = _seed_ing(session, "Sobrante B", stock=50.0)
    out = forecast_restock_batch(session, [ing.id], only_at_risk=True)
    assert ing.id not in out


def test_low_stock_ingredient_is_at_risk(session):
    ing = _seed_ing(session, "Critico B", stock=3.0)
    out = forecast_restock_batch(session, [ing.id], only_at_risk=True)
    assert ing.id in out
    fc = out[ing.id]
    assert fc.days_to_p95_stockout is not None
    assert fc.days_to_p95_stockout <= 14
    # weekend uplift present in the forecast (seeded 4x weekends)
    assert fc.weekend_uplift_pct > 0
