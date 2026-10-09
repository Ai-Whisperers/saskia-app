"""tests/test_SASKIA-301_severity.py — Phase 0, step 0.5.

Locks the fix for the severity pill naming.
Canonical set: Crítico (red) / Aviso (yellow) / OK (green).
Old code used `saludable` (English loan, lowercase) for the green tier.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT

pytestmark = [pytest.mark.smoke]

TEMPLATES = Path(REPO_ROOT / "app" / "templates")


def test_no_saludable_class_in_inicio():
    """The `sev-pill saludable` class must be replaced with `sev-pill ok` in inicio.html."""
    src = (TEMPLATES / "inicio.html").read_text()
    assert "sev-pill saludable" not in src, "'sev-pill saludable' still in inicio.html"
    assert "sev-pill ok" in src, "Expected 'sev-pill ok' replacement in inicio.html"


def test_no_saludable_user_facing_text():
    """The word `saludable` should not appear as user-facing text in inicio.html.

    Note: `reportes_cierre_mensual.html` has "Margen saludable: > 30%" — that's
    prose, not a pill, and is OK. We only check inicio.html (the forecast
    confidence pill).
    """
    src = (TEMPLATES / "inicio.html").read_text()
    assert "saludable" not in src, "Loan word 'saludable' still in inicio.html"
