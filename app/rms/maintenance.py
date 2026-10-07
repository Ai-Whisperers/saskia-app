"""app/rms/maintenance.py — periodic housekeeping for the production DB.

This module contains idempotent, safe-to-run-again operations for
free-tier hosted Neon Postgres. Each function:
- Fails open (returns silently on DB errors, doesn't raise)
- Is logged for auditability
- Uses session_factory() so it works on both SQLite (tests) and Postgres (prod)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable


def prune_audit_log(
    session_factory: Callable,
    *,
    retention_days: int = 30,
    dry_run: bool = False,
) -> int:
    """Delete audit_log rows older than retention_days.

    Returns the count deleted. Use dry_run=True to report only.

    Free-tier Neon gets expensive when audit_log grows unbounded
    (1k errors/day = 365k rows/year). This is the operator's hammer.

    Defaults to 30 days — long enough for incident investigation,
    short enough to keep the DB lean.

    Fail-soft: if the DB raises, returns 0. The operator's archive
    script (`scripts/audit_prune.py`) handles errors loudly.
    """
    from sqlalchemy import delete, func, select

    try:
        from app.rms.models import AuditLog

        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        with session_factory() as s:
            if dry_run:
                n = (
                    s.execute(
                        select(func.count())
                        .select_from(AuditLog)
                        .where(AuditLog.occurred_at < cutoff)
                    ).scalar()
                    or 0
                )
            else:
                result = s.execute(delete(AuditLog).where(AuditLog.occurred_at < cutoff))
                n = result.rowcount or 0
                s.commit()
        return int(n)
    except Exception as exc:
        # Fail-soft: log the exception but return 0.
        from loguru import logger

        logger.warning(f"prune_audit_log failed: {exc!r}")
        return 0


__all__ = [
    "prune_audit_log",
]
