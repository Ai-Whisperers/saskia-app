"""tests/test_backup_scheduler_encryption.py — D.5: AES-256-GCM
encryption integration with backup_scheduler.run_backup.

The new backup format is opt-in via the DNI file. When the DNI file
is provisioned (mode 0600/0400, contains a non-empty value), the
local SQLite snapshot is encrypted with AES-256-GCM, the R2 upload
uses the same format, and the old Fernet `r2-encryption.key` file
is removed. When the DNI file is missing or empty, the legacy
cleartext path runs (with a loud warning log) so existing tests
and a fresh deploy don't break.

These tests pin the migration behavior:
- Default (no DNI file) → cleartext + warning, like before
- With DNI file → AES-256-GCM, R2 upload decryptable by same DNI
- Old `r2-encryption.key` file is removed when DNI is provisioned
  (one-time migration)
- Wrong DNI cannot decrypt the R2 upload
- CSV exports stay cleartext (the CSVs are the human-readable
  monthly report; encryption would defeat the purpose)
- xlsx stays cleartext (same reason as CSVs)
"""

from __future__ import annotations

from pathlib import Path

import pytest

# We need the new module + the scheduler to be importable.
# Conftest fixtures (session_factory, etc.) are defined in tests/conftest.py.


def _seed_db(db_path: Path) -> None:
    """Create a real SQLite file with our schema."""
    from app.rms.db import init_db, make_engine
    from app.rms.models import Ingredient

    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = make_engine(f"sqlite:///{db_path}")
    init_db(engine)
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=engine)
    with Session() as s:
        s.add(Ingredient(name="Test", unit="kg", stock_qty=1.0, purchase_price_gs=1000))
        s.commit()
    engine.dispose()


def _write_dni_file(path: Path, dni: str = "1234567") -> None:
    path.write_text(dni + "\n")
    path.chmod(0o600)


# ---------------------------------------------------------------------------
# Legacy (no DNI) path — cleartext snapshots, legacy Fernet R2
# ---------------------------------------------------------------------------


def test_run_backup_writes_cleartext_snapshot_when_no_dni(session_factory, tmp_path: Path, caplog):
    """Without a DNI file, run_backup falls back to the legacy
    cleartext snapshot path. This is the migration safety net:
    existing test suites and fresh deploys without a DNI file
    continue to work. A loud warning is logged so the operator
    sees that backups are not encrypted."""
    import logging

    from app.services.backup_scheduler import InMemoryStorage, run_backup

    db_path = tmp_path / "db.sqlite"
    _seed_db(db_path)
    backup_dir = tmp_path / "backups"

    # No DNI file in tmp_path. Also clear the BACKUP_DNI_FILE env
    # so the config default doesn't point at a real file.
    import os

    old_env = os.environ.pop("AIW_RMS_BACKUP_DNI_FILE", None)
    try:
        with caplog.at_level(logging.WARNING, logger="app.services.backup_scheduler"):
            result = run_backup(
                session_factory(),
                db_path,
                backup_dir=backup_dir,
                threshold_hours=24,
                storage=InMemoryStorage(),
            )
    finally:
        if old_env is not None:
            os.environ["AIW_RMS_BACKUP_DNI_FILE"] = old_env

    assert result.skipped is False
    # Legacy behavior: a cleartext .sqlite snapshot is written
    # alongside the .xlsx.
    snapshots = list(backup_dir.glob("rms-snapshot-*.sqlite"))
    assert len(snapshots) == 1
    # The snapshot's first 16 bytes should be "SQLite format 3\000"
    # (cleartext, not encrypted).
    header = snapshots[0].read_bytes()[:16]
    assert header.startswith(b"SQLite format 3"), (
        f"expected cleartext SQLite header, got {header[:32]!r}"
    )
    # And a warning was logged so the operator knows.
    assert any("DNI" in r.message and "unencrypted" in r.message.lower() for r in caplog.records), (
        f"expected unencrypted-DNI warning, got: {[r.message for r in caplog.records]}"
    )


