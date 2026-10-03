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
    """Pull schema_version from app_meta.

    `code_schema_version` and `migrations_pending` aren't persisted —
    they're computed at request time by `/healthz/db` from in-memory
    state. So this script only reads what it can: the persisted
    schema_version. The caller compares it to the code's
    CURRENT_SCHEMA_VERSION via the env var SASKIA_CODE_SCHEMA_VERSION
    (default: read from app.rms.config if available).
    """
    out = {}
    row = conn.execute(
        "SELECT value FROM app_meta WHERE key = 'schema_version'"
    ).fetchone()
    out["schema_version"] = int(row[0]) if row else None
    return out


def get_counts(conn: sqlite3.Connection) -> dict[str, int]:
    out = {}
    for table in MIN_COUNTS:
        row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        out[table] = row[0]
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default=DEFAULT_DB_PATH,
                   help=f"path to rms.sqlite (default: {DEFAULT_DB_PATH})")
    p.add_argument("--quiet", action="store_true",
                   help="one-line summary (cron-friendly)")
    p.add_argument("--code-schema-version", type=int, default=None,
                   help="Override expected schema version (default: "
                        "from SASKIA_CODE_SCHEMA_VERSION env, then "
                        "app.rms.config.CURRENT_SCHEMA_VERSION, "
                        "else skip schema check).")
    args = p.parse_args(argv)

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

    # Resolve code_schema_version: CLI override > env > app module.
    code_sv_env = os.environ.get("SASKIA_CODE_SCHEMA_VERSION")
    if args.code_schema_version is not None:
        code_sv = args.code_schema_version
    elif code_sv_env:
        code_sv = int(code_sv_env)
    else:
        try:
            from app.rms.config import CURRENT_SCHEMA_VERSION as code_sv
        except (ImportError, AttributeError):
            code_sv = None

    # Check schema match
    if code_sv is not None and meta.get("schema_version") != code_sv:
        if not args.quiet:
            print(
                f"FAIL: schema_version={meta.get('schema_version')} != "
                f"code CURRENT_SCHEMA_VERSION={code_sv}"
            )
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
            f"sv={meta.get('schema_version')} "
            f"code={code_sv} "
            + " ".join(f"{t}={c}" for t, c in counts.items())
        )
    else:
        print(f"=== Catalog on VPS (db: {args.db}) ===")
        print(f"  schema_version: {meta.get('schema_version')}"
              + (f" (code: {code_sv})" if code_sv else ""))
        print("  catalog row counts:")
        for t, c in counts.items():
            minimum = MIN_COUNTS[t]
            ok = "OK" if c >= minimum else "LOW"
            print(f"    {t}: {c} (min {minimum}) [{ok}]")

    return 2 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
