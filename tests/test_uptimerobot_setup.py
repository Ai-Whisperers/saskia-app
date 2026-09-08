"""tests/test_uptimerobot_setup.py — verifies the ops script + documents monitoring."""
from __future__ import annotations


def test_uptimerobot_script_help_runs():
    """The setup script at scripts/uptimerobot_setup.py must run with --help."""
    import subprocess
    r = subprocess.run(
        ["uv", "run", "python", "scripts/uptimerobot_setup.py", "--help"],
        capture_output=True, text=True, timeout=30, cwd="/opt/data/profiles/ivan/scratch/saskia-app-work",
    )
    assert r.returncode == 0
    assert "UptimeRobot" in r.stdout or "monitor" in r.stdout.lower()


def test_uptimerobot_keys_in_bws():
    """UPTIMEROBOT_ACCOUNT_API_KEY + MONITOR_KEY must exist in BWS."""
    keys = set()
    with open("/opt/data/.hermes/bws-secrets-cache.tsv") as f:
        for line in f:
            parts = line.strip().split("\t", 1)
            if len(parts) == 2:
                keys.add(parts[0])
    assert "UPTIMEROBOT_ACCOUNT_API_KEY" in keys
    assert "UPTIMEROBOT_MONITOR_KEY" in keys
