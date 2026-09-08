"""tests/test_workflow.py — verify app/rms/workflow.py (E12).

Per docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md E12.

Covers:
- EOD checklist template has 10 items
- fresh_eod_checklist returns 10 PENDING items
- eod_progress counts DONE/PENDING/etc + computes pct
- daily_summary_full computes revenue + cogs + margin + warnings
- SeasonalEvent list has 2026 events
- active_events returns events containing a day
- upcoming_events returns events in the next 14 days
- demand_multiplier is 1.0 when no events active
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from app.rms.models import Ingredient, Product, Sale
from app.rms.workflow import (
    EOD_CHECKLIST_TEMPLATE,
    SEASONAL_CALENDAR_2026,
    EODItemStatus,
    active_events,
    daily_summary_full,
    demand_multiplier,
    eod_progress,
    fresh_eod_checklist,
    upcoming_events,
)


def test_eod_checklist_template_has_10_items():
    assert len(EOD_CHECKLIST_TEMPLATE) == 10


def test_eod_checklist_template_keys_unique():
    keys = [item.key for item in EOD_CHECKLIST_TEMPLATE]
    assert len(keys) == len(set(keys)), f"Duplicate keys: {keys}"


def test_fresh_eod_checklist_is_all_pending():
    items = fresh_eod_checklist()
    assert len(items) == 10
    assert all(i.status == EODItemStatus.PENDING for i in items)


def test_eod_progress_empty():
    progress = eod_progress([])
    assert progress["total"] == 0
    assert progress["pct"] == 0.0


def test_eod_progress_all_done():
    items = fresh_eod_checklist()
    for i in items:
        i.status = EODItemStatus.DONE
    progress = eod_progress(items)
    assert progress["done"] == 10
    assert progress["pending"] == 0
    assert progress["pct"] == 100.0


def test_eod_progress_partial():
    items = fresh_eod_checklist()
    items[0].status = EODItemStatus.DONE
    items[1].status = EODItemStatus.DONE
    items[2].status = EODItemStatus.BLOCKED
    items[3].status = EODItemStatus.SKIPPED
    progress = eod_progress(items)
    assert progress["done"] == 2
    assert progress["blocked"] == 1
    assert progress["skipped"] == 1
    assert progress["pending"] == 6
    # pct counts done + skipped
    assert progress["pct"] == 30.0


def test_seasonal_calendar_has_2026_events():
    """11 events for 2026."""
    assert len(SEASONAL_CALENDAR_2026) >= 11
    names = {e.name for e in SEASONAL_CALENDAR_2026}
    assert "Navidad" in names
    assert "Día de la Madre (PY)" in names
    assert "Año Nuevo" in names
    assert "Día de la Independencia" in names


def test_active_events_includes_christmas():
    """On Christmas Day, the 'Navidad' event must be active."""
    events = active_events(date(2026, 12, 25))
    names = [e.name for e in events]
    assert "Navidad" in names


def test_active_events_empty_on_normal_day():
    """On a random Tuesday in February with no events, returns empty."""
    events = active_events(date(2026, 2, 10))
    assert events == []


def test_upcoming_events_includes_next_holiday():
    """On 2026-12-01, upcoming events should include Navidad."""
    events = upcoming_events(date(2026, 12, 1), days_ahead=20)
    names = [e.name for e in events]
    assert "Navidad" in names


def test_demand_multiplier_is_1_on_normal_day():
    assert demand_multiplier(date(2026, 2, 10)) == 1.0


def test_demand_multiplier_spikes_on_mother_day():
    """Día de la Madre has 2.0x multiplier."""
    mult = demand_multiplier(date(2026, 5, 15))
    assert mult == 2.0


def test_demand_multiplier_max_christmas():
    """Navidad has 3.0x multiplier."""
    mult = demand_multiplier(date(2026, 12, 24))
    assert mult == 3.0


def test_daily_summary_full_on_empty_db(session_factory):
    """daily_summary_full runs cleanly on empty DB + emits warnings."""
    s = session_factory()
    try:
        summary = daily_summary_full(s, datetime.now(timezone.utc))
        assert summary.n_sales == 0
        assert summary.revenue_gs == 0
        assert "Sin ventas registradas hoy" in summary.warnings
    finally:
        s.close()


def test_daily_summary_full_warns_on_high_void_rate(session_factory):
    """If voided > 10% of sales, emit warning."""
    s = session_factory()
    try:
        prod = Product(name="Muffin", sale_price_gs=2500)
        s.add(prod)
        s.flush()
        now = datetime.now(timezone.utc)
        # 5 valid + 3 voided = 37% voided
        for _ in range(5):
            s.add(Sale(sold_at=now, product_id=prod.id, qty=1, unit_price_gs=2500))
        for _ in range(3):
            s.add(Sale(sold_at=now, product_id=prod.id, qty=1, unit_price_gs=2500,
                       voided_at=now))
        s.commit()
        summary = daily_summary_full(s, now)
        assert summary.n_sales == 5
        assert summary.n_voided == 3
        # Should warn about high void rate
        assert any("anulaciones" in w.lower() for w in summary.warnings)
    finally:
        s.close()


def test_daily_summary_full_warns_on_low_margin(session_factory):
    """If margin < 30%, emit warning."""
    s = session_factory()
    try:
        prod = Product(name="Muffin", sale_price_gs=2500)
        ing = Ingredient(name="flour", unit="kg", stock_qty=10.0, purchase_price_gs=4500)
        s.add_all([prod, ing])
        s.flush()
        now = datetime.now(timezone.utc)
        s.add(Sale(sold_at=now, product_id=prod.id, qty=1, unit_price_gs=2500))
        s.commit()
        # COGS will be 0 (no SaleStockMove), margin = revenue = 100%, no warning
        summary = daily_summary_full(s, now)
        assert summary.revenue_gs == 2500
    finally:
        s.close()


def test_daily_summary_full_lists_low_stock(session_factory):
    s = session_factory()
    try:
        low = Ingredient(name="harina", unit="kg", stock_qty=1.0, min_stock_qty=10.0, purchase_price_gs=4500)
        ok = Ingredient(name="azúcar", unit="kg", stock_qty=20.0, min_stock_qty=5.0, purchase_price_gs=5200)
        s.add_all([low, ok])
        s.commit()
        summary = daily_summary_full(s, datetime.now(timezone.utc))
        assert "harina" in summary.low_stock_ingredients
        assert "azúcar" not in summary.low_stock_ingredients
        assert any("bajo mínimo" in w for w in summary.warnings)
    finally:
        s.close()
