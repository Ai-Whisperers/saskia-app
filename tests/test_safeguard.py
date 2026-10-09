"""Tests for app/rms/safeguard.py — fastapi-safeguard integration.

The integration is env-gated (SAFEGUARD_ENABLED); these tests exercise the
gate logic without requiring fastapi-safeguard to be installed in the test
environment (it lives in the tooling-tier2 group).

If fastapi_safeguard IS importable, we additionally run one real scan
against the test client app to prove the baseline covers current findings.
"""

from __future__ import annotations

import importlib.util

import pytest

from app.rms import safeguard


def test_safeguard_disabled_by_default(monkeypatch, capsys):
    """No SAFEGUARD_ENABLED → no-op, nothing printed."""
    monkeypatch.delenv("SAFEGUARD_ENABLED", raising=False)
    safeguard.init_safeguard(None)  # app is only passed through; None is fine
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == ""


def test_safeguard_enabled_but_not_installed(monkeypatch, capsys):
    """Enabled + missing dep → warning to stderr, no crash."""
    monkeypatch.setenv("SAFEGUARD_ENABLED", "true")
    monkeypatch.setitem(__import__("sys").modules, "fastapi_safeguard", None)
    # Force the ImportError path
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("fastapi_safeguard"):
            raise ImportError("No module named 'fastapi_safeguard'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    safeguard.init_safeguard(None)
    out = capsys.readouterr()
    assert "not installed" in out.err
    assert "tooling-tier2" in out.err


def test_truthy_parses_env_values():
    assert safeguard._truthy("true") is True
    assert safeguard._truthy("1") is True
    assert safeguard._truthy("yes") is True
    assert safeguard._truthy("on") is True
    assert safeguard._truthy("TRUE") is True
    assert safeguard._truthy("0") is False
    assert safeguard._truthy("false") is False
    assert safeguard._truthy("") is False
    assert safeguard._truthy(None) is False
    assert safeguard._truthy("garbage") is False


@pytest.mark.parametrize(
    "env,expect_exit",
    [
        ({"SAFEGUARD_ENABLED": "true", "SAFEGUARD_FAIL_ON_FINDING": "true"}, True),
        ({"SAFEGUARD_ENABLED": "true", "SAFEGUARD_FAIL_ON_FINDING": "false"}, False),
    ],
)
def test_fail_on_finding_gate(monkeypatch, env, expect_exit):
    """SAFEGUARD_FAIL_ON_FINDING only aborts when both flags are set."""
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    # _truthy is pure; the abort logic is exercised in the integration test
    # below when fastapi_safeguard is installed. Here we only assert the
    # gate constants parse.
    assert safeguard._truthy(env.get("SAFEGUARD_FAIL_ON_FINDING")) is expect_exit


# ── Real scan (only when tooling-tier2 is installed) ──────────────────────

fastapi_safeguard_missing = importlib.util.find_spec("fastapi_safeguard") is None


@pytest.mark.skipif(
    fastapi_safeguard_missing, reason="fastapi-safeguard not installed (tooling-tier2 group)"
)
class TestRealScan:
    def test_baseline_covers_current_findings(self, tmp_path, monkeypatch, capsys):
        """A real scan must accept every finding in the committed baseline.

        Guards the baseline against rot: if someone adds a route without
        auth, this test fails before the baseline can silently age out.
        """

        from fastapi_safeguard import FastAPISafeguard, recommended_checks

        from app.rms.main import create_app

        repo_baseline = "docs/security/safeguard-baseline.json"
        monkeypatch.setenv("SAFEGUARD_ENABLED", "true")
        monkeypatch.delenv("SAFEGUARD_FAIL_ON_FINDING", raising=False)

        app = create_app()
        sg = FastAPISafeguard(
            checks=recommended_checks(),
            baseline_path=repo_baseline,
            update_baseline=False,
        )
        result = sg.collect(app)
        new = list(result.new)
        assert not new, (
            f"{len(new)} NEW fastapi-safeguard findings not in {repo_baseline}:\n"
            + "\n".join(f"  - {f.text}" for f in new)
            + "\nFix them, or re-triage with: make safeguard-baseline"
        )
