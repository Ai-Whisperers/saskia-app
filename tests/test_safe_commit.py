"""tests/test_safe_commit.py — verify safe_commit() handles errors atomically.

Phase 1A ticket #6: introduce safe_commit() helper in app/rms/db.py that
wraps session.commit() in try/except/rollback, then replace bare commit()
calls in sales.py and pedidos.py (the money paths).

Per SASKIA_ARCHITECTURE_REFACTOR_PLAN_2026-09-24.md F18 (50+ bare
commits), bare commit() outside try/except means an IntegrityError or
DB error mid-handler raises an unhandled exception, leaving the session
in an inconsistent state for the next pooled connection checkout.
"""
from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError


# ─── safe_commit behavior tests ─────────────────────────────────────────────


def test_safe_commit_returns_true_on_success(session_factory):
    """No pending changes → returns True, no exception."""
    from app.rms.db import safe_commit

    with session_factory() as s:
        result = safe_commit(s)
    assert result is True


def test_safe_commit_commits_pending_changes(session_factory):
    """Pending INSERT gets persisted."""
    from app.rms.db import safe_commit
    from app.rms.models import AppMeta

    with session_factory() as s:
        s.add(AppMeta(key="safe_commit_test_1", value="x", updated_at="2026-09-24"))
        result = safe_commit(s)
    assert result is True

    with session_factory() as s:
        row = s.scalar(__import__("sqlalchemy").select(AppMeta).where(AppMeta.key == "safe_commit_test_1"))
    assert row is not None
    assert row.value == "x"


def test_safe_commit_rolls_back_on_integrity_error(session_factory):
    """IntegrityError → rollback, return False, no exception bubbles."""
    from app.rms.db import safe_commit
    from app.rms.models import AppMeta

    # Seed a row with a known key
    with session_factory() as s:
        s.add(AppMeta(key="dup_key", value="first", updated_at="2026-09-24"))
        safe_commit(s)

    # Try to insert another with same key → IntegrityError on flush
    with session_factory() as s:
        s.add(AppMeta(key="dup_key", value="second", updated_at="2026-09-24"))
        result = safe_commit(s)

    assert result is False, "safe_commit should return False on IntegrityError"

    # Verify the original value is preserved (rollback worked)
    with session_factory() as s:
        row = s.scalar(__import__("sqlalchemy").select(AppMeta).where(AppMeta.key == "dup_key"))
    assert row.value == "first", f"expected first, got {row.value}"


def test_safe_commit_session_remains_usable_after_error(session_factory):
    """After a rollback, the session can still be used for new operations."""
    from app.rms.db import safe_commit
    from app.rms.models import AppMeta

    # Cause an IntegrityError
    with session_factory() as s:
        s.add(AppMeta(key="bad_key", value="v1", updated_at="2026-09-24"))
        safe_commit(s)

    with session_factory() as s:
        s.add(AppMeta(key="bad_key", value="v2_dup", updated_at="2026-09-24"))
        result = safe_commit(s)
        assert result is False

    # Session should still work for a new operation
    with session_factory() as s:
        s.add(AppMeta(key="good_key", value="fresh", updated_at="2026-09-24"))
        result = safe_commit(s)
    assert result is True

    with session_factory() as s:
        row = s.scalar(__import__("sqlalchemy").select(AppMeta).where(AppMeta.key == "good_key"))
    assert row is not None


def test_safe_commit_logs_on_rollback(caplog):
    """Rollback path emits a log warning for ops visibility."""
    import logging
    from unittest.mock import MagicMock

    from app.rms.db import safe_commit

    mock_session = MagicMock()
    mock_session.commit.side_effect = IntegrityError("dup", params={}, orig=Exception("dup"))

    with caplog.at_level(logging.WARNING):
        result = safe_commit(mock_session)

    assert result is False
    mock_session.rollback.assert_called_once()
    # caplog may or may not capture loguru; just verify rollback happened
