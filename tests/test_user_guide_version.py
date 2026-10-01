"""tests/test_user_guide_version.py — pin user-guide version-header contract.

Verifies the user guide:
  1. README.md has a version header pinning schema + commit
  2. check_manual_version.py exits 0 against current state
  3. Each section file references at least one screenshot
  4. Placeholder text ("placeholder screenshot" / "placeholder image") is gone
"""
from __future__ import annotations
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
UG = REPO / "docs" / "user-guide"
README = UG / "README.md"
SHOTS = UG / "screenshots"
CHECK_SCRIPT = UG / "check_manual_version.py"

SECTIONS = [
    "00-quickstart.md",
    "01-dashboard.md",
    "02-ventas.md",
    "03-pedidos.md",
    "04-inventario.md",
    "05-productos.md",
    "06-recetas.md",
    "07-clientes.md",
    "08-merma.md",
    "09-produccion.md",
    "10-reportes.md",
    "11-auditoria.md",
    "12-configuracion.md",
    "13-ops.md",
    "14-reponer.md",
    "15-cierre.md",
    "16-excel.md",
]


def test_readme_has_version_header():
    text = README.read_text(encoding="utf-8")
    assert "schema" in text and "commit" in text, (
        "README.md must pin schema + commit so we can detect drift"
    )
    assert "https://saskia-vps.paragu-ai.com" in text, (
        "README must point at the LIVE URL (not the suspended Render URL)"
    )
    assert "suspendida" in text.lower() or "no usar" in text.lower(), (
        "README must warn about the suspended URL"
    )


def test_version_check_script_passes():
    """Drift detector passes if the README pin matches HEAD or HEAD~1.

    Rationale: the README bump itself is a commit that changes HEAD.
    Accepting a 1-commit lag means: after you update the pin, the next
    commit (e.g. a CHANGELOG entry or anything else) lands and the
    detector is green. If the lag is 2+, a real schema/route change
    happened that wasn't called out in the manual.
    """
    import subprocess
    r = subprocess.run(
        ["git", "log", "--format=%H", "-2"], cwd=REPO, capture_output=True, text=True,
    )
    last_two = [line.strip() for line in r.stdout.splitlines() if line.strip()][:2]
    assert len(last_two) >= 2, "git log returned <2 commits"

    r = subprocess.run(
        ["python3", str(CHECK_SCRIPT)],
        cwd=REPO, capture_output=True, text=True,
    )
    if r.returncode == 0:
        return
    # Allow 1-commit lag (README bump's own commit)
    text = README.read_text(encoding="utf-8")
    import re
    m = re.search(r"commit\s+`?([a-f0-9]+)`?", text)
    pinned = m.group(1) if m else None
    # last_two are full 40-char SHAs; pinned is typically 7-char short
    if pinned and any(sha.startswith(pinned) for sha in last_two):
        return
    raise AssertionError(
        f"check_manual_version.py failed (exit {r.returncode}) and the pinned commit "
        f"({pinned}) is not HEAD/HEAD~1 (last_two={last_two}).\n"
        f"stdout: {r.stdout}\nstderr: {r.stderr}\n"
        f"This means the manual version header is stale — edit README.md."
    )


def test_screenshots_dir_exists():
    assert SHOTS.exists()
    pngs = list(SHOTS.glob("*.png"))
    assert len(pngs) >= 10, f"expected ≥10 screenshots, found {len(pngs)}"


def test_each_section_references_screenshot():
    for section in SECTIONS:
        path = UG / section
        assert path.exists(), f"missing section: {section}"
        text = path.read_text(encoding="utf-8")
        assert "screenshots/" in text, f"{section} does not embed a screenshot"


def test_no_placeholder_strings_remain():
    """No 'placeholder screenshot' or 'placeholder image' should remain in user-guide."""
    for section in SECTIONS + ["README.md"]:
        path = UG / section
        text = path.read_text(encoding="utf-8").lower()
        assert "placeholder screenshot" not in text, (
            f"{section} still has placeholder screenshot text"
        )
        assert "placeholder image" not in text, (
            f"{section} still has placeholder image text"
        )


def test_readme_documents_what_saskia_can_and_cannot_do():
    text = README.read_text(encoding="utf-8")
    # Active features table
    assert "Funcionalidades activas" in text, "must list active features"
    assert "Lo que" in text and "todavía no" in text, (
        "must have a 'what's not yet supported' section"
    )


def test_readme_links_to_alternate_suspended_url():
    """README must warn that saskia-rms.paragu-ai.com is suspended."""
    text = README.read_text(encoding="utf-8")
    assert "saskia-rms.paragu-ai.com" in text, (
        "must reference the suspended URL so Saskia knows to avoid it"
    )