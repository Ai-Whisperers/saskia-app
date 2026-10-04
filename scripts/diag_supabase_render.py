from typing import Any

#!/usr/bin/env python3
"""Diagnose Supabase + Render state for Saskia RMS.

Fetches SUPABASE_URL from BWS, tests DNS resolution and HTTPS reachability,
and lists Render env vars for the Saskia service.
"""
import json
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, "/opt/data/.venv/lib/python3.11/site-packages")
from bitwarden_sdk import BitwardenClient, ClientSettings, DeviceType

token = Path("/opt/data/.hermes/inbox/bws-token.secret").read_text().strip()
c = BitwardenClient(
    ClientSettings(
        api_url="https://api.bitwarden.com",
        identity_url="https://identity.bitwarden.com",
        user_agent="ops/1",
        device_type=DeviceType.SERVER,
    )
)
c.auth().login_access_token(token, None)

cache = {}
with open("/opt/data/.hermes/bws-secrets-cache.tsv") as f:
    for line in f:
        parts = line.strip().split("\t", 1)
        if len(parts) == 2:
            cache[parts[0]] = parts[1]


def get_secret(key: Any):
    if key not in cache:
        return None
    r = c.secrets().get_by_ids([cache[key]])
    return r.to_dict()["data"]["data"][0]["value"]


print("=== Supabase URL ===")
url = get_secret("SUPABASE_URL")
print(f"  {url}")

# DNS check
host = url.split("//")[1].split("/")[0]
print(f"\n=== DNS resolution for {host} ===")
try:
    ips = socket.getaddrinfo(host, None)
    for ip in ips[:3]:
        print(f"  ✓ {ip[4][0]}")
except Exception as e:
    print(f"  ✗ {e}")

# HTTPS reachability
print(f"\n=== HTTPS reachability ({url}/auth/v1/health) ===")
try:
    req = urllib.request.Request(
        f"{url}/auth/v1/health",
        headers={"apikey": get_secret("SUPABASE_PUBLISHABLE_KEY") or ""},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        print(f"  ✓ HTTP {r.status}")
        print(f"  body: {r.read().decode()[:200]}")
except urllib.error.HTTPError as e:
    print(f"  ✗ HTTP {e.code}: {e.read().decode()[:200]}")
except Exception as e:
    print(f"  ✗ {e}")

# Project status via management API
print("\n=== Supabase project status ===")
mgmt_token = get_secret("SUPABASE_ACCESS_TOKEN")
# URL like https://abc.supabase.co — extract ref
ref = host.split(".")[0]
mgmt_url = f"https://api.supabase.com/v1/projects/{ref}"
try:
    req = urllib.request.Request(
        mgmt_url,
        headers={
            "Authorization": f"Bearer {mgmt_token}",
            "apikey": get_secret("SUPABASE_PUBLISHABLE_KEY") or "",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        proj = json.loads(r.read())
        print(f"  ✓ Project: {proj.get('name')} (id={proj.get('id')})")
        print(f"    Region: {proj.get('region')}")
        print(f"    Status: {proj.get('status')}")
        print(f"    DB: {proj.get('database', {}).get('host')}")
except urllib.error.HTTPError as e:
    print(f"  ✗ HTTP {e.code}: {e.read().decode()[:300]}")
except Exception as e:
    print(f"  ✗ {e}")

# Render env vars
print("\n=== Render env vars ===")
RK = get_secret("RENDER_API_KEY")
base = "https://api.render.com/v1/services/srv-dac8g2u7bikc73f3psf0/env-vars"
try:
    req = urllib.request.Request(
        base,
        headers={"Authorization": f"Bearer {RK}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        envs = json.loads(r.read())
        for e in envs:
            key = e["key"]
            value = e.get("value", "")
            if any(s in key.lower() for s in ["supabase", "database", "secret", "key", "token"]):
                masked = value[:8] + "..." + value[-4:] if len(value) > 16 else "***"
                print(f"  {key}: {masked}")
            else:
                print(f"  {key}: {value}")
except urllib.error.HTTPError as e:
    print(f"  ✗ HTTP {e.code}: {e.read().decode()[:200]}")
except Exception as e:
    print(f"  ✗ {e}")
