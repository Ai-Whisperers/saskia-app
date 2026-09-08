"""scripts/uptimerobot_setup.py — Idempotent setup for saskia-rms healthz monitor.

Reads credentials from BWS (UPTIMEROBOT_ACCOUNT_API_KEY for read + write,
UPTIMEROBOT_MONITOR_KEY for monitor-specific operations).

Idempotent: re-running won't create duplicates. If a monitor for
https://saskia-rms.paragu-ai.com/healthz already exists, prints its ID
and exits.

Usage:
    python scripts/uptimerobot_setup.py          # verify or create
    python scripts/uptimerobot_setup.py --pause  # pause the monitor
    python scripts/uptimerobot_setup.py --delete # delete the monitor
"""
from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API_URL = "https://api.uptimerobot.com/v2"
MONITOR_URL = "https://saskia-rms.paragu-ai.com/healthz"
MONITOR_FRIENDLY = "saskia-rms /healthz"


def _post(endpoint: str, params: dict) -> dict:
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(
        f"{API_URL}/{endpoint}",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    raw = urllib.request.urlopen(req, timeout=15).read().decode()
    import json
    return json.loads(raw)


def find_monitor(api_key: str) -> dict | None:
    """Find an existing monitor for our healthz URL."""
    resp = _post("getMonitors", {
        "api_key": api_key,
        "format": "json",
        "url": MONITOR_URL,
    })
    if resp.get("stat") != "ok":
        return None
    monitors = resp.get("monitors", [])
    return monitors[0] if monitors else None


def create_monitor(api_key: str) -> dict:
    """Create a new HTTP monitor for /healthz."""
    return _post("newMonitor", {
        "api_key": api_key,
        "format": "json",
        "type": 1,              # HTTP
        "url": MONITOR_URL,
        "friendly_name": MONITOR_FRIENDLY,
        "interval": 300,        # 5 min
        "timeout": 30,
        "retention": 30,        # keep 30 response time entries
    })


def pause_monitor(api_key: str, monitor_id: str) -> dict:
    return _post("editMonitor", {
        "api_key": api_key,
        "format": "json",
        "id": monitor_id,
        "status": 0,           # 0 = paused
    })


def delete_monitor(api_key: str, monitor_id: str) -> dict:
    return _post("deleteMonitor", {
        "api_key": api_key,
        "format": "json",
        "id": monitor_id,
    })


def main():
    parser = argparse.ArgumentParser(description="Manage UptimeRobot monitor for saskia-rms")
    parser.add_argument("--pause", action="store_true", help="Pause the existing monitor")
    parser.add_argument("--delete", action="store_true", help="Delete the existing monitor")
    parser.add_argument(
        "--api-key",
        help="Override UptimeRobot account API key (default: read from BWS at runtime)",
    )
    args = parser.parse_args()

    if args.api_key:
        api_key = args.api_key
    else:
        try:
            sys.path.insert(0, "/opt/data/.venv/lib/python3.11/site-packages")
            from pathlib import Path

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

            cache = {}
            with open("/opt/data/.hermes/bws-secrets-cache.tsv") as f:
                for line in f:
                    parts = line.strip().split("\t", 1)
                    if len(parts) == 2:
                        cache[parts[0]] = parts[1]

            r = client.secrets().get_by_ids([cache["UPTIMEROBOT_ACCOUNT_API_KEY"]])
            api_key = r.to_dict()["data"]["data"][0]["value"]
        except Exception as exc:
            print(f"Failed to fetch UptimeRobot key from BWS: {exc!r}")
            sys.exit(1)

    existing = find_monitor(api_key)
    if not existing:
        print(f"No existing monitor for {MONITOR_URL}; creating one...")
        created = create_monitor(api_key)
        if created.get("stat") == "ok":
            print(f"Created monitor id={created['monitor']['id']} for {MONITOR_URL}")
            return
        print(f"Failed to create monitor: {created}")
        sys.exit(2)

    mid = existing["id"]
    print(f"Found existing monitor id={mid} status={existing.get('status')}")

    if args.pause:
        result = pause_monitor(api_key, mid)
        if result.get("stat") == "ok":
            print(f"Paused monitor {mid}")
        else:
            print(f"Failed to pause: {result}")
            sys.exit(3)
    elif args.delete:
        result = delete_monitor(api_key, mid)
        if result.get("stat") == "ok":
            print(f"Deleted monitor {mid}")
        else:
            print(f"Failed to delete: {result}")
            sys.exit(4)
    else:
        print("Nothing to do (use --pause or --delete to modify).")


if __name__ == "__main__":
    main()
