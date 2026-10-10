"""tests/test_docs_quality_gate.py — pin the docs-lint + link-check gates.

Background: the 2026-10-09 docs-quality audit (see
docs/operations/2026-10-09-docs-quality-audit.md) found 21 broken
relative links and 11,510 markdownlint findings across 328 .md files.
The fix split into two gates:

1. `scripts/check_md_links.py` (the link checker) is strict: zero
   broken links allowed. CI runs it; PR fails on any broken link.
   This test runs the checker and asserts rc=0. If you rename/move
   a file, update its references too — don't relax this test.

2. `scripts/check_docs_quality.py --check docs-quality-baseline.json`
   is the docs-lint gate. New findings fail the PR; the baseline's
   known cosmetic issues don't. This test asserts the baseline file
   exists, is valid JSON, has the expected shape, and that the
   gate reports "0 new findings" when run against it.

The baseline is regenerated via `make docs-lint-baseline` (only when
the new findings are triaged and accepted as cosmetic residue).
The CI gate runs in `.github/workflows/ci.yml`.

Both tests are fast and have no env requirements (just the scripts
and the .venv in the repo). They run as part of CI.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE = REPO_ROOT / "docs-quality-baseline.json"


def _venv_python() -> str:
    """Return absolute path to .venv/bin/python (Hermes env may not match)."""
    return str(REPO_ROOT / ".venv" / "bin" / "python")


def test_link_checker_finds_zero_broken_links():
    """Strict: 0 broken relative links/images in markdown files."""
    p = _venv_python()
    r = subprocess.run(
        [p, "scripts/check_md_links.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if r.returncode != 0:
        print("STDOUT:", r.stdout, file=sys.stderr)
        print("STDERR:", r.stderr, file=sys.stderr)
    assert r.returncode == 0, (
        f"link-check failed (rc={r.returncode}). See STDERR. "
        "Fix the broken references in the listed files, OR if the "
        "rename was intentional, update the docs to match."
    )


def test_docs_lint_baseline_exists():
    """Baseline JSON file must be present at the expected path."""
    assert BASELINE.exists(), (
        f"docs-lint baseline missing at {BASELINE}. "
        "Re-create it by running `make docs-lint-baseline` and "
        "committing the result."
    )


def test_docs_lint_baseline_is_valid_json():
    data = json.loads(BASELINE.read_text())
    assert "keys" in data, "baseline missing 'keys' array"
    assert "snapshot" in data, "baseline missing 'snapshot' count"
    assert isinstance(data["keys"], list), "baseline 'keys' must be a list"
    # Every key is a 4-tuple: (file, line, rule, message)
    for k in data["keys"][:5]:
        assert isinstance(k, list) and len(k) == 4, f"baseline key malformed: {k!r}"
        assert isinstance(k[0], str) and k[0], f"baseline file path empty: {k!r}"
        assert re.match(r"^MD\d+$", k[2]), f"baseline rule not MDxxx: {k!r}"


def test_docs_lint_gate_reports_no_new_findings():
    """Docs-lint gate must report 0 new findings vs the checked-in baseline."""
    p = _venv_python()
    r = subprocess.run(
        [p, "scripts/check_docs_quality.py", "docs/", "--check", str(BASELINE)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    out = (r.stdout or "") + (r.stderr or "")
    assert "new=0" in out, (
        f"docs-lint gate failed. Output:\n{out}\n\n"
        "If you introduced a NEW finding, fix it. If you want to accept "
        "it, regenerate the baseline (only after triaging it as cosmetic "
        "residue): `make docs-lint-baseline`."
    )
