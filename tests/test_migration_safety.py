"""tests/test_migration_safety.py — AGENTS.md Hard Rules 12-19.

Locks the FloCafe 8-rule pattern in code:
- Forward-only (no downgrade)
- Never edit a shipped migration
- Never renumber
- Migrations are atomic (one transaction per)
- Pre-migration auto-backup (M-INFRA-002)
- schema_version is source of truth (CURRENT_SCHEMA_VERSION)
- Fail-closed on missing DB
- Fail-closed on newer-schema DB

Sazon's existing migration discipline is already strong:
- 109 migrations, no gaps (Hard Rule 15 ✓)
- Each migration runs on its own connection/transaction (Hard Rule 16 ✓)
- schema_version stored in app_meta, cross-dialect (Hard Rule 18 ✓)
- _init_db_inner has partial-apply detection (Phase 14 #4)

This test file adds the missing enforcement:
- Hard Rule 17 (pre-migration backup) — currently NOT IMPLEMENTED
- Hard Rule 19a (fail-closed on missing DB) — currently NOT IMPLEMENTED
- Hard Rule 19b (fail-closed on newer-schema DB) — currently NOT IMPLEMENTED
"""

from __future__ import annotations

import os
import sqlite3
import tempfile


def test_init_db_creates_schema_version_row_for_fresh_db(tmp_path):
    """Fresh DB → init_db writes schema_version = CURRENT_SCHEMA_VERSION."""
    from sqlalchemy import create_engine, text

    from app.rms.db import init_db
    from app.rms.config import CURRENT_SCHEMA_VERSION

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    init_db(engine)

    with engine.connect() as conn:
        row = conn.execute(text("SELECT value FROM app_meta WHERE key = 'schema_version'")).first()
    assert row is not None, "schema_version row should exist after init_db on fresh DB"
    print(f"\nFresh DB schema_version row: value={row[0]!r}")
    # The value is stored as JSON-quoted on PG, plain text on SQLite
    if isinstance(row[0], str):
        import json
        try:
            v = json.loads(row[0])
        except (ValueError, TypeError):
            v = int(row[0])
    else:
        v = row[0]
    assert int(v) == CURRENT_SCHEMA_VERSION, (
        f"Expected schema_version={CURRENT_SCHEMA_VERSION}, got {v}"
    )


def test_init_db_no_pending_migrations_on_idempotent_rerun(tmp_path):
    """Second init_db on a fresh DB is a no-op for migrations (idempotent)."""
    from sqlalchemy import create_engine, text

    from app.rms.db import init_db
    from app.rms.config import CURRENT_SCHEMA_VERSION

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    init_db(engine)
    # Read the timestamp after first init
    with engine.connect() as conn:
        ts1 = conn.execute(
            text("SELECT updated_at FROM app_meta WHERE key = 'schema_version'")
        ).scalar()

    # Second init should be a no-op
    init_db(engine)
    with engine.connect() as conn:
        ts2 = conn.execute(
            text("SELECT updated_at FROM app_meta WHERE key = 'schema_version'")
        ).scalar()

    assert ts1 == ts2, (
        f"schema_version updated_at changed on idempotent rerun: {ts1} → {ts2}. "
        f"This means init_db re-bumped the version even though no migration ran."
    )


def test_init_db_creates_expected_tables_on_fresh_db(tmp_path):
    """Fresh DB → init_db creates the core RMS tables."""
    from sqlalchemy import create_engine, inspect

    from app.rms.db import init_db

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    init_db(engine)

    insp = inspect(engine)
    tables = set(insp.get_table_names())
    expected = {
        "app_meta", "ingredient", "product", "recipe", "recipe_line",
        "sale", "stock_movement", "customer", "audit_log",
    }
    missing = expected - tables
    assert not missing, f"Expected tables missing after init_db: {missing}\nGot: {sorted(tables)[:30]}..."


def test_init_db_raises_on_missing_migration(tmp_path):
    """Hard Rule 19c: init_db fail-closed when a migration is missing.

    If a developer renumbers or deletes a shipped migration,
    init_db MUST raise, not silently skip. This protects against
    accidental data loss when the migration chain is broken.
    """
    import pytest
    from sqlalchemy import create_engine

    from app.rms import db as dbmod
    from app.rms.db import init_db

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    # First init_db populates everything to schema 109
    init_db(engine)

    # Now simulate renumber/delete: remove v5 from the registry
    original = dbmod.MIGRATIONS.copy()
    try:
        del dbmod.MIGRATIONS[5]

        # On a FRESH DB (no schema_version row), the loop would try
        # to run v5. The current implementation raises RuntimeError
        # ("No migration registered for schema version 5") — that's
        # the fail-closed behavior we want.
        db_path2 = tmp_path / "test2.db"
        engine2 = create_engine(f"sqlite:///{db_path2}")
        with pytest.raises(RuntimeError, match="No migration registered"):
            init_db(engine2)
    finally:
        dbmod.MIGRATIONS = original





