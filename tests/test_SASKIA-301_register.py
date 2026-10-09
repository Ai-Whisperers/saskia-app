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

pytestmark = [pytest.mark.smoke]

TEMPLATES = Path("/opt/data/work/saskia-app/app/templates")


def test_no_guarda_in_button_text():
    """No `<button>` element should contain the Argentine voseo `Guardá` text."""
    offenders = []
    for html in TEMPLATES.glob("*.html"):
        text = html.read_text()
        # Match <button ...>Guardá</button> patterns
        if ">Guardá<" in text or 'aria-label="Guardá' in text:
            # Allow `Guardá` only in CSS class names or non-user-facing contexts
            for line in text.split("\n"):
                if ">Guardá<" in line or 'aria-label="Guardá' in line:
                    offenders.append((html.name, line.strip()))
    assert not offenders, "Argentine voseo 'Guardá' still in button text:\n" + "\n".join(
        f"  {f}: {line}" for f, line in offenders
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
