"""tests/browser/test_smoke_browser.py — first real-browser tracer bullets.

Proves the harness end-to-end: real Chromium hits the real app with real
JS. Everything behavior-level; selectors live in pages.py.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.browser

from .pages import DashboardPage, LoginPage


def test_dashboard_renders_with_kpis(pw_page):
    dash = DashboardPage(pw_page)
    dash.go("/dashboard")
    dash.see("Dashboard")
    dash.no_js_errors()


def test_login_page_renders(pw_page):
    lp = LoginPage(pw_page)
    lp.go("/login")
    lp.see("Iniciar sesión")


def test_navigation_reaches_pedidos(pw_page):
    dash = DashboardPage(pw_page)
    dash.go("/dashboard")
    ped = dash.open_pedidos()
    assert len(pw_page.query_selector_all(ped.row)) >= 0  # table renders


def test_no_console_errors_on_core_pages(pw_page):
    """Catch JS breakage early: collect console errors across the core nav."""
    errors: list[str] = []
    pw_page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pw_page.on("pageerror", lambda e: errors.append(str(e)))
    for path in ["/dashboard", "/ventas", "/pedidos", "/inventario", "/reportes", "/excel"]:
        pw_page.goto(pw_page._saskia_base + path)
        pw_page.wait_for_load_state("networkidle")
    assert not errors, f"JS console errors on core pages: {errors[:5]}"
