#!/usr/bin/env python3
"""Fix PERF401: `out = []; for x in items: out.append(<expr>)` patterns.

Handles:
  1. Single-line append: `out.append(<expr>)`
  2. Multi-line append: `out.append(\n    <expr>\n)`

Layout (typical, single-line):
  N:     out: list[X] = []
  N+1:     for <loop_var> in <iterable>:
  N+2:         out.append(<expr>)

Layout (typical, multi-line):
  N:     out: list[X] = []
  N+1:     for <loop_var> in <iterable>:
  N+2:         out.append(
  N+3:             <expr>
  N+4:         )

Skips any loop with nested control flow, multi-statement body, or
conditional append.
"""
from __future__ import annotations

import re
import subprocess


def get_violations() -> dict[str, list[int]]:
    out = subprocess.run(
        ['uv', 'run', 'ruff', 'check', '.', '--select', 'PERF401',
         '--output-format', 'concise', '--no-fix'],
        capture_output=True, text=True
    )
    by_file: dict[str, list[int]] = {}
    for line in out.stdout.splitlines():
        m = re.match(r'^(\S+\.py):(\d+):\d+: PERF401', line)
        if m:
            by_file.setdefault(m.group(1), []).append(int(m.group(2)))
    return by_file


def extract_append_expr(lines: list[str], idx: int, indent: str) -> tuple[str | None, int, str | None]:
    """Try to extract the expression inside `out.append(...)` starting
    at `lines[idx]`. Returns (expr, end_idx_inclusive, var_name).
    var_name is the receiver of `.append(...)`.
    Handles both single-line and multi-line append."""
    line = lines[idx].rstrip('\n')
    # Single-line: `var.append(<expr>)`
    m = re.match(rf'^{re.escape(indent)}([A-Za-z_][\w.]*)\.append\((.*)\)\s*$', line)
    if m:
        return m.group(2), idx, m.group(1)
    # Multi-line opener: `var.append(` OR `var.append(Constructor(`
    m = re.match(rf'^{re.escape(indent)}([A-Za-z_][\w.]*)\.append\((?:\w+\()?\s*$', line)
    if not m:
        return None, idx, None
    var = m.group(1)
    body_lines: list[str] = []
    j = idx + 1
    # Body indented one level deeper than indent
    inner_indent = indent + '    '
    closed = False
    while j < len(lines):
        body = lines[j]
        if body.lstrip().startswith(')'):
            closed = True
            break
        if not body.startswith(inner_indent):
            return None, idx, None
        body_lines.append(body[len(inner_indent):].rstrip('\n'))
        j += 1
    if not closed:
        return None, idx, None
    expr = '\n'.join(body_lines).strip()
    return expr, j, var


def fix_file(path: str, line_nums: list[int]) -> int:
    with open(path) as f:
        lines = f.readlines()
    fixed = 0
    # Process from the bottom up
    for ln in sorted(set(line_nums), reverse=True):
        idx = ln - 1
        if idx < 2 or idx >= len(lines):
            continue
        # Try to extract the append expression
        line = lines[idx]
        m_indent = re.match(r'^(\s+)', line)
        if not m_indent:
            continue
        indent = m_indent.group(1)
        expr, end_idx, var = extract_append_expr(lines, idx, indent)
        if expr is None or var is None:
            continue
        # Check expr is not control-flow heavy. Skip if a control keyword
        # starts a line (statement head), not when it's inside a string
        # or ternary expression.
        expr_lines = [line.strip() for line in expr.split('\n') if line.strip()]
        control_found = False
        for el in expr_lines:
            first = el.split()[0] if el else ''
            if first in ('if', 'while', 'for', 'return', 'continue', 'break'):
                # Allow `if`/`for` as part of a ternary or comprehension
                if first == 'if' and ' else ' in el:
                    continue
                if first == 'for' and ' in ' in el:
                    continue
                control_found = True
                break
        if control_found:
            continue
        # Find the `for ... in ...:` line above
        if idx - 1 < 0:
            continue
        for_line = lines[idx - 1]
        m2 = re.match(r'^(\s+)for\s+(\w+)\s+in\s+(.+):\s*$', for_line.rstrip('\n'))
        if not m2:
            continue
        for_indent = m2.group(1)
        loop_var = m2.group(2)
        iterable = m2.group(3)
        # Search backward up to 30 lines for the init `var: list[...] = []`.
        init_line = None
        init_idx = None
        var_match = None
        for back in range(2, min(81, idx + 1)):
            candidate = lines[idx - back]
            m3 = re.match(
                r'^(\s+)([A-Za-z_][\w.]*):\s*list\[?[^\]]*\]?\s*=\s*\[\]\s*$',
                candidate.rstrip('\n')
            )
            if not m3:
                m3 = re.match(
                    r'^(\s+)([A-Za-z_][\w.]*)\s*=\s*\[\]\s*$',
                    candidate.rstrip('\n')
                )
            if m3 and m3.group(1) == for_indent:
                if m3.group(2) == var:
                    init_line = candidate
                    init_idx = idx - back
                    var_match = m3
                    break
        if init_line is None:
            continue
        var = var_match.group(2)
        # Replace the lines from init_idx to end_idx inclusive with
        # a single comprehension. Keep the body as multi-line so it
        # stays readable for complex constructors.
        if '\n' in expr:
            # Multi-line expression. Re-indent body lines to match the
            # comprehension's level (one indent deeper than the var).
            body_indent = for_indent + '    '
            new_block = [f'{for_indent}{var}: list = [\n']
            for el in expr.split('\n'):
                # Re-attach the trailing newline if expr was split.
                if el and not el.endswith('\n'):
                    new_block.append(body_indent + el + '\n')
                else:
                    new_block.append(body_indent + el)
            new_block.append(f'{body_indent}for {loop_var} in {iterable}]\n')
        else:
            new_block = [
                f'{for_indent}{var}: list = [{expr} for {loop_var} in {iterable}]\n',
            ]
        # Replace init_idx with new_block, then delete the OLD for/append lines.
        # After insertion, the original lines from init_idx+1 onward are
        # shifted by `len(new_block) - 1` (we replaced 1 line with N).
        shift = len(new_block) - 1
        lines[init_idx:init_idx + 1] = new_block
        # The OLD end_idx (closing paren line) is now at
        # end_idx + shift. Delete from end of new_block (init_idx+len(new_block))
        # through end_idx + shift + 1 (exclusive).
        del lines[init_idx + len(new_block):end_idx + shift + 1]
        fixed += 1
    if fixed:
        with open(path, 'w') as f:
            f.writelines(lines)
    return fixed


def main() -> int:
    by_file = get_violations()
    total = 0
    for path, line_nums in by_file.items():
        n = fix_file(path, line_nums)
        if n:
            print(f'  {path}: fixed {n}')
        total += n
    print(f'Total: {total}')
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
