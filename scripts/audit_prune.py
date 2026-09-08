#!/usr/bin/env python3
"""scripts/audit_prune.py — operator hammer for the audit_log table.

Use:
    python scripts/audit_prune.py --dry-run          # see count
    python scripts/audit_prune.py                    # delete >30 days
    python scripts/audit_prune.py --days 7          # delete >7 days
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=30,
                        help="Retention in days. Default: 30.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Count what would be deleted, don't modify DB.")
    args = parser.parse_args()

    # Bootstrap: load DATABASE_URL or AIW_SASKIA_DB_PATH.
    if not os.getenv("DATABASE_URL") and not os.getenv("AIW_SASKIA_DB_PATH"):
        print("ERROR: neither DATABASE_URL nor AIW_SASKIA_DB_PATH set.")
        sys.exit(1)

    project_dir = Path(__file__).resolve().parents[1]
    code = f"""
import os, sys
sys.path.insert(0, "{project_dir}")
from app.rms.db import make_session_factory
from app.rms.db_dialect import make_engine
from app.rms.maintenance import prune_audit_log
engine = make_engine(os.environ.get("DATABASE_URL") or None)
factory = make_session_factory(engine)
n = prune_audit_log(factory, retention_days={args.days}, dry_run={args.dry_run})
mode = "DRY-RUN" if {args.dry_run} else "APPLIED"
print(f"{{mode}}: {{n}} rows older than {args.days} days deleted")
"""
    import subprocess
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, timeout=120,
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
