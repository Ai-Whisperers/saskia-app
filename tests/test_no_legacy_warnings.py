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
    result = subprocess.run(
        [
            "uv", "run", "pytest", "-q", "--tb=no",
            "tests/test_audit_prune.py",
            "tests/test_dependencies.py",
            "tests/test_daily_summary.py",
        ],
        capture_output=True, text=True, timeout=60,
        cwd="/opt/data/work/saskia-app",
    )
    # Should pass.
    assert result.returncode == 0, f"Test failures:\n{result.stdout[-1000:]}"
    # Should not mention warnings in the summary line.
    assert "passed in" in result.stdout, (
        f"Expected 'passed in' (zero warnings) but got:\n{result.stdout[-500:]}"
    )
    # The literal substring "warnings" should NOT appear in the summary line.
    summary = result.stdout.split("====")[-1] if "====" in result.stdout else result.stdout
    assert "warnings" not in summary, (
        f"Unexpected warnings in summary:\n{summary}"
    )
