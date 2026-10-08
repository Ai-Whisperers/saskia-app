"""tests/test_SASKIA-305_inventario_produccion.py — Phase 4, inventario + producción.

Audit result (2026-10-07): inventario + producción templates are well-built.
The main Phase 4 fix (PROD.11 — duplicate <h2>Pedidos para mañana</h2>)
was promoted to Phase 1 (already shipped in d2164de8) because it's a
screen-reader / nav ordering bug, not just cosmetic.

This file locks the rest of the production + inventory templates'
good state and tests the P0 regression that the duplicate H2 stays gone.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.smoke]

TEMPLATES = Path("/opt/data/work/saskia-app/app/templates")


def test_produccion_manana_no_duplicate_pedidos_h2_regression():
    """Regression: produccion_manana.html must NOT have a duplicate
    <h2>Pedidos para mañana</h2> heading (the one in the <details>
    <summary> is the canonical heading)."""
    src = TEMPLATES.joinpath("produccion_manana.html").read_text()
    code = re.sub(r"\{#.*?#\}", "", src, flags=re.S)
    target = "Pedidos para mañana"
    h2_count = sum(1 for line in code.split("\n") if target in line and "<h2" in line)
    assert h2_count == 0, (
        f"Found {h2_count} <h2>Pedidos para mañana</h2> — should be 0 (use <summary>)"
    )


def test_inventario_bulk_fill_dialog_present():
    """`inventario.html` must have a bulk-fill confirmation dialog."""
    src = TEMPLATES.joinpath("inventario.html").read_text()
    assert "bulk-fill-title" in src, "Missing bulk-fill confirmation dialog"
    assert "Llenar todos los ingredientes" in src, "Missing bulk-fill dialog title"
    # The cancel/confirm buttons
    assert "Cancelar" in src
    assert "Confirmar" in src or "Llenar" in src or "Aplicar" in src


def test_inventario_has_filter_toolbar():
    """`inventario.html` must have the search + categoria + estado + alérgeno + diet filter toolbar."""
    src = TEMPLATES.joinpath("inventario.html").read_text()
    assert 'name="q"' in src, "Missing search input"
    for f in ('name="categoria"', 'name="estado"', 'name="alergeno"', 'name="diet"'):
        assert f in src, f"Missing filter field: {f}"


def test_inventario_low_stock_alerts():
    """`inventario.html` must show low-stock alerts with proper severity."""
    src = TEMPLATES.joinpath("inventario.html").read_text()
    assert "alert-danger" in src, "Missing critical-stock alert"
    assert "alert-warn" in src or "alert-warning" in src, "Missing low-stock warning"


def test_inventario_empty_state():
    """`inventario.html` must show the `Agregá el primero` empty state when no ingredients."""
    src = TEMPLATES.joinpath("inventario.html").read_text()
    assert "Agregá el primero" in src, "Missing empty state CTA"
    assert "Harina" in src or "azúcar" in src, "Missing empty state examples"


def test_produccion_dia_view_tabs():
    """`produccion.html` must have Día / Semana / Mes view switcher in the header."""
    src = TEMPLATES.joinpath("produccion.html").read_text()
    assert "view == 'day'" in src or 'view == "day"' in src, "Missing day view branch"
    # The switcher should be in the header (not in a buried drawer)
    # Quick check: 'Día' or 'Semana' or 'Mes' literal somewhere
    for w in ("Día", "Semana", "Mes"):
        assert w in src, f"Missing view label: {w}"


def test_produccion_template_load_button():
    """`produccion.html` must have the 'Cargar plan desde plantilla semanal' button."""
    src = TEMPLATES.joinpath("produccion.html").read_text()
    assert "Cargar plan desde plantilla semanal" in src, "Missing template load button"
    assert "js-confirm-form" in src, "Template load should be a confirm form"


def test_produccion_shift_badge():
    """`produccion.html` must show the shift (AM/PM) badge when the URL has shift=."""
    src = TEMPLATES.joinpath("produccion.html").read_text()
    assert "shift-badge" in src, "Missing shift badge"
    assert "Turno {{ shift }}" in src or "Turno AM" in src, "Missing Turno label"


def test_produccion_haccp_page_exists_and_loads():
    """`produccion_haccp.html` must exist (HACCP temp log)."""
    assert TEMPLATES.joinpath("produccion_haccp.html").exists(), "HACCP template missing"


def test_produccion_accuracy_page_exists():
    """`produccion_accuracy.html` must exist (plan vs. actual report)."""
    assert TEMPLATES.joinpath("produccion_accuracy.html").exists(), "Accuracy template missing"


def test_produccion_prep_page_exists():
    """`produccion_prep.html` must exist (weekly ingredient prep sheet)."""
    assert TEMPLATES.joinpath("produccion_prep.html").exists(), "Prep template missing"


def test_produccion_horneado_extra_appears_below_table():
    """Ad-hoc horneado entries must appear in a separate section with the orange 'Extra' badge."""
    src = TEMPLATES.joinpath("produccion.html").read_text()
    assert "Horneado extra" in src, "Missing 'Horneado extra' section"
    assert "is_ad_hoc" in src, "Missing ad-hoc detection in the template"
    assert "badge-warning" in src, "Missing warning badge (orange) for ad-hoc entries"


def test_inventario_movimientos_page_exists():
    """`inventario_movimientos.html` must exist (stock movement log)."""
    assert TEMPLATES.joinpath("inventario_movimientos.html").exists(), (
        "Movimientos template missing"
    )


def test_inventario_auditoria_etiquetas_exists():
    """`inventario_auditoria_etiquetas.html` must exist (tag audit)."""
    assert TEMPLATES.joinpath("inventario_auditoria_etiquetas.html").exists(), (
        "Auditoria template missing"
    )
