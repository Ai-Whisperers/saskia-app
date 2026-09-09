"""tests/test_audit_prune.py — retention policy deletes rows older than N days.

Audit log grows unbounded. 1k errors/day = 365k rows/year. Free-tier
Neon shouldn't be loaded with archival data. This module keeps
the table bounded.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def test_prune_keeps_recent_deletes_old(session_factory):
    """Rows older than retention_days are deleted; recent are preserved."""
    from app.rms.models import AuditLog

    with session_factory() as s:
        now = datetime.now(timezone.utc)
        s.add(AuditLog(occurred_at=now, action="keep_recent", user_id=None))
        s.add(AuditLog(occurred_at=now - timedelta(days=10), action="keep_week_ago", user_id=None))
        s.add(AuditLog(occurred_at=now - timedelta(days=45), action="delete_old", user_id=None))
        s.commit()

    from app.rms.maintenance import prune_audit_log
    n = prune_audit_log(session_factory, retention_days=30)

    assert n == 1  # one row deleted
    with session_factory() as s:
        rows = s.query(AuditLog).all()
        actions = sorted([r.action for r in rows])
        # The two recent rows survive; the 45-day-old row is gone.
        assert actions == ["keep_recent", "keep_week_ago"]


def test_prune_dry_run_does_not_delete(session_factory):
    """Dry run reports what would be deleted without removing anything."""
    from app.rms.models import AuditLog

    with session_factory() as s:
        for _ in range(3):
            s.add(AuditLog(
                occurred_at=datetime.now(timezone.utc) - timedelta(days=60),
                action="old_row",
                user_id=None,
            ))
        s.commit()

    from app.rms.maintenance import prune_audit_log
    n = prune_audit_log(session_factory, retention_days=30, dry_run=True)
    assert n == 3
    # All 3 still present.
    with session_factory() as s:
        assert s.query(AuditLog).count() == 3


def test_prune_zero_retention_keeps_nothing_old(session_factory):
    """retention_days=0 deletes everything except very-recent rows.

    Useful for emergency cleanup, not for normal operation.
    """
    from app.rms.models import AuditLog

    with session_factory() as s:
        s.add(AuditLog(occurred_at=datetime.now(timezone.utc), action="today", user_id=None))
        s.add(AuditLog(occurred_at=datetime.now(timezone.utc) - timedelta(hours=1), action="hour", user_id=None))
        s.add(AuditLog(occurred_at=datetime.now(timezone.utc) - timedelta(days=2), action="two_days", user_id=None))
        s.commit()

    from app.rms.maintenance import prune_audit_log
    # retention_days=1 keeps things 1+ day old only; the 2-day-old goes.
    n = prune_audit_log(session_factory, retention_days=1)
    assert n == 1


def test_prune_db_failure_doesnt_crash():
    """If the DB raises, prune must return 0 (fail-soft)."""
    from app.rms.maintenance import prune_audit_log

    # Pass a bad factory — one that errors.
    class BadFactory:
        def __call__(self):
            raise RuntimeError("DB down")

    # Should not raise — should return 0.
    n = prune_audit_log(BadFactory(), retention_days=30, dry_run=False)
    assert n == 0
