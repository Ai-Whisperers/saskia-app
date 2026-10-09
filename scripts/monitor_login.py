#!/usr/bin/env python3
"""scripts/monitor_login.py — verify the full prod LOGIN path, not just /healthz.

The 2026-10-09 incident: /healthz was green while every login returned
500 ConnectError (Supabase NXDOMAIN). /healthz does not exercise auth.

This script performs the real login POST (credentials + cookie jar) and
fails (exit 1) unless the login lands on /puesto with a session cookie.
The login endpoint does not require a CSRF token (verified 2026-10-09;
the puesto-picker form does, the login form does not).

Runs from anywhere (Hermes cron, VPS crontab). Stdlib only.

Usage:
    python3 scripts/monitor_login.py
    python3 scripts/monitor_login.py --url https://saskia-vps.paragu-ai.com \
        --user demo --password "$SASKIA_USER_PASSWORD"
"""

from __future__ import annotations

import argparse
import http.cookiejar
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_URL = "https://saskia-vps.paragu-ai.com"
DEFAULT_USER = "demo"
DEFAULT_PASSWORD = "demo1234"  # synced from BWS SASKIA_USER_PASSWORD


def die(msg: str) -> None:
    print(f"LOGIN-MONITOR FAIL: {msg}")
    sys.exit(1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.environ.get("MONITOR_URL", DEFAULT_URL))
    ap.add_argument("--user", default=DEFAULT_USER)
    ap.add_argument("--password", default=os.environ.get("SASKIA_USER_PASSWORD", DEFAULT_PASSWORD))
    args = ap.parse_args()

    base = args.url.rstrip("/")
    cj = http.cookiejar.CookieJar()
    # urllib follows redirects: a successful login ends at /puesto with
    # sazon_session set; a failed one bounces back to /login?error=...
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    data = urllib.parse.urlencode(
        {"username": args.user, "password": args.password}
    ).encode()
    req = urllib.request.Request(
        f"{base}/login",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with opener.open(req, timeout=20) as r:
            final_url = r.url
    except urllib.error.HTTPError as e:
        die(f"POST /login HTTP {e.code} (5xx = auth backend down)")
    except Exception as e:
        die(f"POST /login failed: {e}")

    if "error=" in final_url or final_url.rstrip("/").endswith("/login"):
        die(f"login rejected (bad credentials or auth backend error): {final_url}")
    if not any(c.name == "sazon_session" for c in cj):
        die("no sazon_session cookie set")

    print(f"LOGIN-MONITOR OK: {args.user} -> {final_url} @ {base}")


if __name__ == "__main__":
    main()
