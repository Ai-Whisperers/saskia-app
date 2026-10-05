"""tests/test_bootstrap_password_sync.py — Phase 1.A password sync from env vars.

Validates the idempotent first-boot behavior in app/rms/bootstrap.py.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.rms.models import User


def _make_user(username, password):
    u = User(
        username=username,
        role="admin",
        is_active=True,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    u.set_password(password)
    return u


def test_no_op_when_env_vars_unset(session_factory):
    """If no SASKIA_*_PASSWORD env vars are set, the sync is a no-op."""
    from app.rms.bootstrap import run_password_sync

    Session = session_factory
    session = Session()
    try:
        # Clean any existing users
        session.query(User).delete()
        # Seed a user with a known password
        session.add(_make_user("admin", "original-password"))
        session.commit()
        # Run sync with no env vars
        run_password_sync(session)
        session.commit()
        user = session.query(User).filter_by(username="admin").one()
        assert user.check_password("original-password"), "Password should be unchanged"
    finally:
        session.close()


def test_creates_user_when_env_var_set_and_user_missing(session_factory, monkeypatch):
    """If SASKIA_ADMIN_PASSWORD is set but no 'admin' user exists, create it."""
    from app.rms.bootstrap import run_password_sync

    Session = session_factory
    session = Session()
    try:
        session.query(User).delete()
        session.commit()
        monkeypatch.setenv("SASKIA_ADMIN_PASSWORD", "fresh-admin-pw")
        run_password_sync(session)
        session.commit()
        user = session.query(User).filter_by(username="admin").one()
        assert user.check_password("fresh-admin-pw")
        assert user.role == "admin"
        assert user.is_active is True
    finally:
        session.close()
        monkeypatch.delenv("SASKIA_ADMIN_PASSWORD", raising=False)


def test_updates_password_when_env_var_set_and_mismatch(session_factory, monkeypatch):
    """If SASKIA_ADMIN_PASSWORD is set and password mismatches, update the hash."""
    from app.rms.bootstrap import run_password_sync

    Session = session_factory
    session = Session()
    try:
        session.query(User).delete()
        session.add(_make_user("admin", "old-password"))
        session.commit()
        monkeypatch.setenv("SASKIA_ADMIN_PASSWORD", "new-password")
        run_password_sync(session)
        session.commit()
        user = session.query(User).filter_by(username="admin").one()
        assert not user.check_password("old-password")
        assert user.check_password("new-password")
    finally:
        session.close()
        monkeypatch.delenv("SASKIA_ADMIN_PASSWORD", raising=False)


def test_no_op_when_env_var_matches_existing_hash(session_factory, monkeypatch):
    """If SASKIA_ADMIN_PASSWORD matches, no hash update happens."""
    from app.rms.bootstrap import run_password_sync

    Session = session_factory
    session = Session()
    try:
        session.query(User).delete()
        session.add(_make_user("admin", "stable-password"))
        session.commit()
        monkeypatch.setenv("SASKIA_ADMIN_PASSWORD", "stable-password")
        run_password_sync(session)
        session.commit()
        # bcrypt produces same hash for same input + same salt, but salt is random
        # so the test is: check_password still True.
        user = session.query(User).filter_by(username="admin").one()
        assert user.check_password("stable-password")
    finally:
        session.close()
        monkeypatch.delenv("SASKIA_ADMIN_PASSWORD", raising=False)


def test_syncs_demo_user_from_user_password_env(session_factory, monkeypatch):
    """SASKIA_USER_PASSWORD targets the 'demo' user."""
    from app.rms.bootstrap import run_password_sync

    Session = session_factory
    session = Session()
    try:
        session.query(User).delete()
        session.add(_make_user("demo", "demo1234"))
        session.commit()
        monkeypatch.setenv("SASKIA_USER_PASSWORD", "demo-replacement")
        run_password_sync(session)
        session.commit()
        user = session.query(User).filter_by(username="demo").one()
        assert user.check_password("demo-replacement")
        assert not user.check_password("demo1234")
    finally:
        session.close()
        monkeypatch.delenv("SASKIA_USER_PASSWORD", raising=False)


def test_env_var_with_whitespace_is_ignored(session_factory, monkeypatch):
    """If the env var is just whitespace, treat as unset (no-op)."""
    from app.rms.bootstrap import run_password_sync

    Session = session_factory
    session = Session()
    try:
        session.query(User).delete()
        session.add(_make_user("admin", "original"))
        session.commit()
        monkeypatch.setenv("SASKIA_ADMIN_PASSWORD", "   ")
        run_password_sync(session)
        session.commit()
        user = session.query(User).filter_by(username="admin").one()
        assert user.check_password("original")
    finally:
        session.close()
        monkeypatch.delenv("SASKIA_ADMIN_PASSWORD", raising=False)
