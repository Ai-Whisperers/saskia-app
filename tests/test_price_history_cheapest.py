"""tests/test_price_history_cheapest.py — Q4 cheapest-supplier aggregation.

The /reorder hint "Proveedor más barato" is powered by
``cheapest_supplier()`` (single ingredient) and
``batch_cheapest_supplier()`` (many ingredients in one query).
"""
from __future__ import annotations

from app.rms.price_history import (
    batch_cheapest_supplier,
    cheapest_supplier,
    record_price_event,
)


def _make_supplier(session, name: str) -> int:
    from app.rms.models import Supplier

    s = Supplier(name=name, is_active=True)
    session.add(s)
    session.flush()
    return s.id


def _make_ingredient(session, name: str) -> int:
    from app.rms.models import Ingredient

    i = Ingredient(name=name, unit="kg", stock_qty=0)
    session.add(i)
    session.flush()
    return i.id


def test_cheapest_supplier_empty_when_no_events(session_factory):
    """No events in window → None."""
    Session = session_factory
    with Session() as s:
        iid = _make_ingredient(s, "harina")
        s.commit()
        result = cheapest_supplier(s, iid)
        assert result is None


def test_cheapest_supplier_picks_lowest_mean(session_factory):
    """3 events from supplier A at 5000, 2 from B at 3000 → B is cheapest."""
    Session = session_factory
    with Session() as s:
        iid = _make_ingredient(s, "azucar")
        sa = _make_supplier(s, "A_Caro")
        sb = _make_supplier(s, "B_Barato")
        record_price_event(s, iid, 5000, supplier_id=sa, source="restock")
        record_price_event(s, iid, 5000, supplier_id=sa, source="restock")
        record_price_event(s, iid, 5000, supplier_id=sa, source="restock")
        record_price_event(s, iid, 3000, supplier_id=sb, source="restock")
        record_price_event(s, iid, 3000, supplier_id=sb, source="restock")
        s.commit()
        result = cheapest_supplier(s, iid)
        assert result is not None
        assert result["supplier_id"] == sb
        assert result["supplier_name"] == "B_Barato"
        assert result["avg_price_gs"] == 3000
        assert result["event_count"] == 2


def test_cheapest_supplier_tie_break_prefers_more_events(session_factory):
    """A: 1 event @ 3000, B: 3 events @ 3000 → B wins (more reliable)."""
    Session = session_factory
    with Session() as s:
        iid = _make_ingredient(s, "leche")
        sa = _make_supplier(s, "A_Raro")
        sb = _make_supplier(s, "B_Frecuente")
        record_price_event(s, iid, 3000, supplier_id=sa, source="restock")
        record_price_event(s, iid, 3000, supplier_id=sb, source="restock")
        record_price_event(s, iid, 3000, supplier_id=sb, source="restock")
        record_price_event(s, iid, 3000, supplier_id=sb, source="restock")
        s.commit()
        result = cheapest_supplier(s, iid)
        assert result["supplier_id"] == sb
        assert result["event_count"] == 3


def test_cheapest_supplier_handles_null_supplier_id(session_factory):
    """Legacy events without supplier_id form their own bucket."""
    Session = session_factory
    with Session() as s:
        iid = _make_ingredient(s, "sal")
        sa = _make_supplier(s, "A")
        # 1 event with NULL supplier at 1000, 1 event with supplier A at 5000
        record_price_event(s, iid, 1000, supplier_id=None, source="manual")
        record_price_event(s, iid, 5000, supplier_id=sa, source="restock")
        s.commit()
        result = cheapest_supplier(s, iid)
        assert result["supplier_id"] is None
        assert result["supplier_name"] is None
        assert result["avg_price_gs"] == 1000


def test_batch_cheapest_supplier_returns_per_ingredient(session_factory):
    """Different cheapest supplier per ingredient, batched in one call."""
    Session = session_factory
    with Session() as s:
        iid_h = _make_ingredient(s, "harina")
        iid_a = _make_ingredient(s, "azucar")
        sa = _make_supplier(s, "A")
        sb = _make_supplier(s, "B")
        # Harina cheapest = A (3000), Azucar cheapest = B (2000)
        record_price_event(s, iid_h, 5000, supplier_id=sb, source="restock")
        record_price_event(s, iid_h, 3000, supplier_id=sa, source="restock")
        record_price_event(s, iid_a, 8000, supplier_id=sa, source="restock")
        record_price_event(s, iid_a, 2000, supplier_id=sb, source="restock")
        s.commit()
        results = batch_cheapest_supplier(s, [iid_h, iid_a])
        assert results[iid_h]["supplier_id"] == sa
        assert results[iid_h]["avg_price_gs"] == 3000
        assert results[iid_a]["supplier_id"] == sb
        assert results[iid_a]["avg_price_gs"] == 2000


def test_batch_cheapest_supplier_handles_ingredients_without_events(session_factory):
    """Ingredient with no events returns None, not KeyError."""
    Session = session_factory
    with Session() as s:
        iid_with = _make_ingredient(s, "con_eventos")
        iid_without = _make_ingredient(s, "sin_eventos")
        sa = _make_supplier(s, "X")
        record_price_event(s, iid_with, 4000, supplier_id=sa, source="restock")
        s.commit()
        results = batch_cheapest_supplier(s, [iid_with, iid_without])
        assert results[iid_with]["supplier_id"] == sa
        assert results[iid_without] is None


def test_batch_cheapest_supplier_empty_input_returns_empty(session_factory):
    Session = session_factory
    with Session() as s:
        results = batch_cheapest_supplier(s, [])
        assert results == {}


def test_cheapest_supplier_excludes_events_outside_window(session_factory):
    """Event older than `days` window is excluded."""
    from datetime import datetime, timedelta, timezone

    Session = session_factory
    with Session() as s:
        iid = _make_ingredient(s, "vino")
        sa = _make_supplier(s, "A_actual")
        sb = _make_supplier(s, "B_viejo")
        old_ts = datetime.now(timezone.utc) - timedelta(days=120)
        record_price_event(s, iid, 1000, supplier_id=sb, source="restock", at=old_ts)
        record_price_event(s, iid, 5000, supplier_id=sa, source="restock")
        s.commit()
        # Window of 90 days: the old event is excluded → A wins.
        result = cheapest_supplier(s, iid, days=90)
        assert result["supplier_id"] == sa
        assert result["avg_price_gs"] == 5000
