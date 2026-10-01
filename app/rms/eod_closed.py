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

# Default EOD clock — Asuncion (offset is what zoneinfo says: -3 or -4).
def _today_local() -> date:
    """Return today's date in Asuncion, via the canonical clock module.

    Sprint 1.3: uses ``app.rms.clock.today_local`` (which itself uses the
    IANA ``America/Asuncion`` zone). Avoids the deprecated
    ``datetime.utcnow()`` fallback.
    """
    from app.rms.clock import today_local

    return today_local().date()


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


class EODClosedError(ValueError):
    """Raised when an accounting-sensitive write targets a closed day.

    Backed by ValueError so existing `void_sale` callers don't change,
    but discriminated by class so routers can map it to a 409 Conflict
    and surface a Spanish-language message to the operator.
    """


def assert_day_open_or_raise(
    session: Session, day: date | None, *, action: str
) -> None:
    """Guard an accounting-sensitive write: raise EODClosedError if `day`
    is closed.

    Used by sales insert, sales update, waste (merma), inventory
    adjustment, and any other write that mutates accounting state for a
    past day. The `void_sale` code path uses an inline check (not this
    helper) because it raises a different prefix ("void_after_eod_close")
    — but the underlying logic is the same.

    Args:
        session: Active SQLAlchemy session.
        day: The day the write targets. None is treated as "today" (open)
            — defensive, since some writes may not carry an explicit date.
        action: Short identifier for the action being attempted. Used in
            the error message to make debugging trivial.

    Raises:
        EODClosedError: When `day` is in the past and all EOD checklist
            items for that day are marked done.
    """
    if day is None:
        return  # Treat unknown date as today — let the call site decide.
    if not eod_is_day_closed(session, day):
        return
    raise EODClosedError(
        f"eod_closed:{day.isoformat()}:{action}"
    )


__all__ = ["eod_is_day_closed", "eod_get_open_days", "assert_day_open_or_raise", "EODClosedError"]
