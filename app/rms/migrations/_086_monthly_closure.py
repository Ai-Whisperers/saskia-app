"""Migration 086: Create monthly_closure table.

Sprint 3.1: Expense CRUD + MonthlyClosure

Creates the monthly_closure table to track closed accounting periods:
- period_yyyymm: VARCHAR(7) PRIMARY KEY — YYYY-MM format
- closed_at, closed_by_user_id: when and by whom the period was closed
- total_iva_gs, total_revenue_gs, total_cogs_gs, total_expenses_gs, net_gs: financial metrics
- snapshot_json: TEXT — JSON of full snapshot for audit
- reopened_at, reopened_by_user_id, reopen_reason: reopen audit trail
"""

from typing import Any


def _migration_086_monthly_closure(conn: Any) -> None:
    """Create monthly_closure table."""
    from sqlalchemy import text

    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"

    if dialect == "postgresql":
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS monthly_closure (
                    id SERIAL PRIMARY KEY,
                    period_yyyymm VARCHAR(7) NOT NULL UNIQUE,
                    closed_at TIMESTAMP WITH TIME ZONE,
                    closed_by_user_id VARCHAR(64),
                    total_iva_gs INTEGER DEFAULT 0 NOT NULL,
                    total_revenue_gs INTEGER DEFAULT 0 NOT NULL,
                    total_cogs_gs INTEGER DEFAULT 0 NOT NULL,
                    total_expenses_gs INTEGER DEFAULT 0 NOT NULL,
                    net_gs INTEGER DEFAULT 0 NOT NULL,
                    snapshot_json TEXT,
                    reopened_at TIMESTAMP WITH TIME ZONE,
                    reopened_by_user_id VARCHAR(64),
                    reopen_reason VARCHAR(255),
                    CONSTRAINT ck_monthly_closure_period_format CHECK (length(period_yyyymm) = 7)
                )
                """
            )
        )
    else:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS monthly_closure (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    period_yyyymm TEXT NOT NULL UNIQUE,
                    closed_at TEXT,
                    closed_by_user_id TEXT,
                    total_iva_gs INTEGER DEFAULT 0 NOT NULL,
                    total_revenue_gs INTEGER DEFAULT 0 NOT NULL,
                    total_cogs_gs INTEGER DEFAULT 0 NOT NULL,
                    total_expenses_gs INTEGER DEFAULT 0 NOT NULL,
                    net_gs INTEGER DEFAULT 0 NOT NULL,
                    snapshot_json TEXT,
                    reopened_at TEXT,
                    reopened_by_user_id TEXT,
                    reopen_reason TEXT,
                    CONSTRAINT ck_monthly_closure_period_format CHECK (length(period_yyyymm) = 7)
                )
                """
            )
        )

    # BACKLOG #4 (2026-10-02): migrations 085+ shipped without bumping
    # schema_version, silently breaking fresh installs. Sprint 4.5 fixed.
    from app.rms.db import _bump_schema_version
    _bump_schema_version(conn, 86)