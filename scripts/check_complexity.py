#!/usr/bin/env python3
"""scripts/check_complexity.py — CI gate for cyclomatic complexity.

Wraps `radon cc` and fails if any function has CC > 10 (grade C or worse).
Per Sazon tooling rec 2026-10-08.

Usage:
    python scripts/check_complexity.py           # default: max grade B
    python scripts/check_complexity.py --max A   # stricter (CC <= 5)
    python scripts/check_complexity.py --max C   # looser (CC <= 20)
    python scripts/check_complexity.py --report  # print full table, don't fail
    python scripts/check_complexity.py app/rms/production.py  # single file

Exit codes:
    0 = all functions within ceiling
    1 = violations found
    2 = radon not installed (operator action needed)

Radon grades (CC = cyclomatic complexity):
    A   1-5    simple
    B   6-10   well-structured
    C  11-20   complex
    D  21-30   more complex (refactor signal)
    F  31+     untestable, error-prone (refactor!)

Sazon default is B (CC <= 10). One notch looser than the often-cited
"max 10 per function" rule, so existing code passes without churn.
Tighten with --max A as the codebase matures.
"""

from __future__ import annotations

import argparse
import subprocess
import sys

GRADE_ORDER = ["A", "B", "C", "D", "F"]

# Maps grade name to inclusive max CC for that grade.
GRADE_MAX_CC = {
    "A": 5,
    "B": 10,
    "C": 20,
    "D": 30,
    "F": 10**9,  # F means anything above D
}


def parse_radon_output(output: str) -> list[tuple[str, str, str, int, int]]:
    """Parse `radon cc -s -n B app/` output.

    Returns list of (file, function, grade, cc, lineno) tuples.
    radon output format:
        path/to/file.py
            F name (cc) line N
            M name2 (cc) line N
    """
    rows: list[tuple[str, str, str, int, int]] = []
    current_file = ""
    for line in output.splitlines():
        line = line.rstrip()
        if not line:
            continue
        if not line.startswith(" "):
            # file path line
            current_file = line.strip()
            continue
        # function line: "    F name (cc) line N"
        stripped = line.strip()
        if not stripped or stripped[0] not in GRADE_ORDER:
            continue
        try:
            grade = stripped[0]
            rest = stripped[1:].strip()
            # rest looks like: "function_name (CC) line N"
            # find " (" then ")" then " line "
            open_paren = rest.find(" (")
            close_paren = rest.find(")")
            line_marker = rest.find(" line ")
            if -1 in (open_paren, close_paren, line_marker):
                continue
            name = rest[:open_paren].strip()
            cc = int(rest[open_paren + 2 : close_paren])
            lineno = int(rest[line_marker + 6 :].strip())
            rows.append((current_file, name, grade, cc, lineno))
        except (ValueError, IndexError):
            continue
    return rows


def grade_allowed(grade: str, max_grade: str) -> bool:
    """True if grade is at-or-better than max_grade (A is best, F is worst)."""
    return GRADE_ORDER.index(grade) <= GRADE_ORDER.index(max_grade)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        default=["app/", "scripts/"],
        help="Paths to scan (default: app/ scripts/)",
    )
    parser.add_argument(
        "--max",
        dest="max_grade",
        default="B",
        choices=GRADE_ORDER,
        help="Maximum allowed grade (default: B = CC <= 10)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print full table of all functions, do not fail on violations",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Additional exclude path (repeatable). Default: app/_archive",
    )
    args = parser.parse_args()

    # Default exclude: legacy archives
    excludes = list(set(["app/_archive", ".venv", "tests", *args.exclude]))

    cmd = [
        "radon",
        "cc",
        "-s",  # show only summary (grades)
        "-n",
        args.max_grade,
        *args.paths,
        *[f"--exclude {e}" for e in excludes if not any(c in e for c in [" ", "\t"])],
    ]
    # radon --exclude is a single comma-list; rebuild cleanly
    cmd = [
        "radon",
        "cc",
        "-s",
        "-n",
        args.max_grade,
        *args.paths,
        f"--exclude={','.join(excludes)}",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except FileNotFoundError:
        print(
            "ERROR: `radon` not found. Install with `uv add --dev radon`.",
            file=sys.stderr,
        )
        return 2
    except subprocess.TimeoutExpired:
        print("ERROR: `radon` timed out after 120s.", file=sys.stderr)
        return 2

    if result.returncode not in (0,):
        # radon returns non-zero if any function > -n grade. We want
        # to parse + decide ourselves, so don't bail on non-zero.
        pass

    rows = parse_radon_output(result.stdout + "\n" + result.stderr)
    violations = [r for r in rows if not grade_allowed(r[2], args.max_grade)]

    if args.report:
        print(f"# radon CC report (max allowed: {args.max_grade})")
        print(f"# {'grade':<6} {'cc':<4} {'file':<60} {'fn':<40} line")
        for f, name, grade, cc, lineno in sorted(rows, key=lambda r: (-r[3], r[0])):
            marker = " " if grade_allowed(grade, args.max_grade) else "!"
            print(f"{marker} {grade:<4} {cc:<4} {f:<60} {name:<40} {lineno}")
        print(f"# Total: {len(rows)} functions, {len(violations)} over ceiling {args.max_grade}")
        return 0

    if violations:
        print(
            f"ERROR: {len(violations)} function(s) exceed complexity grade {args.max_grade}.",
            file=sys.stderr,
        )
        print("Refactor each before commit:", file=sys.stderr)
        for f, name, grade, cc, lineno in sorted(violations, key=lambda r: -r[3])[:30]:
            print(f"  {grade} cc={cc:<3} {f}:{lineno}  {name}()", file=sys.stderr)
        if len(violations) > 30:
            print(f"  ... and {len(violations) - 30} more", file=sys.stderr)
        print("", file=sys.stderr)
        print(
            "Tip: extract helper functions, replace if/elif chains with table lookup, "
            "split by concern. See docs/operations/2026-10-08-tooling-hardening.md.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: all {len(rows)} function(s) within complexity grade {args.max_grade}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
