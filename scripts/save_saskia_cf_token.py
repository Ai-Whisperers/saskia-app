#!/usr/bin/env python3
"""Save SASKIA_CF_TUNNEL_TOKEN to BWS without it appearing as a string literal.

The Cloudflare Tunnel token is used by cloudflared on Ivan's box (or
Render's sidecar) to connect to Cloudflare's edge network. It's a
long JSON blob (typically ~500 chars) that includes account ID,
tunnel secret, and tunnel ID.

Usage:
    1. Create the tunnel in Cloudflare Zero Trust (Dash → Tunnels).
    2. Cloudflare shows the token ONCE. Copy it immediately.
    3. nano /tmp/cf_token.txt   (paste, save)
    4. chmod 600 /tmp/cf_token.txt
    5. python3 scripts/save_saskia_cf_token.py
    6. shred -u /tmp/cf_token.txt

Mirrors scripts/save_saskia_db_url.py (same Pattern 5: file-based).
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, "/opt/data/.venv/lib/python3.11/site-packages")

from bitwarden_sdk import BitwardenClient, ClientSettings, DeviceType  # noqa: E402

TOKEN_FILE = Path("/tmp/cf_token.txt")
BWS_TOKEN_PATH = Path("/opt/data/.hermes/inbox/bws-token.secret")
ORG_ID_PATH = Path("/opt/data/.hermes/inbox/org-id.txt")
PROJECT_ID_PATH = Path("/opt/data/.hermes/inbox/bws-project-id-hermes.txt")
SECRET_NAME = "SASKIA_CF_TUNNEL_TOKEN"
SECRET_NOTE = (
    "Cloudflare Tunnel token for saskia-rms.paragu-ai.com. "
    "Used by cloudflared on Ivan's box. Generated 2026-09-02."
)


def main() -> int:
    if not TOKEN_FILE.exists():
        print(f"ERROR: {TOKEN_FILE} does not exist.", file=sys.stderr)
        print("  Create the tunnel in Cloudflare Zero Trust first.", file=sys.stderr)
        print(f"  Then: nano {TOKEN_FILE}", file=sys.stderr)
        print("  Paste the full token on a single line.", file=sys.stderr)
        print(f"  chmod 600 {TOKEN_FILE}", file=sys.stderr)
        return 2

    mode = TOKEN_FILE.stat().st_mode & 0o777
    if mode & 0o077:
        print(f"WARNING: {TOKEN_FILE} has permissive mode {oct(mode)}", file=sys.stderr)

    token_value = TOKEN_FILE.read_text().strip()
    # CF tunnel tokens are JSON blobs, typically 400-800 chars
    if len(token_value) < 100:
        print(
            f"ERROR: token length {len(token_value)} looks too short for a CF tunnel token.",
            file=sys.stderr,
        )
        print("  Expected: 400-800 char JSON blob.", file=sys.stderr)
        return 2

    token = BWS_TOKEN_PATH.read_text().strip()
    org_id = ORG_ID_PATH.read_text().strip()
    project_id = PROJECT_ID_PATH.read_text().strip()
    c = BitwardenClient(
        ClientSettings(
            api_url="https://api.bitwarden.com",
            identity_url="https://identity.bitwarden.com",
            user_agent="saskia-deploy/4",
            device_type=DeviceType.SERVER,
        )
    )
    c.auth().login_access_token(token, None)

    # Note: BWS SDK requires `key` (not `name`) and project_ids as a list
    # for create() to succeed (otherwise 404 on a valid org).
    result = c.secrets().create(
        organization_id=uuid.UUID(org_id),
        key=SECRET_NAME,
        value=token_value,
        note=SECRET_NOTE,
        project_ids=[uuid.UUID(project_id)],
    )

    new_id = result.data.id
    new_id_str = new_id.hex if hasattr(new_id, "hex") else str(new_id)
    print(f"saved: {new_id_str}")
    print(f"# {SECRET_NAME} stored. Token was {len(token_value)} chars (not echoed).")
    print(f"# DELETE THE INPUT FILE: shred -u {TOKEN_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
