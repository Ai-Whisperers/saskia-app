#!/usr/bin/env python3
"""scripts/check_warnings.py — CI gate for test-suite warning count.

Fails the build if the test suite produces more than N warnings.
Used in CI to catch warning regressions early.

Usage:
    python scripts/check_warnings.py           # default: max 0 warnings
    python scripts/check_warnings.py --max 5   # tolerate up to 5
    python scripts/check_warnings.py --verbose  # show the warnings
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max",
        type=int,
        default=0,
        help="Maximum number of allowed warnings (default: 0).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show the warnings.",
    )
    parser.add_argument(
        "test_paths",
        nargs="*",
        default=["tests/"],
        help="Specific test paths to run (default: all).",
    )
    args = parser.parse_args()

    result = subprocess.run(
        [
            "uv", "run", "pytest", "-q", "--tb=no", "--no-header",
            *args.test_paths,
        ],
        capture_output=True, text=True, timeout=600,
        cwd="/opt/data/profiles/ivan/scratch/saskia-app-work",
    )

    # Parse "X passed, Y warnings in Zs" or "X passed in Zs" (zero warnings)
    # Use anchored end-of-line match.
    m = re.search(r"(\d+) passed(?:, (\d+) warnings?)? in", result.stdout)
    if not m:
        print("ERROR: could not parse pytest output")
        print(result.stdout[-1000:])
        return 2

    passed = int(m.group(1))
    warnings_count = int(m.group(2)) if m.group(2) else 0

    print(f"Tests passed: {passed}")
    print(f"Warnings: {warnings_count} (max allowed: {args.max})")

    if args.verbose and warnings_count > 0:
        print()
        print("Last 30 warning lines:")
        for line in result.stdout.split("\n")[-50:]:
            if "Warning" in line or "warning" in line:
                print(f"  {line}")

    if warnings_count > args.max:
        print(f"\nFAIL: {warnings_count} warnings exceed limit {args.max}")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
