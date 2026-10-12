"""Tests for migration 123 — SASKIA-226 soft-delete demo cashiers.

Operator §4.5 of the 2026-10-08 onboarding questionnaire answered
"no" (Saskia runs the POS solo, no cajeros). The seeder used to
create lucia + diego as demo cashier accounts. This migration
soft-deletes them (is_active = 0). The CASHIER_USERS list in the
seeder is now empty so the next seeder run does not re-create them.
"""
from __future__ import annotations

from sqlalchemy import text

DEMO_CASHIERS = ["lucia", "diego"]


def test_migration_123_schema_version_bumped(session_factory):
    """Fresh DB runs init_db through migration 123."""
    with session_factory() as s:
        v = s.execute(text("SELECT value FROM app_meta WHERE key='schema_version'")).scalar()
    assert v is not None
    assert int(v) >= 123


def test_migration_123_soft_deletes_demo_cashiers(session_factory):
    """Create lucia + diego with is_active=1, run the migration, verify
    they are now is_active=0. Other users (saskia, admin, demo) are
    unaffected."""
    with session_factory() as s:
        for username in DEMO_CASHIERS:
            s.execute(
                text(
                    "INSERT INTO user (username, password_hash, role, is_active, created_at) "
                    "VALUES (:u, '$2b$12$abcdefghijklmnopqrstuv', 'cashier', 1, "
                    "'2026-10-08T00:00:00+00:00')"
                ),
                {"u": username},
            )
        # Plus a saskia user that should NOT be touched
        s.execute(
            text(
                "INSERT OR IGNORE INTO user (username, password_hash, role, is_active, created_at) "
                "VALUES ('saskia', '$2b$12$abcdefghijklmnopqrstuv', 'admin', 1, "
                "'2026-10-08T00:00:00+00:00')"
            )
        )
        s.commit()

    from app.rms.migrations._123_drop_demo_cashiers import _migration_123_drop_demo_cashiers

    with session_factory().get_bind().connect() as conn:
        _migration_123_drop_demo_cashiers(conn)
        conn.commit()

    with session_factory() as s:
        # Demo cashiers are soft-deleted
        for username in DEMO_CASHIERS:
            row = s.execute(
                text("SELECT is_active FROM user WHERE username = :u"),
                {"u": username},
            ).fetchone()
            assert row is not None, f"user '{username}' was hard-deleted (should be soft)"
            assert row[0] == 0, f"user '{username}' should be is_active=0 after migration"

        # Saskia is unaffected
        saskia = s.execute(
            text("SELECT is_active FROM user WHERE username = 'saskia'")
        ).fetchone()
        if saskia is not None:
            assert saskia[0] == 1, "saskia should not be touched by migration 123"


def test_migration_123_idempotent(session_factory):
    """Running the migration twice does not re-touch already-inactive rows."""
    with session_factory() as s:
        for username in DEMO_CASHIERS:
            s.execute(
                text(
                    "INSERT INTO user (username, password_hash, role, is_active, created_at) "
                    "VALUES (:u, '$2b$12$abcdefghijklmnopqrstuv', 'cashier', 0, "
                    "'2026-10-08T00:00:00+00:00')"
                ),
                {"u": username},
            )
        s.commit()

    from app.rms.migrations._123_drop_demo_cashiers import _migration_123_drop_demo_cashiers

    # Run twice — should not raise
    with session_factory().get_bind().connect() as conn:
        _migration_123_drop_demo_cashiers(conn)
        conn.commit()
        _migration_123_drop_demo_cashiers(conn)
        conn.commit()

    with session_factory() as s:
        for username in DEMO_CASHIERS:
            row = s.execute(
                text("SELECT is_active FROM user WHERE username = :u"),
                {"u": username},
            ).fetchone()
            assert row[0] == 0


def test_seeder_cashier_users_list_is_empty():
    """The seeder's CASHIER_USERS list is now empty (per operator §4.5)."""
    from app.rms.seed.sazon import CASHIER_USERS

    assert CASHIER_USERS == [], (
        f"CASHIER_USERS should be empty per operator §4.5, got: {CASHIER_USERS!r}. "
        "If you add a cashier, also update the operator and the live DB."
    )
