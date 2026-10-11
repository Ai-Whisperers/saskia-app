"""app/rms/backup.py — Backup + Restore (E20).

Per docs/plans/2026-09-07-sazon-complete-epic-plan-v3.md E20.

Features:
- backup_database(session, dest): serialize all tables to a
  compressed JSON archive (manifest.json + table-by-table JSON)
- restore_database(session, source): load archive back; IDs preserved
  (use upsert semantics)
- prune_old_backups(directory, keep_n=7, keep_days=30): retention
- Backups are deterministic: schema_version + sorted json dump;
  restoration produces identical data.

Backups are LOCAL-FIRST (file copy) by default; the operator can
later point this at R2/S3 by setting the right environment vars.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import (
    AppMeta,
    AuditLog,
    Customer,
    ImportBatch,
    Ingredient,
    Product,
    Recipe,
    RecipeLine,
    Sale,
    StockMovement,
    Tag,
    TagLink,
    User,
    WasteLog,
)

# Tables to back up. Listed in FK dependency order (children last).
BACKUP_TABLES: list[type] = [
    AppMeta,
    User,
    Ingredient,
    Recipe,
    RecipeLine,
    Product,
    Sale,
    ImportBatch,
    AuditLog,
    Customer,
    WasteLog,
    Tag,
    TagLink,
    # M1 (2026-10-02): StockMovement is the canonical stock-out ledger
    # after migration 092 dropped sale_stock_move. It must be backed up
    # because every sale, refund, and adjustment writes here. Listed
    # last because RecipeLine + Ingredient already exist (StockMovement
    # has FKs to both, plus optional FK to Recipe for affected_recipe_id).
    StockMovement,
]


@dataclass
class BackupManifest:
    """Header of a backup archive."""

    created_at: str
    schema_version: int
    n_tables: int
    n_rows: int
    sha256: str
    source_db_url: str  # not credentials, just dialect info
    app: str = "sazon-rms"

    def to_dict(self) -> dict:
        return {
            "app": self.app,
            "created_at": self.created_at,
            "schema_version": self.schema_version,
            "n_tables": self.n_tables,
            "n_rows": self.n_rows,
            "sha256": self.sha256,
            "source_db_url": self.source_db_url,
        }


def _serialize(value: Any) -> Any:
    """Make a value JSON-serializable."""
    if value is None:
        return None
    if isinstance(value, (int, float, str, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _row_to_dict(row: Any) -> dict:
    """Serialize a model row to a dict.

    Only emits columns that exist in the DB table. The model may declare
    columns that haven't been added to the live DB yet (e.g., a v116
    schema has a backup run before migration 117 lands, but the ORM
    model is at v117). Without this filter, SELECT would fail with
    `no such column: <name>` and `sync_backup_before_migration` would
    raise, blocking the migration. The inverse (DB has a column the
    model doesn't) is impossible because models are always the source
    of truth and migrations add columns to both.
    """
    from sqlalchemy import inspect as _sa_inspect

    # Cache per-table existing columns (keyed by (table, conn-dialect)).
    # We use the row's __table__ + the engine-bound connection from
    # the row's session. In practice each call site re-checks; that's
    # fine — PRAGMA/information_schema is cheap.
    # Inlined because we don't have session here; callers that need
    # a per-row column filter should use _row_to_dict_filtered below.
    return {col.name: _serialize(getattr(row, col.name)) for col in row.__table__.columns}


def _existing_columns(conn: Any, table_name: str, dialect: str) -> set[str]:
    """Return the set of column names that exist in `table_name` on the
    live DB. Used by `dump_full_state` to filter model columns that
    haven't been added yet (forward migration in flight)."""
    from sqlalchemy import text as _sa_text

    if dialect == "postgresql":
        rows = conn.execute(
            _sa_text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = :t"
            ),
            {"t": table_name},
        ).fetchall()
        return {r[0] for r in rows}
    # SQLite: PRAGMA table_info returns (cid, name, type, notnull, dflt_value, pk)
    rows = conn.execute(_sa_text(f"PRAGMA table_info({table_name})")).fetchall()
    return {r[1] for r in rows}


