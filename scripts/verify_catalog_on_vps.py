#!/usr/bin/env python3
"""scripts/verify_catalog_on_vps.py — Phase 14 (2026-10-01).

Confirms the HEREBUS catalog (ingredients, recipes, suppliers,
delivery zones, customers) is durable on the VPS SQLite volume.

Background:
  Phase 14 Batch J (catalog import local → VPS) had been on the
  known backlog. When we measured on 2026-10-01, the catalog is
  already on the VPS (Phase 13 migrations ran on the live DB).
  This script is the operator's fast sanity check — confirms the
  counts match the expected minimums (so we know a fresh deploy
  didn't drop the catalog) and reports the schema version.

What it checks:
  - DB reachable
  - schema_version == code_schema_version
  - migrations_pending == 0
  - catalog row counts meet minimums:
      ingredient >= 70
      recipe >= 20
      supplier >= 5
      delivery_zone >= 5
      customer >= 5

Exit codes:
  0 — all checks pass
  1 — DB unreachable or schema mismatch
  2 — catalog missing rows (below minimum)
  3 — script error

Usage:
  python3 scripts/verify_catalog_on_vps.py
  python3 scripts/verify_catalog_on_vps.py --db /custom/path/rms.sqlite

The script is read-only. It never modifies state.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys


MIN_COUNTS = {
    "ingredient": 70,
    "recipe": 20,
    "supplier": 5,
    "delivery_zone": 5,
    "customer": 5,
}

# Path default: matches AIW_SASKIA_DB_PATH env in the live container.
DEFAULT_DB_PATH = os.environ.get(
    "AIW_SASKIA_DB_PATH", "/data/rms.sqlite"
)


def get_db_metadata(conn: sqlite3.Connection) -> dict:
    """Pull schema_version + migrations_pending from app_meta."""
    out = {}
    for key in ("schema_version", "code_schema_version", "migrations_pending"):
        row = conn.execute(
            "SELECT value FROM app_meta WHERE key = ?", (key,)
        ).fetchone()
        out[key] = row[0] if row else None
    return out


def get_counts(conn: sqlite3.Connection) -> dict[str, int]:
    out = {}
    for table in MIN_COUNTS:
        row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        out[table] = row[0]
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default=DEFAULT_DB_PATH,
                   help=f"path to rms.sqlite (default: {DEFAULT_DB_PATH})")
    p.add_argument("--quiet", action="store_true",
                   help="one-line summary (cron-friendly)")
    args = p.parse_args()

    if not os.path.exists(args.db):
        if not args.quiet:
            print(f"ERROR: DB not found at {args.db}")
        return 1

    try:
        conn = sqlite3.connect(args.db)
    except sqlite3.Error as exc:
        if not args.quiet:
            print(f"ERROR: cannot open {args.db}: {exc}")
        return 3

    try:
        meta = get_db_metadata(conn)
        counts = get_counts(conn)
    except sqlite3.Error as exc:
        if not args.quiet:
            print(f"ERROR: query failed: {exc}")
        return 3
    finally:
        conn.close()

    # Check schema match
    if meta.get("schema_version") != meta.get("code_schema_version"):
        if not args.quiet:
            print(
                f"FAIL: schema_version={meta.get('schema_version')} != "
                f"code_schema_version={meta.get('code_schema_version')}"
            )
        return 1
    if str(meta.get("migrations_pending")) not in ("0", "None", None):
        if not args.quiet:
            print(f"FAIL: migrations_pending={meta.get('migrations_pending')}")
        return 1

    # Check catalog row counts
    failures = []
    for table, minimum in MIN_COUNTS.items():
        actual = counts.get(table, 0)
        if actual < minimum:
            failures.append(f"{table}={actual} (need >= {minimum})")

    if args.quiet:
        status = "OK" if not failures else "FAIL"
        print(
            f"vps-catalog-verify[{status}] "
            f"schema={meta.get('schema_version')} "
            + " ".join(f"{t}={c}" for t, c in counts.items())
        )
    else:
        print(f"=== Catalog on VPS (db: {args.db}) ===")
        for k in ("schema_version", "code_schema_version", "migrations_pending"):
            print(f"  {k}: {meta.get(k)}")
        print("  catalog row counts:")
        for t, c in counts.items():
            minimum = MIN_COUNTS[t]
            ok = "OK" if c >= minimum else "LOW"
            print(f"    {t}: {c} (min {minimum}) [{ok}]")

    return 2 if failures else 0


if __name__ == "__main__":
    sys.exit(main())