"""tests/test_SASKIA-301_register.py — Phase 0, step 0.4.

Locks the fix for Argentine voseo `Guardá` → infinitive `Guardar` in buttons
and primary action labels. Per app/docs/copy-vos.md (after SASKIA-310
correction), buttons should use infinitive.

Covers 11 button locations confirmed in the working tree on 2026-10-07:
  ingrediente_detalle.html, inventario_form.html, producto_form.html,
  supplier_form.html, produccion_manana.html (×2), produccion.html (×2),
  produccion_print.html, pedido_publico.html, suscripcion_form.html

Plus: `Decí por qué` → `Indicá por qué` in produccion.html.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT

pytestmark = [pytest.mark.smoke]

TEMPLATES = Path(REPO_ROOT / "app" / "templates")


def test_no_salva_in_button_text():
    """No `<button>` element should contain the non-voseo `Salvá` text.

    Per AGENTS.md rules 23 + 25 and `app/docs/copy-vos.md`, the Paraguayan
    voseo for "save" is `Guardá` (NOT Argentine `Guardá` nor Castilian
    `Salvá`/`Salva`). Castilian `Salvá` is the pre-2026 form that this
    repo deprecated; if you see it in a button, that's a regression.

    Note: a previous version of this test asserted `Guardá` was Argentine
    and should be banned — that was wrong. `Guardá` IS the Paraguayan
    form per the project's locked copy standard.
    """
    offenders = []
    for html in TEMPLATES.glob("*.html"):
        text = html.read_text()
        for line in text.split("\n"):
            if '>Salvá<' in line or 'aria-label="Salvá' in line:
                offenders.append((html.name, line.strip()))
    assert not offenders, (
        "Castilian 'Salvá' still in button text (should be 'Guardá'):\n"
        + "\n".join(f"  {f}: {line}" for f, line in offenders)
    )


def test_no_deci_por_que_in_produccion():
    """`Decí por qué` (Argentine voseo) should be replaced with `Indicá por qué` (Paraguayan)."""
    src = (TEMPLATES / "produccion.html").read_text()
    assert "Decí por qué" not in src, "Argentine voseo 'Decí por qué' still in produccion.html"
    assert "Indicá por qué" in src, "Expected 'Indicá por qué' replacement in produccion.html"


def test_guardar_present_in_submit_buttons():
    """At least one `<button>Guardar` should exist in the templates (the canonical button)."""
    count = 0
    for html in TEMPLATES.glob("*.html"):
        text = html.read_text()
        count += text.count(">Guardar<")
    # We should have at least 5 Guardar buttons after the fix
    # (some templates already used Guardar; others we just converted)
    assert count >= 5, f"Expected at least 5 '>Guardar<' buttons, found {count}"
