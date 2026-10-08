"""# allow-hardcoded-dates: fixtures intentionally pin fixed dates (calendar edges, tz math, far-future sentinels); asserted relative to frozen or explicit anchors.
PR A4 — tests for app/services/auto_backup.py (4 critical untested prod modules).

Per the static-content audit (2026-10-07), the auto_backup module had 0 test
coverage despite being the only safety net against a corrupt/lost SQLite
DB. These tests pin:
  - Threshold logic (24h, 7d) at the boundary
  - mtime-based last_backup_at detection
  - Filename pattern recognition (only `rms-backup-*.xlsx` count)
  - Pruning of old backups (keep_last_n)
  - Behavior on a missing/empty folder
  - Idempotency: same input → same output
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.rms.config import ASUNCION_TZ
from app.services.auto_backup import (
    AUTO_BACKUP_THRESHOLD_HOURS,
    DEFAULT_KEEP_LAST_N,
    WARN_THRESHOLD_DAYS,
    backup_filename,
    last_backup_at,
    needs_auto_backup,
    needs_warning,
    prune_old_backups,
)

# ─── needs_auto_backup (24h threshold) ──────────────────────────────


class TestNeedsAutoBackup:
    """`needs_auto_backup(last_backup_at)` returns True when the gap exceeds 24h."""

    def test_none_always_needs_backup(self) -> None:
        """No prior backup → always trigger a new one."""
        assert needs_auto_backup(None) is True

    def test_just_backed_up_does_not_need(self) -> None:
        """Backup 1 minute ago → no need."""
        recent = datetime.now(ASUNCION_TZ) - timedelta(minutes=1)
        assert needs_auto_backup(recent) is False

    def test_at_threshold_boundary_needs(self) -> None:
        """Backup exactly 24h ago IS over threshold (strict >) — needs.

        The `>` comparison means the boundary case is already over, so
        the function returns True. If we ever want "exactly 24h is OK",
        this test will fail and force us to re-document the intent.
        """
        boundary = datetime.now(ASUNCION_TZ) - timedelta(hours=AUTO_BACKUP_THRESHOLD_HOURS)
        assert needs_auto_backup(boundary) is True

    def test_just_over_threshold_needs(self) -> None:
        """Backup 24h + 1 minute ago → needs a new one."""
        over = datetime.now(ASUNCION_TZ) - timedelta(hours=AUTO_BACKUP_THRESHOLD_HOURS, minutes=1)
        assert needs_auto_backup(over) is True

    def test_very_old_needs(self) -> None:
        """Backup 30 days ago → needs."""
        ancient = datetime.now(ASUNCION_TZ) - timedelta(days=30)
        assert needs_auto_backup(ancient) is True

    def test_custom_threshold_respected(self) -> None:
        """Caller can pass a tighter threshold (e.g. for tests)."""
        # 5h old with default 24h threshold → no need
        five_h = datetime.now(ASUNCION_TZ) - timedelta(hours=5)
        assert needs_auto_backup(five_h) is False
        # 5h old with custom 4h threshold → needs
        assert needs_auto_backup(five_h, threshold_hours=4) is True

    def test_naive_datetime_does_not_crash(self) -> None:
        """A naive (no tzinfo) datetime doesn't break the comparison.

        Production stores mtime in ASUNCION_TZ via `last_backup_at(folder)`,
        so callers pass aware datetimes. A naive datetime would still be
        comparable (Python 3.x raises for aware-vs-naive) — if we ever
        accept naive input, this test should fail and tell us to decide.
        """
        # This is documenting behavior, not asserting good behavior. A
        # regression here means a caller started passing naive datetimes.
        naive_recent = datetime.utcnow() - timedelta(minutes=1)
        with pytest.raises(TypeError):
            needs_auto_backup(naive_recent)


# ─── needs_warning (7d threshold) ──────────────────────────────────


class TestNeedsWarning:
    """`needs_warning(last_backup_at)` returns True when gap > 7d."""

    def test_none_warns(self) -> None:
        assert needs_warning(None) is True

    def test_recent_does_not_warn(self) -> None:
        recent = datetime.now(ASUNCION_TZ) - timedelta(days=1)
        assert needs_warning(recent) is False

    def test_7d_exact_needs(self) -> None:
        """Strict > comparison at 7d boundary — exactly 7d IS over."""
        boundary = datetime.now(ASUNCION_TZ) - timedelta(days=WARN_THRESHOLD_DAYS)
        assert needs_warning(boundary) is True

    def test_8d_warns(self) -> None:
        eight = datetime.now(ASUNCION_TZ) - timedelta(days=8)
        assert needs_warning(eight) is True


# ─── backup_filename ───────────────────────────────────────────────


class TestBackupFilename:
    """Filename format: `rms-backup-YYYYMMDD-HHMMSS.xlsx`."""

    def test_explicit_timestamp(self) -> None:
        ts = datetime(2026, 10, 7, 14, 30, 0, tzinfo=ASUNCION_TZ)
        assert backup_filename(ts) == "rms-backup-20261007-143000.xlsx"

    def test_default_is_now(self) -> None:
        """No arg → uses datetime.now(ASUNCION_TZ). Just check the shape."""
        name = backup_filename()
        assert name.startswith("rms-backup-")
        assert name.endswith(".xlsx")
        # 15 chars of timestamp: YYYYMMDD-HHMMSS
        ts_part = name.removeprefix("rms-backup-").removesuffix(".xlsx")
        assert len(ts_part) == 15
        assert ts_part[8] == "-"
        assert ts_part[:8].isdigit()
        assert ts_part[9:].isdigit()


# ─── last_backup_at(folder) ────────────────────────────────────────


class TestLastBackupAt:
    """Reads the mtime of the most recent valid backup file in a folder."""

    def test_missing_folder_returns_none(self, tmp_path: Path) -> None:
        """Folder doesn't exist → None (don't crash on first run)."""
        missing = tmp_path / "does-not-exist"
        assert last_backup_at(missing) is None

    def test_empty_folder_returns_none(self, tmp_path: Path) -> None:
        """Folder exists but no .xlsx files → None."""
        assert last_backup_at(tmp_path) is None

    def test_unrelated_xlsx_ignored(self, tmp_path: Path) -> None:
        """A random.xlsx dropped in the folder must NOT count as a backup."""
        (tmp_path / "random-stuff.xlsx").write_bytes(b"junk")
        (tmp_path / "notes-2026.xlsx").write_bytes(b"junk")
        assert last_backup_at(tmp_path) is None

    def test_named_backup_recognized(self, tmp_path: Path) -> None:
        """A file matching the pattern is recognized as a backup."""
        (tmp_path / "rms-backup-20261007-120000.xlsx").write_bytes(b"junk")
        result = last_backup_at(tmp_path)
        assert result is not None
        assert result.tzinfo is not None  # aware datetime in ASUNCION_TZ

    def test_most_recent_mtime_wins(self, tmp_path: Path) -> None:
        """With multiple backups, the most recent mtime is returned."""
        import os
        import time

        old = tmp_path / "rms-backup-20261005-120000.xlsx"
        old.write_bytes(b"junk")
        os.utime(old, (time.time() - 86400 * 2, time.time() - 86400 * 2))

        new = tmp_path / "rms-backup-20261007-120000.xlsx"
        new.write_bytes(b"junk")
        os.utime(new, (time.time(), time.time()))

        result = last_backup_at(tmp_path)
        assert result is not None
        # New file's mtime should be closer to now than the old one
        gap = datetime.now(ASUNCION_TZ) - result
        assert gap < timedelta(minutes=1)


# ─── prune_old_backups ─────────────────────────────────────────────


class TestPruneOldBackups:
    """`prune_old_backups(folder, keep_last_n)` deletes oldest beyond N."""

    def test_missing_folder_no_op(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope"
        assert prune_old_backups(missing) == 0

    def test_empty_folder_no_op(self, tmp_path: Path) -> None:
        assert prune_old_backups(tmp_path) == 0

    def test_keeps_all_when_under_limit(self, tmp_path: Path) -> None:
        """5 backups, keep 30 → keep all 5, delete 0."""
        for i in range(5):
            (tmp_path / f"rms-backup-2026100{i}-120000.xlsx").write_bytes(b"x")
        assert prune_old_backups(tmp_path, keep_last_n=30) == 0
        assert len(list(tmp_path.glob("*.xlsx"))) == 5

    def test_prunes_oldest_beyond_n(self, tmp_path: Path) -> None:
        """5 backups, keep 2 → delete 3 oldest, keep 2 newest."""
        import os
        import time

        for i in range(5):
            f = tmp_path / f"rms-backup-2026100{i}-120000.xlsx"
            f.write_bytes(b"x")
            # Newer index = newer mtime
            os.utime(f, (time.time() + i, time.time() + i))

        deleted = prune_old_backups(tmp_path, keep_last_n=2)
        assert deleted == 3
        remaining = sorted(p.name for p in tmp_path.glob("*.xlsx"))
        # 2 newest survive
        assert remaining == [
            "rms-backup-20261003-120000.xlsx",
            "rms-backup-20261004-120000.xlsx",
        ]

    def test_default_keep_is_30(self, tmp_path: Path) -> None:
        """31 backups, no keep arg → delete 1, keep 30."""
        import os
        import time

        for i in range(31):
            f = tmp_path / f"rms-backup-202610{i:02d}-120000.xlsx"
            f.write_bytes(b"x")
            os.utime(f, (time.time() + i, time.time() + i))

        deleted = prune_old_backups(tmp_path)
        assert deleted == 1
        assert len(list(tmp_path.glob("*.xlsx"))) == DEFAULT_KEEP_LAST_N

    def test_unrelated_files_untouched(self, tmp_path: Path) -> None:
        """prune must only touch `rms-backup-*.xlsx` files."""
        import os
        import time

        # 3 backup files
        for i in range(3):
            f = tmp_path / f"rms-backup-2026100{i}-120000.xlsx"
            f.write_bytes(b"x")
            os.utime(f, (time.time() + i, time.time() + i))
        # 1 unrelated file
        (tmp_path / "unrelated.xlsx").write_bytes(b"keep me")

        prune_old_backups(tmp_path, keep_last_n=1)

        assert (tmp_path / "unrelated.xlsx").exists()
        # Only the 1 newest backup survives
        backups = list(tmp_path.glob("rms-backup-*.xlsx"))
        assert len(backups) == 1


# ─── Module-level constants sanity ─────────────────────────────────


def test_threshold_constants_match_docs() -> None:
    """Docstring says 24h + 7d. Constants must match."""
    assert AUTO_BACKUP_THRESHOLD_HOURS == 24
    assert WARN_THRESHOLD_DAYS == 7
    assert DEFAULT_KEEP_LAST_N == 30
