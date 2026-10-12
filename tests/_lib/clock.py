"""tests/_lib/clock.py — Time/clock helpers for deterministic tests.

Replaces 481+ `datetime.now()` calls scattered across tests with a
deterministic clock fixture and helper functions.

Usage:
    from tests._lib.clock import asuncion_now, FROZEN_ASUNCION, FROZEN_NOW
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

# Asuncion is UTC-4 (no DST)
ASUNCION = ZoneInfo("America/Asuncion")
UTC = timezone.utc

# Frozen clock values for tests
FROZEN_ASUNCION = datetime(2026, 10, 1, 12, 0, 0, tzinfo=ASUNCION)
FROZEN_NOW = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)
FROZEN_TS = FROZEN_NOW.timestamp()


def asuncion_now() -> datetime:
    """Current time in America/Asuncion timezone (UTC-4, no DST)."""
    return datetime.now(ASUNCION)


def asuncion_today() -> date:
    """Today's date in Asuncion."""
    return asuncion_now().date()


def utc_now() -> datetime:
    """Current UTC time (tz-aware)."""
    return datetime.now(UTC)


def iso_now() -> str:
    """Current UTC time as ISO string."""
    return utc_now().isoformat()


class FrozenClock:
    """A clock that always returns the same time.

    Use the `freeze_asuncion` fixture from conftest.py for the standard one.
    This class is for ad-hoc use in tests.
    """

    def __init__(self, when: Optional[datetime] = None):
        self._when = when or FROZEN_NOW

    def utcnow(self) -> datetime:
        return self._when

    def now(self, tz: Optional[ZoneInfo] = None) -> datetime:
        if tz is None:
            return self._when
        return self._when.astimezone(tz)

    def asuncion(self) -> datetime:
        return self._when.astimezone(ASUNCION)

    @property
    def timestamp(self) -> float:
        return self._when.timestamp()

    def advance(self, **kwargs) -> "FrozenClock":
        """Return a new clock advanced by timedelta kwargs (days=, hours=, etc)."""
        return FrozenClock(self._when + timedelta(**kwargs))


__all__ = [
    "ASUNCION",
    "FROZEN_ASUNCION",
    "FROZEN_NOW",
    "FROZEN_TS",
    "UTC",
    "FrozenClock",
    "asuncion_now",
    "asuncion_today",
    "iso_now",
    "utc_now",
]
