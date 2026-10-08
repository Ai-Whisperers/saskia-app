"""# allow-hardcoded-dates: fixtures intentionally pin fixed dates (calendar edges, tz math, far-future sentinels); asserted relative to frozen or explicit anchors.
SASKIA-209 — migration rollback contract tests.

Locks: archive matching (newest to_version==current), evidence
archive written, restore integrity + version check, atomic swap with
WAL cleanup, rollback log row, fail-closed paths (no backup, wrong
target, non-SQLite).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.rms.db import init_db
from app.rms.models import AppMeta
from app.rms.rollback import (
    RollbackError,
    find_rollback_backup,
    rollback_sqlite,
)


def _version(s) -> int:
    row = s.execute(
        select(AppMeta.value).where(AppMeta.key == "schema_version")
    ).scalar_one_or_none()
    return int(row) if row else 0


def _marker_value(db_path: Path) -> str | None:
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("SELECT value FROM app_meta WHERE key='rollback_test_marker'").fetchone()
        return row[0] if row else None
    finally:
        conn.close()


@pytest.fixture()
def staged_rollback(tmp_path):
    """Build the full scenario at v(CURRENT): a migrated DB + a rule-17
    backup captured 'before the last migration' (simulated by seeding a
    backup whose contents are at version CURRENT-1)."""
    from app.rms.backup import backup_database
    from app.rms.config import CURRENT_SCHEMA_VERSION

    db_path = tmp_path / "live.sqlite"
    engine = create_engine(f"sqlite:///{db_path}")
    init_db(engine)  # now at CURRENT_SCHEMA_VERSION

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    # Simulate the rule-17 archive: a DB at CURRENT-1 … but we only have
    # the current schema handy. Instead: capture the CURRENT db, then
    # hand-edit its archive manifest? Too deep. Pragmatic: build a second
    # engine, init it, downgrade its app_meta schema_version row to
    # CURRENT-1, back THAT up as pre-mig-v(CURRENT-1)-to-v(CURRENT).
    prev_path = tmp_path / "prev.sqlite"
    prev_engine = create_engine(f"sqlite:///{prev_path}")
    init_db(prev_engine)
    S = sessionmaker(bind=prev_engine)
    with S() as s:
        row = s.execute(select(AppMeta).where(AppMeta.key == "schema_version")).scalar_one()
        row.value = str(CURRENT_SCHEMA_VERSION - 1)
        s.commit()
    with S() as s:
        backup_database(
            s,
            backup_dir
            / f"sazon-pre-mig-v{CURRENT_SCHEMA_VERSION - 1:04d}-to-v{CURRENT_SCHEMA_VERSION:04d}-20261007T000000Z.json.gz",
        )

    return {
        "db_path": db_path,
        "engine": engine,
        "backup_dir": backup_dir,
        "current": CURRENT_SCHEMA_VERSION,
        "prev": CURRENT_SCHEMA_VERSION - 1,
    }


class TestFindRollbackBackup:
    def test_newest_matching_archive_wins(self, tmp_path):
        d = tmp_path / "b"
        d.mkdir()
        (d / "sazon-pre-mig-v0113-to-v0114-20261007T010000Z.json.gz").write_bytes(b"x")
        (d / "sazon-pre-mig-v0113-to-v0114-20261007T020000Z.json.gz").write_bytes(b"y")
        (d / "sazon-pre-mig-v0112-to-v0113-20261007T000000Z.json.gz").write_bytes(b"z")
        got = find_rollback_backup(114, d)
        assert "20261007T020000Z" in got.name

    def test_no_match_raises(self, tmp_path):
        d = tmp_path / "b"
        d.mkdir()
        (d / "sazon-pre-mig-v0112-to-v0113-20261007T000000Z.json.gz").write_bytes(b"z")
        with pytest.raises(RollbackError, match="to_version=114"):
            find_rollback_backup(114, d)

    def test_missing_dir_raises(self, tmp_path):
        with pytest.raises(RollbackError, match="does not exist"):
            find_rollback_backup(114, tmp_path / "nope")


class TestRollbackSqlite:
    def test_full_rollback_roundtrip(self, staged_rollback):
        db_path: Path = staged_rollback["db_path"]
        backup_dir = staged_rollback["backup_dir"]
        cur, prev = staged_rollback["current"], staged_rollback["prev"]

        # Post-migration state: marker row that only exists AFTER the "migration"
        S = sessionmaker(bind=staged_rollback["engine"])
        with S() as s:
            s.add(
                AppMeta(
                    key="rollback_test_marker",
                    value="post-migration",
                    updated_at="2026-10-07T00:00:00+00:00",
                )
            )
            s.commit()

        result = rollback_sqlite(f"sqlite:///{db_path}", backup_dir=backup_dir)
        assert result.previous_version == cur
        assert result.restored_version == prev
        assert result.backup_used.exists()
        assert result.evidence_path.exists()
        assert result.log_key.startswith("migration_rollback_log:")

        # Live file now at prev version…
        S2 = sessionmaker(bind=create_engine(f"sqlite:///{db_path}"))
        with S2() as s:
            assert _version(s) == prev
        # …the post-migration marker is GONE (whole-file restore)…
        assert _marker_value(db_path) is None
        # …and the rollback log row is present.
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute(
                "SELECT value FROM app_meta WHERE key LIKE 'migration_rollback_log:%'"
            ).fetchone()
            assert row is not None
        finally:
            conn.close()

    def test_wal_sidecars_removed(self, staged_rollback):
        db_path: Path = staged_rollback["db_path"]
        # Simulate live WAL sidecars
        Path(str(db_path) + "-wal").write_bytes(b"stale")
        Path(str(db_path) + "-shm").write_bytes(b"stale")

        rollback_sqlite(f"sqlite:///{db_path}", backup_dir=staged_rollback["backup_dir"])
        assert not Path(str(db_path) + "-wal").exists()
        assert not Path(str(db_path) + "-shm").exists()

    def test_wrong_explicit_target_refused(self, staged_rollback):
        with pytest.raises(RollbackError, match="requested to_version"):
            rollback_sqlite(
                f"sqlite:///{staged_rollback['db_path']}",
                to_version=1,
                backup_dir=staged_rollback["backup_dir"],
            )

    def test_missing_backup_refused(self, tmp_path):
        db_path = tmp_path / "live.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        init_db(engine)
        empty_dir = tmp_path / "empty-backups"
        empty_dir.mkdir()
        with pytest.raises(RollbackError, match="No pre-migration backup"):
            rollback_sqlite(f"sqlite:///{db_path}", backup_dir=empty_dir)
        # live DB untouched
        S = sessionmaker(bind=engine)
        with S() as s:
            assert _version(s) > 1

    def test_non_sqlite_refused(self):
        with pytest.raises(RollbackError, match="SQLite only"):
            rollback_sqlite("postgresql://u:p@h/db")

    def test_low_version_refused(self, tmp_path):
        db_path = tmp_path / "live.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        init_db(engine)
        S = sessionmaker(bind=engine)
        with S() as s:
            row = s.execute(select(AppMeta).where(AppMeta.key == "schema_version")).scalar_one()
            row.value = "1"
            s.commit()
        with pytest.raises(RollbackError, match="nothing to roll back"):
            rollback_sqlite(f"sqlite:///{db_path}", backup_dir=tmp_path)
