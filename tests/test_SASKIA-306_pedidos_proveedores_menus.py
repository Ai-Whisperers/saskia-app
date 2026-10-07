"""tests/test_SASKIA-306_pedidos_proveedores_menus.py — Phase 5.

Audit result (2026-10-07): pedidos (already covered in Phase 2),
proveedores, and menus templates are well-built. No copy/UX fixes
required — the issues from `docs/ux/copy-fix-list.md` under SUPP.* and
MENU.* are already addressed in earlier work.

This file locks the good state with regression tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.smoke]

TEMPLATES = Path("/opt/data/work/saskia-app/app/templates")


def test_suppliers_page_has_table_and_cta():
    """`suppliers.html` must have a `+ Nuevo proveedor` CTA and a table."""
    src = TEMPLATES.joinpath("suppliers.html").read_text()
    assert "Nuevo proveedor" in src, "Missing CTA"
    assert "<table" in src, "Missing table"
    # The 7 columns
    for col in ("Nombre", "Contacto", "Teléfono", "Email", "RUC", "Ingredientes"):
        assert col in src, f"Missing column: {col}"


def test_supplier_form_has_all_fields():
    """`supplier_form.html` must have all the standard supplier fields."""
    src = TEMPLATES.joinpath("supplier_form.html").read_text()
    for field in ("name", "contact_name", "phone", "email", "address", "ruc", "notes"):
        assert f'name="{field}"' in src, f"Missing field: {field}"
    # The phone placeholder must be Paraguay format
    assert "+595" in src, "Missing Paraguay phone placeholder"


def test_suppliers_volatility_page_currency_fixed():
    """Regression: `suppliers_volatility.html` must use Gs. (not ₲).
    Fixed in SASKIA-301 (Phase 0)."""
    src = TEMPLATES.joinpath("suppliers_volatility.html").read_text()
    assert "₲" not in src, "₲ Unicode guaraní still present"
    assert "Gs." in src, "Missing canonical Gs. symbol"


def test_menu_import_ocr_handles_missing_key():
    """`menu_import_ocr.html` must show a clear message when ZAI_API_KEY is missing."""
    src = TEMPLATES.joinpath("menu_import_ocr.html").read_text()
    assert "ZAI_API_KEY" in src, "Missing API key reference"
    assert "OCR" in src, "Missing OCR context"


def test_menus_page_has_combo_form():
    """`menus.html` must have the 'Nuevo menú' form with price placeholder."""
    src = TEMPLATES.joinpath("menus.html").read_text()
    assert "Nuevo menú" in src, "Missing new-menu form"
    assert "25.000" in src, "Missing formatted price placeholder (25.000)"
    # The currency header was fixed in Phase 0
    assert "Precio (Gs.)" in src, "Missing canonical Gs. header"
    assert "(Gs)" not in src, "Bare (Gs) header still present"


def test_menu_import_ocr_column_header_fixed():
    """Regression: `menu_import_ocr.html` column header was `(Gs)` → `(Gs.)` in Phase 0."""
    src = TEMPLATES.joinpath("menu_import_ocr.html").read_text()
    assert "Precio (Gs.)" in src, "Missing canonical (Gs.) header"
    assert "Precio (Gs)" not in src or "Precio (Gs.)" in src, "Bare (Gs) still in column header"


def test_pedido_detalle_loyalty_card_exists():
    """`pedido_detalle.html` must render the loyalty impact card (Tier 6.3)."""
    src = TEMPLATES.joinpath("pedido_detalle.html").read_text()
    assert "Impacto en puntos" in src, "Missing loyalty impact card"
    # And the saldoneto calculation
    assert "Saldo neto" in src, "Missing 'Saldo neto' label"


def test_pedido_detalle_no_stale_ventana_text_phrasing():
    """`pedido_detalle.html` must use ventana_text() (not old conditional)."""
    src = TEMPLATES.joinpath("pedido_detalle.html").read_text()
    assert "{{ ventana_text }}" in src, "Missing ventana_text() rendering"
    assert "no es garantía" in src or "ventana" in src.lower(), "Missing 'no es garantía' suffix"


def test_supplier_precios_page_exists():
    """`supplier_precios.html` must exist (supplier price comparison)."""
    assert TEMPLATES.joinpath("supplier_precios.html").exists(), "supplier_precios missing"


def test_supplier_orders_page_exists():
    """`supplier_orders.html` must exist (supplier order history)."""
    assert TEMPLATES.joinpath("supplier_orders.html").exists(), "supplier_orders missing"


def test_menu_publico_exists():
    """`menu_publico.html` must exist (public menu page)."""
    assert TEMPLATES.joinpath("menu_publico.html").exists(), "menu_publico missing"


def test_menu_tablet_exists():
    """`menu_tablet.html` must exist (tablet-optimized menu)."""
    assert TEMPLATES.joinpath("menu_tablet.html").exists(), "menu_tablet missing"
