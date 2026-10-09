#!/usr/bin/env python3
"""Write /etc/sazon/.env.<env> from Bitwarden Secrets on the VPS.

Runs on the VPS, NOT in CI. Invoked by deploy.sh after a successful
build. Idempotent: only rewrites the file if the BWS values changed
since the last write (compared by SHA-256 of the resolved secret set).

Why a per-env file:
    - docker stack deploy can read env_file from a host path. Mounting
      it into the container means secrets never appear in the image,
      never appear in the rendered stack yml, and never appear in
      `docker service inspect` output.
    - One file per env keeps the boundaries obvious: prod, test, and
      dev never share a file. Operators can `cat /etc/sazon/.env.prod`
      for prod-only debugging without leaking test secrets.

Why BWS (not GH Secrets or .env in repo):
    - GH Secrets are only available to CI workflows; the VPS has no GH
      Actions runner. Pulling them via `gh secret` would require
      authenticating the VPS against GitHub.
    - BWS works on a host with just an access token (no API key, no
      OAuth). The token lives in /etc/sazon/bws-token (mode 0400).

Usage:
    python deploy/write_env_file.py --env=prod
    python deploy/write_env_file.py --env=test
    python deploy/write_env_file.py --env=dev

Exit codes:
    0   file written (or unchanged but OK)
    1   bws CLI missing
    2   bws secret for a required key not found
    3   write failed
"""

from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import shutil
import subprocess
import sys

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml required.", file=sys.stderr)
    sys.exit(2)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
ENVS_FILE = REPO_ROOT / "deploy" / "envs.yaml"
BWS_BIN = shutil.which("bws") or "/usr/local/bin/bws"
BWS_TOKEN_FILE = pathlib.Path("/etc/sazon/bws-token")
ALLOWED_ENVS = ("prod", "test", "dev")


def load_envs() -> dict:
    with open(ENVS_FILE) as f:
        return yaml.safe_load(f)


def bws_get(key: str) -> str:
    """Fetch a single secret value from Bitwarden Secrets.

    Uses `bws secret list` then filters in Python — the BWS CLI doesn't
    have a `get-by-key` subcommand. For 10-15 keys per env, this is
    faster than 15 round-trips.
    """
    if not pathlib.Path(BWS_BIN).exists():
        print(f"ERROR: bws CLI not at {BWS_BIN}", file=sys.stderr)
        sys.exit(1)
    token = BWS_TOKEN_FILE.read_text().strip()
    r = subprocess.run(
        [BWS_BIN, "secret", "list"],
        env={**os.environ, "BWS_ACCESS_TOKEN": token},
        capture_output=True,
        text=True,
        timeout=30,
    )
    if r.returncode != 0:
        print(f"bws secret list FAILED: {r.stderr}", file=sys.stderr)
        sys.exit(1)
    import json

    secrets = json.loads(r.stdout)
    for s in secrets:
        if s["key"] == key:
            return s["value"]
    raise KeyError(key)


def write_env_file(env: str) -> int:
    if env not in ALLOWED_ENVS:
        print(f"ERROR: env must be one of {ALLOWED_ENVS}", file=sys.stderr)
        return 2
    envs = load_envs()
    row = envs[env]
    target = pathlib.Path(row["env_file"])
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    # Build the env file from BWS keys declared in envs.yaml. We do NOT
    # accept arbitrary env-var-name keys here — only the whitelisted
    # bws_keys list per env, so a typo in deploy.sh can't dump prod
    # secrets into a test env file.
    lines = [
        f"# /etc/sazon/.env.{env} — written by deploy/write_env_file.py",
        f"# Source: Bitwarden Secrets (project a1d64864)",
        f"# DO NOT EDIT BY HAND — re-run deploy.sh to refresh.",
        "",
    ]
    for key in row["bws_keys"]:
        try:
            val = bws_get(key)
        except KeyError:
            print(f"ERROR: BWS secret '{key}' not found for env={env}", file=sys.stderr)
            return 2
        # Escape any double-quote / newline in the value
        val_escaped = val.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        lines.append(f'{key}="{val_escaped}"')

    new_content = "\n".join(lines) + "\n"

    # Idempotency: only write if the content hash changed.
    new_hash = hashlib.sha256(new_content.encode()).hexdigest()
    old_hash = ""
    if target.exists():
        old_hash = hashlib.sha256(target.read_bytes()).hexdigest()
    if new_hash == old_hash:
        print(f"{target}: unchanged (hash match)", file=sys.stderr)
        return 0

    target.write_text(new_content)
    target.chmod(0o600)
    print(f"{target}: written ({len(new_content)} bytes, sha256={new_hash[:12]})", file=sys.stderr)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Write /etc/sazon/.env.<env> from Bitwarden Secrets.")
    p.add_argument("--env", required=True, choices=ALLOWED_ENVS)
    args = p.parse_args()
    return write_env_file(args.env)


if __name__ == "__main__":
    sys.exit(main())
