"""app/rms/clock.py — single source of truth for ``now()``.

Sprint 1.3 (2026-10-02) of the backend overhaul.

Before this module, the codebase mixed:
- ``datetime.utcnow()`` (deprecated in Python 3.12, naive UTC)
- ``datetime.now()`` (machine-local tz, almost always wrong here)
- ``datetime.now(ASUNCION_TZ)`` (correct, but easy to forget)

This module centralises three things:

1. :func:`now` returns timezone-aware UTC, always.
2. :func:`today_local` returns the calendar date in Asuncion.
3. :func:`asuncion_now` returns the current wall-clock time in Asuncion.

Hard rule from ``app/rms/AGENTS.md``: every DB-stored datetime is
**UTC-aware**. Display and period math use the Asuncion-local clock.

Replace every existing ``datetime.utcnow()`` / ``datetime.now()``
callsite with the appropriate helper here.
"""

from __future__ import annotations

from datetime import datetime, timezone

# Single canonical timezone for the business. Paraguay does not observe
# DST; the offset is stable year-round at UTC-4. Importing from
# app.rms.config keeps this in lock-step with the rest of the app.
from app.rms.config import ASUNCION_TZ

UTC = timezone.utc


def now() -> datetime:
    """Return the current time as a timezone-aware UTC ``datetime``.

    Use this at every persistence site (DB columns, audit log timestamps,
    sent_at on notifications, etc.). The result compares correctly across
    processes and servers; it serialises to ISO-8601 with the ``+00:00``
    suffix that Postgres' ``TIMESTAMP WITH TIME ZONE`` understands.
    """
    return datetime.now(UTC)


def today_local() -> datetime:
    """Return the current wall-clock time in Asuncion (UTC-4, no DST).

    Use this for display ("today", "yesterday's sales", "this week's
    margin") and for any period boundary math (start_of_day, end_of_day).
    Never use the result for DB persistence — store UTC, display Asuncion.
    """
    return datetime.now(ASUNCION_TZ)


def utcnow() -> datetime:
    """Backwards-compatible alias for :func:`now`.

    Provided so existing code can be migrated line by line. Prefer
    ``from app.rms.clock import now`` for new code.
    """
    return now()


def to_utc(dt: datetime) -> datetime:
    """Coerce a possibly-naive datetime to aware UTC.

    Naive datetimes are assumed to already be in UTC (the legacy
    convention from before Sprint 1.3). Aware datetimes in any zone
    are converted to UTC.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def to_asuncion(dt: datetime) -> datetime:
    """Coerce a possibly-naive datetime to aware Asuncion local.

    Naive datetimes are assumed UTC (legacy convention); aware
    datetimes are converted to Asuncion.
    """
    utc_dt = to_utc(dt)
    return utc_dt.astimezone(ASUNCION_TZ)


__all__ = [
    "ASUNCION_TZ",
    "UTC",
    "now",
    "to_asuncion",
    "to_utc",
    "today_local",
    "utcnow",
]
