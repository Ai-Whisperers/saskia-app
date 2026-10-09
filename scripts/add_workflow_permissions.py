#!/usr/bin/env python3
"""Add workflow-level `permissions: { contents: read }` to workflows missing it.

Picks the right block based on the workflow's actual needs:
- Read-only workflows (most): `contents: read`
- Release workflow (tag push + CHANGELOG commit): already has `contents: write` — skip

Idempotent: if a workflow already has a top-level `permissions:` block, this
script is a no-op for that file.
"""
import re
import sys
from pathlib import Path

# Workflows that already have a top-level permissions block (skip)
SKIP = {"date-boundary.yml", "dev-ci.yml", "release.yml", "security-zap.yml",
        "sharded-test.yml", "tooling.yml", "workflows-lint.yml"}

# Workflows needing read-only permissions added
NEEDS_READ = ["browser.yml", "ci.yml", "currency-drift.yml", "deploy-dev.yml",
              "deploy-test.yml", "route-smoke.yml", "smoke.yml"]


def add_read_permissions(path: Path) -> bool:
    """Add `permissions: { contents: read }` above the `jobs:` block. Returns True if changed."""
    content = path.read_text()

    # Skip if already has a top-level permissions block (not indented)
    if re.search(r"^permissions:", content, re.MULTILINE):
        print(f"  ! {path.name}: already has top-level permissions; skipping")
        return False

    # Find the `jobs:` line
    match = re.search(r"^jobs:\s*$", content, re.MULTILINE)
    if not match:
        print(f"  ! {path.name}: no `jobs:` line found; skipping", file=sys.stderr)
        return False

    # Insert permissions block before `jobs:`
    insertion = (
        "# Minimum GitHub token permissions: read-only.\n"
        "# zizmor recommends this default; jobs that need more must override.\n"
        "permissions:\n"
        "  contents: read\n"
        "\n"
    )
    new_content = content[:match.start()] + insertion + content[match.start():]
    path.write_text(new_content)
    return True


def main() -> int:
    workflows_dir = Path(".github/workflows")
    if not workflows_dir.is_dir():
        print(f"ERROR: {workflows_dir} not found; run from repo root", file=sys.stderr)
        return 1

    changed = 0
    for name in NEEDS_READ:
        path = workflows_dir / name
        if not path.exists():
            print(f"  ! {name}: not found; skipping", file=sys.stderr)
            continue
        if add_read_permissions(path):
            print(f"  {name}: added permissions: contents: read")
            changed += 1

    print(f"\nChanged: {changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
