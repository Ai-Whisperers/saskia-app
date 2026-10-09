#!/usr/bin/env python3
"""Refresh GitHub Actions SHA pins to the commits their version tags point at.

Unlike scripts/pin_workflow_actions.py (which re-applies a hardcoded
(action, version) -> sha map), this script RESOLVES each tag live via
the GitHub API and reports/fixes drift: a moved tag (e.g. upstream
force-pushed v7) or a manually-added `uses: action@vN` line.

Usage:
    python scripts/refresh_action_pins.py            # check only, rc=1 on drift
    python scripts/refresh_action_pins.py --fix      # rewrite files in place

In CI (workflow_dispatch / monthly schedule) the pattern is:
check-only + open a PR with --fix output when rc=1.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# uses: owner/repo@ref  # optional comment
USES_RE = re.compile(
    r"(?P<prefix>\buses:\s+)(?P<action>[\w.-]+/[\w.-]+)@(?P<ref>[0-9a-f]{40})"
    r"(?P<comment>\s*#\s*(?P<version>v[\w.-]+))?"
)


def gh_api(path: str) -> dict:
    r = subprocess.run(
        ["gh", "api", path],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if r.returncode != 0:
        raise RuntimeError(f"gh api {path} failed: {r.stderr.strip()[:200]}")
    return json.loads(r.stdout)


def resolve_tag_sha(action: str, tag: str) -> str | None:
    """SHA the tag currently points at (peeling annotated tags)."""
    # Try tag ref first; fall back to branch ref (some actions use branch names).
    for ref in (f"tags/{tag}", f"heads/{tag}"):
        try:
            data = gh_api(f"repos/{action}/git/ref/{ref}")
        except RuntimeError:
            continue
        sha = data["object"]["sha"]
        if data["object"]["type"] == "tag":  # annotated tag -> peel
            commit = gh_api(f"repos/{action}/git/tags/{sha}")
            sha = commit["object"]["sha"]
        return sha
    return None


def scan(fix: bool) -> tuple[int, list[str]]:
    drift: list[str] = []
    changed_files = 0
    for wf in sorted(WORKFLOWS_DIR.glob("*.yml")):
        text = wf.read_text()
        out_lines: list[str] = []
        dirty = False
        for line in text.split("\n"):
            m = USES_RE.search(line)
            if not m or not m.group("version"):
                out_lines.append(line)
                continue
            action, pinned, tag = m["action"], m["ref"], m["version"]
            try:
                current = resolve_tag_sha(action, tag)
            except RuntimeError as exc:
                print(f"WARN: {wf.name}: {action}@{tag}: {exc}", file=sys.stderr)
                out_lines.append(line)
                continue
            if current and current != pinned:
                drift.append(f"{wf.name}: {action}@{tag}: {pinned[:12]} -> {current[:12]}")
                if fix:
                    # Splice ONLY the matched `uses:` span; keep the line's
                    # leading indentation and any trailing content intact.
                    line = (
                        line[: m.start()]
                        + f"{m['prefix']}{action}@{current}  # {tag}"
                        + line[m.end() :]
                    )
                    dirty = True
            out_lines.append(line)
        if dirty:
            wf.write_text("\n".join(out_lines))
            changed_files += 1
    return changed_files, drift


def main() -> int:
    fix = "--fix" in sys.argv
    changed_files, drift = scan(fix=fix)
    if not drift:
        print("OK: all SHA pins match their version tags.")
        return 0
    verb = "Re-pinned" if fix else "Drift detected"
    print(
        f"{verb} in {changed_files if fix else len(set(d.split(':')[0] for d in drift))} file(s), {len(drift)} pin(s):"
    )
    for d in drift:
        print(f"  - {d}")
    return 1 if not fix else 0


if __name__ == "__main__":
    sys.exit(main())
