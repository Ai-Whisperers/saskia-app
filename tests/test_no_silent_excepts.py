"""Regression: ban silent except blocks in routers (BACKLOG #53).

The app had 29 silent `except: pass` blocks across the codebase — many
in routers. When a user clicks "save" and the underlying handler silently
fails, the operator gets no log, no Sentry event, and no audit row.

This test fails loudly if a router silently swallows an exception. It is
the safety net for the ruff rule configured in pyproject.toml.
"""
from __future__ import annotations

import re
import textwrap
from pathlib import Path

import pytest

# Routes that legitimately need to swallow schema errors (DDBB migrations,
# optional cache writes, etc.). NOT routers — those should always log.
EXEMPT_FILES: tuple[str, ...] = (
    "app/rms/migrations/",
    "app/rms/services/email_queue.py",  # Best-effort SMTP writes
)

# Allowed shapes inside an except block:
#   - pass   ← BANNED
#   - ... but only when paired with logger.warning / logger.info / logger.exception
#   - HTTPException / AppError raise ← OK (a typed 4xx is the visible response)
PASS_PATTERN = re.compile(r"^\s+pass\s*(#.*)?$", re.MULTILINE)


def _find_silent_passes(source: str) -> list[tuple[int, str]]:
    """Return (line_number_of_pass, code_window) for each silent pass.

    Walks the file character-by-character with a state machine so we
    correctly distinguish `try: ... except: pass` from `try: ... except
    Exception as e: logger.warning(...); pass` (still silent, but at least
    logged).
    """
    findings: list[tuple[int, str]] = []
    try_stack: list[int] = []  # line numbers of each open try
    except_stack: list[tuple[int, int]] = []  # (line_of_except, end_of_except_block)

    lines = source.splitlines()
    for idx, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        # Open a try block
        if re.match(r"try\s*:\s*$", stripped):
            try_stack.append(idx)
            continue
        # Open an except block — track it so we know what's "inside"
        if re.match(r"except\b", stripped) and try_stack:
            except_stack.append((idx, idx))
            continue
        # close a block (heuristic: a non-indented line at the same level as try/except)
        # easier: just reset on top-level 'def' / 'class' / 'return' / 'raise' /
        # we walk using Python's own AST below

    # Re-walk using AST so we get accurate scoping
    import ast

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return findings

    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        # Skip if file is exempt
        # (caller filters; here we just collect)
        for handler in node.handlers:
            body = handler.body
            if not body:
                continue
            # Silent = body is exactly one statement that's `pass`,
            # OR contains a `pass` with no logging/raise before it.
            has_log = False
            has_raise = False
            first_pass_line: int | None = None
            for stmt in body:
                if isinstance(stmt, ast.Pass):
                    first_pass_line = stmt.lineno
                    break
                # Walk statement text
                snippet = ast.get_source_segment(source, stmt) or ""
                if "logger." in snippet or "logging." in snippet:
                    has_log = True
                if isinstance(stmt, ast.Raise):
                    has_raise = True
                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                    func = stmt.value.func
                    ftext = ast.unparse(func) if hasattr(ast, "unparse") else ""
                    if ftext.endswith("logger") or ftext.endswith("logging"):
                        has_log = True
            if first_pass_line is not None and not has_log and not has_raise:
                window = textwrap.dedent(
                    "\n".join(lines[max(0, node.lineno - 2): first_pass_line + 1])
                )
                findings.append((first_pass_line, window))
    return findings


def _scan_file(path: Path) -> list[tuple[str, int, str]]:
    if not path.is_file() or path.suffix != ".py":
        return []
    # Skip exempt files
    pstr = str(path)
    for ex in EXEMPT_FILES:
        if ex in pstr:
            return []
    findings = _find_silent_passes(path.read_text())
    return [(pstr, line, window) for line, window in findings]


@pytest.mark.parametrize(
    "router_path",
    sorted(
        p
        for p in Path("app/routers").rglob("*.py")
        if not any(ex in str(p) for ex in EXEMPT_FILES)
    ),
)
def test_no_silent_except_in_routers(router_path: Path) -> None:
    """No silent except blocks in app/routers/ (BACKLOG #53)."""
    findings = _scan_file(router_path)
    if findings:
        msgs = "\n".join(
            f"  {p}:{ln}\n{window}\n" for p, ln, window in findings
        )
        pytest.fail(
            f"{router_path} has {len(findings)} silent except block(s):\n\n"
            f"{msgs}\n"
            f"Fix: log the exception (logger.warning) or re-raise as\n"
            f"AppError / HTTPException so it reaches the global handler."
        )


def test_routers_count_is_nonzero() -> None:
    """Sanity: the test actually scanned real routers, not an empty list."""
    routers = list(Path("app/routers").rglob("*.py"))
    assert len(routers) >= 10, f"Only {len(routers)} routers scanned — wrong dir?"


def test_full_audit_summary() -> None:
    """One-glance overview of silent passes across the whole app (non-blocking)."""
    all_paths = [Path("app"), Path("tests")]
    counts: dict[str, list[tuple[str, int]]] = {"routers": [], "rms": [], "tests": []}
    for root in all_paths:
        if not root.exists():
            continue
        for p in root.rglob("*.py"):
            for ex in EXEMPT_FILES:
                if ex in str(p):
                    break
            else:
                findings = _scan_file(p)
                if not findings:
                    continue
                bucket = (
                    "routers" if "routers/" in str(p) else
                    "tests" if "tests/" in str(p) else "rms"
                )
                counts[bucket].extend([(str(p), ln) for _, ln, _ in findings])
    # This test never fails; it prints the audit so CI captures the trend.
    summary = ", ".join(
        f"{k}={len(v)}" for k, v in counts.items()
    )
    print(f"\nSilent pass audit (non-blocking): {summary}")
    for bucket, items in counts.items():
        if bucket == "routers" and items:
            pytest.fail(
                f"routers must have ZERO silent passes; found {len(items)}:\n"
                + "\n".join(f"  {p}:{ln}" for p, ln in items)
            )
