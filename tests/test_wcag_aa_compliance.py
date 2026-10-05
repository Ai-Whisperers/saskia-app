"""
WCAG AA color contrast regression test.

Runs axe-core against key authenticated pages in BOTH light and dark themes via Puppeteer-core.
Requires Chrome at /opt/data/.local/bin/google-chrome and the local server on port 8765.

Use:  pytest tests/test_wcag_aa_compliance.py -v -s
Skip locally: pytest --deselect tests/test_wcag_aa_compliance.py

If this fails:
- Inspect /opt/data/profiles/ivan/cache/scratch/wcag-scan/wcag-results.json for specific selectors.
- Use scripts/wcag-scan.js (or `node wcag-scan.js`) for a full 31-page audit, not just this subset.
"""

import json
import subprocess
import time
from pathlib import Path

import pytest

SCAN_DIR = Path("/opt/data/profiles/ivan/cache/scratch/wcag-scan")
SCAN_SCRIPT = SCAN_DIR / "wcag-scan.js"
SERVER_URL = "http://localhost:8765"

# Authenticated paths to spot-check (highest-traffic user flows).
# Full audit covers 31 pages via wcag-scan.js; this test picks the ones a single
# human is most likely to use.
SMOKE_PATHS = [
    ("/", "Dashboard"),
    ("/pedidos", "Pedidos"),
    ("/pedidos/nuevo", "Nuevo pedido"),
    ("/productos", "Productos"),
    ("/ventas", "Ventas"),
    ("/clientes", "Clientes"),
    ("/reportes/cierre-mensual", "Cierre mensual"),
    ("/settings/catalog", "Settings catalog (tabs)"),
]


def _check_axe_json(result):
    light = result.get("light", {}).get("violations", [])
    dark = result.get("dark", {}).get("violations", [])
    if light:
        # Format top 5 failing selectors per page so a developer can find them.
        for v in light[:5]:
            yield f"LIGHT[{v.get('impact', '?')}] {v.get('help')}: " + "; ".join(
                str(n.get("target")) for n in v.get("nodes", [])[:3]
            )
    if dark:
        for v in dark[:5]:
            yield f"DARK[{v.get('impact', '?')}] {v.get('help')}: " + "; ".join(
                str(n.get("target")) for n in v.get("nodes", [])[:3]
            )


def _run_one(path, name):
    """Invoke axe.run via Puppeteer for one URL in both themes.
    Returns a dict with 'light' and 'dark' violation arrays.
    """
    if not SCAN_SCRIPT.exists():
        pytest.skip(
            f"wcag-scan.js not found at {SCAN_SCRIPT} (run scripts/build-wcag-scanner.py to create)"
        )

    # Use a per-page temp output file
    out_file = SCAN_DIR / f"_smoke_{int(time.time() * 1000)}.json"
    try:
        cp = subprocess.run(
            ["node", "wcag-smoke.js", path, str(out_file)],
            cwd=str(SCAN_DIR),
            capture_output=True,
            text=True,
            timeout=90,
        )
        if cp.returncode != 0:
            pytest.fail(
                f"Scanner exited {cp.returncode} for {path}\nSTDOUT: {cp.stdout}\nSTDERR: {cp.stderr}"
            )
        if not out_file.exists():
            pytest.fail(
                f"Scanner returned no output for {path}\nSTDOUT: {cp.stdout}\nSTDERR: {cp.stderr}"
            )
        return json.loads(out_file.read_text())
    finally:
        if out_file.exists():
            out_file.unlink()


@pytest.fixture(scope="module", autouse=True)
def ensure_server():
    """Best-effort: assume the local uvicorn is already running on port 8765.
    Skip (don't fail) if we can't reach it, since the regression test must not
    block other work when offline.
    """
    import urllib.request

    try:
        urllib.request.urlopen(SERVER_URL + "/login", timeout=2).read()
    except Exception:
        pytest.skip(
            f"Server not reachable at {SERVER_URL}. Start with: "
            "AIW_RMS_DB_PATH=/opt/data/.local/share/aiw-restaurant/rms.sqlite DEV_COMBO_SMOKE=1 "
            "uvicorn app.rms.main:app --port 8765"
        )


def test_wcag_light_theme_clean():
    """Spot-check key pages in light theme. WCAG AA color contrast only."""
    for path, name in SMOKE_PATHS:
        result = _run_one(path, name)
        msgs = list(_check_axe_json({**result, "dark": {}}))
        assert not msgs, f"WCAG light theme violations on {name} ({path}):\n" + "\n".join(msgs)


def test_wcag_dark_theme_clean():
    """Same spot-check in dark theme."""
    for path, name in SMOKE_PATHS:
        result = _run_one(path, name)
        msgs = []
        dark = result.get("dark", {}).get("violations", [])
        for v in dark:
            msgs.append(
                f"DARK[{v.get('impact', '?')}] {v.get('help')}: "
                + "; ".join(str(n.get("target")) for n in v.get("nodes", [])[:3])
            )
        assert not msgs, f"WCAG dark theme violations on {name} ({path}):\n" + "\n".join(msgs)
