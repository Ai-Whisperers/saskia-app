"""tests/test_seasonal.py — verify app/rms/seasonal.py (E19).

Per docs/plans/2026-09-07-sazon-complete-epic-plan-v3.md E19.

Covers:
- serialize_event: includes all fields + duration_days
- calendar_for_year(2026): returns full list
- calendar_for_year(2027, fallback=True): shifts dates correctly
- calendar_for_year(2027, fallback=False): returns empty
- upcoming_calendar_json: shape + next_event populated
- product_hints_for_event: keyword matching
"""

# allow-hardcoded-dates: seasonal analysis needs a fixed full-year date range
from __future__ import annotations

from datetime import date

from app.rms.seasonal import (
    calendar_for_year,
    product_hints_for_event,
    serialize_event,
    upcoming_calendar_json,
)
from app.rms.workflow import SeasonalEvent, active_events


def test_serialize_event_includes_all_fields():
    ev = SeasonalEvent(
        name="Test",
        start=date(2026, 12, 15),
        end=date(2026, 12, 31),
        hint="Test hint",
        multiplier=3.0,
    )
    d = serialize_event(ev)
    assert d["name"] == "Test"
    assert d["start"] == "2026-12-15"
    assert d["end"] == "2026-12-31"
    assert d["hint"] == "Test hint"
    assert d["multiplier"] == 3.0
    assert d["duration_days"] == 17  # 31-15+1


def test_calendar_for_year_2026_returns_full():
    cal = calendar_for_year(2026)
    assert len(cal) >= 11  # at least the 11 events we shipped
    names = {d["name"] for d in cal}
    assert "Navidad" in names


def test_calendar_for_year_2027_shifts_dates():
    """2027 with fallback shifts the calendar by +1 year."""
    cal_2027 = calendar_for_year(2027, fallback_to_2026=True)
    cal_2026 = calendar_for_year(2026)
    assert len(cal_2027) == len(cal_2026)
    # Navidad is Dec 15-31 in 2026; in 2027 should be Dec 15-31 (same)
    christmas_2027 = next(d for d in cal_2027 if d["name"] == "Navidad")
    christmas_2026 = next(d for d in cal_2026 if d["name"] == "Navidad")
    assert christmas_2027["start"].startswith("2027-12")
    assert christmas_2026["start"].startswith("2026-12")


def test_calendar_for_year_2027_no_fallback_returns_empty():
    cal = calendar_for_year(2027, fallback_to_2026=False)
    assert cal == []


def test_upcoming_calendar_json_shape():
    today = date(2026, 12, 1)
    cal = upcoming_calendar_json(days_ahead=20, today=today)
    assert cal["today"] == "2026-12-01"
    assert cal["horizon"] == "2026-12-21"
    assert isinstance(cal["active_events"], list)
    assert isinstance(cal["upcoming_events"], list)
    # Navidad active (Dec 15-31) at horizon Dec 21
    assert cal["next_event"] is not None
    assert cal["next_event"]["name"] == "Navidad"


def test_upcoming_no_next_event_far_from_holidays():
    """On a quiet day in February with no event in 14 days, next_event=None."""
    cal = upcoming_calendar_json(days_ahead=3, today=date(2026, 2, 10))
    assert cal["next_event"] is None


def test_demand_multiplier_in_calendar_json():
    cal = upcoming_calendar_json(days_ahead=14, today=date(2026, 5, 15))
    # Día de la Madre has 2.0x
    assert cal["demand_multiplier"] == 2.0


def test_product_hints_match_tortas_event():
    """A torta/cupcake event hints at torta / cupcake products."""
    ev = SeasonalEvent(
        name="Día de la Madre",
        start=date(2026, 5, 15),
        end=date(2026, 5, 15),
        hint="Tortas y cupcakes premium",
        multiplier=2.0,
    )
    hints = product_hints_for_event(ev, ["Torta", "Cupcake", "Muffin"])
    names = {h.product_name for h in hints}
    assert "Torta" in names
    assert "Cupcake" in names


def test_product_hints_match_pascuas():
    """Pascuas hint mentions huevos + roscas → both products hinted."""
    ev = SeasonalEvent(
        name="Pascuas",
        start=date(2026, 4, 1),
        end=date(2026, 4, 15),
        hint="Huevos de Pascua + roscas",
        multiplier=1.5,
    )
    hints = product_hints_for_event(ev, ["Huevo de Pascua", "Rosca", "Muffin"])
    names = {h.product_name for h in hints}
    assert "Huevo de Pascua" in names
    assert "Rosca" in names


def test_product_hints_no_match():
    """When no keywords match, no hints returned."""
    ev = SeasonalEvent(
        name="Generic",
        start=date(2026, 1, 1),
        end=date(2026, 1, 2),
        hint="Nada relevante",
        multiplier=1.0,
    )
    hints = product_hints_for_event(ev, ["Muffin"])
    assert hints == []


def test_active_events_integration():
    """active_events() from workflow still works through seasonal.py."""
    events = active_events(date(2026, 12, 25))
    assert any(e.name == "Navidad" for e in events)
