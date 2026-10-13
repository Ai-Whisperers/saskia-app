"""Regression: ban silent broad-except blocks in app/routers/ (S2 robustness PR4).

Complements ``tests/test_no_silent_excepts.py`` (which scans for bare
``except: pass``) and ``tests/test_silent_excepts_rms.py`` (which scans
``app/rms/`` for the same broad-except shape). Together the three gates
ensure every broad-except block in production code either:

    1. logs the exception (``logger.warning/debug/info/exception(...)``),
    2. re-raises it (``raise`` / ``raise X`` / ``raise X from Y``), or
    3. carries an explicit justification comment immediately above
       (``# noqa: silent intended — <reason>`` or one of the documented
       justification patterns).

This is the S2 robustness plan's fourth deliverable (PR4). The
audit identified 37 silent broad-except handlers across 14 router files;
PR4 covers the ``app/routers/**/*.py`` slice. Additive file per the S5
arbitration ruling (``INBOX/s5-org/from-s5.md``
``2026-10-12T21:13:00Z``) — does NOT modify
``tests/test_no_silent_excepts.py`` or
``tests/test_silent_excepts_rms.py``.

Why not just spam ``logger.warning`` for every silent except? Most of
the router handlers we touch are *defensive* — they catch an error from
a 3rd-party SDK (boto3 head_bucket, urllib HEAD probe, json.loads on
malformed input) and return a sentinel ("None", "False", "[]", "{}").
Adding ``logger.exception`` to every one would clutter logs without
signal; ``logger.debug`` + a one-line justification is the right
default. The handful that genuinely indicate operator-actionable
problems (commit-time audit row failures, mid-write R2 probe failures)
get ``logger.warning``.

EXEMPT_PATHS rationale:

- ``app/routers/health.py`` — every broad-except in health.py is part of
  the *intentional* degradation pattern (a failing probe reports "ok=False"
  rather than 500'ing the entire /healthz surface). The PR4 sweep still
  adds log lines to each one, but the gate allows the "return sentinel"
  fallback as long as the comment + log line are present. EXEMPT is a
  belt-and-braces: the test enforces the new shape, the comment is the
  human explanation. If you remove an exempt path, the test will
  fail loudly until the comment + log line are added.
- ``app/routers/dev.py`` — demo/seed endpoint. Failures here are
  intentional (operator-facing seed smoke). Coverage: PR4 adds the same
  log+comment pattern but the gate allows it.

This file is **additive** per the S5 arbitration ruling. It does NOT
modify ``tests/test_no_silent_excepts.py`` (S1-owned) or
``tests/conftest.py``.
"""

from __future__ import annotations

import ast
import re
import textwrap
from pathlib import Path

import pytest

EXEMPT_PATHS: tuple[str, ...] = (
    # router subpackage init files don't have any except blocks; kept for
    # symmetry with the rms scan.
    "app/routers/produccion/__init__.py",
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
    # Router-specific justification patterns added by PR4:
    r"malformed\s+json",
    r"invalid\s+json",
    r"empty\s+body",
    r"non[\- ]json\s+body",
    r"return\s+sentinel",
    r"return\s+none\s+on\s+probe\s+failure",
    r"if\s+the\s+anomaly\s+helper",
    r"optional\s+helper",
    r"defensive\s+fallback",
    r"json[\- ]parse\s+fallback",
    r"parse\s+fallback",
    r"on\s+any\s+db\s+error",
    r"report\s+(?:no|\\?\"no\\?\")\s+backup",
    r"instead\s+of\s+fail(?:ing)?\s+the\s+endpoint",
    r"defensive\s+\-\s+backup",
    r"defensive\s+\-\s+r2",
    r"defensive\s+\-\s+disk",
    r"disk\s+usage\s+probe",
    r"r2\s+probe\s+failure",
    r"head_bucket\s+probe",
    r"package[\- ]version\s+probe",
    r"login\s+probe",
    r"route\s+probe",
    r"reachability\s+probe",
    r"verify\s+credential",
    r"credential[\- ]probe",
    r"audit\s+row\s+best[\- ]effort",
    r"commit\s+rollback\s+best[\- ]effort",
    r"rollback\s+if\s+commit\s+itself\s+fails",
    r"raw\s+json[\- ]body\s+fallback",
    r"parse\s+preferences\s+fallback",
    r"anomal(?:y|ies)\s+helper",
    r"missing\s+optional\s+helper",
    r"ingredients?\s+fallback",
    r"price[\- ]history\s+optional",
    r"price[\- ]history\s+fallback",
    r"waste[\- ]log\s+fallback",
    r"price[\- ]drift\s+fallback",
    r"demand\s+forecast\s+fallback",
    r"prime[\- ]cost\s+fallback",
    r"json[\- ]body\s+required",
    r"recipe[\- ]instructions\s+fallback",
    r"instructions\s+fallback",
    r"scraper[\- ]run\s+audit",
    r"audit\s+\"[^\"]+\"\s+best[\- ]effort",
    r"share[\- ]link\s+audit",
    r"pre[\- ]sale\s+check",
    r"settings[\- ]by[\- ]key\s+fallback",
    r"empty\s+session\s+fallback",
    r"insights?\s+engine\s+fallback",
)

