#!/usr/bin/env python3
"""
Markdown quality checker for saskia-app docs.

Uses pymarkdownlnt (Python markdown linter) via uvx.
Install: pip install pymarkdownlnt, or use uvx as below.

Usage:
  ./scripts/check_docs_quality.py             # scan all docs/ and root .md
  ./scripts/check_docs_quality.py --strict    # enable all rules including MD013
  ./scripts/check_docs_quality.py --json      # machine-readable output
  ./scripts/check_docs_quality.py docs/user-guide/  # scan specific dir

Exit code:
  0 = no findings
  1 = findings (with --strict fail)
  2 = tool error

Why pymarkdownlnt and not markdownlint-cli2?
- pymarkdownlnt is pure Python; no Node.js needed (matches our uv-based tooling)
- Same rule set as markdownlint (MD001-MD058)
- 0 system dependencies (just `uvx --from pymarkdownlnt pymarkdownlnt`)

Config: .markdownlint.jsonc at repo root.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Default rules disabled (per .markdownlint.jsonc in repo root).
# MD013: line length — too noisy for prose-heavy docs
# MD033: inline HTML — used in some templates intentionally
# MD041: first-line H1 — applies to fragments, not full pages
DEFAULT_DISABLED = "MD013,MD033,MD041"


def find_md_files(*paths: Path, recursive: bool = True) -> list[Path]:
    """Find all .md files under the given paths."""
    results = []
    for p in paths:
        if p.is_file() and p.suffix == ".md":
            results.append(p)
        elif p.is_dir():
            glob = "**/*.md" if recursive else "*.md"
            results.extend(sorted(p.glob(glob)))
    return results


def run_pymarkdownlnt(
    files: list[Path], config: Path | None = None, strict: bool = False
) -> tuple[int, str, str]:
    """Run pymarkdownlnt on the given files. Returns (returncode, stdout, stderr)."""
    # pymarkdownlnt quirk: --disable goes at the parent level, not on the
    # `scan` subcommand. The config-file format is also finicky in v0.9.x;
    # use --disable inline to keep things simple.
    cmd = [
        "uvx",
        "--from",
        "pymarkdownlnt",
        "pymarkdownlnt",
    ]
    if not strict:
        # Disable noisy rules by default. Strict mode keeps all rules.
        cmd.extend(["--disable", DEFAULT_DISABLED])
    cmd.extend(["scan", "-r"])
    cmd.extend(str(f) for f in files)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=REPO_ROOT)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 2, "", "pymarkdownlnt timed out after 600s"
    except FileNotFoundError as e:
        return 2, "", f"uvx not found: {e}. Install with: pip install uv\n"


def parse_findings(stdout: str) -> list[dict]:
    """Parse pymarkdownlnt output into structured findings."""
    findings = []
    pattern = re.compile(
        r"^(?P<path>[^:]+):(?P<line>\d+):(?P<col>\d+): (?P<rule>MD\d+):\s+(?P<msg>.*?)(?:\s+\((?P<extra>[^)]+)\))?$"
    )
    for line in stdout.splitlines():
        m = pattern.match(line)
        if m:
            findings.append(
                {
                    "file": m.group("path"),
                    "line": int(m.group("line")),
                    "col": int(m.group("col")),
                    "rule": m.group("rule"),
                    "message": m.group("msg").strip(),
                }
            )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Markdown quality checker for saskia-app docs")
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Paths to scan (default: docs/ and root *.md)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable all rules (overrides config file)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of human-readable",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Config file (default: .markdownlint.jsonc)",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        metavar="FILE",
        help="Snapshot current findings to FILE (use after manual triage).",
    )
    parser.add_argument(
        "--check",
        type=Path,
        default=None,
        metavar="FILE",
        help="Fail if current findings are not a subset of FILE (CI gate).",
    )
    args = parser.parse_args()

    # Default paths: docs/ + root .md files
    if not args.paths:
        paths = [REPO_ROOT / "docs"]
        paths.extend(REPO_ROOT.glob("*.md"))
    else:
        paths = list(args.paths)

    files = find_md_files(*paths)
    if not files:
        print(f"No .md files found under: {paths}", file=sys.stderr)
        return 2

    rc, stdout, stderr = run_pymarkdownlnt(files, args.config, args.strict)

    if rc == 2 and stderr:
        # tool error
        print(f"Tool error: {stderr}", file=sys.stderr)
        return 2

    findings = parse_findings(stdout)
    if not findings:
        if not args.json:
            print(f"✓ All {len(files)} .md files pass markdownlint")
        else:
            print(json.dumps({"files": len(files), "findings": []}))
        return 0

    # Aggregate
    rule_counts = Counter(f["rule"] for f in findings)
    file_counts = Counter(f["file"] for f in findings)

    def finding_key(f: dict) -> tuple:
        rel = f["file"]
        try:
            rel = str(Path(rel).relative_to(REPO_ROOT))
        except ValueError:
            pass
        return (rel, f["line"], f["rule"], f["message"][:120])

    current_keys = {finding_key(f) for f in findings}

    if args.baseline is not None:
        args.baseline.write_text(
            json.dumps(
                {
                    "schema": 1,
                    "snapshot": len(current_keys),
                    "by_rule": dict(rule_counts.most_common()),
                    "keys": sorted(current_keys),
                },
                indent=2,
            )
            + "\n"
        )
        print(f"Baseline written: {args.baseline} ({len(current_keys)} findings)")
        return 0

    if args.check is not None:
        baseline_data = json.loads(args.check.read_text())
        baseline_keys = {tuple(k) for k in baseline_data["keys"]}
        new_keys = current_keys - baseline_keys
        removed_keys = baseline_keys - current_keys
        print(
            f"Baseline gate: baseline={len(baseline_keys)} current={len(current_keys)} "
            f"new={len(new_keys)} removed={len(removed_keys)}"
        )
        if new_keys:
            print("\nNEW findings (not in baseline — PR must fix or extend baseline):")
            for k in sorted(new_keys)[:30]:
                print(f"  {k[0]}:{k[1]}  {k[2]}  {k[3][:80]}")
            if len(new_keys) > 30:
                print(f"  ... ({len(new_keys) - 30} more)")
            return 1
        return 0

    if args.json:
        print(
            json.dumps(
                {
                    "files_scanned": len(files),
                    "files_with_findings": len(file_counts),
                    "total_findings": len(findings),
                    "by_rule": dict(rule_counts.most_common()),
                    "by_file": dict((Path(f).name, c) for f, c in file_counts.most_common(20)),
                    "findings": findings,
                },
                indent=2,
            )
        )
    else:
        print(f"Found {len(findings)} issues in {len(file_counts)} of {len(files)} files:\n")
        print("By rule:")
        for rule, cnt in rule_counts.most_common(10):
            print(f"  {rule:8s} {cnt:6d}")
        print("\nTop files:")
        for f, cnt in file_counts.most_common(10):
            print(f"  {cnt:5d}  {Path(f).name}")
        print("\nFirst 20 findings:")
        for f in findings[:20]:
            print(f"  {f['file'].split('/')[-1]}:{f['line']}  {f['rule']}  {f['message'][:80]}")

    return 1  # findings present


if __name__ == "__main__":
    sys.exit(main())
