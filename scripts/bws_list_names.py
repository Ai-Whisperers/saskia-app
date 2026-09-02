#!/usr/bin/env python3
"""
bws_list_names.py — list BWS secret NAMES only (never values).

Pattern 1 from credential-redacted-grep skill. Safe to run and paste
the output in chat — no secrets leak.

Usage:
    python3 scripts/bws_list_names.py [--project-id <uuid>] [--search <substring>]

Examples:
    # List all secrets in the default Hermes BWS project
    python3 scripts/bws_list_names.py

    # Find anything saskia-related
    python3 scripts/bws_list_names.py --search saskia

    # Find anything r2-related
    python3 scripts/bws_list_names.py --search r2

Output: one line per secret, just the NAME. Nothing else.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

# Make BWS SDK importable from the system venv
sys.path.insert(0, "/opt/data/.venv/lib/python3.11/site-packages")

from bitwarden_sdk import BitwardenClient, ClientSettings, DeviceType  # noqa: E402

BWS_TOKEN_PATH = Path("/opt/data/.hermes/inbox/bws-token.secret")
ORG_ID_PATH = Path("/opt/data/.hermes/inbox/org-id.txt")
PROJECT_ID_PATH = Path("/opt/data/.hermes/inbox/bws-project-id-hermes.txt")


def main() -> int:
    p = argparse.ArgumentParser(description="List BWS secret names (never values).")
    p.add_argument(
        "--project-id", help="BWS project UUID (defaults to inbox/bws-project-id-hermes.txt)"
    )
    p.add_argument("--org-id", help="BWS org UUID (defaults to inbox/org-id.txt)")
    p.add_argument("--search", help="Case-insensitive substring filter on name")
    args = p.parse_args()

    token = BWS_TOKEN_PATH.read_text().strip()

    # BWS SDK expects ORG id for list() — but operator may have a project.
    # Try both: project first, then org.
    org_id = args.org_id or ORG_ID_PATH.read_text().strip()
    project_id = args.project_id or PROJECT_ID_PATH.read_text().strip()

    c = BitwardenClient(
        ClientSettings(
            api_url="https://api.bitwarden.com",
            identity_url="https://identity.bitwarden.com",
            user_agent="saskia-bws-list/1",
            device_type=DeviceType.SERVER,
        )
    )
    c.auth().login_access_token(token, None)

    # Try org first (most likely to exist); fall back to project.
    secrets = None
    for attempt_id in (org_id, project_id):
        try:
            result = c.secrets().list(organization_id=uuid.UUID(attempt_id))
            secrets = result.data.data
            break
        except Exception as exc:
            print(f"# tried {attempt_id[:8]}...: {exc}", file=sys.stderr)
            continue
    if secrets is None:
        print("# failed to list — pass --org-id or --project-id", file=sys.stderr)
        return 1

    names = sorted({getattr(s, "key", "") or getattr(s, "name", "") or "" for s in secrets})
    if args.search:
        s_lower = args.search.lower()
        names = [n for n in names if s_lower in n.lower()]

    for n in names:
        print(n)
    print(f"# total: {len(names)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
