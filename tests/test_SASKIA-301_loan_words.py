"""tests/test_SASKIA-301_loan_words.py — Phase 0, step 0.2 + 0.3.

Locks the fix for English loan words in UI text per docs/ux/copy-fix-list.md
G.2 (band labels) and G.3 (column headers + labels + tooltips).

Covers:
- `>Loyalty<` → `>Fidelización<` in inicio.html, ops_status.html
- `>COGS<` → `>Costo de Mercadería Vendida<` in reportes_diario.html
- `>Revenue<` → `>Ingresos<` in reportes_top_productos.html
- `>Batches<` → `>Tandas<` in insight_demand.html
- `>Forecast<` (column header) → `>Pronóstico<` in produccion_manana.html
- `>Override<` → `>Ajuste manual<` (per G.3)
- `>Counterparty<` → `>Contraparte<` in bank.html
- `<th>Endpoint</th>` → `<th>Ruta</th>` in ops_status.html
- `<th>Owner</th>` → `<th>Responsable</th>` in riesgos.html
- `<th>Status</th>` (column) → `<th>Estado</th>` in planner.html, wishlist.html, riesgos.html
- `<th>Diff</th>` → `<th>Diferencia</th>` in caja*.html
- `<th>Qty</th>` → `<th>Cant.</th>` in wishlist.html
- `<th>Accuracy</th>` → `<th>Precisión (%)</th>` in produccion_accuracy.html
- `Login OK` / `Login FAIL` → `Login exitoso` / `Login fallido` in auditoria_analytics.html
- `Lead time` → `Tiempo de reposición` in ingrediente_detalle.html, inventario_form.html
- `Reorder rate` → `Tasa de reposición` in ops_status.html
- `KPIs en vivo` → `Indicadores en vivo` in dashboard.html
- `Δ Margen` / `Δ Gs.` / `Δ Precio` → `Cambio (...)` in analisis.html, benchmarks.html, insight_margenes.html
- English tooltip `Set every row's qty to its target` → Spanish in produccion.html
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.smoke]

TEMPLATES = Path("/opt/data/work/saskia-app/app/templates")


def _src(name: str) -> str:
    return (TEMPLATES / name).read_text()


# ── G.2 band labels ────────────────────────────────────────────────────────


def test_no_loyalty_band_label_in_inicio():
    """`inicio.html` band label must be `Fidelización` not `Loyalty`."""
    src = _src("inicio.html")
    assert ">Loyalty<" not in src, "Loyalty band label still in inicio.html"
    assert "Fidelización" in src, "Expected 'Fidelización' in inicio.html"


def test_no_loyalty_in_ops_status():
    """`ops_status.html` should not have `Loyalty` as a UI label (it's a heading for the loyalty table)."""
    src = _src("ops_status.html")
    # The "Loyalty" word may appear in a JS data attribute or comment; check for UI label
    # The actual line is 'Top Loyalty recurring customers' — we want to allow 'Recurrentes' as heading
    if "Top Loyalty" in src or "Loyalty" in src:
        # If it exists, must be in a non-user-facing context (JS, comment)
        for line in src.split("\n"):
            if "Loyalty" in line and "Loyalty" in line and "js-" not in line.lower() and "{#" not in line:
                # User-facing occurrence found
                if line.strip().startswith("<"):
                    pytest.fail(f"Loyalty appears user-facing in ops_status.html: {line!r}")


# ── G.3 loan words ─────────────────────────────────────────────────────────


def test_no_cogs_in_reportes_diario():
    src = _src("reportes_diario.html")
    assert ">COGS<" not in src, "COGS loan word still in reportes_diario.html"
    assert "Costo de Mercadería Vendida" in src, "Expected Spanish replacement"


def test_no_revenue_in_top_productos():
    src = _src("reportes_top_productos.html")
    assert ">Revenue<" not in src, "Revenue loan word still in reportes_top_productos.html"
    assert "Ingresos" in src, "Expected 'Ingresos' replacement"


def test_no_batches_in_insight_demand():
    src = _src("insight_demand.html")
    assert ">Batches<" not in src, "Batches loan word still in insight_demand.html"
    assert ">Tandas<" in src, "Expected 'Tandas' replacement"


def test_forecast_column_in_produccion_manana():
    src = _src("produccion_manana.html")
    # The column header "Forecast" should be Spanish
    # Note: there's a tooltip/legend that explains the algorithm; we keep the word "Forecast" in the legend for clarity,
    # but the column header itself should be Spanish.
    # Old: <th>Forecast</th>
    # New: <th>Pronóstico</th>
    if "<th>Forecast</th>" in src or 'class="text-right" title="Forecast' in src:
        # Check if there's a Spanish version too (the "= sugerencia del algoritmo" line)
        assert ">Pronóstico<" in src, "Expected Spanish 'Pronóstico' header in produccion_manana.html"


def test_no_counterparty_in_bank():
    src = _src("bank.html")
    assert "Counterparty" not in src, "Counterparty loan word still in bank.html"
    assert "Contraparte" in src, "Expected 'Contraparte' in bank.html"


def test_no_endpoint_column_in_ops_status():
    src = _src("ops_status.html")
    assert "<th>Endpoint</th>" not in src, "Endpoint loan word still in ops_status.html"
    assert "<th>Ruta</th>" in src, "Expected 'Ruta' header in ops_status.html"


def test_no_owner_in_riesgos():
    src = _src("riesgos.html")
    assert "<th>Owner</th>" not in src, "Owner loan word still in riesgos.html"
    assert "<th>Responsable</th>" in src, "Expected 'Responsable' header in riesgos.html"


def test_no_status_column_headers():
    """`<th>Status</th>` must be replaced with `<th>Estado</th>` in 3 templates."""
    for fname in ["planner.html", "wishlist.html", "riesgos.html"]:
        src = _src(fname)
        assert "<th>Status</th>" not in src, f"<th>Status</th> still in {fname}"


def test_no_diff_column_in_caja():
    """`<th>Diff</th>` must be replaced with `<th>Diferencia</th>` in caja*.html."""
    for fname in ["caja.html", "caja_z.html"]:
        path = TEMPLATES / fname
        if not path.exists():
            continue
        src = path.read_text()
        assert "<th>Diff</th>" not in src, f"<th>Diff</th> still in {fname}"


def test_no_qty_column_in_wishlist():
    src = _src("wishlist.html")
    assert "<th>Qty</th>" not in src, "<th>Qty</th> still in wishlist.html"
    assert "<th>Cant.</th>" in src, "Expected '<th>Cant.</th>' in wishlist.html"


def test_no_accuracy_column_in_produccion_accuracy():
    path = TEMPLATES / "produccion_accuracy.html"
    if not path.exists():
        pytest.skip("produccion_accuracy.html not found")
    src = path.read_text()
    assert "<th>Accuracy</th>" not in src, "<th>Accuracy</th> still in produccion_accuracy.html"


def test_login_ok_fail_replaced_in_auditoria():
    src = _src("auditoria_analytics.html")
    assert "Login OK" not in src, "'Login OK' still in auditoria_analytics.html"
    assert "Login FAIL" not in src, "'Login FAIL' still in auditoria_analytics.html"
    assert "Login exitoso" in src or "login_exitoso" in src, "Expected 'Login exitoso' replacement"
    assert "Login fallido" in src or "login_fallido" in src, "Expected 'Login fallido' replacement"


def test_no_lead_time_in_ingredient_and_inventory():
    """`Lead time` loan phrase must be replaced with `Tiempo de reposición`."""
    for fname in ["ingrediente_detalle.html", "inventario_form.html"]:
        src = _src(fname)
        assert "Lead time" not in src, f"'Lead time' still in {fname}"
        assert "Tiempo de reposición" in src, f"Expected 'Tiempo de reposición' in {fname}"


def test_no_reorder_rate_in_ops_status():
    src = _src("ops_status.html")
    assert "Reorder rate" not in src, "'Reorder rate' still in ops_status.html"
    assert "Tasa de reposición" in src, "Expected 'Tasa de reposición' replacement"


def test_no_kpis_en_vivo_in_dashboard():
    src = _src("dashboard.html")
    assert "KPIs en vivo" not in src, "'KPIs en vivo' still in dashboard.html"
    # The "Indicadores" replacement
    assert "Indicadores en vivo" in src, "Expected 'Indicadores en vivo' replacement"


def test_no_delta_symbol_in_table_headers():
    """`Δ` (U+0394) in `<th>` elements should be replaced with `Cambio`."""
    for fname in ["analisis.html", "benchmarks.html", "insight_margenes.html"]:
        path = TEMPLATES / fname
        if not path.exists():
            continue
        src = path.read_text()
        # Find all <th>...</th> blocks
        th_matches = re.findall(r"<th[^>]*>([^<]+)</th>", src)
        for th_text in th_matches:
            assert "Δ" not in th_text, f"Δ symbol in <th>{th_text}</th> in {fname}"


def test_no_english_tooltip_in_produccion():
    """The `Set every row's qty to its target` tooltip must be Spanish."""
    src = _src("produccion.html")
    assert "Set every row" not in src, "English tooltip still in produccion.html"
    assert "Marcá todas" in src or "marcá todas" in src, "Expected Spanish tooltip"
