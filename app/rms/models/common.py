"""app/rms/models/common.py — Common field definitions and types.

Phase 2B: Structural refactoring for domain-driven design.

This module provides common field definitions and types used across
multiple domains to ensure consistency and reduce duplication.

Sprint 3.2: added SoftDeletable + AuditColumns mixins for soft-delete
+ audit-column support on owned tables.
"""

from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from sqlalchemy import DateTime, Float, String, event
from sqlalchemy.orm import Mapped, mapped_column

# Common timestamp fields with consistent typing
CreatedTimestamp = Annotated[datetime, mapped_column(DateTime, nullable=False, default=datetime.now)]
UpdatedTimestamp = Annotated[datetime, mapped_column(DateTime, nullable=False, default=datetime.now)]

# Common price field (consistent across all domains)
PriceGs = Annotated[float, mapped_column(Float, nullable=False, default=0.0)]


class CommonFieldsMixin:
    """Mixin class providing common fields for models that need them."""

    created_at: Mapped[CreatedTimestamp]
    updated_at: Mapped[UpdatedTimestamp]

    # Optional price field for domain models that need it
    price_gs: Mapped[PriceGs] | Mapped[int] | None = None


# ─── Sprint 3.2: SoftDeletable + AuditColumns mixins ─────────────────────


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SoftDeletable:
    """Mixin: rows are archived, not deleted.

    Tables that include this mixin get:
    - ``deleted_at``: UTC timestamp when archived (NULL = active)
    - ``deleted_by_user_id``: who archived it (TEXT for Supabase UUID or int)

    Application code calls ``session.add(instance)`` after setting
    ``deleted_at``; never ``session.delete(instance)``.

    The ``is_active`` property returns ``deleted_at is None``.
    """

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, default=None, index=True
    )
    deleted_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, default=None
    )

    @property
    def is_active(self) -> bool:
        return self.deleted_at is None


class AuditColumns:
    """Mixin: who created/updated a row, and when.

    SQLAlchemy ``before_insert`` / ``before_update`` events
    (registered by :func:`register_audit_event_listeners`) auto-fill
    ``created_at`` / ``updated_at``. Application code sets
    ``*_by_user_id`` explicitly.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
    created_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, default=None
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )
    updated_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, default=None
    )


def register_audit_event_listeners() -> None:
    """Register ``before_insert`` / ``before_update`` listeners on all
    mapped classes that include :class:`AuditColumns`.

    Called once from ``app.rms.db`` after init_db. Idempotent via a
    module-level flag.

    The listeners set ``created_at`` / ``updated_at`` only if the
    application code did not provide one (so tests can pin a fixed
    timestamp).
    """
    if getattr(register_audit_event_listeners, "_registered", False):
        return

    def _before_insert(mapper: Any, connection: Any, target: Any) -> None:
        if isinstance(target, AuditColumns):
            now = _utcnow()
            if target.created_at is None:
                target.created_at = now
            if target.updated_at is None:
                target.updated_at = now

    def _before_update(mapper: Any, connection: Any, target: Any) -> None:
        if isinstance(target, AuditColumns):
            target.updated_at = _utcnow()

    from app.rms.models import Base  # local import to avoid cycle

    for mapper in Base.registry.mappers:
        cls = mapper.class_
        if not issubclass(cls, AuditColumns):
            continue
        event.listen(cls, "before_insert", _before_insert)
        event.listen(cls, "before_update", _before_update)

    register_audit_event_listeners._registered = True


__all__ = [
    "AuditColumns",
    "CommonFieldsMixin",
    "CreatedTimestamp",
    "PriceGs",
    "SoftDeletable",
    "UpdatedTimestamp",
    "register_audit_event_listeners",
]