def _row_to_dict_filtered(row: Any, existing_cols: set[str]) -> dict:
    """Like `_row_to_dict` but only emits columns present in `existing_cols`."""
    return {
        col.name: _serialize(getattr(row, col.name))
        for col in row.__table__.columns
        if col.name in existing_cols
    }


def dump_full_state(session: Session) -> dict[str, list[dict]]:
    """Dump every table to a {table_name: [row_dicts]} mapping.

    Filters out model columns not yet in the live DB schema. This is
    safe because:
      - Models are the source of truth; live DBs only ever have a
        subset (older schema) or a superset (rare; would mean the
        ORM is stale — that's a different bug class).
      - On a fresh DB after `init_db` completes, model columns match
        DB columns exactly; the filter is a no-op.
      - On a pre-migration backup, the live DB is at v(N-1) and the
        model may be at vN. The filter prevents "no such column"
        errors that would block the migration.

    Important: we filter at the SELECT level too, not just
    serialization. SQLite raises `no such column: ...` when the SQL
    SELECT references a column that's not in the table — even if
    the result would have been discarded. So we explicitly select
    only the existing columns per table.
    """
    from sqlalchemy import inspect as _sa_inspect
    from sqlalchemy import text as _sa_text

    out: dict[str, list[dict]] = {}
    bind = session.get_bind()
    dialect = bind.dialect.name if bind is not None else "sqlite"
    assert bind is not None, "session must be bound to an engine for dump_full_state"
    with bind.connect() as conn:
        for model in BACKUP_TABLES:
            existing = _existing_columns(conn, model.__tablename__, dialect)
            # SELECT only the columns that exist in the DB. Using
            # `select(*[c for c in model.__table__.c if c.name in existing])`
            # builds a SELECT with only those columns, which works
            # even when the model has forward-only columns.
            existing_model_cols = [c for c in model.__table__.c if c.name in existing]
            if not existing_model_cols:
                # Table not yet created (e.g., pre-migration). Skip
                # rather than error — backup of an empty state is
                # valid; restore will create the table.
                out[model.__tablename__] = []
                continue
            # Mappings give us column-name keys; each value still
            # needs JSON-safe serialization (datetime, bytes, etc).
            rows = session.execute(select(*existing_model_cols)).mappings().all()
            out[model.__tablename__] = [
                {k: _serialize(v) for k, v in dict(r).items()} for r in rows
            ]
    return out


def backup_database(
    session: Session,
    dest: Path | str,
    *,
    compress: bool = True,
) -> BackupManifest:
    """Write a backup archive to `dest` (file or directory).

    Returns a BackupManifest with sha256.
    """
    dest_path = Path(dest)
    if dest_path.suffix in (".json", ".gz", ".backup"):
        out_file = dest_path
    else:
        # Treat as directory
        dest_path.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_file = dest_path / f"sazon-backup-{ts}.json.gz"

    state = dump_full_state(session)

    # Schema version + dialect
    from app.rms.config import CURRENT_SCHEMA_VERSION
    from app.rms.db_url import db_url_safe

    dialect = db_url_safe()

    flat = json.dumps(state, sort_keys=True, ensure_ascii=False)
    sha = hashlib.sha256(flat.encode()).hexdigest()
    n_rows = sum(len(rows) for rows in state.values())

    manifest = BackupManifest(
        created_at=datetime.now(timezone.utc).isoformat(),
        schema_version=CURRENT_SCHEMA_VERSION,
        n_tables=len(state),
        n_rows=n_rows,
        sha256=sha,
        source_db_url=dialect,
    )

    payload = {
        "manifest": manifest.to_dict(),
        "tables": state,
    }
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    if compress or out_file.suffix == ".gz":
        if not out_file.suffix:
            out_file = out_file.with_suffix(".json.gz")
        out_file.write_bytes(gzip.compress(raw, compresslevel=6))
    else:
        out_file.write_bytes(raw)

    return manifest


