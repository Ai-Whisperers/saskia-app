"""Migration 102 — denormalize entrypoint source on WasteLog.

Renumbered from upstream 072 to fit saskia-rms main which is at
schema 101. The original commit (03a0977 on feat/prod-quick-merma)
targeted schema 71 → 72, but main has progressed past that.

PROD-MERMA-2 (Batch I): adds a `source` column ('manual' |
'production') and an index. Backfills every existing row with
'manual' since all legacy rows were entered by hand (the
production-side modal was added later). This eliminates the
AuditLog join that /merma and /auditoria were doing on every read.

Test: tests/test_waste_log_source_denormalized.py (9 cases).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text


def _migration_102_waste_log_source(conn: Any) -> None:
    try:
        conn.execute(
            text(
                "ALTER TABLE waste_log ADD COLUMN source VARCHAR(32) "
                "NOT NULL DEFAULT 'manual'"
            )
        )
    except Exception:  # noqa: BLE001, S110 — column already exists
        pass
    try:
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_waste_log_source ON waste_log(source)")
        )
    except Exception:  # noqa: BLE001, S110 — index already exists
        pass
    # Defensive backfill (NOT NULL DEFAULT covers new rows, but pre-existing
    # rows on a DB where the column was added without default could be NULL).
    try:
        conn.execute(
            text("UPDATE waste_log SET source = 'manual' WHERE source IS NULL")
        )
    except Exception:  # noqa: BLE001, S110 — table empty or column absent
        pass