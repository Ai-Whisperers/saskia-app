#!/usr/bin/env python3
"""Scan for ACTIVE TODO comments — code comments only, not prose.

Context: the docs-quality audit (PR #93) found 253 grep matches for
TODO/FIXME/XXX across the repo, but most are false positives:
  - Spanish prose ("TODO de un proveedor")
  - Test names referencing closed Phase-14 TODOs
  - Sprint tables in archived plans
  - Audit docs quoting other projects' TODO patterns

This script matches only code-comment style:

  # TODO
  # TODO: ...
  # FIXME: ...
  # XXX: ...
  // TODO (TypeScript/JS, if we ever add it)

Comment markers (`#`, `//`, `<!-- -->`) are detected at line start
or after a column of whitespace. Prose use (lowercase, mid-sentence)
is excluded.

Output: prints one match per line as `<file>:<line>: <text>`. Exits 0
always; the operator decides what to do with the list.

Usage:
  ./scripts/check_active_todos.py
  ./scripts/check_active_todos.py --json
  ./scripts/check_active_todos.py --stats
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Match the START of a code comment line (with optional leading
# whitespace) followed by TODO/FIXME/XXX and a word boundary. The
# 'i' flag is intentionally OFF: 'todo' lowercase is Spanish prose
# ("todo de", "todo el"). Only the ALL-CAPS marker is a code comment.
COMMENT_LINE = re.compile(r"^\s*(?:#|//|<!--)\s*(TODO|FIXME|XXX)\b\s*:?\s*(?P<text>.*)$")

# Files to skip (generated, vendored, or known-noisy)
SKIP_DIRS = {".venv", ".git", "node_modules", "__pycache__", ".mypy_cache", ".ruff_cache"}
SKIP_FILES = {
    "docs/operations/2026-10-09-docs-quality-audit.md",  # self-reference
    "docs/operations/2026-10-09-todo-triage.md",  # this file
    "docs/plans/2026-10-01-phase14-todo-inventory.md",  # doc title starts with "# TODO"
    "docs/roadmap/historical-plans/2026-10-phase14/2026-10-01-phase14-todo-inventory.md",  # duplicate
    "docs/archive/2026-09/operations/2026-09-02-saskia-deploy-runbook.md",  # code block has "# TODO"
}


def scan() -> list[dict]:
    findings: list[dict] = []
    for path in REPO_ROOT.rglob("*"):
        if path.is_dir():
            continue
        rel = str(path.relative_to(REPO_ROOT))
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if rel in SKIP_FILES:
            continue
        if path.suffix not in {
            ".py",
            ".md",
            ".yml",
            ".yaml",
            ".sh",
            ".toml",
            ".cfg",
            ".ini",
            ".html",
            ".js",
            ".ts",
        }:
            continue
        try:
            text = path.read_text(errors="replace")
        except Exception:
            continue
        for i, line in enumerate(text.split("\n"), 1):
            m = COMMENT_LINE.match(line)
            if not m:
                continue
            findings.append(
                {
                    "file": rel,
                    "line": i,
                    "marker": m.group(1),
                    "text": m.group("text").strip()[:120],
                }
            )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan for active code TODO/FIXME/XXX comments.")
    parser.add_argument("--json", action="store_true", help="JSON output.")
    parser.add_argument("--stats", action="store_true", help="Show summary stats only.")
    args = parser.parse_args()

    findings = scan()
    if args.json:
        print(json.dumps({"total": len(findings), "findings": findings}, indent=2))
        return 0
    if args.stats:
        by_file = Counter(f["file"] for f in findings)
        by_marker = Counter(f["marker"] for f in findings)
        print(f"Active TODO comments: {len(findings)} across {len(by_file)} files")
        print("\nBy marker:")
        for m, n in by_marker.most_common():
            print(f"  {m:6s} {n}")
        print("\nTop files:")
        for f, n in by_file.most_common(10):
            print(f"  {n:3d}  {f}")
        return 0

    for f in findings:
        text = f["text"] or "(no message)"
        print(f"{f['file']}:{f['line']}  [{f['marker']}]  {text}")
    print(f"\nTotal: {len(findings)} active TODO comments")
    return 0


if __name__ == "__main__":
    sys.exit(main())
