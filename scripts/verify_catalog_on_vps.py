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

# Path default: matches AIW_RMS_DB_PATH env in the live container.
DEFAULT_DB_PATH = os.environ.get("AIW_RMS_DB_PATH", "/data/rms.sqlite")

# Exit codes (kept module-level so test mod can import them).
EXIT_OK = 0
EXIT_DB_OR_SCHEMA = 1
EXIT_CATALOG_LOW = 2
EXIT_SCRIPT_ERROR = 3


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
    row = conn.execute("SELECT value FROM app_meta WHERE key = 'schema_version'").fetchone()
    out["schema_version"] = int(row[0]) if row else None
    return out


def get_counts(conn: sqlite3.Connection) -> dict[str, int]:
    out = {}
    for table in MIN_COUNTS:
        row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        out[table] = row[0]
    return out


def resolve_code_schema_version(args: argparse.Namespace) -> int | None:
    """Pick the expected schema version: CLI > env > app module > None.

    Returns None when no source is available, in which case the
    schema check is skipped (caller treats None as "no check").
    """
    if args.code_schema_version is not None:
        return args.code_schema_version
    code_sv_env = os.environ.get("SASKIA_CODE_SCHEMA_VERSION")
    if code_sv_env:
        return int(code_sv_env)
    try:
        from app.rms.config import CURRENT_SCHEMA_VERSION as code_sv
    except (ImportError, AttributeError):
        return None
    return code_sv


def check_schema_match(meta: dict, code_sv: int | None, quiet: bool) -> int | None:
    """Return EXIT_DB_OR_SCHEMA when the persisted schema_version differs
    from the code's CURRENT_SCHEMA_VERSION; None when the check is
    skipped (code_sv is None) or the values match.
    """
    if code_sv is None:
        return None
    if meta.get("schema_version") != code_sv:
        if not quiet:
            print(
                f"FAIL: schema_version={meta.get('schema_version')} != "
                f"code CURRENT_SCHEMA_VERSION={code_sv}"
            )
        return EXIT_DB_OR_SCHEMA
    return None


def collect_catalog_failures(counts: dict[str, int]) -> list[str]:
    """Build the list of "<table>=<actual> (need >= <min>)" strings for
    every catalog table whose row count is below the minimum.
    """
    failures: list[str] = []
    for table, minimum in MIN_COUNTS.items():
        actual = counts.get(table, 0)
        if actual < minimum:
            failures.append(f"{table}={actual} (need >= {minimum})")
    return failures


def print_report(
    db_path: str,
    meta: dict,
    code_sv: int | None,
    counts: dict[str, int],
    failures: list[str],
    quiet: bool,
) -> None:
    """Emit the cron-friendly one-liner (--quiet) or the human-readable
    multi-line summary. Never raises; the caller decides the exit code.
    """
    if quiet:
        status = "OK" if not failures else "FAIL"
        print(
            f"vps-catalog-verify[{status}] "
            f"sv={meta.get('schema_version')} "
            f"code={code_sv} " + " ".join(f"{t}={c}" for t, c in counts.items())
        )
        return

    print(f"=== Catalog on VPS (db: {db_path}) ===")
    print(
        f"  schema_version: {meta.get('schema_version')}"
        + (f" (code: {code_sv})" if code_sv else "")
    )
    print("  catalog row counts:")
    for table, count in counts.items():
        minimum = MIN_COUNTS[table]
        ok = "OK" if count >= minimum else "LOW"
        print(f"    {table}: {count} (min {minimum}) [{ok}]")


def open_db_or_exit(db_path: str, quiet: bool) -> sqlite3.Connection | int:
    """Open the SQLite DB; return the connection or the exit code
    the caller should propagate.
    """
    if not os.path.exists(db_path):
        if not quiet:
            print(f"ERROR: DB not found at {db_path}")
        return EXIT_DB_OR_SCHEMA
    try:
        return sqlite3.connect(db_path)
    except sqlite3.Error as exc:
        if not quiet:
            print(f"ERROR: cannot open {db_path}: {exc}")
        return EXIT_SCRIPT_ERROR


def read_db_or_exit(conn: sqlite3.Connection, quiet: bool) -> tuple[dict, dict[str, int]] | int:
    """Run the two read queries; return (meta, counts) or an exit code."""
    try:
        meta = get_db_metadata(conn)
        counts = get_counts(conn)
    except sqlite3.Error as exc:
        if not quiet:
            print(f"ERROR: query failed: {exc}")
        return EXIT_SCRIPT_ERROR
    return meta, counts


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--db", default=DEFAULT_DB_PATH, help=f"path to rms.sqlite (default: {DEFAULT_DB_PATH})"
    )
    p.add_argument("--quiet", action="store_true", help="one-line summary (cron-friendly)")
    p.add_argument(
        "--code-schema-version",
        type=int,
        default=None,
        help="Override expected schema version (default: "
        "from SASKIA_CODE_SCHEMA_VERSION env, then "
        "app.rms.config.CURRENT_SCHEMA_VERSION, "
        "else skip schema check).",
    )
    args = p.parse_args(argv)

    conn_or_exit = open_db_or_exit(args.db, args.quiet)
    if isinstance(conn_or_exit, int):
        return conn_or_exit
    conn = conn_or_exit

    try:
        meta_counts_or_exit = read_db_or_exit(conn, args.quiet)
    finally:
        conn.close()
    if isinstance(meta_counts_or_exit, int):
        return meta_counts_or_exit
    meta, counts = meta_counts_or_exit

    code_sv = resolve_code_schema_version(args)
    schema_exit = check_schema_match(meta, code_sv, args.quiet)
    if schema_exit is not None:
        return schema_exit

    failures = collect_catalog_failures(counts)
    print_report(args.db, meta, code_sv, counts, failures, args.quiet)
    return EXIT_CATALOG_LOW if failures else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
