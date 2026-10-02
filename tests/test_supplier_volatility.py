"""Tests for BACKLOG #31: supplier price volatility leaderboard.

The model `IngredientPriceEvent` exists with a `supplier_id` FK and
0 rows in production DB (per audit). BACKLOG #31 wants a leaderboard
that aggregates price swings per supplier so the operator can spot:

- suppliers with rising prices (avg > current → inflation)
- suppliers with high variance (max-min large relative to avg)
- suppliers with stale pricing (last event > 30 days ago)

Output contract: list of dicts, one per supplier that has any
price_event rows in the window, sorted by volatility desc.

volatility_score = (max-min) / avg  — high = erratic pricing
trend_direction = "up" | "down" | "stable" (avg vs first price)
days_since_last_event = days between window-end and last event
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.rms.config import ASUNCION_TZ
from app.rms.price_history import supplier_volatility
from tests.factories import (
    make_ingredient,
    make_price_event,
    make_supplier,
)


def test_supplier_volatility_returns_expected_keys(session_factory):
    """Shape: list of dicts with the contract keys."""
    with session_factory() as s:
        out = supplier_volatility(s, since_days=90)
    assert isinstance(out, list)
    if out:
        first = out[0]
        assert set(first.keys()) >= {
            "supplier_id",
            "supplier_name",
            "ingredient_count",
            "event_count",
            "min_price_gs",
            "max_price_gs",
            "avg_price_gs",
            "volatility_score",
            "trend_direction",
            "days_since_last_event",
            "current_price_gs",
        }


def test_supplier_volatility_empty_db_returns_empty_list(session_factory):
    """No suppliers → no rows."""
    with session_factory() as s:
        out = supplier_volatility(s, since_days=90)
    assert out == []


def test_supplier_volatility_aggregates_per_supplier(session_factory):
    """Two price events on the same ingredient for the same supplier → one row."""
    with session_factory() as s:
        sup = make_supplier(s, name="VOL_SUP_X")
        ing = make_ingredient(s, name="vol_ing_x", unit="kg", supplier_id=sup.id)
        make_price_event(s, ingredient=ing, price_gs=1000)
        make_price_event(s, ingredient=ing, price_gs=1500)
        s.commit()

    with session_factory() as s:
        out = supplier_volatility(s, since_days=90)

    assert len(out) == 1
    row = out[0]
    assert row["supplier_id"] == sup.id
    assert row["ingredient_count"] == 1
    assert row["event_count"] == 2
    assert row["min_price_gs"] == 1000
    assert row["max_price_gs"] == 1500
    assert row["avg_price_gs"] == 1250


def test_supplier_volatility_counts_distinct_ingredients(session_factory):
    """A supplier selling 3 different ingredients is counted once per ingredient."""
    with session_factory() as s:
        sup = make_supplier(s, name="VOL_SUP_MULTI")
        for i in range(3):
            ing = make_ingredient(s, name=f"v_ing_{i}", unit="kg", supplier_id=sup.id)
            make_price_event(s, ingredient=ing, price_gs=1000 + i * 100)
        s.commit()

    with session_factory() as s:
        out = supplier_volatility(s, since_days=90)

    assert len(out) == 1
    assert out[0]["ingredient_count"] == 3
    assert out[0]["event_count"] == 3


def test_supplier_volatility_rising_trend(session_factory):
    """Price increased → trend_direction = 'up'."""
    with session_factory() as s:
        sup = make_supplier(s, name="VOL_RISING")
        ing = make_ingredient(s, name="v_rise", unit="kg", supplier_id=sup.id)
        # First event at ₲1000, then rising to ₲3000
        make_price_event(s, ingredient=ing, price_gs=1000)
        make_price_event(s, ingredient=ing, price_gs=2000)
        make_price_event(s, ingredient=ing, price_gs=3000)
        s.commit()

    with session_factory() as s:
        out = supplier_volatility(s, since_days=90)

    assert len(out) == 1
    assert out[0]["trend_direction"] == "up"
    assert out[0]["volatility_score"] > 0


def test_supplier_volatility_falling_trend(session_factory):
    """Price decreased → trend_direction = 'down'."""
    with session_factory() as s:
        sup = make_supplier(s, name="VOL_FALLING")
        ing = make_ingredient(s, name="v_fall", unit="kg", supplier_id=sup.id)
        make_price_event(s, ingredient=ing, price_gs=3000)
        make_price_event(s, ingredient=ing, price_gs=2000)
        make_price_event(s, ingredient=ing, price_gs=1000)
        s.commit()

    with session_factory() as s:
        out = supplier_volatility(s, since_days=90)

    assert len(out) == 1
    assert out[0]["trend_direction"] == "down"


def test_supplier_volatility_stable_trend(session_factory):
    """Flat price → trend_direction = 'stable'."""
    with session_factory() as s:
        sup = make_supplier(s, name="VOL_STABLE")
        ing = make_ingredient(s, name="v_flat", unit="kg", supplier_id=sup.id)
        make_price_event(s, ingredient=ing, price_gs=1000)
        make_price_event(s, ingredient=ing, price_gs=1000)
        make_price_event(s, ingredient=ing, price_gs=1000)
        s.commit()

    with session_factory() as s:
        out = supplier_volatility(s, since_days=90)

    assert len(out) == 1
    assert out[0]["trend_direction"] == "stable"
    assert out[0]["volatility_score"] == 0.0


def test_supplier_volatility_sorted_descending_by_score(session_factory):
    """Erratic supplier first, stable supplier last."""
    with session_factory() as s:
        # Erratic: price swings 500 ↔ 5000
        sup_a = make_supplier(s, name="VOL_ERRATIC")
        ing_a = make_ingredient(s, name="v_a", unit="kg", supplier_id=sup_a.id)
        make_price_event(s, ingredient=ing_a, price_gs=500)
        make_price_event(s, ingredient=ing_a, price_gs=5000)
        make_price_event(s, ingredient=ing_a, price_gs=500)

        # Stable: flat at 2000
        sup_b = make_supplier(s, name="VOL_STABLE2")
        ing_b = make_ingredient(s, name="v_b", unit="kg", supplier_id=sup_b.id)
        make_price_event(s, ingredient=ing_b, price_gs=2000)
        make_price_event(s, ingredient=ing_b, price_gs=2000)
        s.commit()

    with session_factory() as s:
        out = supplier_volatility(s, since_days=90)

    assert len(out) == 2
    assert out[0]["supplier_name"] == "VOL_ERRATIC"
    assert out[1]["supplier_name"] == "VOL_STABLE2"


def test_supplier_volatility_respects_since_days(session_factory):
    """Old price events (> since_days) are excluded."""
    with session_factory() as s:
        sup = make_supplier(s, name="VOL_OLD")
        ing = make_ingredient(s, name="v_old", unit="kg", supplier_id=sup.id)
        old = datetime.now(ASUNCION_TZ) - timedelta(days=200)
        make_price_event(s, ingredient=ing, price_gs=1000, at=old)
        s.commit()

    with session_factory() as s:
        out_90 = supplier_volatility(s, since_days=90)
        out_365 = supplier_volatility(s, since_days=365)

    assert out_90 == []
    assert len(out_365) == 1


def test_supplier_volatility_excludes_null_supplier(session_factory):
    """Price events with supplier_id IS NULL are not attributed to anyone."""
    with session_factory() as s:
        ing = make_ingredient(s, name="v_nosup", unit="kg")
        # Make price event WITHOUT supplier (some imports skip the supplier)
        make_price_event(s, ingredient=ing, price_gs=1000)
        s.commit()

    with session_factory() as s:
        out = supplier_volatility(s, since_days=90)

    assert out == []


def test_volatility_page_renders(client):
    """/suppliers/volatility renders even with no data."""
    resp = client.get("/suppliers/volatility")
    assert resp.status_code == 200
    body = resp.text
    assert "volatil" in body.lower() or "supplier" in body.lower() or "proveedor" in body.lower()


def test_volatility_page_respects_days_param(client):
    """/suppliers/volatility?days=30 honors the period param."""
    resp = client.get("/suppliers/volatility?days=30")
    assert resp.status_code == 200
    # 30 appears in the page somewhere (either in period selector or summary)
    assert "30" in resp.text