#!/usr/bin/env python3
"""Save SASKIA_R2_FERNET_KEY to BWS without it appearing as a string literal.

The FERNET key is used to encrypt R2 backup snapshots. Generate with:
    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Usage:
    1. Generate the key (command above). Copy the output.
    2. nano /tmp/fernet_key.txt   (paste, save)
    3. chmod 600 /tmp/fernet_key.txt
    4. python3 scripts/save_saskia_fernet.py
    5. shred -u /tmp/fernet_key.txt

Mirrors scripts/save_saskia_db_url.py + save_saskia_user_password.py
(same Pattern 5: file-based, never echoed).
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, "/opt/data/.venv/lib/python3.11/site-packages")

from bitwarden_sdk import BitwardenClient, ClientSettings, DeviceType  # noqa: E402

KEY_FILE = Path("/tmp/fernet_key.txt")
BWS_TOKEN_PATH = Path("/opt/data/.hermes/inbox/bws-token.secret")
ORG_ID_PATH = Path("/opt/data/.hermes/inbox/org-id.txt")
PROJECT_ID_PATH = Path("/opt/data/.hermes/inbox/bws-project-id-hermes.txt")
SECRET_NAME = "SASKIA_R2_FERNET_KEY"
SECRET_NOTE = (
    "Fernet key (URL-safe base64, 44 chars) for R2 backup encryption. Generated 2026-09-02."
)


def main() -> int:
    if not KEY_FILE.exists():
        print(f"ERROR: {KEY_FILE} does not exist.", file=sys.stderr)
        print("  Generate the key first:", file=sys.stderr)
        print(
            '    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"',
            file=sys.stderr,
        )
        print(f"  Then: nano {KEY_FILE}", file=sys.stderr)
        print("  Paste on a single line.", file=sys.stderr)
        print(f"  chmod 600 {KEY_FILE}", file=sys.stderr)
        return 2

    mode = KEY_FILE.stat().st_mode & 0o777
    if mode & 0o077:
        print(f"WARNING: {KEY_FILE} has permissive mode {oct(mode)}", file=sys.stderr)

    key = KEY_FILE.read_text().strip()
    # FERNET keys are URL-safe base64, 44 chars (32 bytes encoded)
    # Accept either 43 (no padding) or 44 (with padding)
    if not (43 <= len(key) <= 44):
        print(
            f"ERROR: key length {len(key)} doesn't look like a FERNET key (expected 43-44 chars).",
            file=sys.stderr,
        )
        print("  Verify by regenerating:", file=sys.stderr)
        print(
            '    python3 -c "from cryptography.fernet import Fernet; k=Fernet.generate_key(); print(len(k))"',
            file=sys.stderr,
        )
        return 2

    token = BWS_TOKEN_PATH.read_text().strip()
    org_id = ORG_ID_PATH.read_text().strip()
    project_id = PROJECT_ID_PATH.read_text().strip()
    c = BitwardenClient(
        ClientSettings(
            api_url="https://api.bitwarden.com",
            identity_url="https://identity.bitwarden.com",
            user_agent="saskia-deploy/3",
            device_type=DeviceType.SERVER,
        )
    )
    c.auth().login_access_token(token, None)

    # Note: BWS SDK requires `key` (not `name`) and project_ids as a list
    # for create() to succeed (otherwise 404 on a valid org).
    result = c.secrets().create(
        organization_id=uuid.UUID(org_id),
        key=SECRET_NAME,
        value=key,
        note=SECRET_NOTE,
        project_ids=[uuid.UUID(project_id)],
    )

    new_id = result.data.id
    new_id_str = new_id.hex if hasattr(new_id, "hex") else str(new_id)
    print(f"saved: {new_id_str}")
    print(f"# {SECRET_NAME} stored. Key was {len(key)} chars (not echoed).")
    print(f"# DELETE THE INPUT FILE: shred -u {KEY_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