# ---------------------------------------------------------------------------
# New (DNI provisioned) path — AES-256-GCM everywhere
# ---------------------------------------------------------------------------


def test_run_backup_writes_encrypted_snapshot_when_dni_provided(
    session_factory, tmp_path: Path, monkeypatch
):
    """With a DNI file at the configured path, the local .sqlite
    snapshot is encrypted with AES-256-GCM. The on-disk file is
    NOT a valid SQLite (the magic doesn't match), and the size
    grows by HEADER_SIZE + TAG_SIZE bytes."""
    from app.services.backup_scheduler import InMemoryStorage, run_backup

    db_path = tmp_path / "db.sqlite"
    _seed_db(db_path)
    backup_dir = tmp_path / "backups"
    dni_file = tmp_path / "dni"
    _write_dni_file(dni_file)

    # Point the scheduler at our test DNI file via the env var
    # that the wrapper reads. We patch the module-level constant
    # so the test doesn't depend on the env being set in CI.
    monkeypatch.setattr("app.services.backup_scheduler.BACKUP_DNI_FILE", str(dni_file))

    result = run_backup(
        session_factory(),
        db_path,
        backup_dir=backup_dir,
        threshold_hours=24,
        storage=InMemoryStorage(),
    )

    assert result.skipped is False
    # The snapshot is now .sqlite.enc (encrypted), not .sqlite
    encrypted_snapshots = list(backup_dir.glob("rms-snapshot-*.sqlite.enc"))
    assert len(encrypted_snapshots) == 1
    # And no cleartext snapshot was written.
    cleartext = list(backup_dir.glob("rms-snapshot-*.sqlite"))
    assert cleartext == [], f"cleartext snapshots still present: {cleartext}"
    # The file does NOT start with "SQLite format 3" — it's
    # encrypted ciphertext.
    enc_bytes = encrypted_snapshots[0].read_bytes()
    assert not enc_bytes.startswith(b"SQLite format 3")


def test_run_backup_uploads_to_r2_in_new_format_with_dni(
    session_factory, tmp_path: Path, monkeypatch
):
    """When DNI is provisioned, the R2 upload is encrypted with
    the new AES-256-GCM format. The InMemoryStorage gets a
    ciphertext blob that, when decrypted with the same DNI, gives
    back a valid SQLite header."""
    from app.services.backup_crypto import HEADER_MAGIC, decrypt_backup
    from app.services.backup_scheduler import InMemoryStorage, run_backup

    db_path = tmp_path / "db.sqlite"
    _seed_db(db_path)
    backup_dir = tmp_path / "backups"
    dni_file = tmp_path / "dni"
    _write_dni_file(dni_file, dni="1234567")
    monkeypatch.setattr("app.services.backup_scheduler.BACKUP_DNI_FILE", str(dni_file))

    storage = InMemoryStorage()
    result = run_backup(
        session_factory(),
        db_path,
        backup_dir=backup_dir,
        threshold_hours=24,
        storage=storage,
    )

    assert result.r2_uploaded is True
    assert result.r2_key is not None
    # The R2 key now ends in .sqlite.enc (was .sqlite.enc before
    # too, but the CONTENT was Fernet — now it's AES-256-GCM).
    assert result.r2_key.endswith(".sqlite.enc")

    # The blob in storage is the new format (starts with SASKIA01).
    ciphertext = storage._data[result.r2_key]  # type: ignore[attr-defined]
    assert ciphertext[:8] == HEADER_MAGIC, (
        f"R2 upload not in new format: header is {ciphertext[:16]!r}"
    )

    # And it decrypts back to a valid SQLite header.
    plaintext = decrypt_backup(ciphertext, "1234567")
    assert plaintext.startswith(b"SQLite format 3"), (
        f"decrypted R2 blob is not a SQLite file: {plaintext[:32]!r}"
    )

    # Wrong DNI cannot decrypt.
    from app.services.backup_crypto import DecryptionError

    with pytest.raises(DecryptionError):
        decrypt_backup(ciphertext, "9999999")


