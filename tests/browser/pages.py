"""tests/browser/pages.py — Page Objects. EVERY selector lives here.

When the UI evolves, update the selector string in exactly one place.
Tests never touch CSS.
"""

from __future__ import annotations


class Page:
    """Base: navigation + generic waits on top of a Playwright page."""

    def __init__(self, page):
        self.p = page
        self.base = getattr(page, "_saskia_base", "http://127.0.0.1:8000")

    def go(self, path: str):
        self.p.goto(self.base + path)
        self.p.wait_for_load_state("networkidle")
        return self

    def see(self, text: str):
        assert text.lower() in self.p.content().lower(), f"expected {text!r} on page"
        return self

    def no_js_errors(self):
        errors = getattr(self.p, "_saskia_js_errors", [])
        assert not errors, f"JS console errors: {errors[:3]}"


class LoginPage(Page):
    user = "input[name='username']"
    pw = "input[name='password']"
    submit = "button[type='submit']"
    error = ".alert, .flash, [role='alert']"

    def login(self, username: str, password: str):
        self.go("/login")
        self.p.fill(self.user, username)
        self.p.fill(self.pw, password)
        self.p.click(self.submit)
        self.p.wait_for_load_state("networkidle")
        return self


class DashboardPage(Page):
    kpi_revenue = ".kpi-card:has-text('Ingresos')"
    # 2026-09-25 shell redesign: persistent sidebar replaced the hamburger
    # dropdown. Selectors point at the sidebar nav items directly.
    menu_btn = ".sidebar"  # kept for compat; sidebar needs no opening click
    menu_panel = ".sidebar"
    margin_alert = "text=Márgenes en riesgo"

    def open_menu(self):
        # Sidebar is always visible ≥1024px — no toggle needed.
        self.p.locator(self.menu_panel).wait_for(state="visible", timeout=5000)
        return self

    def menu_goto(self, label: str):
        """Click a sidebar section by its visible label."""
        self.open_menu()
        self.p.locator(f"{self.menu_panel} a.nav-item:has-text('{label}')").first.click()
        self.p.wait_for_load_state("networkidle")
        return self.p.url

    def open_pedidos(self):
        self.menu_goto("Pedidos")
        return PedidosPage(self.p)


class PedidosPage(Page):
    row = "tbody tr"


class PosPage(Page):
    """POS / nueva venta."""
    product_combo = "[data-combo], .saskia-combo input, input[name='product_id']"
    qty = "input[name='qty']"
    submit = "button:has-text('Registrar'), button:has-text('Vender')"

    def sell(self, product_name: str, qty: int = 1):
        self.p.fill(self.qty, str(qty))
        self.p.click(self.submit)
        self.p.wait_for_load_state("networkidle")
        return self


class ComboMixin:
    """The saskia-combo custom dropdown: open, filter, pick."""

    combo_root = ".combo"
    combo_input = ".combo input, .combo [contenteditable]"
    combo_list = ".combo ul, .combo [role='listbox']"
    combo_option = ".combo li, .combo [role='option']"

    def combo_pick(self, root_selector: str, text: str):
        self.p.click(f"{root_selector} {self.combo_input or ''}".strip() or root_selector)
        self.p.wait_for_timeout(150)  # open animation
        self.p.fill(f"{root_selector} input", text)
        option = self.p.locator(
            f"{root_selector} li:has-text('{text}'), "
            f"{root_selector} [role='option']:has-text('{text}')"
        ).first
        option.wait_for(state="visible", timeout=3000)
        option.click()
        return self


class ExcelPage(Page):
    file_input = "input[type='file']"
    mode_full = "input[value='FULL']"
    import_btn = "#import-form button[type='submit']"
    validate_btn = "button:has-text('Vista previa')"
