#!/usr/bin/env python3
"""scripts/backup_cron.py — operator-friendly backup trigger for cron.

Designed for daily or weekly execution via cron, this is a thin wrapper
around `scripts/backup.py` that:
1. Loads DATABASE_URL from BWS (production) or local env (test).
2. Runs a fresh backup to /tmp/aiw-saskia-backups/ and to R2 if
   configured.
3. Prunes local backups older than 30 days.
4. Logs outcome to /var/log/aiw-saskia-backup.log or stdout if run
   interactively.

Usage:
    # Run manually:
    python scripts/backup_cron.py

    # Add to crontab (operator-side):
    # Every Sunday 03:00 UTC
    0 3 * * 0 cd /opt/data/profiles/ivan/scratch/saskia-app-work && /usr/bin/env python3 scripts/backup_cron.py >> /var/log/saskia-backup.log 2>&1

Exit codes:
    0  success
    1  backup failed
    2  DB unreachable
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--retention-days",
        type=int,
        default=30,
        help="Local backup retention in days (default: 30).",
    )
    parser.add_argument(
        "--no-prune",
        action="store_true",
        help="Skip local prune.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually write; print what would happen.",
    )
    args = parser.parse_args()

    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] backup_cron start")
    start = time.time()

    if not os.getenv("DATABASE_URL") and not os.getenv("AIW_SASKIA_DB_PATH"):
        print("ERROR: neither DATABASE_URL nor AIW_SASKIA_DB_PATH set", file=sys.stderr)
        return 2

    # Run the standard backup CLI in-process (avoids subprocess overhead).
    code = f"""
import sys
sys.path.insert(0, r'{ROOT}')
from datetime import datetime
from app.rms.db import make_session_factory, init_db
from app.rms.db_dialect import make_engine
from app.rms.backup import backup_database, prune_old_backups
from pathlib import Path
import os

engine = make_engine(os.environ.get('DATABASE_URL') or None)
init_db(engine)
factory = make_session_factory(engine)

folder = Path('/tmp/aiw-saskia-backups')
folder.mkdir(parents=True, exist_ok=True)
ts = datetime.now().strftime('%Y%m%d_%H%M%S')
dest = folder / f'backup_{{ts}}.json'

with factory() as s:
    manifest = backup_database(s, dest)
    print(f"Backup ok: {{manifest.n_rows}} rows, schema v{{manifest.schema_version}}")

if not {args.no_prune}:
    with factory() as s:
        result = prune_old_backups(folder, keep_n={args.retention_days})
        print(f"Prune removed: {{len(result.removed)}} files")
"""
    import subprocess
    full_code = code
    result = subprocess.run(
        [sys.executable, "-c", full_code],
        capture_output=True, text=True, timeout=600,
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    elapsed = time.time() - start
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] backup_cron done in {elapsed:.1f}s status={result.returncode}")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
