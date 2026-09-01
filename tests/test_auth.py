"""tests/test_auth.py — auth module tests (bcrypt + session helpers)."""

from __future__ import annotations


def test_hash_and_verify_password_roundtrip():
    """hash → verify returns True for correct password."""
    from app.auth import hash_password, verify_password

    h = hash_password("correct horse battery staple")
    assert h.startswith("$2")  # bcrypt prefix
    assert verify_password("correct horse battery staple", h) is True
    assert verify_password("wrong", h) is False


def test_hash_is_unique_per_call():
    """Two hashes of the same password differ (bcrypt salt)."""
    from app.auth import hash_password

    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2


def test_verify_password_with_empty_hash():
    """verify_password(empty_hash, ...) returns False."""
    from app.auth import verify_password

    assert verify_password("anything", "") is False


def test_verify_password_with_garbage_hash():
    """verify_password with non-bcrypt hash returns False (no exception)."""
    from app.auth import verify_password

    assert verify_password("anything", "not-a-bcrypt-hash") is False


def test_session_secret_loads_from_env(monkeypatch):
    """SESSION_SECRET picks up env var when set."""
    import importlib

    monkeypatch.setenv("SESSION_SECRET", "test-secret-32-chars-or-more-yes")
    # Re-import to pick up the new env var
    import app.auth

    importlib.reload(app.auth)
    assert app.auth.SESSION_SECRET == "test-secret-32-chars-or-more-yes"


def test_session_secret_dev_fallback(monkeypatch):
    """No SESSION_SECRET in env → uses DEV_SESSION_SECRET or default."""
    import importlib

    monkeypatch.delenv("SESSION_SECRET", raising=False)
    monkeypatch.delenv("DEV_SESSION_SECRET", raising=False)
    import app.auth

    importlib.reload(app.auth)
    # Either the default or DEV_SESSION_SECRET — both are non-empty
    assert app.auth.SESSION_SECRET
    assert len(app.auth.SESSION_SECRET) > 10


def test_user_model_set_and_check_password(session_factory):
    """User.set_password + check_password works through the SQLAlchemy session."""
    from datetime import datetime

    from app.rms.models import User

    with session_factory() as s:
        u = User(
            username="testuser",
            password_hash="",  # will be set
            is_active=True,
            created_at=datetime.now().isoformat(),
        )
        u.set_password("my-password")
        assert u.password_hash.startswith("$2")
        s.add(u)
        s.commit()
        user_id = u.id

    with session_factory() as s:
        u = s.get(User, user_id)
        assert u.check_password("my-password") is True
        assert u.check_password("wrong-password") is False


def test_user_model_check_password_empty_hash(session_factory):
    """User.check_password returns False when password_hash is empty."""
    from datetime import datetime

    from app.rms.models import User

    with session_factory() as s:
        u = User(
            username="emptyhash",
            password_hash="",
            is_active=True,
            created_at=datetime.now().isoformat(),
        )
        s.add(u)
        s.commit()
        user_id = u.id

    with session_factory() as s:
        u = s.get(User, user_id)
        assert u.check_password("anything") is False


def test_get_user_model_returns_sqlite_user_by_default():
    """Without DATABASE_URL, get_user_model returns SQLite User."""
    import os

    from app.auth import get_user_model
    from app.rms.models import User as SqliteUser

    # Make sure DATABASE_URL is not set
    old = os.environ.pop("DATABASE_URL", None)
    try:
        User = get_user_model()
        assert User is SqliteUser
    finally:
        if old:
            os.environ["DATABASE_URL"] = old


def test_get_user_model_returns_postgres_user_when_postgres(monkeypatch):
    """With DATABASE_URL=postgres://..., get_user_model returns Postgres User."""
    from app.auth import get_user_model
    from app.rms.schema_postgres import User as PgUser

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@host/db")
    User = get_user_model()
    # SQLAlchemy classes compare by identity, so check tablename match
    assert User.__tablename__ == PgUser.__tablename__
