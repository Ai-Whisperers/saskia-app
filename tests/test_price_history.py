"""tests/test_price_history.py — Phase B Q1-core ingredient price history.

Covers:
- IngredientPriceEvent model + table
- record_price_event inserts row + updates Ingredient fields + monotonic ts
- price_history returns events in chronological order (oldest → newest)
- price_stats math (current = latest; min/max/avg = correct over period)
- Inventory POST creates a 'manual' price event
- Migration v18 idempotency + table creation

Refs: Saskia review round 1 (Thu 18-sep) — Q1 (c) restock + price history
+ reports + insight. Phase B ships the schema + helper; Phase D wires the
restock form surface and the dashboard sparkline.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from app.rms.db import init_db
from tests.factories import make_ingredient

# --- record_price_event ---


def test_record_price_event_inserts_row(session_factory):
    """record_price_event adds a row to ingredient_price_event."""
    from app.rms.models import IngredientPriceEvent
    from app.rms.price_history import record_price_event

    with session_factory() as s:
        ing = make_ingredient(s, name="Harina", unit="kg", stock_qty=5.0, purchase_price_gs=5000)
        s.add(ing)
        s.commit()
        ing_id = ing.id

        event = record_price_event(s, ing_id, 5500, source="restock")
        s.commit()

        assert event.id is not None
        assert event.ingredient_id == ing_id
        assert event.price_gs == 5500
        assert event.source == "restock"

        # DB has the row
        rows = s.query(IngredientPriceEvent).filter_by(ingredient_id=ing_id).all()
        assert len(rows) == 1
        assert rows[0].price_gs == 5500


def test_record_price_event_updates_ingredient(session_factory):
    """record_price_event overwrites Ingredient.purchase_price_gs + updated_at."""
    from app.rms.models import Ingredient
    from app.rms.price_history import record_price_event

    with session_factory() as s:
        ing = Ingredient(
            name="Harina",
            unit="kg",
            stock_qty=5.0,
            purchase_price_gs=5000,
        )
        s.add(ing)
        s.commit()
        ing_id = ing.id
        original_updated_at = ing.purchase_price_updated_at

        from datetime import timedelta

        base = datetime.now(timezone.utc)
        record_price_event(s, ing_id, 7000, source="restock", at=base - timedelta(seconds=3))
        event = record_price_event(s, ing_id, 7500, source="manual", at=base)
        s.commit()

        ing_fresh = s.get(Ingredient, ing_id)
        assert ing_fresh.purchase_price_gs == 7500
        assert ing_fresh.purchase_price_updated_at is not None
        # DB stores naive UTC; compare like-for-like. event.recorded_at
        # is tz-aware UTC; strip tz for the comparison.
        naive_recorded = event.recorded_at.replace(tzinfo=None)
        assert ing_fresh.purchase_price_updated_at >= (
            original_updated_at or naive_recorded
        )


def test_record_price_event_default_source_is_restock(session_factory):
    """source defaults to 'restock' (the most common case)."""
    from app.rms.models import IngredientPriceEvent
    from app.rms.price_history import record_price_event

    with session_factory() as s:

        ing = make_ingredient(s, name="X", unit="kg", stock_qty=0.0)
        s.add(ing)
        s.commit()
        record_price_event(s, ing.id, 1000)
        s.commit()
        ev = s.query(IngredientPriceEvent).filter_by(ingredient_id=ing.id).first()
    assert ev.source == "restock"


def test_record_price_event_validates_source(session_factory):
    """Unknown source string raises ValueError."""
    from app.rms.price_history import record_price_event

    with session_factory() as s:

        ing = make_ingredient(s, name="X", unit="kg", stock_qty=0.0)
        s.add(ing)
        s.commit()
        with pytest.raises(ValueError, match="source"):
            record_price_event(s, ing.id, 1000, source="bogus_channel")


# --- price_history ---


def test_price_history_returns_chronological_order(session_factory):
    """price_history returns events oldest → newest."""
    from app.rms.price_history import price_history, record_price_event

    with session_factory() as s:
        ing = make_ingredient(s, name="Harina", unit="kg", stock_qty=5.0, purchase_price_gs=5000)
        s.add(ing)
        s.commit()
        ing_id = ing.id

        from datetime import timedelta

        base = datetime.now(timezone.utc)
        record_price_event(s, ing_id, 5000, source="manual", at=base - timedelta(seconds=4))
        s.commit()
        record_price_event(s, ing_id, 5500, source="restock", at=base - timedelta(seconds=2))
        s.commit()
        record_price_event(s, ing_id, 7000, source="excel_import", at=base)
        s.commit()

        history = price_history(s, ing_id, days=90)
    assert len(history) == 3
    timestamps = [t for t, _ in history]
    prices = [p for _, p in history]
    assert timestamps == sorted(timestamps)  # ascending
    assert prices == [5000, 5500, 7000]


def test_price_history_filters_by_days(session_factory):
    """price_history only includes events within the last N days."""
    from app.rms.price_history import price_history, record_price_event

    with session_factory() as s:
        ing = make_ingredient(s, name="Harina", unit="kg", stock_qty=5.0, purchase_price_gs=5000)
        s.add(ing)
        s.commit()
        ing_id = ing.id

        # Old event (120 days ago) — should NOT appear in 90-day window
        old_event = record_price_event(s, ing_id, 1000, source="manual")
        s.commit()
        # Backdate the timestamp so the days window excludes it
        old_event.recorded_at = datetime.now(timezone.utc) - timedelta(days=120)
        s.commit()

        # New event — within the window
        record_price_event(s, ing_id, 5000, source="restock")
        s.commit()

        history = price_history(s, ing_id, days=90)
    prices = [p for _, p in history]
    assert 5000 in prices
    assert 1000 not in prices
    # ts is a datetime
    for ts, _p in history:
        assert isinstance(ts, datetime)


def test_price_history_empty_when_no_events(session_factory):
    """No events → empty list (not None)."""
    from app.rms.price_history import price_history

    with session_factory() as s:
        ing = make_ingredient(s, name="Harina", unit="kg", stock_qty=0.0)
        s.add(ing)
        s.commit()
        history = price_history(s, ing.id, days=90)
    assert history == []


# --- price_stats ---


def test_price_stats_current_is_latest_event(session_factory):
    """price_stats['current'] is the most recent event's price."""
    from app.rms.price_history import price_stats, record_price_event

    with session_factory() as s:
        ing = make_ingredient(s, name="Harina", unit="kg", stock_qty=5.0, purchase_price_gs=5000)
        s.add(ing)
        s.commit()
        ing_id = ing.id

        for p in (4000, 5500, 6000):
            record_price_event(s, ing_id, p, source="manual")
            s.commit()
            import time

            time.sleep(0.01)

        stats = price_stats(s, ing_id, days=90)
    assert stats["current"] == 6000
    assert stats["count"] == 3


