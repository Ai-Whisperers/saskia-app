#!/usr/bin/env python3
"""CI failure alert — emails the operator when the test suite fails on main.

Used by .github/workflows/ci.yml. Uses the same Resend API the app uses
(app/observability/email.py). Gated on RESEND_API_KEY; no-op when unset.

Outputs to stdout either way. Never raises (the email path must not
fail the build).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API_KEY = os.environ.get("RESEND_API_KEY", "")
TO = os.environ.get("ALERT_EMAIL_TO", "ivan@aiwhisperers.dev")
GITHUB_SHA = os.environ.get("GITHUB_SHA", "unknown")
GITHUB_RUN_ID = os.environ.get("GITHUB_RUN_ID", "unknown")
GITHUB_SERVER = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "")

if not API_KEY:
    print("RESEND_API_KEY not set; skipping alert email")
    sys.exit(0)

commit_short = GITHUB_SHA[:7]
run_url = f"{GITHUB_SERVER}/{GITHUB_REPO}/actions/runs/{GITHUB_RUN_ID}"

payload = {
    "from": "Saskia CI <noreply@aiwhisperers.dev>",
    "to": [TO],
    "subject": f"[saskia-critical] CI test suite failed ({commit_short})",
    "text": (
        f"Saskia RMS test suite failed on main.\n\n"
        f"Commit: {commit_short}\n"
        f"Run: {GITHUB_RUN_ID}\n"
        f"URL: {run_url}\n\n"
        f"Check the workflow logs and fix before the next deploy."
    ),
    "html": (
        f"<pre>Saskia RMS test suite failed on main.\n\n"
        f"Commit: {commit_short}\n"
        f"Run: {GITHUB_RUN_ID}\n"
        f'<a href="{run_url}">View logs</a></pre>'
    ),
}

req = urllib.request.Request(
    "https://api.resend.com/emails",
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    },
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=5) as r:
        print(f"alert sent, status {r.status}")
except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
    print(f"alert failed: {exc!r}")
    # Never fail the build over a broken alert path.
    sys.exit(0)
