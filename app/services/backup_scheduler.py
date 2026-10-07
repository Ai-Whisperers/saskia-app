"""app/services/backup_scheduler.py — orchestrate local + R2 backups.

Per dev plan §9 Task 7 + v2 §7 (backup scheduler).

Called from main.py's lifespan handler on every app startup. Behavior:

1. If `last_backup_at` is older than `BACKUP_THRESHOLD_HOURS` (default 24h),
   OR if there are no backups yet → run a new backup.
2. The backup:
   a. Exports the current SQLite DB to a timestamped .xlsx in BACKUP_DIR.
   b. If a DNI file is provisioned (D.5), encrypts the SQLite snapshot
      with AES-256-GCM (PBKDF2-derived key from the DNI) and writes
      `rms-snapshot-YYYYMMDD-HHMMSS.sqlite.enc`. If no DNI file is
      configured, falls back to the legacy cleartext path with a loud
      warning log (so the operator knows backups are not encrypted).
   c. If R2 is configured (`r2.toml` exists), encrypts the same snapshot
      (DNI-derived AES-256-GCM, or Fernet fallback) and uploads to R2
      under a versioned key.
   d. Prunes local backups older than KEEP_LOCAL_BACKUPS_DAYS.
3. Updates `app_meta` row `last_backup_at` so the UI can show
   "último backup: hace N horas" + a stale-warning.

The actual encryption + upload lives in `r2_backup.py` and
`backup_crypto.py`. This module is the orchestrator: it's
idempotent, has no business logic of its own, and is covered by
unit tests with fake storage.

D.5 — DNI-derived backup encryption. The DNI file is operator-managed
(typically on a USB stick, NOT on the VPS). When the file is
provisioned (mode 0600/0400, non-empty), all snapshots are encrypted
with AES-256-GCM using a key derived from the DNI at backup time.
The key is never persisted; rotating the DNI rotates the
keyspace an attacker must search to decrypt old backups.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.config import (
    ASUNCION_TZ,
    BACKUP_DIR,
    BACKUP_DNI_FILE,
    BACKUP_THRESHOLD_HOURS,
    KEEP_LOCAL_BACKUPS_DAYS,
)
from app.rms.models import AppMeta
from app.services.backup_crypto import (
    BackupCryptoError,
    encrypt_backup,
)
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

logger = logging.getLogger(__name__)

KEY_FILE_NAME = "r2-encryption.key"
APP_META_LAST_BACKUP = "last_backup_at"
APP_META_LAST_R2_BACKUP = "last_r2_backup_at"
APP_META_BACKUP_WARN = "backup_stale_warning"

# Re-export for tests and for the cron wrapper (which needs to
# monkeypatch it). Tests in test_backup_scheduler_encryption.py
# import this name explicitly.
BACKUP_DNI_FILE = BACKUP_DNI_FILE


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
        session.add(AppMeta(key=key, value=value, updated_at=datetime.now(ASUNCION_TZ).isoformat()))
    else:
        row.value = value
        row.updated_at = datetime.now(ASUNCION_TZ).isoformat()


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
    from datetime import timezone as _tz

    now = datetime.now(_tz.utc)
    if last.tzinfo is None:
        # last was stored naive (legacy rows) — assume UTC
        last = last.replace(tzinfo=_tz.utc)
    return now - last > timedelta(hours=threshold_hours)


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
    """Keep the N most recent SQLite snapshots; delete the rest.

    D.5: snapshots are now `*.sqlite.enc` (encrypted) when a DNI
    is provisioned. We glob both patterns so the prune step
    doesn't leave orphan .sqlite.enc files behind on a deploy
    that transitions a system from legacy to encrypted mode.
    """
    if not folder.exists():
        return 0
    files = sorted(
        list(folder.glob("rms-snapshot-*.sqlite")) +
        list(folder.glob("rms-snapshot-*.sqlite.enc")),
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


def _resolve_dni(dni_path: Path | None = None) -> str | None:
    """Load the DNI from the operator-provisioned file.

    Returns the DNI string if the file exists, is mode 0600/0400,
    and is non-empty. Returns None otherwise (with a warning log
    so the operator knows backups are unencrypted).

    The optional `dni_path` arg lets tests point at a fixture
    file; production code uses the module-level BACKUP_DNI_FILE
    which is read fresh on each call (so deploys that change the
    env var take effect on the next backup run).
    """
    from app.services.backup_crypto import derive_key_from_dni_file

    target = Path(dni_path) if dni_path is not None else Path(BACKUP_DNI_FILE)
    try:
        return derive_key_from_dni_file(target)
    except BackupCryptoError as exc:
        # Loud warning so the operator sees this in logs — it means
        # backups are running unencrypted. NOT a crash, because the
        # legacy behavior is "backup anyway" and we don't want to
        # brick the lifespan on a missing file.
        logger.warning(
            "D.5 backup encryption DISABLED: %s. "
            "Backups are running unencrypted. See "
            "docs/operations/backup-cron.md to provision the DNI file.",
            exc,
        )
        return None


def _migrate_legacy_fernet_key(backup_dir: Path, dni: str) -> None:
    """One-time migration: delete the legacy `r2-encryption.key`
    file when a DNI is provisioned.

    Before D.5, the Fernet key lived on disk and encrypted every
    R2 upload. After D.5, the key is derived from the DNI and
    the file is dead weight (and a target for an attacker — they
    could decrypt all old backups with it). Delete it loudly
    so the operator sees the action in logs.

    Idempotent: if the file doesn't exist, no-op.
    """
    legacy = backup_dir / KEY_FILE_NAME
    if not legacy.exists():
        return
    try:
        legacy.unlink()
        logger.warning(
            "D.5 migration: removed legacy r2-encryption.key at %s. "
            "All backups are now encrypted with AES-256-GCM using the "
            "DNI-derived key. Old Fernet-encrypted R2 backups from "
            "before this deploy CANNOT be decrypted by the new code — "
            "the operator must have kept the old key file separately "
            "if they need to restore from a pre-D.5 backup.",
            legacy,
        )
    except OSError as exc:
        logger.error(
            "D.5 migration FAILED to remove legacy r2-encryption.key "
            "at %s: %s. The file is no longer used but is still on "
            "disk. Remove it manually after deploy.",
            legacy, exc,
        )


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
    dni: str | None = None,
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
            Used only when no DNI is provisioned (legacy path).
        storage: Inject a Storage for tests. None → use real R2 if configured.
        now: Inject "now" for tests. None → use datetime.now(ASUNCION_TZ).
        dni: Inject the DNI for tests. None → read from
            BACKUP_DNI_FILE env / default path. If neither works,
            fall back to the legacy cleartext + Fernet R2 path
            with a loud warning.
    """
    now = now or datetime.now(ASUNCION_TZ)
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

    # 0. Resolve DNI for encryption. If not provisioned, we fall
    #    back to the legacy cleartext + Fernet path with a warning.
    #    Production code should always have the file; the fallback
    #    exists for the migration window and for tests.
    if dni is None:
        dni = _resolve_dni()

    # 1. Local xlsx export (human-readable; monthly report for the operator)
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    local_path = backup_dir / f"rms-backup-{timestamp}.xlsx"
    written = to_file(session, local_path)
    assert written == local_path.resolve() or written == local_path

    # 1b. CSV exports (diffable, importable anywhere; one file per table)
    to_csv_dir(session, backup_dir)

    # 1c. SQLite snapshot (byte-perfect restore; takes copy under WAL lock)
    snap_path_cleartext = backup_dir / f"rms-snapshot-{timestamp}.sqlite"
    snap_path_encrypted = backup_dir / f"rms-snapshot-{timestamp}.sqlite.enc"
    import sqlite3

    with sqlite3.connect(str(db_path)) as src:
        with sqlite3.connect(str(snap_path_cleartext)) as dst:
            src.backup(dst)
    # Read the cleartext into memory while we have it. We use it
    # twice: once to write the encrypted file to disk, and once
    # to encrypt a fresh copy for the R2 upload (different salt
    # + nonce = different ciphertext, which is correct for
    # authenticated encryption).
    snapshot_plaintext = snap_path_cleartext.read_bytes()

    # 1d. D.5 — encrypt the snapshot on disk if DNI is available.
    #     When encrypted, the cleartext file is deleted (it was
    #     only a staging file for the encryption). The encrypted
    #     file is what survives on the local disk for restore;
    #     the R2 upload gets a freshly-encrypted copy.
    if dni is not None:
        ciphertext = encrypt_backup(snapshot_plaintext, dni)
        snap_path_encrypted.write_bytes(ciphertext)
        # Wipe the cleartext staging file. If the encryption
        # crashed mid-write, the cleartext is still there for
        # forensics (no data lost). On success, the cleartext
        # is the dangerous artifact — delete it.
        try:
            snap_path_cleartext.unlink()
        except OSError as exc:
            logger.error(
                "D.5: failed to remove cleartext snapshot %s after "
                "encrypting: %s. The file is now redundant; remove "
                "it manually to free disk space.",
                snap_path_cleartext, exc,
            )
        # One-time migration: delete the legacy Fernet key on the
        # first run with DNI. Idempotent.
        _migrate_legacy_fernet_key(backup_dir, dni)
    else:
        # Legacy path: cleartext snapshot, no encryption on disk.
        # The on-disk file is left in place for backward compat;
        # the prune step (which globs `rms-snapshot-*.sqlite` and
        # `rms-snapshot-*.sqlite.enc`) handles retention.
        pass

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
            if dni is not None:
                # D.5: encrypt the snapshot plaintext fresh for
                # the R2 upload. We do NOT upload the encrypted
                # file from disk (that would be encrypting already-
                # encrypted bytes with a different key — a bug).
                # The cost is one extra PBKDF2 derivation + GCM
                # encrypt (~1s total, on top of the 1s we already
                # spent for the local encryption).
                r2_ciphertext = encrypt_backup(snapshot_plaintext, dni)
                r2_key = f"rms-snapshots/{timestamp}.sqlite.enc"
                r2_storage.put(r2_key, r2_ciphertext)
                _set_meta(
                    session,
                    APP_META_LAST_R2_BACKUP,
                    now.isoformat(),
                )
                session.commit()
                r2_uploaded = True
            else:
                # Legacy path: Fernet on the cleartext snapshot.
                key_path = key_file or (backup_dir / KEY_FILE_NAME)
                fernet_key = load_or_create_key(key_path)
                r2_key = f"rms-snapshots/{timestamp}.sqlite.enc"
                encrypt_and_upload(r2_storage, fernet_key, r2_key, snapshot_plaintext)
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
    "APP_META_BACKUP_WARN",
    "APP_META_LAST_BACKUP",
    "APP_META_LAST_R2_BACKUP",
    "BACKUP_DNI_FILE",
    "BackupResult",
    "InMemoryStorage",
    "run_backup",
]
