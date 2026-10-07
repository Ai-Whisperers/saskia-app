"""tests/test_SASKIA-307_reportes_insights_dashboard.py — Phase 6.

Audit result (2026-10-07): reportes + insights + dashboard templates
are well-built. Food cost % is implemented at the global level in
dashboard.html and analisis.html (the plan's Phase 6.5 "settings
field" is moot — the value comes from `insights.food_cost` /
`food_cost_pct` at runtime, no operator-editable target needed for
the simple "≤35%" target_direction='low' framing).

Per-product food cost % is implemented in `insight_price_impact.html`
(line 35: `{{ p.food_cost_pct }}%`).

The plan's Phase 6.5 was for "target CMV per product" (a per-product
operator-editable target). That's still out of scope; the global
≤35% target is the current truth.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.smoke]

TEMPLATES = Path("/opt/data/work/saskia-app/app/templates")


def test_analisis_food_cost_semaforo_exists():
    """`analisis.html` must have the food cost semáforo (C4)."""
    src = TEMPLATES.joinpath("analisis.html").read_text()
    assert "Costo de materia prima" in src, "Missing food cost label"
    assert "Semáforo" in src, "Missing semáforo context"
    # The three branches set the color variable
    for state in ("danger", "warning", "ok"):
        assert f'semaforo_color = "{state}"' in src, f"Missing semáforo branch: {state}"
    # The interpolation var(--X) is used to color the dot
    assert "var(--{{ semaforo_color }})" in src, "Missing semáforo color binding"


def test_analisis_kpi_panorama_has_food_cost():
    """`analisis.html` Panorama strip must include the 30d food cost % KPI."""
    src = TEMPLATES.joinpath("analisis.html").read_text()
    assert "Costo de materia prima % (30d)" in src, "Missing 30d food cost KPI"


def test_analisis_stars_dogs_rising_churning_sections():
    """`analisis.html` must have the four quadrant sections."""
    src = TEMPLATES.joinpath("analisis.html").read_text()
    for s in ("Estrellas", "Para revisar", "En alza", "En baja"):
        assert s in src, f"Missing section: {s}"


def test_dashboard_food_cost_kpi():
    """`dashboard.html` must show the food cost % KPI with the ≤35% target."""
    src = TEMPLATES.joinpath("dashboard.html").read_text()
    assert "Costo de materia prima %" in src, "Missing food cost KPI on dashboard"
    assert "objetivo: 35%" in src or "objetivo: ≤35%" in src, "Missing 35% target reference"
    # And the waste %
    assert "Merma %" in src, "Missing waste % KPI"


def test_dashboard_uses_indicadores_not_kpis():
    """Regression: Phase 0 changed 'KPIs en vivo' to 'Indicadores en vivo'."""
    src = TEMPLATES.joinpath("dashboard.html").read_text()
    assert "Indicadores en vivo" in src, "Missing 'Indicadores en vivo' label"
    assert "KPIs en vivo" not in src, "Old 'KPIs en vivo' still present"


def test_dashboard_currency_symbol():
    """Regression: dashboard.html must use Gs. (not ₲) for currency columns."""
    src = TEMPLATES.joinpath("dashboard.html").read_text()
    assert "₲" not in src, "₲ Unicode guaraní still present in dashboard"
    assert "Gs." in src, "Missing canonical Gs. symbol"


def test_insight_price_impact_per_product_food_cost():
    """`insight_price_impact.html` must render per-product food_cost_pct."""
    src = TEMPLATES.joinpath("insight_price_impact.html").read_text()
    assert "food_cost_pct" in src, "Missing per-product food_cost_pct"
    assert "under_target" in src, "Missing under_target CSS class"


def test_reportes_diario_cogs_label():
    """Regression: Phase 0 changed 'COGS' to 'Costo de Mercadería Vendida'."""
    src = TEMPLATES.joinpath("reportes_diario.html").read_text()
    assert "Costo de Mercadería Vendida" in src, "Missing Spanish COGS label"
    assert ">COGS<" not in src, "English 'COGS' label still present"


def test_reportes_diario_currency():
    """Regression: reportes_diario must use Gs. for currency."""
    src = TEMPLATES.joinpath("reportes_diario.html").read_text()
    assert "₲" not in src, "₲ Unicode guaraní still in reportes_diario"
    assert "Gs." in src, "Missing canonical Gs. symbol"


def test_reportes_top_productos_revenue_label():
    """Regression: Phase 0 changed 'Revenue' to 'Ingresos'."""
    src = TEMPLATES.joinpath("reportes_top_productos.html").read_text()
    assert "Ingresos" in src, "Missing 'Ingresos' label"
    assert ">Revenue<" not in src, "English 'Revenue' label still present"


def test_reportes_mermas_cost_currency():
    """Regression: reportes_mermas_cost must use Gs. (fixed in Phase 0)."""
    src = TEMPLATES.joinpath("reportes_mermas_cost.html").read_text()
    assert "₲" not in src, "₲ Unicode guaraní still in reportes_mermas_cost"
    assert "Gs." in src, "Missing canonical Gs. symbol"


def test_reportes_libro_ventas_exists():
    """`reportes_libro_ventas.html` must exist (tax book)."""
    assert TEMPLATES.joinpath("reportes_libro_ventas.html").exists(), "libro_ventas missing"


def test_reportes_retencion_exists():
    """`reportes_retencion.html` must exist (retention report)."""
    assert TEMPLATES.joinpath("reportes_retencion.html").exists(), "retencion missing"


def test_reportes_iva_exists():
    """`reportes_iva.html` must exist (VAT report)."""
    assert TEMPLATES.joinpath("reportes_iva.html").exists(), "iva missing"


def test_insight_margenes_currency():
    """Regression: insight_margenes must use Gs. for currency columns."""
    src = TEMPLATES.joinpath("insight_margenes.html").read_text()
    assert "Gs." in src, "Missing canonical Gs. symbol"
    # The old Δ Margen Gs. was fixed
    assert "Cambio (Gs.)" in src, "Missing 'Cambio (Gs.)' column header"
    assert "Δ Margen Gs." not in src, "Old 'Δ Margen Gs.' header still present"


def test_benchmarks_currency():
    """Regression: benchmarks must use Gs. for currency."""
    src = TEMPLATES.joinpath("benchmarks.html").read_text()
    assert "Gs." in src, "Missing canonical Gs. symbol"
    assert "Δ Gs." not in src, "Old 'Δ Gs.' header still present"
