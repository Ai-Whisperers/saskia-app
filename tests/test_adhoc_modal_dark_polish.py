"""TDD test for ad-hoc modal: dark colors + pre-fill qty (T-2026-10-06e).

Bug: the ad-hoc modal used no explicit color CSS. Native <dialog> in
Chrome renders browser-default white background, and inheriting body
{ color: var(--color-text) } (= #f3f4f6 in dark mode) produced
white-on-white: invisible title, labels, hint text.

Also: the qty input was empty by default. The operator had to look
up the demand manually and type it. The user wants default = forecast +
pending pedidos, with the option to override.

TDD: this test asserts
1. The <dialog> has an explicit background color (not browser default white).
2. The qty hint shows "rolling + pedidos" math.
3. Each <option> carries data-forecast and data-pending-pedidos attrs.
4. The JS pre-fill is wired (data-action buttons still work).
"""
from __future__ import annotations

import re
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / "app" / "templates" / "produccion.html"


def _modal_html() -> str:
    """Extract the adhoc-modal block."""
    text = TEMPLATE.read_text()
    start = text.find('<dialog id="adhoc-modal"')
    end = text.find('</dialog>', start) + len('</dialog>')
    return text[start:end]


class TestModalDarkColors:
    def test_dialog_has_explicit_background_color(self):
        modal = _modal_html()
        # Must have background: <color> that's not 'transparent' or 'white'
        bg_match = re.search(r'background:\s*([^;]+);', modal)
        assert bg_match, "modal has no background declaration"
        bg = bg_match.group(1).strip().lower()
        assert bg not in ('transparent', 'white', '#fff', '#ffffff'), (
            f"modal background must be a dark color in dark mode, got {bg!r}. "
            "White-on-white was the bug."
        )

    def test_h3_has_explicit_color(self):
        modal = _modal_html()
        h3_match = re.search(r'<h3[^>]*style="([^"]+)"[^>]*>', modal)
        assert h3_match
        style = h3_match.group(1).lower()
        # Must have a color that's not transparent/inherit
        color_match = re.search(r'color:\s*([^;]+);', style)
        assert color_match
        color = color_match.group(1).strip()
        assert color not in ('transparent', 'inherit'), (
            f"h3 color must be explicit, got {color!r}"
        )

    def test_labels_have_explicit_color(self):
        modal = _modal_html()
        labels = re.findall(r'<label[^>]*style="([^"]+)"[^>]*>', modal)
        assert len(labels) >= 3, f"expected 3+ labels, got {len(labels)}"
        for style in labels:
            assert 'color:' in style, f"label has no color: {style}"


class TestModalPrefill:
    def test_uses_ui_combo_not_native_select(self):
        """T-2026-10-06f: native <select> was replaced with <ui-combo>
        so the operator can type to filter (catalog has 30+ products
        and a select dropdown was unusable)."""
        modal = _modal_html()
        assert '<select' not in modal, (
            "modal must use <ui-combo> for type-to-filter, not <select>. "
            "User explicitly asked for a searchable dropdown."
        )
        assert '<ui-combo' in modal, "modal must include <ui-combo>"
        assert 'id="adhoc-product"' in modal, "ui-combo must keep id='adhoc-product'"

    def test_combo_carries_forecast_and_pedidos(self):
        """The src= attribute must include forecast_qty and pending_pedidos
        for each product so the JS can pre-fill the qty input."""
        modal = _modal_html()
        # The src= attribute is multi-line (Jinja for-loop), so use re.DOTALL.
        # Outer quote is `'`, content may contain `"` (JSON keys).
        m = re.search(r"src='(.*?)'", modal, re.DOTALL)
        assert m, "ui-combo must have a src= attribute with the product list"
        src = m.group(1)
        assert 'forecast_qty' in src, (
            "src= must include forecast_qty per product for qty pre-fill"
        )
        assert 'pending_pedidos' in src, (
            "src= must include pending_pedidos per product for qty pre-fill"
        )

    def test_qty_input_pre_fill_script_present(self):
        text = TEMPLATE.read_text()
        # The modal is followed by a <script> that recomputes qty on change.
        # Find the script that references both the combo and qty input.
        scripts = re.findall(r'<script[^>]*>(.*?)</script>', text, re.DOTALL)
        found = False
        for s in scripts:
            if ('adhoc-product' in s and 'adhoc-qty' in s
                and 'getSelectedData' in s
                and 'forecast_qty' in s and 'pending_pedidos' in s):
                found = True
                break
        assert found, (
            "missing pre-fill JS: must call combo.getSelectedData() and "
            "use forecast_qty + pending_pedidos to update #adhoc-qty"
        )

    def test_qty_hint_shows_math_breakdown(self):
        modal = _modal_html()
        # Hint should explain the math: rolling + pedidos
        hint_match = re.search(r'<small[^>]*id="adhoc-qty-hint"[^>]*>(.*?)</small>', modal, re.DOTALL)
        assert hint_match
        hint_text = hint_match.group(1).lower()
        assert 'rolling' in hint_text or 'forecast' in hint_text, (
            "qty hint should explain 'rolling + pedidos' so the operator knows what "
            "the pre-filled number means"
        )
        assert 'pedidos' in hint_text


class TestModalDataActionStillWorks:
    """Regression — moving the modal must NOT break the open-adhoc-modal CTA."""

    def test_open_adhoc_modal_still_wired_in_static_js(self):
        # Verify shortcuts.js still has the handler
        from pathlib import Path
        shortcuts = Path(__file__).resolve().parents[1] / "app" / "static" / "shortcuts.js"
        js = shortcuts.read_text()
        assert "open-adhoc-modal" in js, (
            "shortcuts.js must still wire data-action='open-adhoc-modal'"
        )
        assert "showModal" in js, "handler must call showModal()"

    def test_modal_id_unchanged(self):
        modal = _modal_html()
        assert 'id="adhoc-modal"' in modal, "modal id must remain 'adhoc-modal'"