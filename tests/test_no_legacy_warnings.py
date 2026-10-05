"""tests/test_no_legacy_warnings.py — verifies the suite runs warning-free.

Pre-fix: 860 warnings (1,112 unclosed sqlite + 25 DeprecationWarning +
amplified counters). After the conftest fixture + filterwarnings in
pyproject.toml + utcnow replacements: 0 warnings.

This test asserts that a clean run reports zero warnings.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.manual


def test_clean_run_reports_zero_warnings():
    """Running a few representative tests should emit zero warnings."""
    import subprocess
    from pathlib import Path

    # T-2026-10-04: was hardcoded to /opt/data/work/saskia-app (a
    # sibling worktree). Follow the current worktree so subprocess
    # can find the right tests/ and pyproject.toml.
    project_root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [
            "uv",
            "run",
            "pytest",
            "-q",
            "--tb=no",
            # T-2026-10-04: --no-cov to bypass the project's 35% coverage
            # floor. The 3 selected tests don't cover 35% on their own
            # (they exercise audit_prune + dependencies + daily_summary
            # modules which is a small slice of the codebase). The
            # "legacy warnings" check is what we care about, not coverage.
            "--no-cov",
            "tests/test_audit_prune.py",
            "tests/test_dependencies.py",
            "tests/test_daily_summary.py",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(project_root),
    )
    # Should pass.
    assert result.returncode == 0, f"Test failures:\n{result.stdout[-1000:]}"
    # Should not mention warnings in the summary line.
    assert "passed in" in result.stdout, (
        f"Expected 'passed in' (zero warnings) but got:\n{result.stdout[-500:]}"
    )
    # The literal substring "warnings" should NOT appear in the summary line.
    summary = result.stdout.split("====")[-1] if "====" in result.stdout else result.stdout
    assert "warnings" not in summary, f"Unexpected warnings in summary:\n{summary}"