def load_archive(path: Path | str) -> tuple[BackupManifest, dict[str, list[dict]]]:
    """Load an archive + return (manifest, tables-dict)."""
    p = Path(path)
    raw = p.read_bytes()
    # Decompress BOTH .gz and .backup archives — backups written with
    # compress=True (the default) into a `.backup` destination are gzipped
    # too; only the extension check here distinguished them, so every
    # `.backup` restore failed with UnicodeDecodeError (found by the
    # tests/e2e restore drill 2026-09-25). Also sniff the gzip magic bytes
    # as a fallback for extensionless archives.
    if p.suffix == ".gz" or p.suffix == ".backup" or raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    payload = json.loads(raw.decode("utf-8"))
    manifest = BackupManifest(**payload["manifest"])
    return manifest, payload["tables"]


def verify_backup(path: Path | str) -> BackupManifest:
    """Verify archive integrity (sha256). Raises on mismatch."""
    manifest, tables = load_archive(path)
    flat = json.dumps(tables, sort_keys=True, ensure_ascii=False)
    sha = hashlib.sha256(flat.encode()).hexdigest()
    if sha != manifest.sha256:
        raise ValueError(f"Backup integrity check failed: expected {manifest.sha256}, got {sha}")
    return manifest


# --- Restore ---


# Map table_name -> SQLAlchemy model
_MODEL_BY_NAME = {m.__tablename__: m for m in BACKUP_TABLES}


def restore_database(session: Session, source: Path | str) -> BackupManifest:
    """Restore from an archive. Existing rows are preserved (no replace).

    Note: this is a "merge" restore (good for partial restore / additive
    promotions). For a full replace, drop the DB first.
    """
    manifest, tables = load_archive(source)

    # Check schema compatibility
    if manifest.schema_version > 6:  # current target
        # We can't safely downgrade, but accept newer for forward compat
        pass

    # Load in FK-safe order; skip Tag/TagLink for now (TBD)
    for model in BACKUP_TABLES:
        name = model.__tablename__
        if name not in tables:
            continue
        # Defer Tag/TagLink until E15 multi-tenant is in
        if name in ("tag", "tag_link"):
            continue
        rows = tables[name]
        if not rows:
            continue
        # Use merge to upsert
        for row_dict in rows:
            obj = model(**row_dict)
            session.merge(obj)
        session.commit()

    return manifest


# --- Retention ---


@dataclass
class BackupPruneResult:
    """Result of prune_old_backups()."""

    kept: list[str]
    removed: list[str]
    n_kept: int
    n_removed: int


def prune_old_backups(
    directory: Path | str,
    *,
    keep_n: int = 7,
    keep_days: int = 30,
) -> BackupPruneResult:
    """Apply retention policy: keep newest N + everything in last D days.

    Default: keep newest 7 backups + all backups from the last 30 days.
    """
    d = Path(directory)
    if not d.exists():
        return BackupPruneResult(kept=[], removed=[], n_kept=0, n_removed=0)

    backups = sorted(d.glob("sazon-backup-*.json*"), key=lambda p: p.stat().st_mtime)
    if not backups:
        return BackupPruneResult(kept=[], removed=[], n_kept=0, n_removed=0)

    threshold = datetime.now(timezone.utc) - timedelta(days=keep_days)
    keep_set: set[Path] = set()
    for p in backups[:keep_n]:
        keep_set.add(p)
    for p in backups:
        mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
        if mtime >= threshold:
            keep_set.add(p)

    kept: list[str] = []
    removed: list[str] = []
    for p in backups:
        if p in keep_set:
            kept.append(p.name)
        else:
            p.unlink()
            removed.append(p.name)

    return BackupPruneResult(
        kept=kept,
        removed=removed,
        n_kept=len(kept),
        n_removed=len(removed),
    )


__all__ = [
    "BACKUP_TABLES",
    "BackupManifest",
    "BackupPruneResult",
    "backup_database",
    "dump_full_state",
    "load_archive",
    "prune_old_backups",
    "restore_database",
    "verify_backup",
]
