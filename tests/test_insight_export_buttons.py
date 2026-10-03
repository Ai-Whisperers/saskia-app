"""Phase 22 — Excel export button + insight page coverage.

Adds a reusable macro `excel_export_btn` to _components/atoms.html that
renders a download link. Tested across the 6 insight pages.
"""
from __future__ import annotations

from app.services.template_render import templates


def _render_macro(endpoint="/excel/exportar", label="Exportar Excel"):
    src = (
        '{% import "_components/atoms.html" as ui %}'
        "{{ ui.excel_export_btn(endpoint='" + endpoint + "', label='" + label + "') }}"
    )
    return templates.env.from_string(src).render()


def test_excel_export_btn_basic():
    html = _render_macro()
    assert "/excel/exportar" in html
    assert "Exportar Excel" in html
    assert "download=" in html
    assert "icon-download" in html


def test_excel_export_btn_custom_endpoint():
    html = _render_macro(endpoint="/reportes/demand.xlsx", label="Descargar demanda")
    assert "/reportes/demand.xlsx" in html
    assert "Descargar demanda" in html


def test_excel_export_btn_has_aria_label():
    """The button should have aria-label for screen readers."""
    html = _render_macro(label="Reporte de demanda")
    assert 'aria-label="Reporte de demanda"' in html


# ---------------------------------------------------------------------------
# Insight page coverage — verify each has the export button wired in
# ---------------------------------------------------------------------------


INSIGHT_PAGES = [
    "insight_demand.html",
    "insight_food_cost.html",
    "insight_freshness.html",
    "insight_afinidades.html",
    "insight_price_impact.html",
    "insight_stock.html",
]


def test_each_insight_page_has_export_button():
    for page in INSIGHT_PAGES:
        path = f"app/templates/{page}"
        with open(path) as f:
            text = f.read()
        assert "Exportar Excel" in text, f"{page} missing Exportar Excel"
        assert "excel_export_btn" in text, f"{page} missing excel_export_btn call"


def test_each_insight_page_uses_distinct_source_key():
    """Each insight should have a distinct source key for filtering exports."""
    seen_keys = set()
    for page in INSIGHT_PAGES:
        with open(f"app/templates/{page}") as f:
            text = f.read()
        # Find the key value
        import re
        m = re.search(r"key=([a-z\-]+)", text)
        if m:
            seen_keys.add(m.group(1))
    # Each page should use a distinct key
    assert len(seen_keys) == len(INSIGHT_PAGES), (
        f"Duplicate keys: {seen_keys}"
    )