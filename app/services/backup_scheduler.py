"""app/services/backup_scheduler.py — orchestrate local + R2 backups.

Per dev plan §9 Task 7 + v2 §7 (backup scheduler).

Called from main.py's lifespan handler on every app startup. Behavior:

1. If `last_backup_at` is older than `BACKUP_THRESHOLD_HOURS` (default 24h),
   OR if there are no backups yet → run a new backup.
2. The backup:
   a. Exports the current SQLite DB to a timestamped .xlsx in BACKUP_DIR.
   b. If R2 is configured (`r2.toml` exists), encrypts the SQLite snapshot
      and uploads to R2 under a versioned key.
   c. Prunes local backups older than KEEP_LOCAL_BACKUPS_DAYS.
3. Updates `app_meta` row `last_backup_at` so the UI can show
   "último backup: hace N horas" + a stale-warning.

The actual encryption + upload lives in `r2_backup.py`. This module is the
orchestrator: it's idempotent, has no business logic of its own, and is
covered by unit tests with fake storage.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.config import BACKUP_DIR, BACKUP_THRESHOLD_HOURS, KEEP_LOCAL_BACKUPS_DAYS
from app.rms.models import AppMeta
from app.services.export_csv import to_dir as to_csv_dir
from app.services.export_xlsx import to_file
from app.services.r2_backup import (
    Boto3Storage,
    InMemoryStorage,
    Storage,
    StorageError,
    encrypt_and_upload,
    load_or_create_key,
    load_r2_settings,
    make_boto3_client,
)

KEY_FILE_NAME = "r2-encryption.key"
APP_META_LAST_BACKUP = "last_backup_at"
APP_META_LAST_R2_BACKUP = "last_r2_backup_at"
APP_META_BACKUP_WARN = "backup_stale_warning"


@dataclass
class BackupResult:
    """Result of a backup run. Used for tests + future logging/UI."""

    local_path: Path | None
    local_pruned: int
    r2_uploaded: bool
    r2_key: str | None
    skipped: bool
    reason: str


def _get_meta(session: Session, key: str) -> str | None:
    row = session.scalars(select(AppMeta).where(AppMeta.key == key)).first()
    return row.value if row else None


def _set_meta(session: Session, key: str, value: str) -> None:
    row = session.scalars(select(AppMeta).where(AppMeta.key == key)).first()
    if row is None:
        session.add(AppMeta(key=key, value=value, updated_at=datetime.now().isoformat()))
    else:
        row.value = value
        row.updated_at = datetime.now().isoformat()


def _last_backup_at_meta(session: Session) -> datetime | None:
    s = _get_meta(session, APP_META_LAST_BACKUP)
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _needs_backup(last: datetime | None, threshold_hours: int) -> bool:
    if last is None:
        return True
    return datetime.now() - last > timedelta(hours=threshold_hours)


def _prune_old_local_backups(folder: Path, keep_last_n: int) -> int:
    """Keep the N most recent .xlsx backups; delete the rest."""
    if not folder.exists():
        return 0
    files = sorted(
        folder.glob("rms-backup-*.xlsx"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    deleted = 0
    for f in files[keep_last_n:]:
        try:
            f.unlink()
            deleted += 1
        except OSError:
            pass
    return deleted


def _prune_old_csv_backups(folder: Path, keep_last_n: int) -> int:
    """Keep the N most recent sets of CSV backups; delete the rest.

    Files are matched on the timestamp prefix so we keep the N most recent
    *export runs* (each run writes 8 files, one per table). We don't split
    the same timestamp's files across the cutoff.
    """
    if not folder.exists():
        return 0
    files = list(folder.glob("rms-csv-*.csv"))
    if not files:
        return 0
    # Group by timestamp prefix (rms-csv-YYYYMMDD-HHMMSS-...)
    timestamps: dict[str, list[Path]] = {}
    for f in files:
        # Filename: rms-csv-YYYYMMDD-HHMMSS-<table>.csv
        parts = f.name.split("-", 4)
        if len(parts) < 5:
            continue
        ts = "-".join(parts[1:4])  # YYYYMMDD-HHMMSS
        timestamps.setdefault(ts, []).append(f)
    # Sort timestamps newest-first (filenames sort the same as timestamps)
    sorted_ts = sorted(timestamps.keys(), reverse=True)
    deleted = 0
    for ts in sorted_ts[keep_last_n:]:
        for f in timestamps[ts]:
            try:
                f.unlink()
                deleted += 1
            except OSError:
                pass
    return deleted


def _prune_old_sqlite_snapshots(folder: Path, keep_last_n: int) -> int:
    """Keep the N most recent SQLite snapshots; delete the rest."""
    if not folder.exists():
        return 0
    files = sorted(
        folder.glob("rms-snapshot-*.sqlite"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    deleted = 0
    for f in files[keep_last_n:]:
        try:
            f.unlink()
            deleted += 1
        except OSError:
            pass
    return deleted


def _build_storage() -> Storage | None:
    """Build an R2 Storage adapter if configured; else None.

    Returns None when R2 isn't configured — caller treats None as
    "skip R2 step".
    """
    settings = load_r2_settings()
    if settings is None:
        return None
    client = make_boto3_client(settings)
    return Boto3Storage(client=client, bucket=settings.bucket)


def run_backup(
    session: Session,
    db_path: Path,
    *,
    backup_dir: Path = BACKUP_DIR,
    threshold_hours: int = BACKUP_THRESHOLD_HOURS,
    keep_last_n: int = KEEP_LOCAL_BACKUPS_DAYS,
    key_file: Path | None = None,
    storage: Storage | None = None,
    now: datetime | None = None,
) -> BackupResult:
    """Run a backup if needed. Returns a BackupResult describing what happened.

    Args:
        session: SQLAlchemy session. Reads/writes app_meta.
        db_path: Path to the SQLite database file. The R2 snapshot is
            a fresh copy of this file taken under WAL awareness.
        backup_dir: Local directory for .xlsx exports. Defaults to config.
        threshold_hours: Only back up if last_backup_at is older than this.
        keep_last_n: Prune local backups beyond this count.
        key_file: Path to the Fernet key. Defaults to BACKUP_DIR / "r2-encryption.key".
        storage: Inject a Storage for tests. None → use real R2 if configured.
        now: Inject "now" for tests. None → use datetime.now().
    """
    now = now or datetime.now()
    last_backup = _last_backup_at_meta(session)

    if not _needs_backup(last_backup, threshold_hours):
        return BackupResult(
            local_path=None,
            local_pruned=0,
            r2_uploaded=False,
            r2_key=None,
            skipped=True,
            reason=f"Last backup at {last_backup.isoformat()} is within {threshold_hours}h threshold",
        )

    # 1. Local xlsx export (human-readable; monthly report for the operator)
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    local_path = backup_dir / f"rms-backup-{timestamp}.xlsx"
    written = to_file(session, local_path)
    assert written == local_path.resolve() or written == local_path

    # 1b. CSV exports (diffable, importable anywhere; one file per table)
    to_csv_dir(session, backup_dir)

    # 1c. SQLite snapshot (byte-perfect restore; takes copy under WAL lock)
    snap_path = backup_dir / f"rms-snapshot-{timestamp}.sqlite"
    import sqlite3

    with sqlite3.connect(str(db_path)) as src:
        with sqlite3.connect(str(snap_path)) as dst:
            src.backup(dst)

    # 2. Prune old local backups (xlsx only; CSVs and snapshots are pruned
    #    in their own folders below — keeps the policy simple)
    pruned = _prune_old_local_backups(backup_dir, keep_last_n)
    pruned += _prune_old_csv_backups(backup_dir, keep_last_n)
    pruned += _prune_old_sqlite_snapshots(backup_dir, keep_last_n)

    # 3. Update last_backup_at meta
    _set_meta(session, APP_META_LAST_BACKUP, now.isoformat())
    _set_meta(session, APP_META_BACKUP_WARN, "false")
    session.commit()

    # 4. R2 upload (best-effort; failure does not invalidate local backup)
    r2_uploaded = False
    r2_key: str | None = None
    r2_storage = storage
    if r2_storage is None:
        r2_storage = _build_storage()

    if r2_storage is not None:
        try:
            key_path = key_file or (backup_dir / KEY_FILE_NAME)
            fernet_key = load_or_create_key(key_path)
            # Re-use the local snapshot we already wrote (1c above).
            plaintext = snap_path.read_bytes()
            r2_key = f"rms-snapshots/{timestamp}.sqlite.enc"
            encrypt_and_upload(r2_storage, fernet_key, r2_key, plaintext)
            _set_meta(
                session,
                APP_META_LAST_R2_BACKUP,
                now.isoformat(),
            )
            session.commit()
            r2_uploaded = True
        except StorageError as exc:
            # Don't crash the app on R2 failure; log and continue.
            # Real logging is added in Batch 5.5; for now we leave a
            # sentinel value the UI can read.
            r2_key = None  # upload never completed; clear the placeholder
            _set_meta(
                session,
                "last_r2_backup_error",
                f"{now.isoformat()}: {exc}",
            )
            session.commit()

    return BackupResult(
        local_path=local_path,
        local_pruned=pruned,
        r2_uploaded=r2_uploaded,
        r2_key=r2_key,
        skipped=False,
        reason="Backup completed",
    )


__all__ = [
    "BackupResult",
    "run_backup",
    "APP_META_LAST_BACKUP",
    "APP_META_LAST_R2_BACKUP",
    "APP_META_BACKUP_WARN",
    "InMemoryStorage",
]
