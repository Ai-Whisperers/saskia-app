"""tests/test_producto_form_grid.py — Phase 21 producto form layout.

Verifies:
- The IVA% native <select> is killed (replaced with saskia-combo).
- Related fields (sale/mayorista/iva, rspa_number/rspa_expiry) are
  grouped into grid containers so the form is shorter.
- The form still has all expected fields by label.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "app" / "templates"


def test_iva_rate_no_longer_native_select():
    """producto_form.html must not have a native <select> named iva_rate."""
    text = (TEMPLATES_DIR / "producto_form.html").read_text()
    m = re.search(r'<select[^>]*\bname=[\'"]iva_rate[\'"][^>]*>', text)
    assert not m, f"still has native iva_rate select: {m.group()[:100]}"


def test_iva_rate_uses_saskia_combo():
    """iva_rate must be a saskia-combo (via m.static_combo)."""
    text = (TEMPLATES_DIR / "producto_form.html").read_text()
    # Either an inline saskia-combo or a static_combo call with id=iva_rate
    assert ('id="iva_rate"' in text or "id='iva_rate'" in text), \
        "iva_rate combo id not found"


def test_prices_grouped_in_grid_3():
    """sale_price, mayorista_price, iva_rate must live in a grid-3 container."""
    text = (TEMPLATES_DIR / "producto_form.html").read_text()
    # Find the grid-3 block
    m = re.search(
        r'<div class="grid grid-3">(.*?)</div>\s*</div>',
        text, re.DOTALL,
    )
    assert m, "no grid-3 container found around the price block"
    block = m.group(1)
    assert 'sale_price_gs' in block, "sale_price_gs missing from grid-3"
    assert 'mayorista_price_gs' in block, "mayorista_price_gs missing from grid-3"
    assert 'iva_rate' in block, "iva_rate missing from grid-3"


def test_rspa_fields_grouped_in_grid_2():
    """rspa_number + rspa_expiry should be in a grid-2 container."""
    text = (TEMPLATES_DIR / "producto_form.html").read_text()
    # Find the rspa-fields block — followed by closing of </details> deeply nested
    m = re.search(
        r'<div id="rspa-fields"[^>]*>(.*?rspa_expiry.*?)</div>\s*</div>\s*</div>',
        text, re.DOTALL,
    )
    assert m, "rspa-fields block not found"
    block = m.group(1)
    assert 'grid grid-2' in block, "rspa fields not in grid-2"
    assert 'rspa_number' in block
    assert 'rspa_expiry' in block


def test_inventario_variant_id_uses_saskia_combo():
    """inventario.html's variant_id must not be a native <select>."""
    text = (TEMPLATES_DIR / "inventario.html").read_text()
    m = re.search(r'<select[^>]*\bname=[\'"]variant_id[\'"][^>]*>', text)
    assert not m, f"still has native variant_id select: {m.group()[:100]}"
    assert 'name="variant_id"' in text, "variant_id name attribute lost"


def test_produccion_adhoc_product_uses_saskia_combo():
    """produccion.html's adhoc product must be saskia-combo, not native select."""
    text = (TEMPLATES_DIR / "produccion.html").read_text()
    m = re.search(r'<select[^>]*\bname=[\'"]product_id[\'"][[^>]*adhoc', text)
    assert not m, f"adhoc product still has native select: {m.group()[:100]}"
    assert 'id="adhoc-product"' in text, "adhoc-product id lost"
    assert 'name="product_id"' in text, "product_id name attribute lost"
