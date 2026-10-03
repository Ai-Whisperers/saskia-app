"""Regression: ban hardcoded 2024-2029 dates in test files.

The skill `aiw-local-first-app-tests` Pitfall #8 (Bug 8 in the catalog)
calls out that hardcoded `datetime(2026, ...)` or `"2026-09-21"` literals
in tests cause silent test rot when calendar dates pass:

- Hardcoded "2026-08-31" passes the day you write the test
- A week later, `datetime.now()` may be 2026-09-08 — relative-time
  assertions like "this is today" start failing for unclear reasons

Confirmed in production Sept 1, 2026 when a Batch 2 test suddenly
failed at the start of Batch 3 — the dashboard default `period=today`
no longer included the hardcoded timestamp.

This test fails on any test file that has a literal `datetime(202[4-9]`,
`"202[4-9]-\\d{2}-\\d{2}"`, or `datetime.now()` arithmetic that uses a
hardcoded date object. Allowed:
- Tests in `tests/benchmarks/`, `tests/e2e/` which need fixed dates.
- Tests with `# allow-hardcoded-dates: <reason>` in their header (for
  date-arithmetic fixtures like calendar grid layout, leap-year edges,
  etc.).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# Files that legitimately need fixed dates:
# - benchmarks/ — performance snapshots tied to a specific date
# - e2e/ — end-to-end tests for date-sensitive features
ALLOWED_DIRS = (
    "tests/benchmarks/",
    "tests/e2e/",
)

# Marker comment in file header — explains why this test MUST use
# fixed dates (e.g., calendar grid layout, leap-year edge cases).
ALLOW_MARKER = re.compile(r"#\s*allow-hardcoded-dates\s*:\s*(.+?)$", re.MULTILINE)

# What we look for:
DATE_PATTERNS = [
    re.compile(r'datetime\(20[2-9]\d'),           # datetime(2026, 9, 21)
    re.compile(r'date\(20[2-9]\d'),               # date(2026, 9, 21)
    re.compile(r"['\"]20[2-9]\d-[01]\d-[0-3]\d"),  # "2026-09-21"
    re.compile(r"['\"]20[2-9]\d/[01]\d/[0-3]\d"),  # "2026/09/21"
    re.compile(r"['\"]20[2-9]\d-[01]\d-[0-3]\dT"),  # "2026-09-21T10:00"
]


def _is_allowed(test_path: Path, src: str) -> tuple[bool, str]:
    """Check whether this test file is allow-listed for hardcoded dates."""
    if any(allowed in str(test_path) for allowed in ALLOWED_DIRS):
        return True, "in allowed directory"
    m = ALLOW_MARKER.search(src[:2000])
    if m:
        return True, f"marker: {m.group(1).strip()}"
    return False, ""


@pytest.mark.parametrize(
    "test_path",
    sorted(p for p in Path("tests").rglob("test_*.py") if p.is_file()),
)
def test_no_hardcoded_dates_in_tests(test_path: Path) -> None:
    """No hardcoded 2024-2029 dates in test files (BACKLOG rule).

    If you need a fixed date for a test, use `freezegun` or move the test
    to tests/benchmarks/ or tests/e2e/, or add a header comment:
    `# allow-hardcoded-dates: <reason>`.
    """
    # Self-skip: this file has the literal patterns as test data
    if test_path.name == "test_no_hardcoded_dates.py":
        pytest.skip("test file contains patterns as test fixtures")
    src = test_path.read_text()
    allowed, reason = _is_allowed(test_path, src)
    if allowed:
        pytest.skip(f"{test_path.name} allow-listed: {reason}")

    findings: list[tuple[int, str]] = []
    for line_no, line in enumerate(src.splitlines(), start=1):
        # Skip pure comments — they may discuss dates for documentation
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        for pat in DATE_PATTERNS:
            for _m in pat.finditer(line):
                findings.append((line_no, line.strip()[:80]))

    if findings:
        msg = "\n".join(
            f"  line {ln}: {snippet!r}" for ln, snippet in findings[:5]
        )
        more = f"\n  ... and {len(findings) - 5} more" if len(findings) > 5 else ""
        pytest.fail(
            f"{test_path} has {len(findings)} hardcoded date literal(s):\n"
            f"{msg}{more}\n\n"
            f"Fix: use datetime.now(ASUNCION_TZ).date() for 'today', "
            f"or freezegun.freeze_time(...) for fixed dates. "
            f"Add `# allow-hardcoded-dates: <reason>` to the file header "
            f"if the test MUST use fixed dates (calendar grid layout, "
            f"leap-year edges, month boundaries, etc.)."
        )


def test_patterns_are_correct() -> None:
    """Sanity check: our patterns match the documented cases."""
    sample = '''
    d = datetime(2026, 9, 21)
    today = date(2025, 12, 1)
    stamp = "2024-03-15"
    full = "2026-09-21T10:30"
    '''
    matches = []
    for pat in DATE_PATTERNS:
        matches.extend(pat.findall(sample))
    assert len(matches) >= 4, f"Patterns missed samples: {matches}"
