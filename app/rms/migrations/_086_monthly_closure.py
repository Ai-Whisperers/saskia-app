"""Migration 086: Create monthly_closure table.

Sprint 3.1: Expense CRUD + MonthlyClosure

Creates the monthly_closure table to track closed accounting periods:
- period: VARCHAR(7) — YYYY-MM format (primary key)
- closed_at: DATE — when the period was closed
- closed_by_user_id: VARCHAR(64) — who closed the period
- total_revenue_gs: INTEGER — revenue for the period
- total_expenses_gs: INTEGER — expenses for the period
- total_margin_gs: INTEGER — revenue - expenses
- expense_count: INTEGER — number of expenses in the period
- reopen_count: INTEGER — number of times reopened
- notes: TEXT — optional notes
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
                    period VARCHAR(7) PRIMARY KEY,
                    closed_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    closed_by_user_id VARCHAR(64) NOT NULL,
                    total_revenue_gs INTEGER DEFAULT 0,
                    total_expenses_gs INTEGER DEFAULT 0,
                    total_margin_gs INTEGER DEFAULT 0,
                    expense_count INTEGER DEFAULT 0,
                    reopen_count INTEGER DEFAULT 0 NOT NULL,
                    reopen_reason TEXT,
                    reopened_at TIMESTAMP WITH TIME ZONE,
                    reopened_by_user_id VARCHAR(64),
                    notes TEXT
                )
                """
            )
        )
    else:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS monthly_closure (
                    period TEXT PRIMARY KEY,
                    closed_at TEXT NOT NULL,
                    closed_by_user_id TEXT NOT NULL,
                    total_revenue_gs INTEGER DEFAULT 0,
                    total_expenses_gs INTEGER DEFAULT 0,
                    total_margin_gs INTEGER DEFAULT 0,
                    expense_count INTEGER DEFAULT 0,
                    reopen_count INTEGER DEFAULT 0 NOT NULL,
                    reopen_reason TEXT,
                    reopened_at TEXT,
                    reopened_by_user_id TEXT,
                    notes TEXT
                )
                """
            )
        )