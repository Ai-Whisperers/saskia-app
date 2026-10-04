"""check_manual_version.py — verify the user-guide README is current.

Compares the version header in docs/user-guide/README.md against:
  1. The current git HEAD commit SHA
  2. The current schema version in app/rms/config.py

Exits non-zero if the manual is stale.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path("/opt/data/profiles/ivan/scratch/saskia-app-work")
README = REPO / "docs" / "user-guide" / "README.md"
CONFIG = REPO / "app" / "rms" / "config.py"


def get_git_sha() -> str:
    r = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    return r.stdout.strip()


def get_schema_version() -> int:
    text = CONFIG.read_text(encoding="utf-8")
    m = re.search(r"CURRENT_SCHEMA_VERSION\s*=\s*(\d+)", text)
    if not m:
        raise RuntimeError(f"CURRENT_SCHEMA_VERSION not found in {CONFIG}")
    return int(m.group(1))


def parse_manual_header(readme_text: str) -> tuple[str, int]:
    """Pull 'schema NN' and 'commit XXXX' from the version header line.

    Allows them to be on the same line OR on the same logical line (the
    'Versión del manual: ...' line), as long as both appear.
    """
    m = re.search(r"schema\s+(\d+).*?commit\s+`?([a-f0-9]+)`?", readme_text, re.DOTALL)
    if not m:
        raise RuntimeError("Manual version header not found. Expected 'schema NN ... commit XXXX'.")
    return m.group(2), int(m.group(1))


def main() -> int:
    if not README.exists():
        print(f"FAIL: {README} not found")
        return 2

    text = README.read_text(encoding="utf-8")
    try:
        manual_commit, manual_schema = parse_manual_header(text)
    except RuntimeError as e:
        print(f"FAIL: {e}")
        return 2

    actual_sha = get_git_sha()
    actual_schema = get_schema_version()

    print(f"Manual says:  schema={manual_schema}  commit={manual_commit}")
    print(f"Repo says:    schema={actual_schema}  commit={actual_sha}")
    print()

    drift = []
    if actual_sha != manual_commit:
        drift.append(f"commit drift (manual pinned to {manual_commit}, current is {actual_sha})")
    if actual_schema != manual_schema:
        drift.append(f"schema drift (manual pinned to {manual_schema}, current is {actual_schema})")

    if drift:
        print("DRIFT DETECTED:")
        for d in drift:
            print(f"  - {d}")
        print()
        print("Action: edit docs/user-guide/README.md 'Versión del manual' line")
        print("        and re-run this check after commit.")
        return 1

    print("OK: manual is current.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
