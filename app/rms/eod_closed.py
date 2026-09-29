"""P0 fix — EOD closed-day protection for void_sale and other accounting-sensitive mutations.

The roadmap (saskia-only-roadmap.md) flagged a critical violation: `void_sale()` does not
check whether the sale belongs to a day whose EOD has been closed. Saskia could void a
Monday sale on Wednesday AFTER closing Monday's books.

This module introduces a single source of truth: `eod_is_day_closed(session, day) ->
bool`. It returns True if and only if all 9 mandatory EOD checklist items are checked
off for that date.

The 9 items come from `workflow.fresh_eod_checklist()`. A day is "closed" when each item's
`eod_check_<date>_<key>` AppMeta row has value="1".

Why AppMeta (not a new table):
- Existing EOD state is already in AppMeta (eod_check_<date>_<key>)
- The migration would touch every installation
- Adding one derived boolean is cheap; querying the 9 keys per void call is 9 indexed
  lookups on AppMeta.key

Public API:
    eod_is_day_closed(session: Session, day: date) -> bool
    eod_get_open_days(session: Session, since: date) -> list[date]
        # Useful for /reportes/dashboard to show "X días sin cerrar"

Edge cases:
- Future dates: never closed
- Dates before EOD feature shipped: never closed (no rows means open)
- Day with 0 checklist items: not closed (defensive; shouldn't happen)
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import AppMeta
from app.rms.workflow import fresh_eod_checklist

# Default EOD clock — Asuncion (UTC-4 year-round). Same TZ used by eod.py.
def _today_local() -> date:
    from datetime import datetime

    try:
        from app.rms.config import ASUNCION_TZ
        return datetime.now(ASUNCION_TZ).date()
    except ImportError:
        # Fallback if config module is unavailable in tests.
        return datetime.utcnow().date()


def eod_is_day_closed(session: Session, day: date) -> bool:
    """Return True iff ALL mandatory EOD checklist items for `day` are checked off.

    A day is considered "closed" (accounting-final) when every *checkable* item in
    `fresh_eod_checklist()` has an `eod_check_<iso-date>_<key>` AppMeta row with
    value="1".

    Notes-only items (e.g. `notes_for_tomorrow`) are text inputs, not checkboxes,
    and are intentionally excluded from the closed-day gate — operators may
    legitimately skip them.

    Future dates are never closed.
    Dates with no checklist rows in AppMeta are NOT closed.
    """
    if day > _today_local():
        return False  # Future — never closed.

    items = fresh_eod_checklist()
    # Exclude text-only fields (notes) — they're not checkboxes, so they
    # never appear in eod_check_<date>_<key> AppMeta rows.
    checkable_items = [item for item in items if item.key != "notes_for_tomorrow"]
    if not checkable_items:
        return False  # Defensive: empty checklist can't be closed.

    prefix = f"eod_check_{day.isoformat()}_"
    keys = [prefix + item.key for item in checkable_items]
    rows = session.scalars(
        select(AppMeta).where(AppMeta.key.in_(keys))
    ).all()
    completed_keys = {row.key for row in rows if row.value == "1"}
    return all(prefix + item.key in completed_keys for item in checkable_items)


def eod_get_open_days(session: Session, since: date) -> list[date]:
    """Return all dates in [since, today] whose EOD is NOT closed."""
    today = _today_local()
    if since > today:
        return []
    open_days = []
    cursor = since
    while cursor <= today:
        if not eod_is_day_closed(session, cursor):
            open_days.append(cursor)
        cursor += timedelta(days=1)
    return open_days


__all__ = ["eod_is_day_closed", "eod_get_open_days"]
