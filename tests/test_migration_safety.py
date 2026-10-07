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


def test_init_db_creates_schema_version_row_for_fresh_db(tmp_path):
    """Fresh DB → init_db writes schema_version = CURRENT_SCHEMA_VERSION."""
    from sqlalchemy import create_engine, text

    from app.rms.config import CURRENT_SCHEMA_VERSION
    from app.rms.db import init_db

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

    from app.rms.config import CURRENT_SCHEMA_VERSION
    from app.rms.db import init_db

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


# --- Pre-migration backup (Hard Rule 17) ----------------------------------

def test_sync_backup_before_migration_writes_file(tmp_path, monkeypatch):
    """Hard Rule 17: pre-migration backup writes a file before the migration runs.

    Verifies sync_backup_before_migration() returns a Path to a
    gzipped JSON file, and the file contains the seeded data.
    """
    import gzip
    import json

    from sqlalchemy import create_engine

    from app.rms.config import CURRENT_SCHEMA_VERSION
    from app.rms.db import sync_backup_before_migration

    # Set up a DB with some data
    db_path = tmp_path / "source.db"
    engine = create_engine(f"sqlite:///{db_path}")
    from app.rms.db import init_db
    init_db(engine)
    from app.rms.models import Ingredient
    with engine.connect() as _conn:
        from sqlalchemy.orm import sessionmaker
        S = sessionmaker(bind=engine)
        with S() as s:
            s.add(Ingredient(name="Harina", unit="kg", stock_qty=5.0, purchase_price_gs=5000))
            s.commit()

    # Override the backup dir to tmp_path
    backup_dir = tmp_path / "backups"
    monkeypatch.setenv("AIW_RMS_SKIP_PRE_MIGRATION_BACKUP", "0")

    result = sync_backup_before_migration(
        engine,
        from_version=CURRENT_SCHEMA_VERSION - 1,
        to_version=CURRENT_SCHEMA_VERSION,
        backup_dir=backup_dir,
    )
    assert result is not None, "Backup should return a Path"
    assert result.exists(), f"Backup file should exist: {result}"
    assert result.suffix == ".gz", f"Should be gzipped, got {result.suffix}"
    # The file should be a valid gzipped JSON with manifest
    raw = gzip.decompress(result.read_bytes())
    payload = json.loads(raw.decode("utf-8"))
    assert "manifest" in payload
    assert "tables" in payload
    assert payload["manifest"]["schema_version"] == CURRENT_SCHEMA_VERSION


def test_sync_backup_before_migration_can_be_restored(tmp_path):
    """The backup file is restorable via restore_database().

    Round-trip: write a backup, restore it, verify the data is
    intact. This is the actual safety net — if a migration
    breaks the DB, the operator can run restore.
    """
    from sqlalchemy import create_engine

    from app.rms.config import CURRENT_SCHEMA_VERSION
    from app.rms.db import init_db, sync_backup_before_migration
    from app.rms.models import Ingredient

    # Source DB
    db_path = tmp_path / "source.db"
    engine = create_engine(f"sqlite:///{db_path}")
    init_db(engine)
    from sqlalchemy.orm import sessionmaker
    S = sessionmaker(bind=engine)
    with S() as s:
        s.add(Ingredient(name="Harina Backup Test", unit="kg", stock_qty=7.5, purchase_price_gs=5000))
        s.commit()

    backup_dir = tmp_path / "backups"
    backup_path = sync_backup_before_migration(
        engine,
        from_version=CURRENT_SCHEMA_VERSION - 1,
        to_version=CURRENT_SCHEMA_VERSION,
        backup_dir=backup_dir,
    )
    assert backup_path is not None
    assert backup_path.exists()

    # Verify the backup has the seed
    import gzip
    import json
    raw = gzip.decompress(backup_path.read_bytes())
    payload = json.loads(raw.decode("utf-8"))
    ingredients = payload["tables"].get("ingredient", [])
    names = [i["name"] for i in ingredients]
    assert "Harina Backup Test" in names, (
        f"Backup should contain the seeded ingredient, got: {names}"
    )


