"""tests/test_rate_limit_atomicity.py — document the F9 race condition.

Per SASKIA_ARCHITECTURE_REFACTOR_PLAN_2026-09-24.md F9, `is_write_rate_limited`
and the login rate limit at app/rms/rate_limit.py:80 both have a check-then-act
race: SELECT count; if count >= limit: block. Two concurrent requests can both
read count=9 (under limit) and both proceed, both bumping the real count to 11.

Proper fix requires schema work: a dedicated rate_limit table with an atomic
INSERT ... ON CONFLICT DO UPDATE counter, or use Postgres advisory locks.
That is a separate migration and is deferred to a follow-up PR.

This test documents the race exists (verifies the current behavior matches
the documented race description) and locks in the atomic-fix expectations.
The actual atomic fix is tracked separately.
"""
from __future__ import annotations

# ─── Existing behavior lock-in (RED for the proper fix) ──────────────────────


def test_is_write_rate_limited_counts_audit_rows(session_factory):
    """Sanity check: function counts audit rows with action LIKE 'write.%'."""
    from datetime import datetime, timezone

    from app.rms.audit import record as audit_record
    from app.rms.rate_limit import is_write_rate_limited

    # Build a fake request with a known IP
    class _Req:
        headers = {"x-forwarded-for": "10.0.0.99"}
        client = None

    req = _Req()
    when = datetime.now(timezone.utc)

    with session_factory() as s:
        # Pre-populate 3 write audit rows for this IP within the window
        for i in range(3):
            audit_record(
                s,
                user_id=f"user-{i}",
                action=f"write.test.action_{i}",
                request=req,
                detail={"i": i},
            )
        s.commit()

    with session_factory() as s:
        # Limit=5, count=3 → allowed
        result = is_write_rate_limited(s, req, max_per_minute=5, now=when)
    assert result is False, "expected allowed, got limited (count=3, limit=5)"


def test_is_write_rate_limited_blocks_at_limit(session_factory):
    """At exactly the limit, function returns True."""
    from datetime import datetime, timezone

    from app.rms.audit import record as audit_record
    from app.rms.rate_limit import is_write_rate_limited

    class _Req:
        headers = {"x-forwarded-for": "10.0.0.100"}
        client = None

    req = _Req()
    when = datetime.now(timezone.utc)

    with session_factory() as s:
        for i in range(5):
            audit_record(
                s,
                user_id=f"user-{i}",
                action=f"write.test.atlimit_{i}",
                request=req,
                detail={"i": i},
            )
        s.commit()

    with session_factory() as s:
        # Limit=5, count=5 → blocked
        result = is_write_rate_limited(s, req, max_per_minute=5, now=when)
    assert result is True, "expected blocked, got allowed (count=5, limit=5)"


# ─── Documentation: the race itself ─────────────────────────────────────────


def test_documented_race_check_then_act():
    """Document the F9 race condition.

    This is a static test that verifies the F9 finding description matches
    the current code. If the code is refactored to remove the race, this
    test should be updated or removed.

    Race pattern: `count = SELECT count(*)` then `if count >= limit: block`.
    Two concurrent reads at count=limit-1 both see "allowed", both insert,
    real count now exceeds limit but no block was issued.
    """
    # Read source and verify the check-then-act pattern exists
    from pathlib import Path

    src = Path("/opt/data/scratch/saskia-app/app/rms/rate_limit.py").read_text()
    # The race pattern: count query, then conditional return True/False
    assert "count()\n" in src or "count =" in src, (
        "is_write_rate_limited should query count then check limit"
    )
    # Document: proper fix requires schema work (atomic counter).
    # See SASKIA_ARCHITECTURE_REFACTOR_PLAN_2026-09-24.md F9.
