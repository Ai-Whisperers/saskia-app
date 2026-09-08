"""tests/test_uptimerobot_setup_extended.py — verifies the script works.

Touches network only when invoked manually against BWS-fetched key.
--dry-run prints intent without API calls.
"""
from __future__ import annotations


def test_setup_dry_run():
    """--dry-run must not hit the network."""
    import subprocess
    r = subprocess.run(
        ["uv", "run", "python", "scripts/uptimerobot_setup.py", "--dry-run"],
        capture_output=True, text=True, timeout=60,
        cwd="/opt/data/profiles/ivan/scratch/saskia-app-work",
    )
    assert r.returncode == 0, f"stderr={r.stderr}"
    out = r.stdout.lower()
    assert "dry run" in out
    # All three monitor URLs must be listed.
    for url in ("/healthz", "/healthz/db", "/healthz/schema"):
        assert url in out, f"URL {url} missing from dry-run output"


def test_default_monitors_contain_required_endpoints():
    """Script must declare all 3 production endpoints."""
    sys_path = "/opt/data/profiles/ivan/scratch/saskia-app-work/scripts/uptimerobot_setup.py"
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location("uptime_setup", sys_path)
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)

    urls = [url for url, _ in mod.DEFAULT_MONITORS]
    assert any("/healthz" == url or url.endswith("/healthz") for url in urls)
    assert any(url.endswith("/healthz/db") for url in urls)
    assert any(url.endswith("/healthz/schema") for url in urls)
