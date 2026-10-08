"""app/rms/rollback.py — one-command migration rollback (SASKIA-209).

Forward-only migrations (AGENTS.md rule 13) mean the undo path is
**restore-to-pre-migration-state**, not down-migrations. Rule 17
already writes a fail-closed pre-migration backup before every
migration (`sazon-pre-mig-v<A>-to-v<B>-<ts>.json.gz`); this module
turns that archive into a one-command, integrity-checked,
version-marked restore.

What rollback(v) does (SQLite, prod shape):
  1. Locate the newest pre-migration backup whose to_version == the
     CURRENT schema version (that archive captured the state just
     before `current` was applied — i.e. the state AT the target).
  2. Archive the CURRENT (suspect) state first — evidence + retry
     point: `sazon-post-mig-rollback-evidence-v<N>-<ts>.json.gz`.
  3. Restore the pre-migration archive into a FRESH temp DB file and
     run `PRAGMA integrity_check` on it.
  4. Atomically os.replace() the temp file over the live DB. WAL
     sidecars are removed (they belong to the old incarnation).
  5. Verify the restored schema_version == target; write an
     app_meta `migration_rollback_log` entry (JSON, append-style key
     per rollback: `migration_rollback_log:<ts>`).

What it does NOT do:
  - No Postgres path (prod is SQLite; the Postgres CheckConstraints
    in models_legacy are parity-only). Refuses loudly on non-SQLite.
  - No data reversal: rows written by the rolled-back migration's
    data backfills stay in the backup as they were — restore is
    whole-file, so this is inherent.
  - No re-migration: run `sazon migrate` afterwards to re-apply.

Fail-closed everywhere: missing backup, wrong version, integrity
failure, non-SQLite URL → RollbackError, live DB untouched.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PRE_MIG_RE = re.compile(
    r"sazon-pre-mig-v(?P<from>\d+)-to-v(?P<to>\d+)-(?P<ts>\d{8}T\d{6}Z)\.json\.gz$"
)


class RollbackError(RuntimeError):
    """Rollback refused — live DB untouched."""


@dataclass
class RollbackResult:
    previous_version: int
    restored_version: int
    backup_used: Path
    evidence_path: Path
    live_db: Path
    log_key: str


def find_rollback_backup(current_version: int, backup_dir: Path | str) -> Path:
    """Newest pre-migration backup whose to_version == current_version.

    The archive `pre-mig-v<A>-to-v<B>` captured the DB state BEFORE v<B>
    was applied — i.e. the state AT v<A>. So rolling back `current`=B
    restores archive with to==B (landing at A=B-1, or wherever A was).
    """
    backup_dir = Path(backup_dir)
    if not backup_dir.exists():
        raise RollbackError(f"backup dir does not exist: {backup_dir}")

    candidates: list[tuple[str, Path, int, int]] = []
    for p in backup_dir.glob("sazon-pre-mig-v*.json.gz"):
        m = PRE_MIG_RE.match(p.name)
        if not m:
            continue
        candidates.append((m.group("ts"), p, int(m.group("from")), int(m.group("to"))))

    matching = [c for c in candidates if c[3] == current_version]
    if not matching:
        raise RollbackError(
            f"No pre-migration backup with to_version={current_version} in {backup_dir}. "
            f"Available to_versions: {sorted({c[3] for c in candidates})}"
        )
    matching.sort(key=lambda c: c[0], reverse=True)  # newest ts wins
    return matching[0][1]


def _sqlite_integrity_check(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        if not row or row[0] != "ok":
            raise RollbackError(f"restored DB failed integrity_check: {row}")
    finally:
        conn.close()


def _read_schema_version(db_path: Path) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("SELECT value FROM app_meta WHERE key='schema_version'").fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def _write_rollback_log(db_path: Path, entry: dict[str, Any]) -> str:
    """Append-style log: one app_meta row per rollback event."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    key = f"migration_rollback_log:{ts}"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "INSERT INTO app_meta (key, value, updated_at) VALUES (?, ?, ?)",
            (key, json.dumps(entry, ensure_ascii=False), entry["rolled_back_at"]),
        )
        conn.commit()
    finally:
        conn.close()
    return key


