"""tests/test_waste_roi_per_ingredient.py — BACKLOG #34 waste ROI per ingredient.

Ported to the shipped API: `waste_roi_by_ingredient` (sales_intel.py)
aggregates WasteLog.cost_gs per ingredient over the window. The old
drafts targeted a never-shipped `waste_roi_per_ingredient` signature
(batch_id/qty_gs StockMovement fields that no longer exist) and a
`testdb` fixture that was never defined — both caused permanent
collection errors. These tests exercise the real contract.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.rms.models import Ingredient, WasteLog
from app.rms.sales_intel import waste_roi_by_ingredient


def _seed_waste(s, ing: Ingredient, cost_gs: float, days_ago: int = 0) -> None:
    s.add(
        WasteLog(
            ingredient_id=ing.id,
            qty=1.0,
            cost_gs=cost_gs,
            reason="vencida",
            recorded_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
        )
    )


def test_waste_roi_no_data(session_factory):
    """When no waste data, return empty list."""
    s = session_factory()
    try:
        assert waste_roi_by_ingredient(s) == []
    finally:
        s.close()


def test_waste_roi_with_merma(session_factory):
    """Waste events aggregate into total_waste_gs with name + count."""
    s = session_factory()
    try:
        ing = Ingredient(name="Azúcar", unit="kg", stock_qty=10.0, purchase_price_gs=5000)
        s.add(ing)
        s.flush()
        _seed_waste(s, ing, 1000.0)
        s.commit()

        result = waste_roi_by_ingredient(s, since_days=1)
        assert len(result) == 1
        r = result[0]
        assert r["ingredient_name"] == "Azúcar"
        assert r["total_waste_gs"] == 1000
        assert r["event_count"] == 1
        assert r["avg_waste_per_event_gs"] == 1000.0
        assert r["waste_pct"] == 0.0  # v1: consumed left to the operator dashboard
    finally:
        s.close()


def test_waste_roi_multiple_events(session_factory):
    """Sum waste + average across multiple events on one ingredient."""
    s = session_factory()
    try:
        ing = Ingredient(name="Harina", unit="kg", stock_qty=20.0, purchase_price_gs=3000)
        s.add(ing)
        s.flush()
        _seed_waste(s, ing, 500.0)
        _seed_waste(s, ing, 1500.0)
        s.commit()

        result = waste_roi_by_ingredient(s, since_days=1)
        assert len(result) == 1
        r = result[0]
        assert r["total_waste_gs"] == 2000
        assert r["event_count"] == 2
        assert r["avg_waste_per_event_gs"] == 1000.0
    finally:
        s.close()


def test_waste_roi_window_excludes_old_events(session_factory):
    """Events outside the since_days window are excluded."""
    s = session_factory()
    try:
        ing = Ingredient(name="Leche", unit="l", stock_qty=12.0, purchase_price_gs=2000)
        s.add(ing)
        s.flush()
        _seed_waste(s, ing, 500.0, days_ago=30)  # outside a 7-day window
        s.commit()

        assert waste_roi_by_ingredient(s, since_days=7) == []
        # And inside a wide window it shows up
        result = waste_roi_by_ingredient(s, since_days=90)
        assert len(result) == 1
        assert result[0]["total_waste_gs"] == 500
    finally:
        s.close()


def test_waste_roi_sorted_by_waste_desc(session_factory):
    """Biggest money leak first."""
    s = session_factory()
    try:
        cheap = Ingredient(name="Vainilla", unit="kg", stock_qty=5.0, purchase_price_gs=4000)
        pricey = Ingredient(name="Chocolate", unit="kg", stock_qty=5.0, purchase_price_gs=10000)
        s.add_all([cheap, pricey])
        s.flush()
        _seed_waste(s, cheap, 100.0)
        _seed_waste(s, pricey, 2000.0)
        s.commit()

        result = waste_roi_by_ingredient(s)
        assert [r["ingredient_name"] for r in result] == ["Chocolate", "Vainilla"]
        assert result[0]["total_waste_gs"] == 2000
    finally:
        s.close()
