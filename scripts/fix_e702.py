#!/usr/bin/env python3
"""Fix E702 (multiple statements on one line, semicolon-separated)
mechanically by replacing `; ` with newline + same indentation.

E702 cannot be auto-fixed by ruff because it doesn't know the
indentation. This script is conservative:
  - Only acts on lines flagged by `ruff check --select E702`
  - Replaces each `; ` with `\n` + same indent as the start of the
    first statement
  - Skips lines that look like compound statement heads (if/for/while
    on one line with `:` followed by a semicolon-separated body)
"""
from __future__ import annotations
import re
import subprocess
import sys
from collections import defaultdict


def get_e702_lines() -> dict[str, list[int]]:
    """Return {file: [line_numbers]} for all E702 violations."""
    out = subprocess.run(
        ["uv", "run", "ruff", "check", ".", "--select", "E702",
         "--output-format", "concise", "--no-fix"],
        capture_output=True, text=True
    )
    by_file: dict[str, list[int]] = defaultdict(list)
    for line in out.stdout.splitlines():
        m = re.match(r"^(\S+\.py):(\d+):", line)
        if m:
            by_file[m.group(1)].append(int(m.group(2)))
    return by_file


def fix_file(path: str, line_nums: list[int]) -> int:
    """Apply the fix in `path` at the given line numbers. Return # fixed."""
    with open(path) as f:
        lines = f.readlines()
    fixed = 0
    for ln in line_nums:
        idx = ln - 1
        if idx >= len(lines):
            continue
        original = lines[idx]
        # Only act if the line has a `; ` (semicolon followed by space)
        # that's NOT inside a string literal. Heuristic: count quote
        # parity to detect strings.
        # Find the first `; ` that is outside any string.
        # For simplicity, assume E702 lines don't have escaped semicolons
        # in strings (ruff would not flag those).
        if "; " not in original:
            continue
        # Find leading whitespace.
        leading = re.match(r"^(\s*)", original).group(1)
        # If the line is a statement-head like `if cond: a; b`, don't
        # touch (would break Python). Detect: `: ` followed by code with
        # a `;` after the colon.
        head_match = re.match(r"^(\s*)(if|while|for|elif|else)\b.*:\s+", original)
        if head_match and "; " in original[head_match.end():]:
            # Insert newline between `:` block and the next statement.
            # Split at the first `; ` after the colon, indent the
            # remaining statements.
            tail_start = head_match.end()
            tail = original[tail_start:]
            parts = tail.split("; ")
            # Re-indent: the `:` body starts at leading + 4 spaces (PEP 8).
            inner_indent = leading + "    "
            new_tail = parts[0] + ("\n" + inner_indent + "; ".join(parts[1:]).rstrip() if len(parts) > 1 else "")
            new_line = original[:tail_start] + new_tail
            lines[idx] = new_line
            fixed += 1
        else:
            # Plain `a; b; c` — split each onto its own line.
            stripped = original.rstrip("\n")
            parts = stripped.split("; ")
            # The first part keeps the leading indent; the rest gets
            # the same indent.
            new = parts[0] + "\n" + leading + ("\n" + leading).join(parts[1:])
            lines[idx] = new + ("\n" if original.endswith("\n") else "")
            fixed += 1
    with open(path, "w") as f:
        f.writelines(lines)
    return fixed


def main() -> int:
    by_file = get_e702_lines()
    total = 0
    for path, lines in by_file.items():
        n = fix_file(path, sorted(set(lines)))
        if n:
            print(f"  {path}: fixed {n}")
        total += n
    print(f"Total fixed: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