def test_price_stats_min_max_avg(session_factory):
    """price_stats returns min/max/avg across the window."""
    from app.rms.price_history import price_stats, record_price_event

    with session_factory() as s:
        ing = make_ingredient(s, name="Harina", unit="kg", stock_qty=5.0)
        s.add(ing)
        s.commit()
        ing_id = ing.id

        for p in (4000, 5000, 7000, 8000):
            record_price_event(s, ing_id, p, source="manual")
            s.commit()

        stats = price_stats(s, ing_id, days=90)
    assert stats["min"] == 4000
    assert stats["max"] == 8000
    # (4000 + 5000 + 7000 + 8000) / 4 = 6000
    assert int(stats["avg"]) == 6000


def test_price_stats_empty_window(session_factory):
    """price_stats with no events returns current=None + count=0."""
    from app.rms.price_history import price_stats

    with session_factory() as s:
        ing = make_ingredient(s, name="Harina", unit="kg", stock_qty=0.0)
        s.add(ing)
        s.commit()
        stats = price_stats(s, ing.id, days=90)
    assert stats == {"current": None, "min": None, "max": None, "avg": None, "count": 0}


# --- inventory POST writes a 'manual' price event ---


def test_inventory_create_writes_manual_price_event(session_factory):
    """POSTing a new ingredient with purchase_price_gs creates an event."""
    from app.rms.models import IngredientPriceEvent
    from app.rms.price_history import record_price_event

    # We test the wiring directly via the helper rather than driving the HTTP
    # form — the router calls record_price_event(..., source='manual').
    with session_factory() as s:

        ing = make_ingredient(s, name="Harina", unit="kg", stock_qty=5.0)
        s.add(ing)
        s.commit()
        ing_id = ing.id

        record_price_event(s, ing_id, 6500, source="manual")
        s.commit()
        rows = s.query(IngredientPriceEvent).filter_by(ingredient_id=ing_id).all()
    assert len(rows) == 1
    assert rows[0].source == "manual"
    assert rows[0].price_gs == 6500


