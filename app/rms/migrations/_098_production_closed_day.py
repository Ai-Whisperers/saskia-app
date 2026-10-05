"""Migration 098 (Part 1): production_closed_day table for holidays/no-bake dates.

T-2026-10-04 (P1): Operators need to mark a date as "closed" (holiday,
vacation, equipment failure) so the plan shows an empty day instead of
defaulting to a forecast. One row per closed date.

RECOVERED from origin/feat/phase-3-ci-cleanup (commit 6da78a4) on
2026-10-05. The branch diverged from main without being merged; the
migration ran on the prod DB while the source was lost during a
rebase. This file restores the source to align with the live schema
version (98). Idempotent: CREATE TABLE IF NOT EXISTS — safe to run
on a DB that already has the table.

Schema:
  - for_date DATE PRIMARY KEY (one row per date)
  - reason VARCHAR(120) NULL  (e.g., "Feriado", "Vacaciones")
  - closed_by VARCHAR(64) NULL
  - closed_at DATETIME NOT NULL

Why a separate table (not ProductionPlanOverride with qty=0):
  - Override is per-product; we need a whole-day flag
  - Distinct semantics: "no plan" vs "this product is 0"
  - One row per date keeps the day-view render a single LEFT JOIN
    check instead of "any override exists with qty=0?"
"""
from typing import Any

from sqlalchemy import text


def _migration_098_production_closed_day(conn: Any) -> None:
    """Create production_closed_day table (idempotent)."""
    try:
        dialect_name = conn.dialect.name
    except Exception:
        dialect_name = "sqlite"

    if dialect_name == "sqlite":
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS production_closed_day (
                for_date DATE PRIMARY KEY,
                reason VARCHAR(120),
                closed_by VARCHAR(64),
                closed_at DATETIME NOT NULL
            )
        """)
        )
    else:
        # Postgres
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS production_closed_day (
                for_date DATE PRIMARY KEY,
                reason VARCHAR(120),
                closed_by VARCHAR(64),
                closed_at TIMESTAMP NOT NULL
            )
        """)
        )

    # BACKLOG #4 (2026-10-02): always bump schema_version so fresh
    # installs sync to the right target.
    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 98)
