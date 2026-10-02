"""Migration 085: Add recurring_period and receipt_url to expense table.

Sprint 3.1: Expense CRUD + MonthlyClosure

Adds two optional columns to the expense table:
- recurring_period: VARCHAR(32) — 'once' | 'monthly' | 'quarterly' | 'yearly'
- receipt_url: VARCHAR(512) — URL to uploaded receipt image (nullable)

Both columns are nullable for backwards compatibility.
"""

from typing import Any

from sqlalchemy import text


def _migration_093_expense_receipt_recurring(conn: Any) -> None:
    """Add recurring_period and receipt_url columns to expense table.

    Idempotent: checks for column existence before adding.
    """
    from app.rms.db import atomic_ddl_block

    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"

    # Check existing columns
    if dialect == "postgresql":
        existing_cols = conn.execute(
            text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'expense'
            """)
        ).fetchall()
        existing = {row[0] for row in existing_cols}
    else:
        existing_cols = conn.execute(text("PRAGMA table_info(expense)")).fetchall()
        # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
        existing = {row[1] for row in existing_cols}

    # BACKLOG #4 (2026-10-02): wrap each ADD COLUMN in atomic_ddl_block so
    # Postgres DDL auto-commits are isolated per-statement.
    if "recurring_period" not in existing:
        atomic_ddl_block(conn, [
            "ALTER TABLE expense ADD COLUMN recurring_period VARCHAR(32) "
            "DEFAULT 'once' NOT NULL"
        ])

    if "receipt_url" not in existing:
        atomic_ddl_block(conn, [
            "ALTER TABLE expense ADD COLUMN receipt_url VARCHAR(512)"
        ])

    # BACKLOG #4 (2026-10-02): migrations 085+ shipped without bumping
    # schema_version, silently breaking fresh installs. Sprint 4.5 fixed
    # this — each migration MUST bump its own version.
    from app.rms.db import _bump_schema_version
    _bump_schema_version(conn, 93)