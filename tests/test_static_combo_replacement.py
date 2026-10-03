"""tests/test_static_combo_replacement.py — Phase 21 banned-pattern sweep.

Verifies that the 4 remaining native <select> instances have been
replaced with <saskia-combo> wrappers (via m.static_combo or inline).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "app" / "templates"


# (filename, must-have attribute, must-NOT-have native select)
REPLACEMENTS = [
    ("bank.html",      "bank-with-type",      "with_type"),
    ("productos.html", "bulk-action-select",  "bulk_action"),
    ("riesgos.html",   "risk-category",       "category"),
    ("pedidos_nuevo.html", "customer_invoice_profile_select", "invoice_profiles"),
]


@pytest.mark.parametrize("filename,combo_id,ctx", REPLACEMENTS)
def test_template_uses_saskia_combo_not_native_select(filename, combo_id, ctx):
    """The file must contain a saskia-combo with the expected id, and
    no native <select> with the same name."""
    path = TEMPLATES_DIR / filename
    text = path.read_text()
    # Must reference the saskia-combo id — either as a literal in a
    # saskia-combo element, or as a kwarg to a combo macro.
    has_combo_id = (
        f'id="{combo_id}"' in text
        or f"id='{combo_id}'" in text
    )
    assert has_combo_id, \
        f"{filename}: missing saskia-combo with id={combo_id}"
    # Must NOT have a native <select> with that name
    native_pattern = re.compile(
        r'<select[^>]*\bname=[\'"]' + ctx + r'[\'"][^>]*>',
    )
    m = native_pattern.search(text)
    assert not m, \
        f"{filename}: still has native <select> with name={ctx}: {m.group()[:100]}"


def test_static_combo_macro_exists():
    """_components/macros.html must define static_combo macro."""
    macros = (TEMPLATES_DIR / "_components" / "macros.html").read_text()
    assert "macro static_combo" in macros, "static_combo macro missing"


def test_static_combo_macro_renders_saskia_combo():
    """static_combo macro must emit a <saskia-combo> tag."""
    macros = (TEMPLATES_DIR / "_components" / "macros.html").read_text()
    # Extract static_combo body
    m = re.search(
        r'\{%\s*macro\s+static_combo\s*\([^)]*\)\s*-?%\}(.*?)\{%-\s*endmacro\s*%\}',
        macros, re.DOTALL,
    )
    assert m, "could not extract static_combo macro body"
    body = m.group(1)
    assert "<saskia-combo" in body, "macro does not emit saskia-combo"
    assert "src=" in body, "macro does not pass src= to the combo"
    assert "name=" in body, "macro does not pass name= to the combo"
    assert "<select" not in body, "macro still emits a native <select>"


def test_bank_html_has_macros_import():
    """bank.html must import the macros module."""
    text = (TEMPLATES_DIR / "bank.html").read_text()
    assert 'import "_components/macros.html" as m' in text, \
        "bank.html: missing macros import"


def test_riesgos_html_has_macros_import():
    """riesgos.html must import the macros module."""
    text = (TEMPLATES_DIR / "riesgos.html").read_text()
    assert 'import "_components/macros.html" as m' in text, \
        "riesgos.html: missing macros import"
