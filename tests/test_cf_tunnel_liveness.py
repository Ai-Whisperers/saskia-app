"""tests/test_cf_tunnel_liveness.py — Phase 14 (2026-10-01).

Validates the decision matrix of scripts/cf_tunnel_liveness.py.
The script is the production cron probe for CF-Tunnel flap detection;
the matrix below is the spec. Any future change must keep these
mappings or update this test FIRST.
"""
import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "cf_tunnel_liveness.py"


def _load_module():
    """Load scripts/cf_tunnel_liveness.py as a module (not in sys.path
    by default since scripts/ isn't a package)."""
    spec = importlib.util.spec_from_file_location("cf_tunnel_liveness", SCRIPT_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise RuntimeError(f"could not load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["cf_tunnel_liveness"] = module
    spec.loader.exec_module(module)
    return module


def _patch_probes(monkeypatch, *, public_ok, dns_ok, local_ok):
    """Replace probe_public/probe_dns/probe_local with canned values."""
    mod = _load_module()
    monkeypatch.setattr(
        mod, "probe_public",
        lambda: (public_ok, "mock public"),
    )
    monkeypatch.setattr(
        mod, "probe_dns",
        lambda: (dns_ok, "mock dns"),
    )
    monkeypatch.setattr(
        mod, "probe_local",
        lambda: (local_ok, "mock local"),
    )
    return mod


def test_all_ok_exits_zero(capsys, monkeypatch):
    mod = _patch_probes(monkeypatch, public_ok=True, dns_ok=True, local_ok=True)
    rc = mod.main([])
    assert rc == 0


def test_cf_tunnel_flap_exits_one(capsys, monkeypatch):
    """Public broken + local ok = exit 1 (CF-tunnel class).

    This is the false-positive class the script is designed to catch.
    A naive operator might redeploy the app; this test pins the
    'don't redeploy' guidance by locking the exit code.
    """
    mod = _patch_probes(monkeypatch, public_ok=False, dns_ok=True, local_ok=True)
    rc = mod.main([])
    assert rc == 1, "CF-Tunnel flap must exit 1"


def test_dns_drift_exits_two(capsys, monkeypatch):
    """DNS broken = exit 2. Even if public still works (cached), this
    is a real fault — surface it."""
    mod = _patch_probes(monkeypatch, public_ok=True, dns_ok=False, local_ok=True)
    rc = mod.main([])
    assert rc == 2


def test_local_broken_exits_three(capsys, monkeypatch):
    """Local app unhealthy = exit 3 (the deploy class)."""
    mod = _patch_probes(monkeypatch, public_ok=False, dns_ok=True, local_ok=False)
    rc = mod.main([])
    assert rc == 3


def test_local_broken_outranks_dns(capsys, monkeypatch):
    """When local is broken AND dns is broken, local-broken wins
    (return 3, not 2). The deploy class is more actionable than DNS.
    """
    mod = _patch_probes(monkeypatch, public_ok=False, dns_ok=False, local_ok=False)
    rc = mod.main([])
    assert rc == 3, "local-broken must outrank DNS-bad"


def test_quiet_mode_one_line(capsys, monkeypatch):
    """--quiet output is exactly one line (cron log aggregator friendly)."""
    mod = _patch_probes(monkeypatch, public_ok=True, dns_ok=True, local_ok=True)
    rc = mod.main(["--quiet"])
    captured = capsys.readouterr()
    # Allow trailing newline (one newline after one print())
    lines = [l for l in captured.out.split("\n") if l.strip()]
    assert len(lines) == 1
    assert lines[0].startswith("cf-tunnel-liveness[")


def test_quiet_mode_marks_failure_class(capsys, monkeypatch):
    mod = _patch_probes(monkeypatch, public_ok=False, dns_ok=True, local_ok=True)
    rc = mod.main(["--quiet"])
    captured = capsys.readouterr()
    assert "[FAIL]" in captured.out
    assert "public=FAIL" in captured.out