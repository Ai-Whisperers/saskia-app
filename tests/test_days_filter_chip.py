"""tests/test_days_filter_chip.py — Phase 20 native-select kill-switch.

Validates that the date-range filter pattern is implemented as a chip
row (saskia-compliant) and not as a banned native <select> in any
template that previously used one.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "app" / "templates"


# Templates that previously had a native <select> for "Últimos N días".
# Each must now use the days_filter macro and contain no <select>.
DAY_RANGE_TEMPLATES = [
    "insight_margenes.html",
    "insight_margenes_detalle.html",
    "reportes_mermas_cost.html",
    "suppliers_volatility.html",
    "auditoria_analytics.html",
]


@pytest.mark.parametrize("filename", DAY_RANGE_TEMPLATES)
def test_days_filter_template_uses_macro_and_no_select(filename):
    """Each previously-select-bearing template must:
    1. Import the macros module (as m).
    2. Use the days_filter macro.
    3. Contain zero <select> elements.
    """
    path = TEMPLATES_DIR / filename
    assert path.exists(), f"missing template: {path}"
    text = path.read_text()

    assert 'import "_components/macros.html" as m' in text, \
        f"{filename}: missing macros import"
    assert "days_filter" in text, \
        f"{filename}: not using days_filter macro"
    assert "<select" not in text, \
        f"{filename}: still contains a native <select>"


def test_days_filter_macro_exists_in_macros_module():
    """The days_filter macro must exist in _components/macros.html."""
    macros_path = TEMPLATES_DIR / "_components" / "macros.html"
    text = macros_path.read_text()
    assert re.search(r'\{%\s*macro\s+days_filter\s*\(', text), \
        "days_filter macro is not defined in macros.html"


def test_days_filter_macro_emits_chip_buttons_not_select():
    """The days_filter macro must render <button class="chip"> for each option,
    never a <select>."""
    macros_path = TEMPLATES_DIR / "_components" / "macros.html"
    text = macros_path.read_text()
    # Extract macro body
    m = re.search(
        r'\{%\s*macro\s+days_filter\s*\([^)]*\)\s*-?%\}(.*?)\{%-\s*endmacro\s*%\}',
        text, re.DOTALL,
    )
    assert m, "could not extract days_filter macro body"
    body = m.group(1)
    assert '<button' in body, "macro does not emit <button> elements"
    assert 'class="chip' in body, "macro does not use the chip class"
    assert '<select' not in body, "macro still emits a native <select>"


def test_combobox_css_has_days_filter_styles():
    """The .days-filter CSS must exist in combobox.css."""
    css_path = (
        Path(__file__).resolve().parent.parent
        / "app" / "static" / "combobox.css"
    )
    text = css_path.read_text()
    assert ".days-filter" in text, "missing .days-filter CSS rules"
    assert ".chip--active" in text, "missing .chip--active state CSS"
