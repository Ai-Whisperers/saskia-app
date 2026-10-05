#!/usr/bin/env python3
"""scripts/daily_summary.py — send a daily summary to the operator.

Designed for cron (or operator-side invocation). Loads DATABASE_URL
from env, computes the day's sales/merma, formats a WhatsApp or
email summary, and dispatches via app.rms.notifications.

The default backend is `dryrun` (writes to /tmp/sazon-notifications/)
so running this in CI is safe. To wire to a real WhatsApp/Twilio or
email backend, set the corresponding env vars:

    AIW_RMS_NOTIFY_BACKEND=whatsapp
    TWILIO_ACCOUNT_SID=AC...
    TWILIO_AUTH_TOKEN=...
    TWILIO_WHATSAPP_FROM=+14155238886
    NOTIFY_TO_PHONE=+595...

Or for email:

    AIW_RMS_NOTIFY_BACKEND=email
    SMTP_HOST=smtp.gmail.com
    SMTP_USER=...
    SMTP_PASS=...
    NOTIFY_TO_EMAIL=...

Usage:
    python scripts/daily_summary.py            # today, default backend
    python scripts/daily_summary.py --yesterday # yesterday
    python scripts/daily_summary.py --backend dryrun  # explicit
    python scripts/daily_summary.py --backend email

Cron entry:
    0 22 * * * cd /opt/data/profiles/ivan/scratch/sazon-app-work && /usr/bin/env python3 scripts/daily_summary.py --backend whatsapp >> /var/log/ui-summary.log 2>&1

(Send at 22:00 UTC = 18:00 PY, end of business day.)
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yesterday",
        action="store_true",
        help="Send yesterday's summary instead of today's.",
    )
    parser.add_argument(
        "--backend",
        default=None,
        choices=["dryrun", "whatsapp", "email"],
        help="Override the notification backend (default: env var).",
    )
    args = parser.parse_args()

    if not os.getenv("DATABASE_URL") and not os.getenv("AIW_RMS_DB_PATH"):
        print("ERROR: neither DATABASE_URL nor AIW_RMS_DB_PATH set", file=sys.stderr)
        return 2

    # Compute target day
    if args.yesterday:
        target = datetime.now(timezone.utc) - timedelta(days=1)
        day_label = target.strftime("%Y-%m-%d (ayer)")
    else:
        target = datetime.now(timezone.utc)
        day_label = target.strftime("%Y-%m-%d (hoy)")

    if args.backend:
        os.environ["AIW_RMS_NOTIFY_BACKEND"] = args.backend

    code = f"""
import sys
sys.path.insert(0, r'{ROOT}')
from app.rms.db import init_db, make_session_factory
from app.rms.db_dialect import make_engine
from app.rms.notifications import format_daily_summary_message, send_notification
from app.rms.workflow import daily_summary_full
from datetime import datetime, timezone

engine = make_engine(None)
init_db(engine)
factory = make_session_factory(engine)
with factory() as s:
    summary = daily_summary_full(s, datetime.now(timezone.utc))
    body = format_daily_summary_message(summary)
    result = send_notification(body)
    print(f"backend={{result.kind}}, ok={{result.ok}}, detail={{result.detail or ''}}")
"""
    import subprocess

    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=120,
    )
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] daily_summary for {day_label}")
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
