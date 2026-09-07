"""Apply schema to Neon. Standalone helper script.

Idempotent. Safe to re-run. Reads DATABASE_URL from env, calls init_db() which
both creates missing tables AND applies pending migrations from app/rms/db.py.

This script was originally a thin wrapper around metadata.create_all() but that
missed the schema_version bookkeeping (CURRENT_SCHEMA_VERSION in config.py). The
2026-09-04 plan's E2.S3.T1 brought it into alignment with init_db() so that
running this script twice in a row is a no-op on the second run.

Usage:
    DATABASE_URL=postgres://... python scripts/apply_neon_schema.py
    uv run python scripts/apply_neon_schema.py    # picks up DATABASE_URL from .env if loaded
"""

from __future__ import annotations

import os

from sqlalchemy import inspect

from app.rms.db import CURRENT_SCHEMA_VERSION, _current_schema_version, init_db
from app.rms.db_dialect import make_engine


def main() -> int:
    raw = os.environ.get("DATABASE_URL")
    if not raw:
        print("ERROR: DATABASE_URL not set. Export it or use --db-url.", file=__import__("sys").stderr)
        return 1

    print(f"raw DATABASE_URL: {raw[:25]}...")
    engine = make_engine(raw)
    print(f"engine driver: {engine.url.drivername}")

    # Check schema version BEFORE we touch anything — so a no-op run is silent.
    try:
        with engine.connect() as conn:
            before = _current_schema_version(conn)
    except Exception:
        before = 0  # tables don't exist yet — fine, we'll create them

    if before == CURRENT_SCHEMA_VERSION:
        print(f"schema_version already at {CURRENT_SCHEMA_VERSION} (no-op)")
        insp = inspect(engine)
        schema = "public" if engine.dialect.name == "postgresql" else None
        for t in sorted(insp.get_table_names(schema=schema)):
            print(f"  - {t}")
        return 0

    print(f"schema_version: {before} -> {CURRENT_SCHEMA_VERSION}")
    init_db(engine)

    insp = inspect(engine)
    schema = "public" if engine.dialect.name == "postgresql" else None
    created = sorted(insp.get_table_names(schema=schema))
    print(f"verified: {len(created)} tables in DB")
    for t in created:
        print(f"  - {t}")
    print(f"schema applied at version {CURRENT_SCHEMA_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
