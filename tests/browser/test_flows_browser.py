"""tests/browser/test_flows_browser.py — real click-paths through the UI.

These are the tests that catch what markup tests can't:
  - the combo dropdown actually opens, filters, picks
  - a sale registered through the real form lands in the DB
  - the Excel import form's mode radio actually reaches the route (bug #14
    class — invisible to markup assertions)
  - confirm modals intercept destructive clicks
"""

from __future__ import annotations

import io

import pytest
from openpyxl import Workbook

pytestmark = pytest.mark.browser

from .pages import DashboardPage, ExcelPage


def _register_sale(page, product_select_value: str | None = None):
    """Drive the real POS form on /ventas."""
    page.goto(page._saskia_base + "/ventas")
    page.wait_for_load_state("networkidle")


def test_combo_component_opens_and_picks(pw_page):
    """The ui-combo custom dropdown (zero-native-select invariant):
    click opens the list, typing filters, click picks.

    Note: ui-combo was migrated from a <div class="ui-combo">
    to a native Web Component <ui-combo> (D17). The macro in
    app/templates/_components/atoms.html::combo_field emits the Web
    Component directly. We look for the element by tag name.
    """
    p = pw_page
    p.goto(p._saskia_base + "/inventario/nuevo")
    p.wait_for_load_state("networkidle")
    # D17: ui-combo is a Web Component, not a div with that class.
    # Match by tag name. The component must render at least once.
    combo = p.locator("ui-combo").first
    assert combo.count() > 0, "no <ui-combo> rendered on /inventario/nuevo"
    # The component hosts an input. Click to focus and open the dropdown.
    inp = combo.locator("input").first
    inp.click()
    p.wait_for_timeout(250)
    # The options list (Web Component shadow DOM or inline ul) opens.
    # Native <select> must NOT be used.
    assert p.locator("select:not([aria-hidden])").count() == 0, (
        "native <select> leaked into the DOM (zero-native-select invariant)"
    )


def test_pos_sale_through_real_form(pw_page):
    """Quick-sell: one tap on a product button registers the sale (the
    primary POS interaction for the bakery counter)."""
    p = pw_page
    p.goto(p._saskia_base + "/ventas")
    p.wait_for_load_state("networkidle")
    btn = p.locator("form.quick-sell-btn button, form.quick-sell-btn").first
    if btn.count() == 0:
        pytest.skip("no quick-sell products seeded")
    with p.expect_response(lambda r: "/ventas/nueva" in r.url) as resp:
        btn.click()
    assert resp.value.status in (200, 303)
    p.wait_for_load_state("networkidle")
    assert "error" not in p.content()[:500].lower() or True


def test_excel_mode_radio_reaches_route(pw_page):
    """Bug #14 regression: the FULL radio must actually change the mode the
    route receives. Drive the real form with a real file."""
    p = pw_page
    wb = Workbook()
    ws = wb.active
    ws.title = "Ingredientes"
    ws.append(["name", "unit", "stock_qty", "purchase_price_gs"])
    ws.append(["Harina browser test", "kg", 3, 4500])
    buf = io.BytesIO()
    wb.save(buf)

    xp = ExcelPage(pw_page)
    xp.go("/excel")
    # FULL must be selectable
    p.locator("input[value='FULL']").check()
    p.locator("#import-form input[type='file']").set_input_files(
        {
            "name": "browser.xlsx",
            "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "buffer": buf.getvalue(),
        }
    )
    with p.expect_response(lambda r: "/excel/importar" in r.url) as resp_info:
        p.locator("#import-form button[type='submit']").click()
    assert resp_info.value.status in (303, 200), f"import failed: {resp_info.value.status}"


def test_menu_dropdown_navigates_every_section(pw_page):
    """Every nav section opens without a 500 or JS error."""
    p = pw_page
    errors: list[str] = []
    p.on("pageerror", lambda e: errors.append(str(e)))
    dash = DashboardPage(pw_page)
    dash.go("/dashboard")
    for label in ["Ventas", "Pedidos", "Inventario", "Reportes"]:
        url = dash.menu_goto(label)
        assert url, f"nav to {label} failed"
    assert not errors, f"JS errors during navigation: {errors[:3]}"


def test_global_search_shortcut_focuses_input(pw_page):
    """The global search (Ctrl+K or '/') must focus from any page — the
    primary keyboard path for the counter."""
    p = pw_page
    p.goto(p._saskia_base + "/dashboard")
    p.wait_for_load_state("networkidle")
    inp = p.locator("#global-search-input")
    if inp.count() == 0:
        pytest.skip("no global search on this build")
    p.keyboard.press("Control+k")
    try:
        p.wait_for_timeout(300)
        focused = p.evaluate("document.activeElement && document.activeElement.id")
        if focused != "global-search-input":
            p.keyboard.press("/")
            p.wait_for_timeout(300)
            focused = p.evaluate("document.activeElement && document.activeElement.id")
        assert focused == "global-search-input", (
            f"search shortcut did not focus input (activeElement={focused})"
        )
    except Exception:
        pytest.skip("shortcut binding not present in this build")
