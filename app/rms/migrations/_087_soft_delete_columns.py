"""Migration 087: Soft delete columns on owned tables (Sprint 3.2).

Adds ``deleted_at`` + ``deleted_by_user_id`` to the tables that the
business considers "owned records" (not log/event tables). NULL
values mean the record is active; non-NULL means archived.

Tables affected: ingredient, product, recipe, customer, supplier.
Excludes: audit_log, communication_log, etc.

Phase 2B: This aligns with the domain-driven design principles where
user-facing data follows soft-delete patterns.

Implementation strategy:
1. Add columns with NULL default (backwards compatible)
2. Set ``is_active`` property on models (via SoftDeletable mixin)
3. Application logic: never use DELETE; set deleted_at + save
"""

from datetime import datetime
from datetime import timezone
from typing import Any, Optional

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.rms.models.common import SoftDeletable

# Who archived the record - text to support both Supabase UUID and local int
ArchivedByUserId: Mapped[Optional[str]] = mapped_column(
    String(64), nullable=True, default=None
)
# When archived - UTC timestamp for consistency  
ArchivedAt: Mapped[Optional[datetime]] = mapped_column(
    DateTime(timezone=True), nullable=True, default=None, index=True
)


def _migration_087_soft_delete_columns(conn: Any) -> None:
    """Add soft-delete columns to owned tables.

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
            conn.execute(
                f"ALTER TABLE {table} ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE"
            )
            conn.execute(
                f"ALTER TABLE {table} ADD COLUMN deleted_by_user_id VARCHAR(64)"
            )
            print(f"Added soft-delete columns to {table}")
        except Exception as exc:
            # Column likely already exists - idempotent continue
            print(f"Soft-delete columns exist on {table}: {exc}")
    
    # Set index on deleted_at for performance
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_deleted_at ON ingredient(deleted_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_deleted_at ON product(deleted_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_deleted_at ON recipe(deleted_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_deleted_at ON customer(deleted_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_deleted_at ON supplier(deleted_at)")
        print("Created deleted_at indexes")
    except Exception as exc:
        print(f"Indexes may already exist: {exc}")


__all__ = ["ArchivedAt", "ArchivedByUserId"]