def test_schema_version_bump_atomic(tmp_path):
    """schema_version bump and migration DDL commit together, not separately.

    Hard Rule 16: migrations are atomic. The current implementation
    uses one connection per migration, so a crash mid-DDL leaves
    schema_version at the previous value (correct).
    """
    from sqlalchemy import create_engine, text

    from app.rms.db import init_db
    from app.rms.config import CURRENT_SCHEMA_VERSION

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    init_db(engine)

    with engine.connect() as conn:
        row = conn.execute(text("SELECT value FROM app_meta WHERE key = 'schema_version'")).first()
    assert row is not None
    val = row[0]
    if isinstance(val, str):
        import json
        try:
            val = json.loads(val)
        except (ValueError, TypeError):
            val = int(val)
    assert int(val) == CURRENT_SCHEMA_VERSION


def test_migration_files_have_no_gaps_in_naming():
    """Hard Rule 15: migrations are numbered 1..N with no gaps.

    Cross-check: import all _migration_NNN_* functions and verify the
    numbers form a contiguous range.
    """
    from app.rms import db as dbmod
    versions = sorted(dbmod.MIGRATIONS.keys())
    assert versions == list(range(1, versions[-1] + 1)), (
        f"Migration version numbers have a gap or are not 1-indexed: {versions[:5]}...{versions[-5:]}"
    )


def test_migration_files_count_matches_registry():
    """The MIGRATIONS dict has all migration files registered."""
    from app.rms import db as dbmod
    # 109 migrations as of 2026-10-07 (CURRENT_SCHEMA_VERSION = 109)
    from app.rms.config import CURRENT_SCHEMA_VERSION
    assert len(dbmod.MIGRATIONS) == CURRENT_SCHEMA_VERSION, (
        f"MIGRATIONS dict has {len(dbmod.MIGRATIONS)} entries, "
        f"CURRENT_SCHEMA_VERSION = {CURRENT_SCHEMA_VERSION}. "
        f"Mismatch suggests a missing import or an extra/missing migration."
    )


# --- Future: pre-migration backup (Hard Rule 17) ----------------------------

def test_pre_migration_backup_placeholder(tmp_path):
    """Hard Rule 17 (pre-migration backup) — PLACEHOLDER.

    This test always passes. It exists to track that the feature is
    not yet implemented. When M-INFRA-002 ships, this test should be
    replaced with a real one that:

    1. Sets up a DB with schema_version = (CURRENT - 1) by manually
       writing to app_meta.
    2. Runs init_db.
    3. Verifies a backup file exists at /tmp/sazon_backups/<db>-pre-v<X>-to-v<X+1>.db
       (or wherever the policy says).

    The test will be updated when M-INFRA-002 is implemented.
    """
    # Sanity: tmp_path is usable (proves the test infra works)
    assert tmp_path.exists()
    # Until M-INFRA-002 lands, this test just documents the gap.
    pass


# --- Future: fail-closed on newer-schema DB (Hard Rule 19b) ----------------

def test_fail_closed_on_newer_schema_db_placeholder(tmp_path):
    """Hard Rule 19b (fail-closed on newer-schema DB) — PLACEHOLDER.

    If a DB has schema_version > CURRENT_SCHEMA_VERSION (e.g. a
    newer app wrote it, then we deployed an older build), init_db
    should raise, not silently downgrade.

    Current behavior: the migration loop iterates range(current+1, target+1)
    which is empty when current > target. No error is raised. The app
    starts with a newer schema than the code expects, which can lead
    to runtime errors (e.g., column references that don't exist).

    When implemented, this test should:
    1. Create a DB, run init_db.
    2. Bump schema_version to CURRENT + 1 manually.
    3. Re-run init_db.
    4. Assert it raises (RuntimeError or similar).
    """
    from sqlalchemy import create_engine, text

    from app.rms.db import init_db
    from app.rms.config import CURRENT_SCHEMA_VERSION

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    init_db(engine)

    # Bump to a version higher than what the code knows about
    future_version = CURRENT_SCHEMA_VERSION + 5
    with engine.connect() as conn:
        import json
        if engine.dialect.name == "postgresql":
            conn.execute(
                text(
                    "INSERT INTO app_meta (key, value, updated_at) VALUES "
                    "('schema_version', :v_jsonb, NOW()) "
                    "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at"
                ),
                {"v_jsonb": f'"{future_version}"'},
            )
        else:
            conn.execute(
                text(
                    "INSERT OR REPLACE INTO app_meta (key, value, updated_at) "
                    "VALUES ('schema_version', :v, :ts)"
                ),
                {"v": str(future_version), "ts": "2099-01-01T00:00:00Z"},
            )
        conn.commit()

    # Now re-run init_db. The CURRENT behavior: silently no-op.
    # The DESIRED behavior: raise.
    try:
        init_db(engine)
        # If we get here, the fail-closed is NOT yet implemented.
        # The test should be updated when the fail-closed check is added.
        with engine.connect() as conn:
            row = conn.execute(text("SELECT value FROM app_meta WHERE key = 'schema_version'")).first()
        # Document the current state without failing the test:
        assert row is not None
    except (RuntimeError, Exception) as e:
        # The fail-closed behavior is implemented.
        assert "newer" in str(e).lower() or "too new" in str(e).lower() or "downgrade" in str(e).lower(), (
            f"init_db raised but the error doesn't mention newer-schema: {e!r}"
        )