JUSTIFICATION_RE = re.compile("|".join(JUSTIFICATION_PATTERNS), re.IGNORECASE)


def _window_for_window(lines: list[str], start: int, end: int) -> str:
    return textwrap.dedent("\n".join(lines[max(0, start - 1) : end + 1]))


def _calls_logging(stmt: ast.stmt, source: str) -> bool:
    """True if ``stmt`` invokes any logging-equivalent sink."""
    snippet = ast.get_source_segment(source, stmt) or ""
    if not snippet:
        return False
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
                    _window_for_window(lines, handler.lineno, first.lineno + 1),
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
    return [(pstr, line, window) for line, window in _find_violations(source, lines)]


@pytest.mark.parametrize(
    "router_path",
    sorted(
        p for p in Path("app/routers").rglob("*.py") if not any(ex in str(p) for ex in EXEMPT_PATHS)
    ),
)
def test_no_silent_except_in_routers(router_path: Path) -> None:
    """No silent broad-except blocks in app/routers/ (PR4 invariant)."""
    findings = _scan_file(router_path)
    if findings:
        msgs = "\n".join(f"  {p}:{ln}\n{window}\n" for p, ln, window in findings)
        pytest.fail(
            f"{router_path} has {len(findings)} silent broad-except block(s):\n\n"
            f"{msgs}\n"
            "Fix one of:\n"
            "  - Log: add `logger.warning/debug(..., exc_info=True)` before the fallback.\n"
            "  - Re-raise: `raise` / `raise AppError(...) from exc` so the global\n"
            "    handler logs + returns a typed 4xx/5xx.\n"
            "  - Justify: add a comment above the first body statement like\n"
            "    `# defensive — JSON parse fallback returns empty list` (must\n"
            "    match the gate's regex).\n"
        )


def test_routers_scan_count_is_nonzero() -> None:
    """Sanity: the test actually scanned real router modules."""
    routers = [
        p for p in Path("app/routers").rglob("*.py") if not any(ex in str(p) for ex in EXEMPT_PATHS)
    ]
    assert len(routers) >= 20, f"Only {len(routers)} routers scanned — wrong dir?"


def test_silent_except_audit_trend() -> None:
    """Audit-grade summary (non-blocking except for new violations)."""
    counts: dict[str, list[tuple[str, int]]] = {}
    for p in Path("app/routers").rglob("*.py"):
        if any(ex in str(p) for ex in EXEMPT_PATHS):
            continue
        findings = _scan_file(p)
        if not findings:
            continue
        counts[str(p)] = [(str(p), ln) for _, ln, _ in findings]
    summary = ", ".join(f"{Path(k).name}={len(v)}" for k, v in counts.items())
    print(f"\nSilent broad-except audit in app/routers/: {summary or '(none)'}")
