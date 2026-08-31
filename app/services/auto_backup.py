"""Auto-backup on app startup.

Per docs/operations/2026-09-fase-1-specs.md §1.

Every time the app starts, if the last backup is more than 24 hours old,
automatically export the SQLite database to a timestamped .xlsx file in
a configured local folder. No user action required.

If the last backup is more than 7 days old, set a flag the UI can read to
show a notification: "Hace más de 7 días que no exportás."

This module is dependency-free except for the app's own modules (config,
export_xlsx).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

# Threshold constants — kept here (not config.py) because they're
# rarely changed. If you need to tune, change them here.
AUTO_BACKUP_THRESHOLD_HOURS = 24
WARN_THRESHOLD_DAYS = 7
DEFAULT_KEEP_LAST_N = 30


def needs_auto_backup(last_backup_at, threshold_hours: int = AUTO_BACKUP_THRESHOLD_HOURS) -> bool:
    """True if last_backup_at is older than threshold, or no backup yet.

    Examples:
        >>> needs_auto_backup(None)
        True
        >>> from datetime import datetime, timedelta
        >>> needs_auto_backup(datetime.now() - timedelta(hours=1))
        False
        >>> needs_auto_backup(datetime.now() - timedelta(hours=25))
        True
    """
    if last_backup_at is None:
        return True
    return datetime.now() - last_backup_at > timedelta(hours=threshold_hours)


def needs_warning(last_backup_at, threshold_days: int = WARN_THRESHOLD_DAYS) -> bool:
    """True if last_backup_at is older than threshold_days, or no backup yet."""
    if last_backup_at is None:
        return True
    return datetime.now() - last_backup_at > timedelta(days=threshold_days)


def last_backup_at(folder: Path):
    """Return the mtime of the most recent .xlsx in folder, or None.

    Only counts files matching the backup naming pattern
    `rms-backup-YYYYMMDD-HHMMSS.xlsx` to avoid false positives
    (e.g., if she manually drops an unrelated xlsx in the folder).
    """
    if not folder.exists():
        return None
    files = list(folder.glob("rms-backup-*.xlsx"))
    if not files:
        return None
    return datetime.fromtimestamp(max(f.stat().st_mtime for f in files))


def backup_filename(timestamp: datetime | None = None) -> str:
    """Generate the standard backup filename for a given timestamp."""
    ts = (timestamp or datetime.now()).strftime("%Y%m%d-%H%M%S")
    return f"rms-backup-{ts}.xlsx"


def prune_old_backups(folder: Path, keep_last_n: int = DEFAULT_KEEP_LAST_N) -> int:
    """Delete oldest backups beyond keep_last_n. Returns count deleted.

    Backups are kept newest-first; everything beyond keep_last_n is deleted.
    """
    if not folder.exists():
        return 0
    files = sorted(
        folder.glob("rms-backup-*.xlsx"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    deleted = 0
    for f in files[keep_last_n:]:
        f.unlink()
        deleted += 1
    return deleted


# Note: the actual `auto_backup()` function is in app/services/auto_backup_impl.py
# (kept separate to avoid circular imports with export_xlsx). It's wired up in
# main.py's lifespan handler.
#
# This module is the public API: helper functions only. The full export happens
# when main.py calls auto_backup_impl.run_backup(db_path, folder).


__all__ = [
    "AUTO_BACKUP_THRESHOLD_HOURS",
    "WARN_THRESHOLD_DAYS",
    "DEFAULT_KEEP_LAST_N",
    "needs_auto_backup",
    "needs_warning",
    "last_backup_at",
    "backup_filename",
    "prune_old_backups",
]