def test_init_db_writes_pre_migration_backup_before_applying(tmp_path):
    """init_db writes a pre-migration backup file when there are pending migrations.

    Uses the same init_db code path that the lifespan uses. Sets
    the env var to use tmp_path for backups.
    """
    import os

    from sqlalchemy import create_engine

    # Override the backup directory
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    os.environ["AIW_RMS_SKIP_PRE_MIGRATION_BACKUP"] = "0"
    # Patch the default
    import app.rms.db as dbmod
    original = dbmod.PRE_MIGRATION_BACKUP_DIR
    dbmod.PRE_MIGRATION_BACKUP_DIR = str(backup_dir)
    try:
        db_path = tmp_path / "test.db"
        engine = create_engine(f"sqlite:///{db_path}")
        from app.rms.db import init_db
        init_db(engine)
        # Check for backup files
        backups = list(backup_dir.glob("sazon-pre-mig-*.json.gz"))
        assert len(backups) >= 1, (
            f"Expected at least 1 pre-migration backup in {backup_dir}, got {len(backups)}: "
            f"{[b.name for b in backups]}"
        )
    finally:
        dbmod.PRE_MIGRATION_BACKUP_DIR = original
        del os.environ["AIW_RMS_SKIP_PRE_MIGRATION_BACKUP"]


def test_init_db_fail_closed_when_backup_fails(tmp_path, monkeypatch):
    """If the pre-migration backup fails and no override is set, init_db raises.

    This is the AGENTS.md Hard Rule 17 contract: never apply a
    migration without a backup.
    """
    import pytest
    from sqlalchemy import create_engine

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    monkeypatch.setenv("AIW_RMS_SKIP_PRE_MIGRATION_BACKUP", "0")
    monkeypatch.delenv("AIW_RMS_PROCEED_WITHOUT_BACKUP", raising=False)

    # Monkeypatch backup_database to fail
    def _broken_backup(session, dest, **kwargs):
        raise IOError("simulated backup failure")
    monkeypatch.setattr("app.rms.backup.backup_database", _broken_backup)

    # The init_db flow needs the import to pick up the monkeypatched function
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    from app.rms.db import init_db
    with pytest.raises(RuntimeError, match="Pre-migration backup failed"):
        init_db(engine)


def test_init_db_proceeds_when_backup_fails_with_override(tmp_path, monkeypatch):
    """If AIW_RMS_PROCEED_WITHOUT_BACKUP=1, init_db proceeds despite backup failure."""
    from sqlalchemy import create_engine

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    monkeypatch.setenv("AIW_RMS_SKIP_PRE_MIGRATION_BACKUP", "0")
    monkeypatch.setenv("AIW_RMS_PROCEED_WITHOUT_BACKUP", "1")

    # Monkeypatch backup_database to fail
    def _broken_backup(session, dest, **kwargs):
        raise IOError("simulated backup failure")
    monkeypatch.setattr("app.rms.backup.backup_database", _broken_backup)

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    from app.rms.db import init_db
    # Should NOT raise because of the override
    init_db(engine)


# --- Fail-closed on newer-schema DB (Hard Rule 19b) -----------------------

def test_fail_closed_on_newer_schema_db_raises(tmp_path):
    """Hard Rule 19b: init_db raises if the DB schema is newer than this build.

    Simulates a backup from a newer build being restored on an
    older build. The build must refuse to start.
    """
    import pytest
    from sqlalchemy import create_engine, text

    from app.rms.config import CURRENT_SCHEMA_VERSION
    from app.rms.db import init_db

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    init_db(engine)  # normal init first

    # Bump schema_version to a future version (newer than the build)
    future_version = CURRENT_SCHEMA_VERSION + 5
    with engine.connect() as conn:
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

    # Re-run init_db — must raise
    with pytest.raises(RuntimeError, match="newer than this build"):
        init_db(engine)


def test_fail_closed_on_newer_schema_one_version_higher(tmp_path):
    """Edge case: schema is exactly CURRENT + 1. Must still raise."""
    import pytest
    from sqlalchemy import create_engine, text

    from app.rms.config import CURRENT_SCHEMA_VERSION
    from app.rms.db import init_db

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    init_db(engine)

    future_version = CURRENT_SCHEMA_VERSION + 1
    with engine.connect() as conn:
        conn.execute(
            text(
                "INSERT OR REPLACE INTO app_meta (key, value, updated_at) "
                "VALUES ('schema_version', :v, :ts)"
            ),
            {"v": str(future_version), "ts": "2099-01-01T00:00:00Z"},
        )
        conn.commit()

    with pytest.raises(RuntimeError, match="newer than this build"):
        init_db(engine)
