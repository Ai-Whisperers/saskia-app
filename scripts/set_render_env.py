#!/usr/bin/env python3
"""Set AIW_SASKIA_FORCE_SECURE_COOKIES=1 on Render.

Without this env var, the CSRF middleware sets Secure=False on the
csrf cookie. Browsers in HTTPS contexts (Render behind Cloudflare
TLS) reject non-Secure cookies, so every POST 403s.

This is the runtime flag flipped ON for hosted deployments; local
dev / tests leave it unset so plain HTTP works.
"""

import json
import os
import sys
import time
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

time.sleep(2)
r = c.secrets().get_by_ids([cache["RENDER_API_KEY"]])
RK = r.to_dict()["data"]["data"][0]["value"]
Path("/tmp/_rk").write_text(RK)
Path("/tmp/_rk").chmod(0o600)

base = "https://api.render.com/v1/services/srv-dac8g2u7bikc73f3psf0/env-vars"
req = urllib.request.Request(
    base + "/AIW_SASKIA_FORCE_SECURE_COOKIES",
    method="PUT",
    data=json.dumps({"value": "1"}).encode(),
    headers={
        "Authorization": "Bearer " + RK,
        "Content-Type": "application/json",
        "Accept": "application/json",
    },
)
try:
    resp = urllib.request.urlopen(req, timeout=15)
    print(f"PUT /AIW_SASKIA_FORCE_SECURE_COOKIES: HTTP {resp.status}")
    print(resp.read()[:200].decode())
except urllib.error.HTTPError as e:
    print(f"PUT failed: HTTP {e.code}: {e.reason}")
    print(e.read()[:300].decode())

# Verify by listing
req = urllib.request.Request(base + "?limit=100", headers={"Authorization": "Bearer " + RK})
data = json.loads(urllib.request.urlopen(req, timeout=15).read())
for e in data:
    k = e.get("envVar", {}).get("key", "")
    if "SECURE_COOKIES" in k or "MIGRATION" in k.upper():
        v = e.get("envVar", {}).get("value", "")
        print(f"  ✓ {k}={v}")

os.unlink("/tmp/_rk")
