"""tests/test_rate_limit.py — verify /login is rate-limited after N failures.

Per the 2026-09-04 critical-path plan, E3.S2.

Covers:
- Below threshold: requests pass through to login_submit
- At/above threshold: 429 + Retry-After header
- login.rate_limited audit row written for forensics
- Sliding window: old failures expire and the IP is unblocked
- AIW_SASKIA_AUTH_DISABLED=1 bypasses the limit (test/maintenance)
- /healthz is NEVER rate-limited (UptimeRobot fires every 5 min)
- Fail-open behavior: if the DB raises, login proceeds
- Different IPs tracked separately (no false positives)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.security


def _make_request(ip="203.0.113.1"):
    """Build a fake Request with the X-Forwarded-For IP set."""
    from starlette.requests import Request as StarletteRequest

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/login",
        "headers": [(b"x-forwarded-for", ip.encode())],
        "client": ("127.0.0.1", 50000),
        "query_string": b"",
    }
    return StarletteRequest(scope)


def test_below_threshold_passes(session_factory):
    """is_rate_limited returns allowed=True when count < limit."""
    from app.rms.rate_limit import DEFAULT_LIMIT, is_rate_limited

    req = _make_request("203.0.113.10")
    decision = is_rate_limited(session_factory(), req)
    assert decision.allowed is True
    assert decision.current_count == 0
    assert decision.limit == DEFAULT_LIMIT


def test_at_threshold_blocks(session_factory):
    """After LIMIT failed logins from the same IP, is_rate_limited blocks."""
    from app.rms.audit import record as audit_record
    from app.rms.rate_limit import DEFAULT_LIMIT, is_rate_limited

    ip = "203.0.113.20"
    req = _make_request(ip)
    with session_factory() as s:
        for i in range(DEFAULT_LIMIT):
            audit_record(
                s,
                user_id=None,
                action="login.failure",
                request=req,
                detail={"i": i},
            )
        s.commit()

        decision = is_rate_limited(s, req)
        assert decision.allowed is False
        assert decision.current_count == DEFAULT_LIMIT
        assert decision.retry_after_seconds > 0


def test_block_writes_audit_row(session_factory):
    """A blocked request creates a login.rate_limited audit row."""
    from app.rms.audit import record as audit_record
    from app.rms.models import AuditLog
    from app.rms.rate_limit import DEFAULT_LIMIT, is_rate_limited

    ip = "203.0.113.30"
    req = _make_request(ip)
    with session_factory() as s:
        for i in range(DEFAULT_LIMIT):
            audit_record(s, user_id=None, action="login.failure", request=req)
        s.commit()

        is_rate_limited(s, req)  # blocked, writes audit row

        rows = (
            s.query(AuditLog).filter(AuditLog.action == "login.rate_limited").all()
        )
        assert len(rows) == 1
        assert rows[0].ip == ip
        assert rows[0].detail["limit"] == DEFAULT_LIMIT
        assert rows[0].detail["observed_count"] == DEFAULT_LIMIT


def test_sliding_window_expires_old_failures(session_factory):
    """Failures older than the window do NOT count toward the limit."""
    from app.rms.audit import record as audit_record
    from app.rms.models import AuditLog
    from app.rms.rate_limit import is_rate_limited

    ip = "203.0.113.40"
    req = _make_request(ip)

    # Insert LIMIT-1 old failures (10 min ago) + 1 fresh failure (just now)
    with session_factory() as s:
        for i in range(5):
            audit_record(s, user_id=None, action="login.failure", request=req)
        s.commit()

        # Backdate all to 10 minutes ago
        ten_min_ago = datetime.now(timezone.utc) - timedelta(minutes=10)
        s.query(AuditLog).filter(AuditLog.ip == ip).update(
            {"occurred_at": ten_min_ago}
        )
        s.commit()

        # Now (within 5-min window), no recent failures → allowed
        decision = is_rate_limited(s, req)
        assert decision.allowed is True
        assert decision.current_count == 0


def test_different_ips_tracked_separately(session_factory):
    """Limit applies per-IP, not globally."""
    from app.rms.audit import record as audit_record
    from app.rms.rate_limit import DEFAULT_LIMIT, is_rate_limited

    alice = _make_request("198.51.100.1")
    bob = _make_request("198.51.100.2")

    with session_factory() as s:
        # Alice hits the limit
        for i in range(DEFAULT_LIMIT):
            audit_record(s, user_id=None, action="login.failure", request=alice)
        s.commit()

        # Bob has zero failures
        decision = is_rate_limited(s, bob)
        assert decision.allowed is True
        assert decision.current_count == 0

        # Alice is still blocked
        decision_a = is_rate_limited(s, alice)
        assert decision_a.allowed is False


def test_disabled_via_env_var(monkeypatch):
    """AIW_SASKIA_AUTH_DISABLED=1 bypasses the limiter entirely."""
    from app.rms.rate_limit import is_disabled

    monkeypatch.setenv("AIW_SASKIA_AUTH_DISABLED", "true")
    assert is_disabled() is True

    monkeypatch.setenv("AIW_SASKIA_AUTH_DISABLED", "0")
    assert is_disabled() is False

    monkeypatch.delenv("AIW_SASKIA_AUTH_DISABLED", raising=False)
    assert is_disabled() is False


def test_healthz_never_rate_limited(client):
    """/healthz MUST NOT be rate-limited even after many hits (UptimeRobot)."""
    for _ in range(50):
        r = client.get("/healthz")
        assert r.status_code == 200, f"got {r.status_code} after repeated /healthz"


def test_login_returns_429_after_failures(session_factory, monkeypatch):
    """End-to-end: 5 wrong passwords → 6th request gets 429.

    Note: this test exercises is_rate_limited() directly (no TestClient)
    because the rate-limiter and the /login route are tested separately.
    The unit test below verifies that login_submit returns 429 when
    is_rate_limited blocks.

    Suite isolation: each test uses session_factory (autouse reset_app_state
    wipes app.state between tests) and a unique IP. The in-memory DB is
    wiped between tests via tmp_db_path so audit rows do not leak.
    """
    from datetime import datetime

    from app.rms.audit import record as audit_record
    from app.rms.models import AuditLog, User
    from app.rms.rate_limit import is_rate_limited

    monkeypatch.setenv("AIW_SASKIA_AUTH_DISABLED", "")

    test_ip = "203.0.113.99-unique-to-rl-test"
    req = _make_request(test_ip)

    with session_factory() as s:
        u = User(
            username="rl-test",
            password_hash="$2b$12$abcdefghijklmnopqrstuv1234567890ABCDEFGHIJKLMNOPQRSTUxy",
            is_active=True,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        s.add(u)
        s.commit()

        # Simulate 5 failed login attempts writing audit rows
        for i in range(5):
            audit_record(s, user_id=None, action="login.failure", request=req)
        s.commit()

        # Now check the limiter blocks the 6th request
        decision = is_rate_limited(s, req)
        assert decision.allowed is False
        assert decision.current_count >= 5

        # Verify the rate-limited audit row was written
        rows = (
            s.query(AuditLog)
            .filter(AuditLog.action == "login.rate_limited")
            .all()
        )
        assert len(rows) == 1


def test_login_submit_returns_429_when_limiter_blocks(client, session_factory, monkeypatch):
    """End-to-end: login_submit returns 429 with Retry-After header when blocked.

    This is the thin glue test that verifies the rate-limiter integrates with
    the login route. Uses fresh seed + unique IP for isolation.
    """
    from datetime import datetime

    from app.rms.audit import record as audit_record
    from app.rms.models import AuditLog, User

    monkeypatch.setenv("AIW_SASKIA_AUTH_DISABLED", "")

    test_ip = "203.0.113.99-unique-rl-glue"

    with session_factory() as s:
        u = User(
            username="rl-glue-test",
            password_hash="$2b$12$abcdefghijklmnopqrstuv1234567890ABCDEFGHIJKLMNOPQRSTUxy",
            is_active=True,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        s.add(u)

        # Pre-populate 5 failures from the test IP
        req = _make_request(test_ip)
        for _ in range(5):
            audit_record(s, user_id=None, action="login.failure", request=req)
        s.commit()

    # Now POST /login with wrong password from the same IP
    r = client.post(
        "/login",
        data={"username": "rl-glue-test", "password": "wrong"},
        headers={"X-Forwarded-For": test_ip},
        follow_redirects=False,
    )
    assert r.status_code == 429, f"expected 429, got {r.status_code}"
    assert "Retry-After" in r.headers
    # Confirm audit row written
    with session_factory() as s:
        rl_rows = s.query(AuditLog).filter(
            AuditLog.action == "login.rate_limited",
            AuditLog.ip == test_ip,
        ).all()
        assert len(rl_rows) >= 1


def test_fail_open_on_db_error(session_factory, monkeypatch):
    """If the DB raises during count, login proceeds (fail-open).

    Per the rate_limit.py docstring: failing closed would lock all users
    out during a DB outage. We accept that one attacker may slip through
    during such an outage in exchange for not bricking production.
    """
    from app.rms import rate_limit

    class BoomSession:
        def query(self, *args, **kwargs):
            raise RuntimeError("DB is down")

    decision = rate_limit.is_rate_limited(BoomSession(), _make_request())
    assert decision.allowed is True
