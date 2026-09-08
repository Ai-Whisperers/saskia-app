"""scripts/backup.py — operator-facing backup CLI.

Per docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md E20.

Usage:
    uv run python scripts/backup.py                  # default
    uv run python scripts/backup.py --dest /path     # custom dir
    uv run python scripts/backup.py --restore <file> # restore
    uv run python scripts/backup.py --prune          # apply retention
    uv run python scripts/backup.py --list           # list backups
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.rms.backup import (  # noqa: E402
    backup_database,
    load_archive,
    prune_old_backups,
    restore_database,
)
from app.rms.db import init_db, make_session_factory  # noqa: E402
from app.rms.db_dialect import make_engine  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Saskia RMS backup/restore")
    sub = parser.add_subparsers(dest="cmd")

    p_backup = sub.add_parser("backup", help="Write a backup")
    p_backup.add_argument("--dest", default="./backups", help="Output dir/file")
    p_backup.add_argument("--no-compress", action="store_true")

    sub.add_parser("list", help="List existing backups")

    p_restore = sub.add_parser("restore", help="Restore from an archive")
    p_restore.add_argument("source", help="Archive path")

    sub.add_parser("prune", help="Apply retention policy")
    sub.add_parser("verify", help="Verify archive integrity")

    p_verify = sub.add_parser("verify")
    p_verify.add_argument("source", help="Archive path")

    args = parser.parse_args(argv)

    engine = make_engine()
    init_db(engine)
    sf = make_session_factory(engine)

    if args.cmd == "backup":
        with sf() as session:
            dest = Path(args.dest)
            dest.mkdir(parents=True, exist_ok=True)
            manifest = backup_database(session, dest)
            print(f"Backup written to {dest}")
            print(f"  tables: {manifest.n_tables}, rows: {manifest.n_rows}")
            print(f"  sha256: {manifest.sha256[:16]}...")
        return 0

    if args.cmd == "list":
        d = Path("./backups")
        if not d.exists():
            print("No backups yet.")
            return 0
        files = sorted(d.glob("saskia-backup-*.json*"))
        for f in files:
            sz = f.stat().st_size
            print(f"  {f.name}  ({sz:,} bytes)")
        return 0

    if args.cmd == "restore":
        with sf() as session:
            manifest = restore_database(session, args.source)
            print(f"Restored from {args.source}")
            print(f"  schema: {manifest.schema_version}, rows: {manifest.n_rows}")
        return 0

    if args.cmd == "prune":
        result = prune_old_backups("./backups")
        print(f"Kept {result.n_kept}, removed {result.n_removed}")
        return 0

    if args.cmd == "verify":
        manifest, _ = load_archive(args.source)
        print(f"Archive {args.source}")
        print(f"  schema: {manifest.schema_version}, rows: {manifest.n_rows}")
        print(f"  sha256: {manifest.sha256[:16]}...")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
