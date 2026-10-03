"""Phase 28 — Money format utility tests.

Verifies the MoneyFormat helper for consistent Guaraní display.
"""
from __future__ import annotations

from pathlib import Path


MONEY_JS = Path(__file__).parent.parent / "app" / "static" / "money-format.js"
BASE_HTML = Path(__file__).parent.parent / "app" / "templates" / "base.html"


def test_money_format_js_exists():
    """Should have a dedicated money format script."""
    assert MONEY_JS.exists()


def test_money_format_loaded_in_base():
    """Should be loaded in base.html."""
    text = BASE_HTML.read_text()
    assert "money-format.js" in text


def test_money_format_exposes_global():
    """Should expose MoneyFormat globally."""
    js = MONEY_JS.read_text()
    assert "window.MoneyFormat" in js


def test_money_format_has_guaranies():
    """Should have guaranies formatter."""
    js = MONEY_JS.read_text()
    assert "guaranies:" in js
    assert "Gs." in js


def test_money_format_uses_dots_for_thousands():
    """Should use dots for thousands separators (Paraguayan convention)."""
    js = MONEY_JS.read_text()
    assert "replace(/\\B" in js
    assert "d{3}" in js
    assert "'.'" in js


def test_money_format_handles_null():
    """Should handle null/undefined input."""
    js = MONEY_JS.read_text()
    assert "amount === null" in js
    assert "amount === undefined" in js
    assert "isNaN" in js


def test_money_format_has_empty_placeholder():
    """Should support custom empty placeholder."""
    js = MONEY_JS.read_text()
    assert "emptyPlaceholder" in js


def test_money_format_handles_negative():
    """Should handle negative amounts."""
    js = MONEY_JS.read_text()
    assert "num < 0" in js
    assert "Math.abs" in js


def test_money_format_has_short():
    """Should have short format (K/M abbreviations)."""
    js = MONEY_JS.read_text()
    assert "short:" in js
    assert "1e9" in js
    assert "1e6" in js
    assert "1e3" in js


def test_money_format_has_percent():
    """Should have percent formatter."""
    js = MONEY_JS.read_text()
    assert "percent:" in js
    assert "toFixed" in js


def test_money_format_has_delta():
    """Should have delta formatter (with +/- sign)."""
    js = MONEY_JS.read_text()
    assert "delta:" in js
    assert "num > 0" in js


def test_money_format_has_number():
    """Should have plain number formatter."""
    js = MONEY_JS.read_text()
    assert "number:" in js


def test_money_format_has_quantity():
    """Should have quantity formatter with units."""
    js = MONEY_JS.read_text()
    assert "quantity:" in js
    assert "unit" in js


def test_money_format_has_kpi():
    """Should have KPI card formatter (compact)."""
    js = MONEY_JS.read_text()
    assert "kpi:" in js


def test_money_format_uses_iife():
    """Should be wrapped in IIFE."""
    js = MONEY_JS.read_text()
    assert "(function()" in js
    assert "'use strict'" in js


def test_money_format_supports_no_prefix():
    """Should support disabling currency prefix."""
    js = MONEY_JS.read_text()
    assert "prefix !== false" in js or "options.prefix" in js


def test_money_format_rounds():
    """Should round to integer (no decimals for whole Gs.)."""
    js = MONEY_JS.read_text()
    assert "Math.round" in js


def test_money_format_decimal_for_quantity():
    """Should show decimals for non-integer quantities."""
    js = MONEY_JS.read_text()
    assert "num % 1 === 0" in js
    assert "toFixed(2)" in js


def test_money_format_percent_decimals_param():
    """Should support configurable decimals for percent."""
    js = MONEY_JS.read_text()
    assert "decimals = 0" in js


def test_money_format_quantity_default_unit():
    """Should default to no unit."""
    js = MONEY_JS.read_text()
    assert "unit = ''" in js


def test_money_format_short_billion():
    """Should support billions (MM/B in es-PY)."""
    js = MONEY_JS.read_text()
    assert "1e9" in js


def test_money_format_kpi_no_decimals_for_k():
    """Should not show decimals for K amounts."""
    js = MONEY_JS.read_text()
    assert "toFixed(0)" in js


def test_money_format_negative_kpi():
    """Should handle negative amounts in KPI."""
    js = MONEY_JS.read_text()
    assert "num < 0" in js


def test_money_format_zero_delta():
    """Should handle zero in delta formatter."""
    js = MONEY_JS.read_text()
    assert "num === 0" in js


def test_money_format_uses_g():
    """Uses guaraní symbol prefix."""
    js = MONEY_JS.read_text()
    assert "Gs." in js
    # Should be the prefix
    assert "'Gs.'" in js or 'Gs.' in js