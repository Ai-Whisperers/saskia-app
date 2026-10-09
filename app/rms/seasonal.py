"""app/rms/seasonal.py — Seasonal calendar HTTP helpers (E19).

Per docs/plans/2026-09-07-sazon-complete-epic-plan-v3.md E19.

Most of E19 (the calendar data + seasonal_multiplier) was shipped in
E12 (workflow.py). This module adds the HTTP-facing helpers:

- serialize_event(event) → JSON-ready dict
- calendar_for_year(year) → list of serialized events for a year
- upcoming_calendar_json(days_ahead=14) → dict used by the dashboard
  widget + WhatsApp daily summary footer

The data lives in workflow.SEASONAL_CALENDAR_2026 today. This module
will be the place to expand to multi-year calendars (2027, 2028) once
we have them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.rms.workflow import (
    SeasonalEvent,
    active_events,
    demand_multiplier,
    upcoming_events,
)


def serialize_event(ev: SeasonalEvent) -> dict[str, Any]:
    """Convert a SeasonalEvent to a JSON-ready dict."""
    return {
        "name": ev.name,
        "start": ev.start.isoformat(),
        "end": ev.end.isoformat(),
        "hint": ev.hint,
        "multiplier": ev.multiplier,
        "duration_days": (ev.end - ev.start).days + 1,
    }


def calendar_for_year(year: int, *, fallback_to_2026: bool = True) -> list[dict[str, Any]]:
    """Return all seasonal events for a given year.

    Today the only data we have is 2026. For other years we either
    return [] or transparently fall back to the 2026 calendar shifted
    by (year - 2026) years, depending on the flag.
    """
    from app.rms.workflow import SEASONAL_CALENDAR_2026

    if year == 2026:
        return [serialize_event(e) for e in SEASONAL_CALENDAR_2026]

    if not fallback_to_2026:
        return []

    # Shift the calendar to the requested year
    shifted: list[dict[str, Any]] = []
    for ev in SEASONAL_CALENDAR_2026:
        new_start = ev.start.replace(year=year)
        new_end = ev.end.replace(year=year)
        shifted.append(
            {
                "name": ev.name,
                "start": new_start.isoformat(),
                "end": new_end.isoformat(),
                "hint": ev.hint,
                "multiplier": ev.multiplier,
                "duration_days": (new_end - new_start).days + 1,
            }
        )
    return shifted


def upcoming_calendar_json(
    *,
    days_ahead: int = 14,
    today: date | None = None,
) -> dict[str, Any]:
    """Dashboard widget data: today + upcoming events + multiplier."""
    today = today or datetime.now(timezone.utc).date()
    horizon = today + timedelta(days=days_ahead)

    active = active_events(today)
    next_events = upcoming_events(today, days_ahead=days_ahead)

    return {
        "today": today.isoformat(),
        "horizon": horizon.isoformat(),
        "active_events": [serialize_event(e) for e in active],
        "upcoming_events": [serialize_event(e) for e in next_events],
        "demand_multiplier": demand_multiplier(today),
        "next_event": (serialize_event(next_events[0]) if next_events else None),
    }


@dataclass
class ProductHint:
    """A hint about which products to push for an upcoming event."""

    product_name: str
    reason: str
    multiplier: float


DEFAULT_PRODUCT_NAMES = [
    "Muffin",
    "Torta",
    "Tostado",
    "Chipá",
    "Sopa paraguaya",
    "Galleta",
    "Cupcake",
    "Pan dulce",
    "Rosca",
    "Huevo de Pascua",
]

# Keyword rules: (keyword_in_hint, name_match_predicate, message_template)
# message_template uses {event_name} and {multiplier}
_HINT_RULES = [
    ("torta", lambda n: n.lower() in ("torta", "cupcake"), "Demanda alta en {event_name}"),
    ("cupcake", lambda n: n.lower() in ("torta", "cupcake"), "Demanda alta en {event_name}"),
    ("pan dulce", lambda n: n == "Pan dulce", "Sube en {event_name}"),
    ("rosca", lambda n: "rosca" in n.lower(), "Sube en {event_name}"),
    ("huevo", lambda n: "huevo" in n.lower(), "Sube en {event_name}"),
    ("chipa", lambda n: "chipa" in n.lower(), "Sube en {event_name}"),
    ("galleta", lambda n: "galleta" in n.lower(), "Sube en {event_name}"),
    ("muffin", lambda n: "muffin" in n.lower(), "Sube en {event_name}"),
]


def product_hints_for_event(
    event: SeasonalEvent,
    product_names: list[str] | None = None,
) -> list[ProductHint]:
    """Map a calendar event to product-level hints.

    The mapping is heuristic: we look for keywords in the event hint
    string and recommend matching product categories. Operator can
    override via tags (E9) — this is the simple default.
    """
    if product_names is None:
        product_names = DEFAULT_PRODUCT_NAMES
    keywords = event.hint.lower()
    return _collect_matching_hints(event, keywords, product_names)


def _collect_matching_hints(event: SeasonalEvent, keywords: str, product_names: list[str]) -> list[ProductHint]:
    """Collect product hints matching the event keywords.

    Extracted from product_hints_for_event to reduce complexity.
    """
    hints: list[ProductHint] = []
    for name in product_names:
        for keyword, predicate, msg_template in _HINT_RULES:
            if keyword in keywords and predicate(name):
                hints.append(ProductHint(
                    name,
                    msg_template.format(event_name=event.name),
                    event.multiplier,
                ))
                break
    return hints


