"""Migration 099: updated_at column on production_completion.

T-2026-10-04 (Tier 5-K): Two cooks editing the same shift's completion
in parallel currently do last-write-wins silently. We add a column
``updated_at`` so the form can detect "someone else saved while you
were filling it out" and show a soft warning + a refresh button.

Schema:
  - production_completion.updated_at DATETIME NOT NULL DEFAULT
    CURRENT_TIMESTAMP
  - Index on (for_date, updated_at) for "what changed since X" queries

Idempotent: try/except per column. If the column already exists, the
ALTER raises and we move on.
"""

from typing import Any

from sqlalchemy import text


def _migration_099_production_completion_updated_at(conn: Any) -> None:
    """Add updated_at column + index to production_completion."""
    try:
        dialect_name = conn.dialect.name
    except Exception:
        dialect_name = "sqlite"

    # 1) Add the column. SQLite uses TIMESTAMP; Postgres uses
    # TIMESTAMP WITH TIME ZONE to match the rest of the schema.
    if dialect_name == "sqlite":
        col_type = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
    else:
        col_type = "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP"

    try:
        conn.execute(text(f"ALTER TABLE production_completion ADD COLUMN updated_at {col_type}"))
    except Exception:
        pass

    # 2) Backfill any existing rows to "now" so we have a sensible
    # timestamp for old data. We can't recover the real updated_at
    # for past rows; we just give them a value so the column is
    # non-NULL going forward.
    try:
        conn.execute(
            text(
                "UPDATE production_completion SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"
            )
        )
    except Exception:
        pass

    # 3) Index for "what changed since X" queries.
    try:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_production_completion_updated ON production_completion(for_date, updated_at)"
            )
        )
    except Exception:
        pass

    # BACKLOG #4 (2026-10-02): migrations 085+ shipped without bumping
    # schema_version, silently breaking fresh installs. Sprint 4.5 fixed.
    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 99)
