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
    "03-inventario.md",
    "04-productos.md",
    "05-recetas.md",
    "06-clientes.md",
    "07-merma.md",
    "08-produccion.md",
    "09-reportes.md",
    "10-auditoria.md",
    "11-configuracion.md",
    "12-ops.md",
    "13-reponer.md",
    "14-cierre.md",
    "15-excel.md",
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
    r = subprocess.run(
        ["python3", str(CHECK_SCRIPT)],
        cwd=REPO, capture_output=True, text=True,
    )
    assert r.returncode == 0, (
        f"check_manual_version.py failed (exit {r.returncode}).\n"
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