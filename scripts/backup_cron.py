#!/usr/bin/env python3
"""scripts/backup_cron.py — host-cron entry point for daily backups (B.8).

This wrapper POSTs to the running app's /admin/backup/cron endpoint
rather than running a backup in-process. The design choice (HTTP, not
in-process) has three benefits:

1. **Single replica wins.** With Docker Swarm 1 replica, only one
   cron can hit the endpoint at a time; the endpoint itself is
   idempotent and no-op if the last backup is < 24h old (the
   "skipped: true" response), so even if 5 cron wrappers fire
   (e.g. on multiple hosts) only one actually does the upload.
2. **No env duplication.** The R2 credentials, DB path, and Sentry
   config all live in the app's process. The wrapper just needs
   the URL + a shared secret.
3. **Same observability.** The endpoint logs to Sentry, the lifespan
   job, and the response itself — so a cron run that "succeeded"
   in cron but actually failed inside the backup is still visible
   to the on-call operator.

Exit codes (cron-friendly):
  0  backup ran or was skipped (< 24h since last)
  2  config error (missing env, 401, 503) — operator must fix
  3  backup raised (500) — alert on-call
  4  app unreachable (connection refused, DNS) — cron retries

Usage in crontab (operator-side, set in deploy.sh):
  0 3 * * *  SASKIA_BACKUP_URL=http://localhost:8000 \\
              SASKIA_CRON_BACKUP_TOKEN_FILE=/etc/sazon/backup-cron.token \\
              /usr/bin/python3 /opt/sazon-app/scripts/backup_cron.py \\
              >> /var/log/sazon-cron.log 2>&1

Manual:
  SASKIA_BACKUP_URL=https://sazon.example.com \\
  SASKIA_CRON_BACKUP_TOKEN_FILE=~/.sazon-cron-token \\
  ./scripts/backup_cron.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

EXIT_OK = 0
EXIT_CONFIG = 2
EXIT_BACKUP_RAISED = 3
EXIT_APP_DOWN = 4

DEFAULT_TIMEOUT_S = 120  # backups can take 30-90s on slow nights


def _resolve_token(cli_token: str | None) -> str | None:
    """Resolve the cron token from (in order): --token, $SASKIA_CRON_BACKUP_TOKEN,
    $SASKIA_CRON_BACKUP_TOKEN_FILE (file contents)."""
    if cli_token:
        return cli_token
    direct = os.getenv("SASKIA_CRON_BACKUP_TOKEN")
    if direct:
        return direct
    file_path = os.getenv("SASKIA_CRON_BACKUP_TOKEN_FILE")
    if file_path:
        try:
            return Path(file_path).read_text().strip()
        except OSError as e:
            print(f"ERROR: cannot read SASKIA_CRON_BACKUP_TOKEN_FILE={file_path}: {e}",
                  file=sys.stderr)
            return None
    return None


def _resolve_url(cli_url: str | None) -> str | None:
    """Resolve the backup URL from --url or $SASKIA_BACKUP_URL.

    The endpoint path /admin/backup/cron is appended automatically
    so operators only need to set the base URL (e.g.
    https://sazon.example.com)."""
    url = cli_url or os.getenv("SASKIA_BACKUP_URL")
    if not url:
        return None
    # Strip trailing slash, then append the endpoint path.
    return url.rstrip("/") + "/admin/backup/cron"


def _print_request_dry_run(url: str, token: str, timeout: int) -> None:
    """Print a curl-style summary so --dry-run is self-documenting."""
    print("DRY-RUN: would POST the following request")
    print(f"  URL:     {url}")
    print(f"  Header:  X-Cron-Token: {token[:8]}...{token[-4:] if len(token) > 12 else ''}")
    print(f"  Timeout: {timeout}s")
    print()
    print("Example curl (for manual testing):")
    print(f'  curl -fsS -X POST -H "X-Cron-Token: $TOKEN" {url}')


def _do_request(url: str, token: str, timeout: int) -> tuple[int, dict]:
    """POST the endpoint and return (http_status, body_dict).

    The body is always parsed as JSON; if the response is not JSON
    (e.g. an nginx 502), the body is wrapped in {"_raw": "..."} so
    the caller can still log it.
    """
    req = urllib.request.Request(
        url,
        method="POST",
        headers={"X-Cron-Token": token},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return 200, _safe_json(raw)
    except urllib.error.HTTPError as e:
        raw = e.read() if e.fp else b""
        return e.code, _safe_json(raw)
    except urllib.error.URLError as e:
        # Connection refused, DNS failure, timeout, etc.
        return 0, {"_transport_error": str(e.reason)}


def _safe_json(raw: bytes) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {"_raw": raw.decode("utf-8", errors="replace")[:500]}


def _format_summary(body: dict, elapsed: float) -> str:
    """One-line summary for cron log (human-readable when --json is off)."""
    status = body.get("status") or body.get("error") or "unknown"
    skipped = body.get("skipped", False)
    r2 = body.get("r2_uploaded", False)
    r2_key = body.get("r2_key") or "-"
    return (
        f"backup_cron: status={status} skipped={skipped} "
        f"r2_uploaded={r2} r2_key={r2_key} elapsed={elapsed:.1f}s"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Daily backup cron wrapper (POSTs /admin/backup/cron).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--url", help="Base URL of the app (e.g. https://sazon.example.com)")
    parser.add_argument("--token", help="Cron token (overrides env vars)")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S,
                        help=f"HTTP timeout in seconds (default: {DEFAULT_TIMEOUT_S})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the request that would be made, don't send it")
    parser.add_argument("--json", action="store_true", dest="json_output",
                        help="Output a single JSON line for downstream parsing")
    args = parser.parse_args()

    url = _resolve_url(args.url)
    if not url:
        print("ERROR: --url or SASKIA_BACKUP_URL must be set", file=sys.stderr)
        return EXIT_CONFIG

    token = _resolve_token(args.token)
    if not token:
        print("ERROR: --token, $SASKIA_CRON_BACKUP_TOKEN, or "
              "$SASKIA_CRON_BACKUP_TOKEN_FILE must be set", file=sys.stderr)
        return EXIT_CONFIG

    if args.dry_run:
        _print_request_dry_run(url, token, args.timeout)
        return EXIT_OK

    if not args.json_output:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] backup_cron POST {url}")

    start = time.time()
    status, body = _do_request(url, token, args.timeout)
    elapsed = time.time() - start

    if args.json_output:
        # Single JSON line on stdout (cron logs are line-oriented;
        # we don't want to pollute the log file with multi-line JSON).
        body.setdefault("_status", status)
        body.setdefault("_elapsed_seconds", round(elapsed, 2))
        body.setdefault("_ts", time.strftime("%Y-%m-%dT%H:%M:%S"))
        print(json.dumps(body, default=str))
    else:
        print(_format_summary(body, elapsed))
        if status != 200 and body:
            print(f"  body: {json.dumps(body, default=str)[:300]}",
                  file=sys.stderr)

    if status == 200:
        return EXIT_OK
    if status in (401, 503):
        return EXIT_CONFIG
    if status == 500:
        return EXIT_BACKUP_RAISED
    if status == 0:  # transport error (URLError)
        return EXIT_APP_DOWN
    # Unknown HTTP status — treat as backup raised so cron alerts.
    return EXIT_BACKUP_RAISED


if __name__ == "__main__":
    sys.exit(main())
