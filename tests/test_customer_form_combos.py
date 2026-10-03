"""tests/test_customer_form_combos.py — Phase 21 customer/subscription form combos.

Verifies the 10 customer-form native <select>s have been replaced
with <saskia-combo> (via m.static_combo or inline).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "app" / "templates"


# (filename, expected combo_ids, no-more-allowed select names)
CASES = [
    ("cliente_editar.html",
     ["how_found", "preferred_channel", "phone-kind", "addr-zone"],
     ["how_found", "preferred_channel"]),
    ("clientes_nuevo.html",
     ["how_found", "preferred_channel"],
     ["how_found", "preferred_channel"]),
    ("suscripcion_form.html",
     ["customer_id", "cadence", "status", "preferred_day_of_week"],
     ["customer_id", "cadence", "status", "preferred_day_of_week"]),
]


@pytest.mark.parametrize("filename,combo_ids,native_names", CASES)
def test_no_native_selects_with_target_names(filename, combo_ids, native_names):
    """The file must not contain a <select> with any of the target names."""
    path = TEMPLATES_DIR / filename
    text = path.read_text()
    for name in native_names:
        m = re.search(
            r'<select[^>]*\bname=[\'"]' + re.escape(name) + r'[\'"][^>]*>',
            text,
        )
        assert not m, \
            f"{filename}: still has <select name={name}>: {m.group()[:100]}"


@pytest.mark.parametrize("filename,combo_ids,native_names", CASES)
def test_all_expected_combo_ids_present(filename, combo_ids, native_names):
    """Each expected combo id must appear (via saskia-combo or macro)."""
    path = TEMPLATES_DIR / filename
    text = path.read_text()
    for cid in combo_ids:
        assert f'id="{cid}"' in text or f"id='{cid}'" in text, \
            f"{filename}: missing saskia-combo with id={cid}"


def test_suscripcion_form_imports_macros():
    """suscripcion_form.html must import the macros module."""
    text = (TEMPLATES_DIR / "suscripcion_form.html").read_text()
    assert 'import "_components/macros.html" as m' in text, \
        "suscripcion_form.html: missing macros import"
