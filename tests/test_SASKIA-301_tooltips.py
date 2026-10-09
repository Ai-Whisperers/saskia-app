"""tests/test_SASKIA-301_tooltips.py — Phase 0, step 0.7.

Locks the rationale for `aria-label="Cerrar"` on close buttons.

After repo audit (2026-10-07): all 8 `aria-label="Cerrar"` buttons in the
templates have an SVG X icon as visible content (not the text "Cerrar").
The aria-label is the accessible name for screen readers — this is the
correct accessibility pattern. No fix needed; the test exists to lock
this rationale and prevent a future agent from "fixing" the wrong thing.
"""

from __future__ import annotations

import re

import pytest

pytestmark = [pytest.mark.smoke]

from tests.conftest import REPO_ROOT

TEMPLATES = REPO_ROOT / "app" / "templates"


def test_no_redundant_aria_label_cerrar_in_templates():
    """No `<button ... aria-label="Cerrar" ...>Cerrar</button>` pattern.

    The bad pattern is when the visible text AND the aria-label are both
    "Cerrar" — screen readers would announce it twice, which is the bug.
    The good pattern is `aria-label="Cerrar"` on a button with an SVG X icon
    (no visible text), which we DO allow.
    """
    offenders = []
    pattern = re.compile(
        r'<button[^>]*aria-label="Cerrar"[^>]*>\s*Cerrar\s*</button>',
        re.MULTILINE,
    )
    for html in TEMPLATES.glob("*.html"):
        text = html.read_text()
        for m in pattern.finditer(text):
            line_no = text[: m.start()].count("\n") + 1
            offenders.append((html.name, line_no, m.group(0)[:80]))
    assert not offenders, (
        "Redundant aria-label='Cerrar' (with visible text 'Cerrar') found:\n"
        + "\n".join(f"  {f}:{ln}: {line}" for f, ln, line in offenders)
    )


def test_aria_label_cerrar_inventory():
    """Inventory check: report all `aria-label="Cerrar"` buttons.

    These are the legitimate ones (close buttons with X icon).
    """
    inventory = []
    for html in TEMPLATES.glob("*.html"):
        text = html.read_text()
        for line_no, line in enumerate(text.split("\n"), 1):
            if 'aria-label="Cerrar"' in line:
                # Trim the line for readability
                inventory.append((html.name, line_no, line.strip()[:100]))
    # Document the count — if this changes, the test will fail and force a review
    # Current count: 8 (dashboard 1, produccion 1, productos 1, receta_form 1,
    # recetas 1, users 3)
    assert len(inventory) == 8, (
        f"Expected 8 'aria-label=\"Cerrar\"' buttons (icon-only X), found {len(inventory)}:\n"
        + "\n".join(f"  {f}:{ln}: {line}" for f, ln, line in inventory)
    )
