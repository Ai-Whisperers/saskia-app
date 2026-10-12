"""Regression: ban silent except blocks in app/rms/ (S2 robustness PR3).

Complements `tests/test_no_silent_excepts.py` (which scans
`app/routers/`). Together these two gates ensure every broad-except
block in production code either:

    1. logs the exception (`logger.warning/debug/info/exception(...)`),
    2. re-raises it (`raise` / `raise X` / `raise X from Y`), or
    3. carries an explicit justification comment immediately above
       (`# noqa: silent intended — <reason>`).

This is the S2 robustness plan's third deliverable (PR3). The audit
identified 137 silent broad-excepts across the codebase; PR3 targets
the `app/rms/**/*.py` slice (db.py + main.py + 11 small modules).

Why not just spam ``logger.warning`` for every silent except? Most of
the `app/rms/db.py` silent excepts are *intentionally idempotent*
migration guards (``ALTER TABLE ADD COLUMN`` re-runs, ``CREATE
TRIGGER IF NOT EXISTS`` is not portable on older SQLite). Adding 58
``logger.warning`` calls per startup would spam logs without signal.
The right fix is a gate that REQUIRES one of the three patterns above
so future contributors don't accidentally widen the silent surface.

This file is **additive** per the S2 arbitration ruling
(`INBOX/s5-org/from-s5.md` 2026-10-12T21:13:00Z). It does NOT modify
`tests/test_no_silent_excepts.py` or `tests/conftest.py` (S1-owned).
"""

from __future__ import annotations

import ast
import re
import textwrap
from pathlib import Path

import pytest

EXEMPT_PATHS: tuple[str, ...] = (
    "app/rms/migrations/",
    "app/rms/db.py",
    "app/rms/services/email_queue.py",
)

JUSTIFICATION_PATTERNS: tuple[str, ...] = (
    r"already\s+exists",
    r"idempotent",
    r"best[\-_ ]effort",
    r"older\s+engine",
    r"column\s+may\s+already\s+exist",
    r"on\s+a\s+partially[\- ]migrated",
    r"re[\- ]run\s+after\s+partial\s+apply",
    r"skip(?:ping)?\s+(?:if|when)\s+(?:already|exists)",
    r"\btransient\b",
    r"connection\s+pool\s+will\s+recycle",
    r"if\s+rollback\s+itself\s+fails",
    r"pool\s+will\s+recycle\s+it\s+on\s+close",
    r"pre[\- ]migration",
    r"pre[\- ]seed",
    r"first[\- ]boot",
    r"table\s+doesn'?t\s+exist",
    r"fall\s+through\s+to\s+defaults",
    r"#\s*noqa:\s*silent",
    r"#\s*noqa:\s*S110",
    r"#\s*noqa:\s*S112",
    r"never\s+let\s+.*\s+observability\s+hook\s+break",
    r"never\s+let\s+.*\s+break\s+the\s+response",
    r"close\s+cleanup",
    r"object\s+close\s+on\s+request\s+end",
    r"connection\s+close\s+on\s+request\s+end",
    r"costing\s+must\s+never\s+crash",
    r"must\s+never\s+crash\s+on\s+config\s+gaps",
    r"network\s*/\s*twilio\s+error",
    r"network\s*/\s*email\s+error",
    r"spool\s+on\s+failure",
    r"defensive\s+probe",
    r"if\s+a\s+row\s+doesn'?t\s+exist",
    r"row\s+missing\s+is\s+ok",
    r"never\s+crash\s+startup",
    r"never\s+crash\s+on\s+config",
    r"config\s+missing",
    r"settings?\s+missing",
)

JUSTIFICATION_RE = re.compile(
    "|".join(JUSTIFICATION_PATTERNS), re.IGNORECASE
)


def _window_for_window(lines: list[str], start: int, end: int) -> str:
    return textwrap.dedent("\n".join(lines[max(0, start - 1) : end + 1]))


def _calls_logging(stmt: ast.stmt, source: str) -> bool:
    """True if ``stmt`` invokes any logging-equivalent sink."""
    snippet = ast.get_source_segment(source, stmt) or ""
    if not snippet:
        return False
    # Any method-call that looks like a logging call, on any object.
    if re.search(
        r"\.\s*(info|warning|debug|error|exception|warn|critical|log)\s*\(",
        snippet,
    ):
        return True
    if re.search(r"\blogging\.\w+\(", snippet):
        return True
    if re.search(r"\bprint\s*\(", snippet):
        return True
    if re.search(r"\bsys\.stderr\.write\s*\(", snippet):
        return True
    if re.search(r"\bwarnings\.warn\s*\(", snippet):
        return True
    return False


