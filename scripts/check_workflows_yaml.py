#!/usr/bin/env python3
"""Check that every workflow YAML parses.

s4-tooling pass 2026-10-12. The #159 lesson: ci.yml's safe_load was
broken since #112 and silently skipped the full test suite. This script
runs `yaml.safe_load` over every .github/workflows/*.yml and exits
non-zero on any parse failure.

Wired into:
  - `make audit` (pre-PR local)
  - `.github/workflows/fast-pr-gate.yml` (CI, parallel to ci.yml)
  - `.github/workflows/ci.yml` (existing — could be added as a self-check
    step there too; see PR #159 followup)

Idempotent and read-only.
"""

from __future__ import annotations

import pathlib
import sys

import yaml


def main() -> int:
    wf_dir = pathlib.Path(__file__).resolve().parent.parent / ".github" / "workflows"
    if not wf_dir.is_dir():
        print(f"WARN: workflow dir not found: {wf_dir}", file=sys.stderr)
        return 0
    ok = fail = 0
    failed: list[tuple[str, str]] = []
    for f in sorted(wf_dir.glob("*.yml")):
        try:
            yaml.safe_load(f.read_text())
            ok += 1
        except Exception as e:
            print(f"PARSE FAIL: {f.relative_to(wf_dir.parent.parent)}: {e}", file=sys.stderr)
            failed.append((f.name, str(e)))
            fail += 1
    print(f"YAML self-check: {ok} workflows parsed OK, {fail} failed")
    if failed:
        for name, err in failed:
            print(f"  - {name}: {err}", file=sys.stderr)
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