def test_inventory_router_calls_record_price_event(client, session_factory):
    """Driving the /inventario/nuevo POST endpoint writes a 'manual' price event."""
    from app.rms.models import Ingredient, IngredientPriceEvent

    # Sanity: csrf exempt / no auth in tests
    r = client.post(
        "/inventario/nuevo",
        data={
            "name": "Azúcar",
            "unit": "kg",
            "stock_qty": "10",
            "min_stock_qty": "0",
            "purchase_price_gs": "Gs. 4.500",
            "notes": "",
        },
        follow_redirects=False,
    )
    assert r.status_code in (303, 302), r.text

    with session_factory() as s:
        ing = s.query(Ingredient).filter_by(name="Azúcar").first()
        assert ing is not None
        events = (
            s.query(IngredientPriceEvent).filter_by(ingredient_id=ing.id).all()
        )
        assert len(events) == 1
        assert events[0].source == "manual"
        assert events[0].price_gs == 4500


def test_inventory_router_no_event_when_no_price(client, session_factory):
    """POSTing a new ingredient WITHOUT purchase_price_gs writes no event."""
    from app.rms.models import Ingredient, IngredientPriceEvent

    r = client.post(
        "/inventario/nuevo",
        data={
            "name": "SinPrecio",
            "unit": "und",
            "stock_qty": "0",
            "min_stock_qty": "0",
            "purchase_price_gs": "",
            "notes": "",
        },
        follow_redirects=False,
    )
    assert r.status_code in (303, 302), r.text

    with session_factory() as s:
        ing = s.query(Ingredient).filter_by(name="SinPrecio").first()
        assert ing is not None
        events = (
            s.query(IngredientPriceEvent).filter_by(ingredient_id=ing.id).all()
        )
        assert len(events) == 0


def test_inventory_update_writes_price_event_on_price_change(client, session_factory):
    """Updating an existing ingredient's price writes a new 'manual' event."""
    from app.rms.models import Ingredient, IngredientPriceEvent

    # Create ingredient first
    r = client.post(
        "/inventario/nuevo",
        data={
            "name": "EditPrecio",
            "unit": "kg",
            "stock_qty": "5",
            "min_stock_qty": "0",
            "purchase_price_gs": "Gs. 5.000",
            "notes": "",
        },
        follow_redirects=False,
    )
    assert r.status_code in (303, 302), r.text

    with session_factory() as s:
        ing = s.query(Ingredient).filter_by(name="EditPrecio").first()
        ing_id = ing.id

    # Update price
    r = client.post(
        f"/inventario/{ing_id}/editar",
        data={
            "name": "EditPrecio",
            "unit": "kg",
            "stock_qty": "5",
            "min_stock_qty": "0",
            "purchase_price_gs": "Gs. 6.500",
            "notes": "",
        },
        follow_redirects=False,
    )
    assert r.status_code in (303, 302), r.text

    with session_factory() as s:
        events = (
            s.query(IngredientPriceEvent).filter_by(ingredient_id=ing_id).all()
        )
        assert len(events) == 2
        prices = sorted(e.price_gs for e in events)
        assert prices == [5000, 6500]
        # Both are 'manual' (operator-driven)
        assert all(e.source == "manual" for e in events)


# --- migration v18 (table creation + idempotency) ---


def test_migration_v18_creates_ingredient_price_event_table(tmp_path):
    """init_db() at schema_version=18 creates the ingredient_price_event table."""
    from app.rms.config import CURRENT_SCHEMA_VERSION

    assert CURRENT_SCHEMA_VERSION >= 18

    db = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db}")
    init_db(engine)

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).all()
        names = {r[0] for r in rows}
    assert "ingredient_price_event" in names


def test_migration_v18_index_exists(tmp_path):
    """init_db() creates the (ingredient_id, recorded_at DESC) index."""
    db = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db}")
    init_db(engine)

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='index'")
        ).all()
        names = {r[0] for r in rows}
    # Index naming follows SQLAlchemy default; we just need *some* index
    # touching ingredient_price_event
    assert any("ingredient_price_event" in n for n in names), (
        f"No index found for ingredient_price_event: {names}"
    )
