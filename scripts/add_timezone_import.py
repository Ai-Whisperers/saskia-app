#!/usr/bin/env python3
"""Add `timezone` to existing `from datetime import ...` lines when the
file uses `timezone.utc` but doesn't import `timezone`.

Specifically handles:
  - `from datetime import datetime`         -> `from datetime import datetime, timezone`
  - `from datetime import datetime as _dt`  -> `from datetime import datetime as _dt, timezone`
  - `from datetime import date, timedelta`  -> `from datetime import date, datetime, timedelta, timezone`
    (and `from datetime import datetime, ...` -> add `timezone`)
  - If no `from datetime import` exists, add `from datetime import timezone`
    as a new import after the first `from datetime import datetime` (or
    on its own if nothing is imported).

Skip if the file already has `, timezone` somewhere in its datetime imports
or any plain `import datetime; datetime.timezone` access pattern.
"""
from __future__ import annotations
import re
import subprocess


def get_files_using_timezone_utc() -> list[str]:
    out = subprocess.run(
        ["grep", "-l", "-E", r"timezone\.utc", "-r", ".",
         "--include=*.py"],
        capture_output=True, text=True
    )
    return [f for f in out.stdout.split("\n") if f]


def has_timezone_import(content: str) -> bool:
    """True if `timezone` is already imported."""
    patterns = [
        r"^from datetime import .*\btimezone\b",
        r"^import datetime\s*$",
        r"^from datetime import \*",
    ]
    for p in patterns:
        if re.search(p, content, re.M):
            return True
    return False


def fix_file(path: str) -> str | None:
    """Try to fix the file. Return description of what was done, or None."""
    with open(path) as f:
        content = f.read()
    if has_timezone_import(content):
        return None
    orig = content

    # Case A: `from datetime import datetime` (no extras) — add `, timezone`
    m = re.search(r"^(\s*)from datetime import datetime$", content, re.M)
    if m:
        content = re.sub(
            r"^(\s*)from datetime import datetime$",
            r"\1from datetime import datetime, timezone",
            content, flags=re.M, count=1,
        )

    # Case B: `from datetime import datetime, X, Y` — extend with `, timezone`
    if has_timezone_import(content):
        with open(path, "w") as f:
            f.write(content)
        return "extended existing import"
    m = re.search(r"^(\s*)from datetime import (datetime(?:,\s*\w+)*)$", content, re.M)
    if m:
        indent = m.group(1)
        imports = m.group(2)
        # Add timezone at the end (keep alphabetical-friendly)
        if "timezone" not in imports:
            new_imports = imports + ", timezone"
            old = f"{indent}from datetime import {imports}"
            new = f"{indent}from datetime import {new_imports}"
            content = content.replace(old, new, 1)
        with open(path, "w") as f:
            f.write(content)
        return "extended existing multi import"

    # Case C: `from datetime import datetime as _dt` (with optional extras)
    if has_timezone_import(content):
        with open(path, "w") as f:
            f.write(content)
        return "extended alias import"
    m = re.search(r"^(\s*)from datetime import (datetime as _dt(?:,\s*\w+)*)$", content, re.M)
    if m:
        indent = m.group(1)
        imports = m.group(2)
        if "timezone" not in imports:
            new_imports = imports + ", timezone"
            old = f"{indent}from datetime import {imports}"
            new = f"{indent}from datetime import {new_imports}"
            content = content.replace(old, new, 1)
        with open(path, "w") as f:
            f.write(content)
        return "extended alias import"

    # Case D: `from datetime import date, timedelta` only — add `datetime, timezone`
    m = re.search(r"^(\s*)from datetime import (date(?:,\s*\w+)*)$", content, re.M)
    if m:
        indent = m.group(1)
        imports = m.group(2)
        if "timezone" not in imports:
            new_imports = imports + ", timezone"
            old = f"{indent}from datetime import {imports}"
            new = f"{indent}from datetime import {new_imports}"
            content = content.replace(old, new, 1)
        with open(path, "w") as f:
            f.write(content)
        return "added timezone to date-only import"

    # Case E: No `from datetime import` at all — add `from datetime import timezone`
    if "from datetime import" not in content:
        # Find first `^import ` or `^from ` line and add after it
        # Or, just prepend after module docstring
        lines = content.split("\n")
        # Find a good place: after any `from __future__` or `import` lines at top
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("from __future__") or line.startswith("import ") or line.startswith("from "):
                insert_idx = i + 1
        lines.insert(insert_idx, "from datetime import timezone")
        with open(path, "w") as f:
            f.write("\n".join(lines))
        return "added new from datetime import timezone"

    return None


def main() -> int:
    files = get_files_using_timezone_utc()
    fixed = 0
    for path in files:
        if not path:
            continue
        result = fix_file(path)
        if result:
            print(f"  {path}: {result}")
            fixed += 1
    print(f"\nTotal fixed: {fixed}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())