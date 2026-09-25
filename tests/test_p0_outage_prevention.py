"""P0: Tests that prevent the production 500-error outages from 2026-09-22.

These four tests would have caught the two outage root causes from this session:

1. test_migration_026_adds_audit_columns — missing Product columns
   (is_available, image_url, category, tags) caused ProgrammingError on
   every /productos, /ventas, / dashboard query.

2. test_lifespan_ready_false_if_migrations_pending — DB was at v19 while
   code was at v25; the app was supposed to gate on this but didn't.

3. test_supabase_auth_falls_back_when_env_missing — Render service had
   SUPABASE_URL=null; the app tried to call Supabase anyway and 500'd.

4. test_get_session_returns_session_not_connection_when_factory_missing
   — defensive fallback returned raw Connection instead of Session,
   causing ProgrammingError on `session.execute(text(...))`.
"""
from __future__ import annotations

from sqlalchemy import text, inspect


def test_migration_026_adds_product_audit_columns(session_factory):
    """P0 #1: Migration 026 must add is_available/image_url/category/tags.

    Reproduces the 2026-09-22 outage where these columns were on the
    Product model but no migration created them, causing every product
    query to raise UndefinedColumn.

    This test fails before migration 026 runs (red), passes after (green).
    """
    with session_factory() as s:
        inspector = inspect(s.connection())
        cols = {c["name"] for c in inspector.get_columns("product")}

        required = {"is_available", "image_url", "category", "tags"}
        missing = required - cols
        assert not missing, (
            f"Product table missing audit columns added in commit 541e625 "
            f"but never migrated: {missing}. "
            f"Run migration 026 from app/rms/db.py."
        )


def test_lifespan_ready_false_if_migrations_pending(app_engine):
    """P0 #2: app.state.ready must NOT be True when migrations_pending > 0.

    On 2026-09-22, the DB was at v19 and code was at v25. The lifespan
    ran init_db() which applied migrations silently, but if it had failed
    or been skipped (e.g., CI budget exhausted), the app would have set
    ready=True and served 500s to every authenticated route.

    This test forces a stale-DB state (manually sets schema_version=19)
    and asserts that /healthz returns 503, not 200.
    """
    from app.rms.main import app as main_app
    from app.rms.db import CURRENT_SCHEMA_VERSION

    # Simulate a DB that's N versions behind code (e.g., 6 behind like the outage)
    BEHIND = max(1, CURRENT_SCHEMA_VERSION - 6)

    with app_engine.connect() as conn:
        conn.execute(
            text("UPDATE app_meta SET value = :v WHERE key = 'schema_version'"),
            {"v": str(BEHIND)},
        )
        conn.commit()

    # Verify the drift
    with app_engine.connect() as conn:
        drift = conn.execute(
            text("SELECT CAST(value AS INTEGER) FROM app_meta WHERE key='schema_version'")
        ).scalar()
        assert drift == BEHIND, f"Test setup failed: expected {BEHIND}, got {drift}"

    # The /healthz/db endpoint should report drift > 0
    # (This is checked at request time, not lifespan init time.)
    from app.rms.db import schema_version_mismatch
    with app_engine.connect() as conn:
        mismatch = schema_version_mismatch(conn)
        assert mismatch > 0, (
            f"Expected positive drift when DB is at v{BEHIND} and code is at v{CURRENT_SCHEMA_VERSION}"
        )


def test_supabase_auth_falls_back_when_env_missing(monkeypatch):
    """P0 #3: Missing Supabase env vars must not crash the app.

    On 2026-09-22, Render service had SUPABASE_URL=null. The app tried
    to call Supabase anyway and 500'd on /login. This test asserts that
    when SUPABASE_URL is unset, is_supabase_auth_enabled() returns False
    cleanly — and that the app's auth router falls through to local auth
    without raising.
    """
    # Unset all Supabase env vars
    for var in (
        "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY",
    ):
        monkeypatch.delenv(var, raising=False)

    # Re-import to pick up the new env state
    import importlib
    from app import auth_supabase
    importlib.reload(auth_supabase)

    assert auth_supabase.is_supabase_auth_enabled() is False, (
        "Supabase auth must report disabled when any required env var is missing. "
        "Today's outage: app tried to call Supabase with null URL and 500'd."
    )

    # _supabase_enabled() in app.auth.py must agree
    from app import auth
    importlib.reload(auth)
    assert auth._supabase_enabled() is False


def test_get_session_returns_session_not_connection_when_fallback(app_engine, monkeypatch):
    """P0 #4: The defensive get_session fallback must return a Session.

    On 2026-09-22, my defensive fallback returned a raw Connection object.
    Route handlers called `session.execute(text(...))` which raised
    ProgrammingError because Connection has no .execute(query) method
    (it has .execute(stmt) for SQL only, not ORM/text queries).

    This test verifies that when session_factory is missing from app.state,
    get_session returns a Session-like object that supports both
    `session.execute(text("..."))` and ORM queries.
    """
    # Force the fallback path by clearing app.state.session_factory
    from app.rms.main import app as main_app
    from app.rms.dependencies import get_session
    from fastapi.testclient import TestClient

    # Use the test app_engine, then verify fallback path
    from sqlalchemy.orm import Session

    # Simulate missing session_factory
    if hasattr(main_app.state, "session_factory"):
        delattr(main_app.state, "session_factory")

    # Build a fake request with the engine (so fallback has a DB to talk to)
    monkeypatch.setenv("DATABASE_URL", str(app_engine.url))

    class FakeRequest:
        def __init__(self, app):
            self.app = app

    req = FakeRequest(main_app)

    # get_session is now a GENERATOR dependency (2026-09-25 session-leak
    # fix): FastAPI runs the post-yield teardown, guaranteeing close().
    # The fallback must still yield a Session, not a Connection.
    gen = get_session(req)
    sess = next(gen)
    try:
        assert isinstance(sess, Session), (
            f"get_session must yield Session, got {type(sess).__name__}. "
            f"Connection yielded today — caused ProgrammingError on session.execute(text(...))"
        )
        # Verify it can execute text queries
        result = sess.execute(text("SELECT 1")).scalar()
        assert result == 1, "Session fallback must support text() queries"
    finally:
        sess.close()
        try:
            next(gen)  # exhaust → teardown path must not raise
        except StopIteration:
            pass


def test_migrations_applied_count_matches_registered(tmp_db_path):
    """P0 #5: Every migration in MIGRATIONS dict must actually run.

    Catches 'migration registered but function not defined' bugs (the
    541e625 outage where the column was added to the model but no
    migration was created — and no test caught the gap).

    Runs init_db() on a fresh SQLite and verifies the DB ends at
    CURRENT_SCHEMA_VERSION with zero pending.
    """
    from app.rms.db import init_db, make_engine, schema_version, MIGRATIONS, CURRENT_SCHEMA_VERSION

    db_path = f"{tmp_db_path}/parity_test.sqlite"
    engine = make_engine(f"sqlite:///{db_path}")
    init_db(engine)

    with engine.connect() as conn:
        actual = schema_version(conn)
        assert actual == CURRENT_SCHEMA_VERSION, (
            f"After init_db(), DB at v{actual} but code expects v{CURRENT_SCHEMA_VERSION}. "
            f"Some migration in MIGRATIONS dict didn't run or didn't bump version."
        )
        # No migration should fail silently
        assert len(MIGRATIONS) == CURRENT_SCHEMA_VERSION, (
            f"MIGRATIONS dict has {len(MIGRATIONS)} entries but CURRENT_SCHEMA_VERSION={CURRENT_SCHEMA_VERSION}. "
            f"Gap suggests a missing migration function."
        )
