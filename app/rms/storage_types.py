"""app/rms/storage_types.py — HACCP storage codes helper (Phase 8).

Replaces the hardcoded _STORAGE_KEYWORDS dict in app/rms/ingredient_intel.py.
Operators add/edit storage codes from /settings/catalog without code deploy.

HACCP-relevant metadata (requires_temp_min/max, requires_humidity_max)
is preserved as columns on the storage_type table. Downstream HACCP
reports can use these flags to know which temperature/humidity fields
to surface for ingredients stored under each code.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.constants import (
    STORAGE_AMBIENT,
    STORAGE_FROZEN,
    STORAGE_REFRIGERATED,
)
from app.rms.models import StorageType


def list_storage_types(session: Session, include_inactive: bool = False) -> list[StorageType]:
    """Return all storage types sorted by sort_order."""
    q = select(StorageType)
    if not include_inactive:
        q = q.where(StorageType.is_active.is_(True))
    q = q.order_by(StorageType.sort_order.asc(), StorageType.code.asc())
    return list(session.execute(q).scalars())


def valid_storage_codes(session: Session) -> set[str]:
    """Return the set of valid storage codes for validation."""
    return {st.code for st in list_storage_types(session)}


def fallback_storage_codes() -> set[str]:
    """Default valid codes when DB isn't seeded yet (migration 047)."""
    return {STORAGE_AMBIENT, STORAGE_REFRIGERATED, STORAGE_FROZEN}


def is_valid_storage_code(session: Session, code: str) -> bool:
    """Check if `code` is a valid storage code (DB-driven, with fallback)."""
    codes = valid_storage_codes(session) or fallback_storage_codes()
    return code in codes


__all__ = [
    "fallback_storage_codes",
    "is_valid_storage_code",
    "list_storage_types",
    "valid_storage_codes",
]
