#!/usr/bin/env python3
"""
Save DATABASE_URL to BWS without it ever appearing as a string literal
in the script source or in any log output.

Usage:
    1. Paste the DATABASE_URL into /tmp/dbx.txt using a local editor.
       (NEVER include the URL in chat, NEVER echo it, NEVER commit it.)
    2. chmod 600 /tmp/dbx.txt
    3. python3 scripts/save_saskia_db_url.py
    4. shred -u /tmp/dbx.txt  (or just rm it)

The script:
  - Reads the URL from /tmp/dbx.txt
  - Calls BWS SDK to create the secret
  - Prints only the new BWS secret UUID (NEVER the value)
  - Returns exit 0 on success, non-zero otherwise
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

# Add BWS SDK to path
sys.path.insert(0, "/opt/data/.venv/lib/python3.11/site-packages")

from bitwarden_sdk import BitwardenClient, ClientSettings, DeviceType  # noqa: E402

DB_URL_FILE = Path("/tmp/dbx.txt")
BWS_TOKEN_PATH = Path("/opt/data/.hermes/inbox/bws-token.secret")
ORG_ID_PATH = Path("/opt/data/.hermes/inbox/org-id.txt")
PROJECT_ID_PATH = Path("/opt/data/.hermes/inbox/bws-project-id-hermes.txt")
SECRET_NAME = "SASKIA_NEON_DATABASE_URL"
SECRET_NOTE = "Saskia RMS hosted DB. Free tier 0.5GB, US East. 2026-09-02."


def main() -> int:
    # 1. Read the URL from a local file the operator pasted into
    if not DB_URL_FILE.exists():
        print(f"ERROR: {DB_URL_FILE} does not exist.", file=sys.stderr)
        print(f"  Create it with: editor-of-choice {DB_URL_FILE}", file=sys.stderr)
        print("  Paste the DATABASE_URL on a single line.", file=sys.stderr)
        print(f"  Then: chmod 600 {DB_URL_FILE}", file=sys.stderr)
        print(f"  Then: python3 {sys.argv[0]}", file=sys.stderr)
        return 2

    # Restrictive permissions check (warn if readable by group/other)
    mode = DB_URL_FILE.stat().st_mode & 0o777
    if mode & 0o077:
        print(f"WARNING: {DB_URL_FILE} has permissive mode {oct(mode)}", file=sys.stderr)
        print(f"  Recommend: chmod 600 {DB_URL_FILE}", file=sys.stderr)

    # Read; do NOT print
    url = DB_URL_FILE.read_text().strip()
    if not url.startswith("postgresql://"):
        print(f"ERROR: {DB_URL_FILE} does not start with postgresql://", file=sys.stderr)
        print(f"  (length: {len(url)} chars — refusing to proceed)", file=sys.stderr)
        return 2

    # 2. Connect to BWS
    token = BWS_TOKEN_PATH.read_text().strip()
    org_id = ORG_ID_PATH.read_text().strip()
    project_id = PROJECT_ID_PATH.read_text().strip()
    c = BitwardenClient(
        ClientSettings(
            api_url="https://api.bitwarden.com",
            identity_url="https://identity.bitwarden.com",
            user_agent="saskia-deploy/1",
            device_type=DeviceType.SERVER,
        )
    )
    c.auth().login_access_token(token, None)

    # 3. Create the secret. The SDK returns the new secret's UUID.
    #    The value never appears in the response we print.
    # Note: BWS SDK requires `key` (not `name`) and project_ids as a list
    # for create() to succeed (otherwise 404 on a valid org).
    result = c.secrets().create(
        organization_id=uuid.UUID(org_id),
        key=SECRET_NAME,
        value=url,
        note=SECRET_NOTE,
        project_ids=[uuid.UUID(project_id)],
    )

    # 4. Print ONLY the new UUID — operator uses this to confirm.
    #    Do NOT print the URL, the value, or anything else.
    new_id = result.data.id
    new_id_str = new_id.hex if hasattr(new_id, "hex") else str(new_id)
    print(f"saved: {new_id_str}")
    print(f"# {SECRET_NAME} stored. URL was {len(url)} chars (not echoed).")
    print(f"# DELETE THE INPUT FILE: shred -u {DB_URL_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
