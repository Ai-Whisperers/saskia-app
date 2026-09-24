"""app/rms/date_presets.py — Date range preset helpers (Phase 9).

Replaces the hardcoded DATE_RANGE_PRESETS_DAYS dict in
app/rms/constants.py. Operators add/edit presets from
/settings/catalog without code deploy.

Used by date-filter chips in dashboard / reportes / audit.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import DateRangePreset


def list_presets(session: Session, include_inactive: bool = False) -> list[DateRangePreset]:
    """Return all date range presets sorted by sort_order."""
    q = select(DateRangePreset)
    if not include_inactive:
        q = q.where(DateRangePreset.is_active.is_(True))
    q = q.order_by(DateRangePreset.sort_order.asc(), DateRangePreset.code.asc())
    return list(session.execute(q).scalars())


def get_preset_days(session: Session, code: str) -> int | None:
    """Return the days value for a preset code (or None if missing/inactive).

    Callers use this in timedelta(days=N) calls — defaults to 30 if the
    preset is missing so a stale UI doesn't break the report.
    """
    row = session.execute(
        select(DateRangePreset).where(
            DateRangePreset.code == code,
            DateRangePreset.is_active.is_(True),
        )
    ).scalar_one_or_none()
    return row.days if row else None


def get_default_preset(session: Session) -> DateRangePreset | None:
    """Return the preset marked is_default=True (or the first one)."""
    row = session.execute(
        select(DateRangePreset).where(
            DateRangePreset.is_default.is_(True),
            DateRangePreset.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if row is None:
        row = session.execute(
            select(DateRangePreset).where(DateRangePreset.is_active.is_(True))
            .order_by(DateRangePreset.sort_order.asc())
        ).scalars().first()
    return row


__all__ = [
    "list_presets",
    "get_preset_days",
    "get_default_preset",
]
