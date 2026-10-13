"""Tests for migration 120: SettingsKV key 'shop_whatsapp' → 'sales.shop_whatsapp'.

Verifies:
- Schema bumps to 118
- The legacy key is removed from settings_kv
- The new key is created with the legacy value (idempotent copy)
- Re-running the migration is a no-op (idempotent)
- Fresh DB (no legacy key) does not error
"""

from __future__ import annotations

from sqlalchemy import text


def test_migration_120_bumps_schema_version(session_factory):
    """Fresh DB runs init_db through migration 120."""
    with session_factory() as s:
        v = s.execute(text("SELECT value FROM app_meta WHERE key='schema_version'")).scalar()
    assert v is not None
    assert int(v) >= 120


def test_migration_120_copies_legacy_shop_whatsapp(session_factory):
    """After init_db, the legacy 'shop_whatsapp' key (if it existed in a
    pre-120 DB) is moved to 'sales.shop_whatsapp' and the legacy key
    is deleted.

    We simulate a pre-120 DB by inserting a legacy row, then re-running
    init_db to trigger the migration.
    """
    with session_factory() as s:
        # SASKIA-226: migration 122 also writes sales.shop_whatsapp
        # (from the operator's questionnaire answer). Delete that
        # pre-existing row so migration 120's copy-from-legacy path
        # is the one we test.
        s.execute(text("DELETE FROM settings_kv WHERE key = 'sales.shop_whatsapp'"))
        # Insert a legacy row (simulating a pre-120 DB with an admin-
        # configured WhatsApp number).
        s.execute(
            text(
                "INSERT INTO settings_kv (key, value_json, updated_at) "
                "VALUES ('shop_whatsapp', :v, :ts)"
            ),
            {"v": "595981123456", "ts": "2026-10-12T00:00:00+00:00"},
        )
        s.commit()

    # Run the migration directly (the fixture's session_factory uses an
    # engine that has already been through init_db, so we trigger the
    # migration by calling the function on a fresh conn).
    from app.rms.migrations._120_shop_whatsapp_rename import (
        _migration_120_shop_whatsapp_rename,
    )

    with session_factory().get_bind().connect() as conn:
        _migration_120_shop_whatsapp_rename(conn)
        conn.commit()

    with session_factory() as s:
        # The legacy key is gone
        legacy = s.execute(
            text("SELECT value_json FROM settings_kv WHERE key = 'shop_whatsapp'")
        ).fetchone()
        assert legacy is None, "legacy 'shop_whatsapp' key should be removed"

        # The new key exists with the legacy value
        new = s.execute(
            text("SELECT value_json FROM settings_kv WHERE key = 'sales.shop_whatsapp'")
        ).fetchone()
        assert new is not None, "new 'sales.shop_whatsapp' key should exist"
        assert new[0] == "595981123456"


def test_migration_120_idempotent_when_new_key_exists(session_factory):
    """If 'sales.shop_whatsapp' already exists (e.g. from a parallel
    seeder run), the migration does NOT overwrite it (KV-wins).
    """
    with session_factory() as s:
        # SASKIA-226: migration 122 already wrote sales.shop_whatsapp
        # from the operator's questionnaire answer. Update that
        # pre-existing row to a known value so we can verify
        # migration 120 doesn't overwrite it.
        s.execute(
            text(
                "UPDATE settings_kv SET value_json = :v "
                "WHERE key = 'sales.shop_whatsapp'"
            ),
            {"v": "595981123456"},
        )
        # Insert legacy key with a different value (the would-be source)
        s.execute(
            text(
                "INSERT INTO settings_kv (key, value_json, updated_at) "
                "VALUES ('shop_whatsapp', :v, :ts)"
            ),
            {"v": "595000000000", "ts": "2026-10-12T00:00:00+00:00"},
        )
        s.commit()

    from app.rms.migrations._120_shop_whatsapp_rename import (
        _migration_120_shop_whatsapp_rename,
    )

    with session_factory().get_bind().connect() as conn:
        _migration_120_shop_whatsapp_rename(conn)
        conn.commit()

    with session_factory() as s:
        # The new key still has its original value (KV-wins)
        new = s.execute(
            text("SELECT value_json FROM settings_kv WHERE key = 'sales.shop_whatsapp'")
        ).fetchone()
        assert new[0] == "595981123456", "existing new-key value should not be overwritten"
        # The legacy key is still removed
        legacy = s.execute(
            text("SELECT value_json FROM settings_kv WHERE key = 'shop_whatsapp'")
        ).fetchone()
        assert legacy is None


def test_migration_120_noop_when_no_legacy_key(session_factory):
    """Fresh DB (no legacy 'shop_whatsapp' row) — migration is a no-op
    (no copy, no delete, no error).
    """
    # SASKIA-226: migration 122 writes sales.shop_whatsapp from the
    # operator's questionnaire answer. Delete it so we can verify
    # that migration 120 alone produces no sales.shop_whatsapp row.
    with session_factory() as s:
        s.execute(text("DELETE FROM settings_kv WHERE key = 'sales.shop_whatsapp'"))
        s.commit()

    # The fixture's session_factory goes through init_db on creation,
    # so the legacy key shouldn't exist anyway. We just verify the
    # migration runs without error.
    from app.rms.migrations._120_shop_whatsapp_rename import (
        _migration_120_shop_whatsapp_rename,
    )

    with session_factory().get_bind().connect() as conn:
        _migration_120_shop_whatsapp_rename(conn)
        conn.commit()

    with session_factory() as s:
        # No rows at all in settings_kv with these keys
        legacy = s.execute(text("SELECT 1 FROM settings_kv WHERE key = 'shop_whatsapp'")).fetchone()
        new = s.execute(
            text("SELECT 1 FROM settings_kv WHERE key = 'sales.shop_whatsapp'")
        ).fetchone()
        assert legacy is None
        assert new is None