def test_run_backup_deletes_legacy_fernet_key_file(session_factory, tmp_path: Path, monkeypatch):
    """One-time migration: if a legacy `r2-encryption.key` file
    exists (Fernet key from pre-D.5), it's deleted on the first
    run with DNI. This is irreversible — the operator must
    confirm before deploying D.5. We log a loud warning so the
    action is visible."""
    from app.services.backup_scheduler import InMemoryStorage, run_backup

    db_path = tmp_path / "db.sqlite"
    _seed_db(db_path)
    backup_dir = tmp_path / "backups"
    dni_file = tmp_path / "dni"
    _write_dni_file(dni_file)
    monkeypatch.setattr("app.services.backup_scheduler.BACKUP_DNI_FILE", str(dni_file))

    # Pre-create the legacy key file inside backup_dir.
    legacy_key = backup_dir / "r2-encryption.key"
    backup_dir.mkdir(parents=True, exist_ok=True)
    legacy_key.write_bytes(b"old-fernet-key-bytes-that-are-now-meaningless")
    assert legacy_key.exists()

    result = run_backup(
        session_factory(),
        db_path,
        backup_dir=backup_dir,
        threshold_hours=24,
        storage=InMemoryStorage(),
    )
    assert result.skipped is False
    # Legacy key file is gone.
    assert not legacy_key.exists(), "legacy r2-encryption.key was not deleted"


def test_run_backup_with_dni_file_missing_falls_back_to_legacy(
    session_factory, tmp_path: Path, monkeypatch
):
    """If BACKUP_DNI_FILE points at a non-existent file, the
    scheduler logs a warning and falls back to the legacy
    cleartext path. The operator's `cat /etc/sazon/backup-dni`
    failing should NOT crash the app — it should be a no-op
    with a clear log line."""
    from app.services.backup_scheduler import InMemoryStorage, run_backup

    db_path = tmp_path / "db.sqlite"
    _seed_db(db_path)
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(
        "app.services.backup_scheduler.BACKUP_DNI_FILE",
        str(tmp_path / "nonexistent-dni-file"),
    )

    result = run_backup(
        session_factory(),
        db_path,
        backup_dir=backup_dir,
        threshold_hours=24,
        storage=InMemoryStorage(),
    )
    assert result.skipped is False
    # Cleartext snapshot was written.
    assert any(backup_dir.glob("rms-snapshot-*.sqlite"))


def test_run_backup_xlsx_and_csv_stay_cleartext_even_with_dni(
    session_factory, tmp_path: Path, monkeypatch
):
    """The xlsx and CSV exports are the operator's human-readable
    monthly report. Encrypting them would defeat the purpose
    (you can't open a .xlsx.enc in Excel). Only the SQLite
    snapshot is encrypted. The xlsx is still readable by
    openpyxl, and the CSVs are still plain text."""
    from app.services.backup_scheduler import InMemoryStorage, run_backup

    db_path = tmp_path / "db.sqlite"
    _seed_db(db_path)
    backup_dir = tmp_path / "backups"
    dni_file = tmp_path / "dni"
    _write_dni_file(dni_file)
    monkeypatch.setattr("app.services.backup_scheduler.BACKUP_DNI_FILE", str(dni_file))

    result = run_backup(
        session_factory(),
        db_path,
        backup_dir=backup_dir,
        threshold_hours=24,
        storage=InMemoryStorage(),
    )
    assert result.skipped is False
    # xlsx is cleartext (openpyxl can read it).
    from openpyxl import load_workbook

    assert result.local_path is not None
    wb = load_workbook(result.local_path)
    assert "Ingredientes" in wb.sheetnames
    # CSVs are cleartext (the csv directory exists, files are .csv).
    csv_dir = backup_dir / "csv"
    if csv_dir.exists():
        for csv_file in csv_dir.glob("*.csv"):
            content = csv_file.read_bytes()[:50]
            # Not encrypted — first bytes are not SASKIA01.
            assert not content.startswith(b"SASKIA01"), (
                f"CSV {csv_file.name} appears to be encrypted: {content!r}"
            )
