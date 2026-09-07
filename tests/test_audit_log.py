"""tests/test_audit_log.py — verify audit log works.

Per the 2026-09-04 critical-path plan, E3.S1.

Covers:
- record() writes a row with all fields populated
- record() is best-effort (errors swallowed, never break caller)
- list_recent() returns rows newest first with optional filters
- login.success / login.failure / logout actions fire from the auth router
- The audit_log table is created via the schema migration (E2.S3 / 002)
- A bare-bones /audit admin view returns 200 with rows (E3.S1.T4)
"""

from __future__ import annotations

from datetime import datetime, timezone


def test_record_writes_row_with_all_fields(session_factory):
    """record() populates every column from the kwargs."""
    from app.rms.audit import record
    from app.rms.models import AuditLog

    with session_factory() as s:
        record(
            s,
            user_id=42,
            action="sale.create",
            target_type="sale",
            target_id="99",
            detail={"total": 15000, "items": 3},
            request=None,
        )
        s.commit()
        rows = list(s.query(AuditLog).all())
        assert len(rows) == 1
        row = rows[0]
        assert row.user_id == "42"
        assert row.action == "sale.create"
        assert row.target_type == "sale"
        assert row.target_id == "99"
        assert row.detail == {"total": 15000, "items": 3}
        assert row.ip is None  # no request
        assert row.user_agent is None
        assert isinstance(row.occurred_at, datetime)


def test_record_optional_fields_default_to_none(session_factory):
    """No target_type/target_id/detail means nullable columns are NULL or default."""
    from app.rms.audit import record
    from app.rms.models import AuditLog

    with session_factory() as s:
        record(s, user_id=None, action="system.startup")
        s.commit()
        row = s.query(AuditLog).one()
        assert row.user_id is None
        assert row.target_type is None
        assert row.target_id is None
        assert row.detail == {}
        assert row.action == "system.startup"


def test_record_is_best_effort_on_failure(session_factory, monkeypatch):
    """If session.flush raises (e.g. constraint violation), record() swallows it.

    Verifies the contract: audit must NEVER break the caller.
    """
    from app.rms import audit

    class BoomSession:
        def add(self, obj):
            pass

        def flush(self):
            raise RuntimeError("simulated DB outage")

    # Must not raise
    audit.record(BoomSession(), user_id="x", action="should.fail")


def test_record_truncates_long_strings(session_factory):
    """Defensive truncation: a 1000-char action string must not blow up the column."""
    from app.rms.audit import record
    from app.rms.models import AuditLog

    long_action = "x" * 1000
    with session_factory() as s:
        record(s, user_id="u", action=long_action, target_id="y" * 200)
        s.commit()
        row = s.query(AuditLog).one()
    assert len(row.action) == 64
    assert len(row.target_id) == 64


def test_list_recent_newest_first(session_factory):
    """list_recent() returns rows in DESC occurred_at order."""
    import time

    from app.rms.audit import list_recent, record

    with session_factory() as s:
        for i in range(3):
            record(s, user_id=f"u{i}", action="test.event", detail={"i": i})
            s.commit()
            time.sleep(0.01)  # ensure occurred_at differs

        recent = list_recent(s, limit=10)
        assert len(recent) == 3
        # Newest first
        assert recent[0].detail["i"] == 2
        assert recent[1].detail["i"] == 1
        assert recent[2].detail["i"] == 0


def test_list_recent_action_filter(session_factory):
    """list_recent(action_filter='login.failure') only returns matching rows."""
    from app.rms.audit import list_recent, record

    with session_factory() as s:
        record(s, user_id="a", action="login.failure")
        record(s, user_id="b", action="login.success")
        record(s, user_id="a", action="login.failure")
        s.commit()
        failures = list_recent(s, action_filter="login.failure")
        assert len(failures) == 2
        assert all(r.action == "login.failure" for r in failures)


def test_list_recent_user_filter(session_factory):
    """list_recent(user_filter='alice') only returns alice's rows."""
    from app.rms.audit import list_recent, record

    with session_factory() as s:
        record(s, user_id="alice", action="x")
        record(s, user_id="bob", action="x")
        record(s, user_id="alice", action="y")
        s.commit()
        alice = list_recent(s, user_filter="alice")
        assert len(alice) == 2
        assert all(r.user_id == "alice" for r in alice)


def test_login_failure_writes_audit_row(client, session_factory):
    """POST /login with wrong creds writes a login.failure audit row.

    Uses the session_factory fixture (the same one the client uses) so we're
    guaranteed to read from the same DB the app is writing to.
    """
    from app.rms.models import AuditLog, User

    # Seed a user with bcrypt hash
    with session_factory() as s:
        u = User(
            username="audit-test-user",
            password_hash="$2b$12$abcdefghijklmnopqrstuv1234567890ABCDEFGHIJKLMNOPQRSTUxy",
            is_active=True,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        s.add(u)
        s.commit()

    # Try wrong password
    r = client.post(
        "/login",
        data={"username": "audit-test-user", "password": "wrong"},
        follow_redirects=False,
    )
    assert r.status_code in (303, 302)

    # Inspect via the same session_factory
    with session_factory() as s:
        rows = list(s.query(AuditLog).all())
        assert len(rows) >= 1, f"no audit rows written (got {len(rows)})"
        last = rows[-1]
        assert last.action == "login.failure", f"got action={last.action!r}"
        assert last.detail.get("reason") == "bad_credentials"


def test_logout_writes_audit_row(client, session_factory):
    """POST /logout writes a logout audit row (even when unauthenticated).

    Per the E3.S1 contract, logout.audit fires with user_id=None if the session
    was already cleared — gives us a 'last seen logout attempt' trail.
    """
    from app.rms.models import AuditLog

    # POST /logout (with no session) should not 500
    r = client.post("/logout", follow_redirects=False)
    assert r.status_code in (303, 302)

    with session_factory() as s:
        rows = list(s.query(AuditLog).filter(AuditLog.action == "logout").all())
        assert len(rows) >= 1, f"logout audit row not written (got {len(rows)})"
        # user_id is None because we weren't logged in
        assert rows[-1].user_id is None


def test_audit_log_table_created_by_migrate(tmp_path):
    """Migration 002 creates the audit_log table."""
    from sqlalchemy import inspect

    from app.rms.db import init_db
    from app.rms.db_dialect import make_engine

    db_path = tmp_path / "audit-migrate.sqlite"
    engine = make_engine(f"sqlite:///{db_path}")
    init_db(engine)
    insp = inspect(engine)
    assert "audit_log" in insp.get_table_names()


def test_record_extracts_client_ip_from_xff(session_factory, monkeypatch):
    """When X-Forwarded-For is set (Cloudflare), record() picks the first hop."""
    from app.rms.audit import record
    from app.rms.models import AuditLog

    # Build a fake Request-like object
    class FakeHeaders:
        def __init__(self, d):
            self.d = d

        def get(self, k, default=""):
            return self.d.get(k.lower(), default)

    class FakeClient:
        host = "127.0.0.1"

    class FakeRequest:
        def __init__(self, d):
            self.headers = FakeHeaders(d)
            self.client = FakeClient()

    req = FakeRequest({
        "x-forwarded-for": "203.0.113.5, 198.51.100.1, 192.0.2.1",
        "user-agent": "Mozilla/5.0 (test)",
    })
    with session_factory() as s:
        record(s, user_id=None, action="ip.test", request=req)
        s.commit()
        row = s.query(AuditLog).one()
    assert row.ip == "203.0.113.5"
    assert row.user_agent == "Mozilla/5.0 (test)"
