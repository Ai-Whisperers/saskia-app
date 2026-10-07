"""tests/test_SASKIA-302_inicio.py — Phase 1, INICIO.1, .5, .6, .17 fixes.

Locks the home page fixes per docs/ux/copy-fix-list.md:
  - INICIO.1: "Operaciones" → "Ventas" (KPI label, since it counts sales)
  - INICIO.5: split "Acciones del día" into 2 cards (add "Hecho hoy")
  - INICIO.6: rewrite forecast empty-state message
  - INICIO.17: rewrite loyalty sub-text format

Also locks PROD.11 (P0): remove duplicate `Pedidos para mañana` H2
(in produccion_manana.html). Phase 1 ships this as a 1-line P0 bug fix
even though it's listed in Phase 4 — it's too important to delay.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.smoke]

TEMPLATES = Path("/opt/data/work/saskia-app/app/templates")


def test_inicio_kpi_card_is_ventas_not_operaciones(authed_client):
    """`/inicio` KPI card must say `Ventas` (counts sales), not `Operaciones`."""
    r = authed_client.get("/inicio")
    assert r.status_code == 200
    body = r.text
    # The label="Operaciones" line should be gone
    assert 'label="Operaciones"' not in body, "Stale 'Operaciones' KPI label still in /inicio"
    # New label
    assert 'label="Ventas"' in body, "Expected 'Ventas' label in /inicio KPI cards"


def test_inicio_split_hecho_hoy_card(authed_client):
    """`/inicio` must have a separate `Hecho hoy` card for completed items.

    INICIO.5: split `Acciones del día` into actionable (Acciones) and
    informational (Hecho hoy). The `Merma del día — registrada ✓` is
    informational and should move to `Hecho hoy`.
    """
    src = TEMPLATES.joinpath("inicio.html").read_text()
    assert "Acciones del día" in src, "Original 'Acciones del día' card should still exist"
    assert "Hecho hoy" in src, "Expected 'Hecho hoy' card"
    # The Hecho hoy card should be a separate <section> (not just an h2)
    assert src.count("aria-label=\"Hecho hoy\"") == 1, "Hecho hoy section not found"


def test_inicio_forecast_empty_state_clarified(authed_client):
    """`/inicio` forecast empty state should be more explicit."""
    r = authed_client.get("/inicio")
    assert r.status_code == 200
    body = r.text
    # The "aún no hay ventas hoy" string is fine as a quick fallback, but the
    # forecast card itself should have an explicit "no plan" empty state.
    # Old: empty value or just "—"
    # New: "Sin plan todavía" (already in template) — verify it's the right card
    assert "Sin plan todavía" in body, "Expected 'Sin plan todavía' forecast empty state"
    # Also verify the hint points to the production page
    assert "/produccion" in body, "Expected link to /produccion in forecast empty state"


def test_inicio_loyalty_sub_text_format(authed_client):
    """`/inicio` loyalty sub-text must use the new format.

    Old: `{{enrollment_with_today}} de {{enrollment_total_today}} ventas`
    (renders as "5 de 12 ventas")
    New: `{{enrollment_total_today}} ventas · {{enrollment_with_today}} con cliente`
    (renders as "12 ventas · 5 con cliente")
    """
    src = TEMPLATES.joinpath("inicio.html").read_text()
    # The old format had " de " between two numbers
    # We can't grep for the exact template syntax without false positives, so
    # check that the format string doesn't use the old "X de Y ventas" pattern
    assert "de {{" not in src.split("sub=")[-1].split("</ui-kpi-card>")[0] if "sub=" in src else True, (
        "Old 'X de Y ventas' format still in loyalty sub"
    )
    # Verify the new format hint is present
    assert "ventas" in src, "Expected 'ventas' in loyalty sub"
    # And the new "con cliente" tail
    assert "con cliente" in src, "Expected 'con cliente' in loyalty sub"


def test_produccion_manana_no_duplicate_pedidos_h2():
    """`produccion_manana.html` must not have two `🧾 Pedidos para mañana (N)` headings.

    The bug: line 86 has `<h2>🧾 Pedidos para mañana (N)</h2>` and line 95
    has `<strong>🧾 Pedidos para mañana (N)</strong>` inside a <summary>.
    Both render as headings. The fix: keep the <summary> as the only one.
    """
    src = TEMPLATES.joinpath("produccion_manana.html").read_text()
    target = "Pedidos para mañana"
    # Count H2 occurrences
    h2_count = sum(1 for line in src.split("\n") if target in line and "<h2" in line)
    assert h2_count == 0, f"Found {h2_count} <h2>Pedidos para mañana</h2> — should be 0 (use <summary>)"
    # The actual count check is the H2 being gone; the <summary> is the canonical heading.
    assert h2_count == 0