def rollback_sqlite(
    engine_or_url: Any,
    *,
    to_version: int | None = None,
    backup_dir: Path | str | None = None,
) -> RollbackResult:
    """Roll the SQLite DB back one migration using rule-17 archives.

    engine_or_url: a SQLAlchemy Engine OR a sqlite URL string
    ('sqlite:////path/db.sqlite'). to_version: optional explicit target
    (defaults to current-1 semantics via the matching backup's from).
    """
    # Resolve the live DB path
    url = getattr(engine_or_url, "url", None)
    raw = str(url) if url is not None else str(engine_or_url)
    if not raw.startswith("sqlite"):
        raise RollbackError(
            f"rollback supports SQLite only (got {raw.split(':')[0]}). "
            "For Postgres use point-in-time recovery on the server."
        )
    db_path = Path(raw.replace("sqlite:///", "", 1).replace("sqlite://", "", 1))
    if not db_path.exists():
        raise RollbackError(f"live DB not found: {db_path}")

    if backup_dir is None:
        from app.rms.db import _backup_dir_path

        backup_dir = _backup_dir_path()
    backup_dir_path = Path(backup_dir)

    current = _read_schema_version(db_path)
    if current <= 1:
        raise RollbackError(f"schema_version={current}: nothing to roll back")

    backup = find_rollback_backup(current, backup_dir_path)

    # Target version = the backup's from_version (state BEFORE current was applied)
    m = PRE_MIG_RE.match(backup.name)
    assert m is not None
    target = int(m.group("from"))
    if to_version is not None and to_version != target:
        raise RollbackError(
            f"requested to_version={to_version} but the newest matching backup "
            f"restores to {target} ({backup.name}). No intermediate archives."
        )

    # Step 1: evidence archive of the current state
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.rms.backup import backup_database, load_archive, restore_database

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence_path = backup_dir_path / (
        f"sazon-post-mig-rollback-evidence-v{current:04d}-{ts}.json.gz"
    )
    live_engine = create_engine(f"sqlite:///{db_path}")
    LiveSession = sessionmaker(bind=live_engine)
    with LiveSession() as s:
        backup_database(s, evidence_path)
    live_engine.dispose()

    # Step 2: restore into a FRESH temp file + integrity check
    tmp_path = db_path.with_suffix(f".rollback-{ts}.tmp")
    if tmp_path.exists():
        tmp_path.unlink()
    tmp_engine = create_engine(f"sqlite:///{tmp_path}")

    # restore_database() merges into an existing schema; create the bare
    # schema first via init_db on the temp engine, then restore.
    from app.rms.db import init_db

    init_db(tmp_engine)
    TmpSession = sessionmaker(bind=tmp_engine)
    with TmpSession() as ts_session:
        load_archive(evidence_path)  # sanity: evidence archive readable
        restore_database(ts_session, backup)
    tmp_engine.dispose()

    # Step 3: the restored file must be intact AND at the target version
    _sqlite_integrity_check(tmp_path)
    restored_version = _read_schema_version(tmp_path)
    if restored_version != target:
        raise RollbackError(
            f"restored file has schema_version={restored_version}, expected {target}; "
            "refusing to swap."
        )

    # Step 4: log entry written into the TEMP file (so the swap is atomic
    # and the live file never carries a half-logged state)
    log_entry = {
        "rolled_back_at": datetime.now(timezone.utc).isoformat(),
        "from_version": current,
        "to_version": target,
        "backup_used": backup.name,
        "evidence": evidence_path.name,
    }
    log_key = _write_rollback_log(tmp_path, log_entry)

    # Step 5: atomic swap + WAL sidecar cleanup
    for suffix in ("-wal", "-shm"):
        side = Path(str(db_path) + suffix)
        if side.exists():
            side.unlink()
    os.replace(tmp_path, db_path)

    return RollbackResult(
        previous_version=current,
        restored_version=target,
        backup_used=backup,
        evidence_path=evidence_path,
        live_db=db_path,
        log_key=log_key,
    )
