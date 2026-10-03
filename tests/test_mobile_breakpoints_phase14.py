"""tests/test_mobile_breakpoints_phase14.py — Phase 14 (2026-10-01).

Smoke test: the Phase 14 mobile breakpoint rules made it into the
served CSS bundle. Catches the regression class where someone
restructures the stylesheet and silently drops the @media block.
"""


def test_mobile_grid_2_col_rule_in_app_css():
    """The .grid-2-col single-column rule is in app-improvements.css."""
    css = open("app/static/app-improvements.css", encoding="utf-8").read()
    assert ".grid-2-col" in css
    assert ".grid-2-col { grid-template-columns: 1fr !important; }" in css


def test_mobile_kds_kanban_single_column_rule():
    """The KDS kanban grid collapses to 1 column on phones."""
    css = open("app/static/app-improvements.css", encoding="utf-8").read()
    assert ".kds-kanban" in css
    assert ".kds-kanban { grid-template-columns: 1fr !important; }" in css


def test_pedidos_nuevo_uses_grid_2_col_class():
    """Both inline 1fr-1fr grids in pedidos_nuevo.html carry the
    .grid-2-col class so the mobile rule can collapse them."""
    html = open("app/templates/pedidos_nuevo.html", encoding="utf-8").read()
    # Two occurrences expected: ventana-window-fields + invoice_ruc/razon row
    assert html.count('class="grid-2-col"') >= 2, (
        "pedidos_nuevo.html should have at least 2 .grid-2-col wrappers"
    )