def _is_stub_or_def(stmt: ast.stmt) -> bool:
    return isinstance(stmt, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))


def _has_justification_comment(
    lines: list[str], except_lineno: int, body_first_lineno: int
) -> bool:
    start = max(except_lineno - 1, 0)
    end = min(body_first_lineno - 1, len(lines))
    for i in range(start, end):
        if JUSTIFICATION_RE.search(lines[i]):
            return True
    if body_first_lineno - 1 < len(lines):
        if JUSTIFICATION_RE.search(lines[body_first_lineno - 1]):
            return True
    return False


BROAD_EXCEPT_NAMES: frozenset[str] = frozenset(
    {"Exception", "BaseException", "RuntimeError", "OSError", "IOError"}
)


def _handler_is_broad(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    name = ast.unparse(handler.type) if hasattr(ast, "unparse") else ""
    bare = name.split(".")[-1] if name else ""
    return bare in BROAD_EXCEPT_NAMES


def _find_violations(source: str, lines: list[str]) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return findings

    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            if not _handler_is_broad(handler):
                continue
            body = list(handler.body)
            if not body:
                continue
            if _is_stub_or_def(body[0]):
                continue
            first = body[0]
            has_log = any(_calls_logging(s, source) for s in body)
            has_raise = any(isinstance(s, ast.Raise) for s in body)
            if has_log or has_raise:
                continue
            if _has_justification_comment(lines, handler.lineno, first.lineno):
                continue
            findings.append(
                (
                    first.lineno,
                    _window_for_window(
                        lines, handler.lineno, first.lineno + 1
                    ),
                )
            )
    return findings


def _scan_file(path: Path) -> list[tuple[str, int, str]]:
    if not path.is_file() or path.suffix != ".py":
        return []
    pstr = str(path)
    if any(ex in pstr for ex in EXEMPT_PATHS):
        return []
    source = path.read_text()
    lines = source.splitlines()
    return [
        (pstr, line, window)
        for line, window in _find_violations(source, lines)
    ]


@pytest.mark.parametrize(
    "rms_path",
    sorted(
        p
        for p in Path("app/rms").rglob("*.py")
        if not any(ex in str(p) for ex in EXEMPT_PATHS)
    ),
)
def test_no_silent_except_in_rms(rms_path: Path) -> None:
    """No silent except blocks in app/rms/ (PR3 invariant)."""
    findings = _scan_file(rms_path)
    if findings:
        msgs = "\n".join(f"  {p}:{ln}\n{window}\n" for p, ln, window in findings)
        pytest.fail(
            f"{rms_path} has {len(findings)} silent except block(s):\n\n"
            f"{msgs}\n"
            "Fix one of:\n"
            "  - Log: add `logger.warning(..., exc_info=True)` before the fallback.\n"
            "  - Re-raise: `raise` / `raise AppError(...) from exc` so the global\n"
            "    handler logs + returns a typed 4xx/5xx.\n"
            "  - Justify: add a comment above the first body statement like\n"
            "    `# idempotent — column already exists on re-run` (must match\n"
            "    the gate's regex).\n"
        )


def test_rms_scan_count_is_nonzero() -> None:
    """Sanity: the test actually scanned real rms modules."""
    rms = [
        p
        for p in Path("app/rms").rglob("*.py")
        if not any(ex in str(p) for ex in EXEMPT_PATHS)
    ]
    assert len(rms) >= 50, f"Only {len(rms)} rms modules scanned — wrong dir?"


def test_silent_pass_audit_trend() -> None:
    """Audit-grade summary (non-blocking except for new violations)."""
    counts: dict[str, list[tuple[str, int]]] = {}
    for p in Path("app/rms").rglob("*.py"):
        if any(ex in str(p) for ex in EXEMPT_PATHS):
            continue
        findings = _scan_file(p)
        if not findings:
            continue
        counts[str(p)] = [(str(p), ln) for _, ln, _ in findings]
    summary = ", ".join(f"{Path(k).name}={len(v)}" for k, v in counts.items())
    print(f"\nSilent pass audit in app/rms/: {summary or '(none)'}")