"""Auto-backup on app startup.

Per docs/operations/2026-09-fase-1-specs.md §1.

Every time the app starts, if the last backup is more than 24 hours old,
automatically export the SQLite database to a timestamped .xlsx file in
a configured local folder. No user action required.

If the last backup is more than 7 days old, set a flag the UI can read to
show a notification: "Hace más de 7 días que no exportás."

This module is dependency-free except for the app's own modules (config,
export_xlsx).

Batch B4 (2026-10-07) note: the threshold constants that previously
lived as module-level globals (``AUTO_BACKUP_THRESHOLD_HOURS``,
``WARN_THRESHOLD_DAYS``, ``DEFAULT_KEEP_LAST_N``) are kept here as
backward-compat shims — they now alias ``DEFAULT_BACKUP_CONFIG``.
The values match what was previously hardcoded (24, 7, 30). The real
production backup scheduler (``app/services/backup_scheduler.py``) reads
its threshold from an env var (``AIW_RMS_BACKUP_HOURS``) — those are
the values that gate the real backup. This module is the helper-only
public API used by tests + small scripts.

The new ``backup.*`` SettingsKV entries (``backup.auto_threshold_hours``,
``backup.warn_threshold_days``, ``backup.keep_last_n``) are advisory:
they let an operator set defaults from /admin/settings, but wiring them
into the production scheduler is a separate decision (would require the
scheduler to fetch from the DB at startup).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from app.rms.config import ASUNCION_TZ

# Batch B4 (2026-10-07): defaults for the operator-tunable thresholds.
# Mirror of the entries in app/rms/settings.py:SETTINGS under
# SettingGroup.BACKUP. Kept in sync via the corresponding test.
DEFAULT_BACKUP_CONFIG: dict[str, int] = {
    "auto_threshold_hours": 24,  # run auto-backup if last > N hours
    "warn_threshold_days": 7,  # show warning if last > N days
    "keep_last_n": 30,  # prune backups beyond this count
}

# Backward-compat module-level constants. Old code + tests still
# import these by name; they now alias the canonical DEFAULT_BACKUP_CONFIG.
AUTO_BACKUP_THRESHOLD_HOURS = DEFAULT_BACKUP_CONFIG["auto_threshold_hours"]
WARN_THRESHOLD_DAYS = DEFAULT_BACKUP_CONFIG["warn_threshold_days"]
DEFAULT_KEEP_LAST_N = DEFAULT_BACKUP_CONFIG["keep_last_n"]


def needs_auto_backup(
    last_backup_at: object,
    threshold_hours: Optional[int] = None,
    *,
    backup_cfg: Optional[dict[str, int]] = None,
) -> bool:
    """True if last_backup_at is older than threshold, or no backup yet.

    Args:
      last_backup_at: datetime of last backup (tz-aware, ASUNCION_TZ) or None.
      threshold_hours: explicit threshold. When None, falls back to
        ``backup_cfg["auto_threshold_hours"]`` (or DEFAULT_BACKUP_CONFIG).
      backup_cfg: optional override dict (Batch B4, 2026-10-07). When
        provided, partial dicts merge with defaults.

    Returns:
      True iff a new auto-backup should run.

    Examples:
        >>> needs_auto_backup(None)
        True
        >>> from datetime import datetime, timedelta
        >>> needs_auto_backup(datetime.now(ASUNCION_TZ) - timedelta(hours=1))
        False
        >>> needs_auto_backup(datetime.now(ASUNCION_TZ) - timedelta(hours=25))
        True
    """
    cfg = dict(DEFAULT_BACKUP_CONFIG)
    if backup_cfg is not None:
        cfg.update(backup_cfg)
    if threshold_hours is None:
        threshold_hours = cfg["auto_threshold_hours"]
    if last_backup_at is None:
        return True
    return datetime.now(ASUNCION_TZ) - last_backup_at > timedelta(hours=threshold_hours)


def needs_warning(
    last_backup_at: object,
    threshold_days: Optional[int] = None,
    *,
    backup_cfg: Optional[dict[str, int]] = None,
) -> bool:
    """True if last_backup_at is older than threshold_days, or no backup yet.

    Args: same shape as ``needs_auto_backup``. threshold_days falls back to
    ``backup_cfg["warn_threshold_days"]`` when None.
    """
    cfg = dict(DEFAULT_BACKUP_CONFIG)
    if backup_cfg is not None:
        cfg.update(backup_cfg)
    if threshold_days is None:
        threshold_days = cfg["warn_threshold_days"]
    if last_backup_at is None:
        return True
    return datetime.now(ASUNCION_TZ) - last_backup_at > timedelta(days=threshold_days)


def last_backup_at(folder: Path) -> object:
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
    return datetime.fromtimestamp(max(f.stat().st_mtime for f in files), tz=ASUNCION_TZ)


def backup_filename(timestamp: datetime | None = None) -> str:
    """Generate the standard backup filename for a given timestamp."""
    ts = (timestamp or datetime.now(ASUNCION_TZ)).strftime("%Y%m%d-%H%M%S")
    return f"rms-backup-{ts}.xlsx"


def prune_old_backups(
    folder: Path,
    keep_last_n: Optional[int] = None,
    *,
    backup_cfg: Optional[dict[str, int]] = None,
) -> int:
    """Delete oldest backups beyond keep_last_n. Returns count deleted.

    Backups are kept newest-first; everything beyond keep_last_n is deleted.

    Args:
      folder: directory containing the .xlsx backup files.
      keep_last_n: explicit cap. When None, falls back to
        ``backup_cfg["keep_last_n"]`` (or DEFAULT_BACKUP_CONFIG).
      backup_cfg: optional override dict (Batch B4, 2026-10-07).
    """
    cfg = dict(DEFAULT_BACKUP_CONFIG)
    if backup_cfg is not None:
        cfg.update(backup_cfg)
    if keep_last_n is None:
        keep_last_n = cfg["keep_last_n"]
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
    "DEFAULT_BACKUP_CONFIG",
    "DEFAULT_KEEP_LAST_N",
    "WARN_THRESHOLD_DAYS",
    "backup_filename",
    "last_backup_at",
    "needs_auto_backup",
    "needs_warning",
    "prune_old_backups",
]
