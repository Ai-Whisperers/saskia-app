"""Migration 088: Audit columns on owned tables (Sprint 3.2).

Adds ``created_at`` / ``created_by_user_id`` / ``updated_at`` /
``updated_by_user_id`` to the owned tables. ``created_at`` is preserved
if set (test scenarios), otherwise auto-populated by the audit event
listeners.

Tables affected: ingredient, product, recipe, customer, supplier.
Excludes: audit_log, communication_log, etc.

Phase 2B: Implements auditability for domain entities. The
``register_audit_event_listeners()`` in app.rms.models.common auto-fills
timestamps on insert/update if not explicitly set.

Implementation strategy:
1. Add columns with sensible defaults
2. Register event listeners that auto-populate if not set
3. Application code sets ``*_by_user_id`` explicitly
"""

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column

# Standard audit field types for consistency
CreatedTimestamp: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc)
)
UpdatedTimestamp: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    nullable=False,
    default=datetime.now(timezone.utc),
    onupdate=datetime.now(timezone.utc),
)
CreatedByUserId: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, default=None)
UpdatedByUserId: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, default=None)


def _migration_096_audit_columns(conn: Any) -> None:
    """Add audit columns to owned tables.

    Applies to:
    - Ingredient (ingredient)
    - Product (product)
    - Recipe (recipe)
    - Customer (customer)
    - Supplier (supplier)

    Excludes audit/event tables.
    """
    # NOTE: These table names must match actual SQLAlchemy model table names
    owned_tables = ["ingredient", "product", "recipe", "customer", "supplier"]

    # Add columns if they don't exist (idempotent)
    for table in owned_tables:
        try:
            # Standard audit columns
            # T-2026-10-04: wrap in text() — SQLAlchemy 2.0 requires SQL
            # expressions, not raw strings, for conn.execute().
            conn.execute(
                text(
                    f"ALTER TABLE {table} ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP"
                )
            )
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN created_by_user_id VARCHAR(64)"))
            conn.execute(
                text(
                    f"ALTER TABLE {table} ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP"
                )
            )
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN updated_by_user_id VARCHAR(64)"))
            print(f"Added audit columns to {table}")
        except Exception as exc:
            # Columns likely already exist - idempotent continue
            print(f"Audit columns exist on {table}: {exc}")

    # Set indexes for performance on timestamp columns
    try:
        for table in owned_tables:
            conn.execute(
                text(f"CREATE INDEX IF NOT EXISTS idx_{table}_created ON {table}(created_at)")
            )
            conn.execute(
                text(f"CREATE INDEX IF NOT EXISTS idx_{table}_updated ON {table}(updated_at)")
            )
    except Exception:  # noqa: S110 — Indexes may already exist from a partial migration run; ignore.
        pass

    # BACKLOG #4 (2026-10-02): migrations 085+ shipped without bumping
    # schema_version, silently breaking fresh installs. Sprint 4.5 fixed.
    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 96)


__all__ = ["CreatedByUserId", "CreatedTimestamp", "UpdatedByUserId", "UpdatedTimestamp"]
