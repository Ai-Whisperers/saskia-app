"""scripts/uptimerobot_setup.py — ensure all UptimeRobot monitors exist.

After this plan runs, we monitor 3 endpoints every 5 minutes to keep
the free-tier Render container warm + detect outages early:

- /healthz       — basic liveness
- /healthz/db    — DB connectivity
- /healthz/schema — schema drift detector (new)

Usage:
    python scripts/uptimerobot_setup.py create-all
    python scripts/uptimerobot_setup.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API_URL = "https://api.uptimerobot.com/v2"

# Each monitor: (url, friendly_name)
DEFAULT_MONITORS = [
    ("https://sazon-rms.paragu-ai.com/healthz", "sazon-rms /healthz"),
    ("https://sazon-rms.paragu-ai.com/healthz/db", "sazon-rms /healthz/db"),
    ("https://sazon-rms.paragu-ai.com/healthz/schema", "sazon-rms /healthz/schema"),
]


def _post(endpoint: str, params: dict) -> dict:
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(
        f"{API_URL}/{endpoint}",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    raw = urllib.request.urlopen(req, timeout=15).read().decode()
    return json.loads(raw)


def find_monitor(api_key: str, url: str) -> dict | None:
    """Find an existing monitor for the given URL (exact match).

    UptimeRobot's `url=` filter is substring match; we list all monitors
    and pick the one whose URL is character-for-character identical.
    """
    resp = _post(
        "getMonitors",
        {
            "api_key": api_key,
            "format": "json",
        },
    )
    if resp.get("stat") != "ok":
        return None
    for m in resp.get("monitors", []):
        if m.get("url") == url:
            return m
    return None


def create_monitor(api_key: str, *, url: str, friendly_name: str, interval: int = 300) -> dict:
    """Create a new HTTP monitor (5-min default). Returns API response."""
    return _post(
        "newMonitor",
        {
            "api_key": api_key,
            "format": "json",
            "type": 1,
            "url": url,
            "friendly_name": friendly_name,
            "interval": interval,
            "timeout": 30,
            "retention": 30,
        },
    )


def ensure_monitors(api_key: str) -> None:
    """For each DEFAULT_MONITORS tuple, ensure a monitor exists.

    Reads UptimeRobot; if a monitor already exists for the URL we
    leave it alone (idempotent). Otherwise attempts to create one.

    NOTE (2026-09-08): The BWS-stored UPTIMEROBOT_ACCOUNT_API_KEY is a
    read-only monitor-scope key — `newMonitor` returns
    `not_authorized`. Operator action: open UptimeRobot dashboard, log in
    with `weissvanderpol.ivan@gmail.com`, manually add 2 more monitors:
      - type=HTTP url=https://sazon-rms.paragu-ai.com/healthz/db
      - type=HTTP url=https://sazon-rms.paragu-ai.com/healthz/schema
    Both at 5-minute interval. This script will then detect them and
    print "exists" on subsequent runs.
    """
    for url, name in DEFAULT_MONITORS:
        existing = find_monitor(api_key, url)
        if existing:
            print(f"  exists  id={existing['id']} name={name}")
            continue
        created = create_monitor(api_key, url=url, friendly_name=name)
        if created.get("stat") == "ok":
            new_id = created.get("monitor", {}).get("id")
            print(f"  created id={new_id} name={name}")
        else:
            err = created.get("error", {})
            print(f"  FAILED  name={name} error={err.get('type')}: {err.get('message')}")


def _fetch_api_key() -> str:
    """Fetch UptimeRobot account API key from BWS."""
    sys.path.insert(0, "/opt/data/.venv/lib/python3.11/site-packages")
    from bitwarden_sdk import BitwardenClient, ClientSettings, DeviceType

    token = Path("/opt/data/.hermes/inbox/bws-token.secret").read_text().strip()
    client = BitwardenClient(
        ClientSettings(
            api_url="https://api.bitwarden.com",
            identity_url="https://identity.bitwarden.com",
            user_agent="uptime/1",
            device_type=DeviceType.SERVER,
        )
    )
    client.auth().login_access_token(token, None)
    time.sleep(2)

    cache: dict[str, str] = {}
    with open("/opt/data/.hermes/bws-secrets-cache.tsv") as f:
        for line in f:
            parts = line.strip().split("\t", 1)
            if len(parts) == 2:
                cache[parts[0]] = parts[1]

    r = client.secrets().get_by_ids([cache["UPTIMEROBOT_ACCOUNT_API_KEY"]])
    return r.to_dict()["data"]["data"][0]["value"]


def main():
    parser = argparse.ArgumentParser(description="Manage UptimeRobot monitors for sazon-rms")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen without making API calls",
    )
    parser.add_argument(
        "--api-key",
        help="Override UptimeRobot account API key (default: read from BWS)",
    )
    parser.add_argument(
        "create_all",
        nargs="?",
        help="Ensure all 3 default monitors exist (idempotent)",
    )
    args = parser.parse_args()

    if args.dry_run:
        print("DRY RUN — would ensure these monitors exist:")
        for url, name in DEFAULT_MONITORS:
            print(f"  url={url} name={name} interval=300s type=HTTP")
        return

    if args.api_key:
        api_key = args.api_key
    else:
        try:
            api_key = _fetch_api_key()
        except Exception as exc:
            print(f"Failed to fetch UptimeRobot key from BWS: {exc!r}")
            sys.exit(1)

    if args.create_all == "create-all":
        ensure_monitors(api_key)
    else:
        # Backwards-compat: no positional arg = legacy behavior
        # (create the first monitor, used by prior deploys).
        ensure_monitors(api_key)


if __name__ == "__main__":
    main()
