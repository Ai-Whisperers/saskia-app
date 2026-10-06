"""TDD tests for the /produccion UX fixes (2026-10-06 batch).

Five small UX papercuts identified by the operator browsing
/produccion on the live deploy (deploy-20261006-172020):

  1. 'Worksheet en blanco' label is unclear — should say
     'Hoja en blanco para imprimir' or similar (it's a button
     linking to print with mode=worksheet).
  2. Empty-state card on dark theme is hard to read (light
     gradient on dark background).
  3. 'Cómo se calcula' hint text was clipped behind the HACCP
     banner in the screenshot.
  4. The empty-state callout should NOT appear when the day has
     any plan_rows_view (even if all-zero, it would still be
     confusing). Actually wait — current code DOES gate on
     plan_rows_view. Verify.
  5. The 'Guardá ejecución del turno' submit button text is
     somewhat formal; the per-row 'Cerrar turno' is good.

Tests run against the rendered HTML structure (string searches)
to pin the labels and the empty-state gating.
"""
from __future__ import annotations

from pathlib import Path


TEMPLATE = (
    Path(__file__).resolve().parents[1] / "app" / "templates" / "produccion.html"
).read_text()


class TestWorksheetEnBlancoButton:
    """Issue 1: the 'Worksheet en blanco' button should clearly
    indicate it's a print-to-paper action."""

    def test_button_has_print_icon(self):
        assert 'icon-print' in TEMPLATE
        # The Worksheet en blanco link should use the print icon
        assert 'href="/produccion/print?for_date={{ for_date }}&mode=worksheet"' in TEMPLATE

    def test_button_label_has_clearer_text(self):
        """The new label should not be the literal string 'Worksheet en blanco'
        (the English-Spanish mix was confusing). It should be one of:
          - 'Hoja en blanco para imprimir'
          - 'Imprimir hoja en blanco'
          - 'Worksheet para imprimir'
        """
        # The OLD label was 'Worksheet en blanco' alone; the NEW label
        # should include "para imprimir" or "hoja en blanco" hint.
        # Find the button block.
        idx = TEMPLATE.find('mode=worksheet')
        assert idx != -1
        # Look at next 200 chars for the button text
        snippet = TEMPLATE[idx : idx + 400]
        # Must include a hint that this prints
        assert any(
            phrase in snippet
            for phrase in ["para imprimir", "hoja en blanco", "Imprimir worksheet", "Worksheet para"]
        ), f"button text missing print hint: {snippet!r}"


class TestEmptyStateCard:
    """Issue 2: empty-state card uses muted colors on dark theme
    that make it unreadable."""

    def test_empty_state_has_visible_background(self):
        """The empty-state card must NOT use --color-surface-subtle
        (which is near-invisible on dark theme). Use --color-info-soft
        or a similar accent so the operator's eyes land on it."""
        idx = TEMPLATE.find("Sin producción planificada")
        assert idx != -1, "the empty-state label should be present"
        # Look at the surrounding div for the background color
        snippet = TEMPLATE[max(0, idx - 700) : idx]
        # The new style should be visible — soft info tint
        assert any(
            tint in snippet
            for tint in [
                "color-warning-soft",
                "color-info-soft",
                "color-accent-soft",
                "var(--color-warning",
                "var(--color-info",
            ]
        ), f"empty-state background not visible: {snippet!r}"


class TestComoSeCalculaHint:
    """Issue 3: 'Cómo se calcula' hint must render below HACCP banner,
    not clipped. The block is a footer to the plant-shift row."""

    def test_hint_text_present(self):
        assert "Cómo se calcula" in TEMPLATE
        assert "Sugerido por ventas" in TEMPLATE


class TestEmptyStateGating:
    """Issue 4: the empty-state card should ONLY show when the day is truly
    empty (no plan_rows_view)."""

    def test_empty_state_gated_by_plan_rows_view(self):
        """Find the empty-state card and verify it's inside
        `{% if not plan_rows_view %}`."""
        idx = TEMPLATE.find("Sin producción planificada")
        assert idx != -1
        # Look backwards for the most recent {% if %} — the comment block
        # before the gate is ~600 chars, so search 1500 chars back.
        before = TEMPLATE[max(0, idx - 1500) : idx]
        last_open = before.rfind("{% if")
        assert last_open != -1, "the empty-state should be inside an {% if %}"
        # last_open is relative to `before`, so to get back into TEMPLATE
        # we need to add the offset where `before` starts.
        before_start = max(0, idx - 1500)
        condition_text = TEMPLATE[before_start + last_open : before_start + last_open + 200]
        # Should mention plan_rows_view and a not-ing gate
        assert "plan_rows_view" in condition_text
        assert "not" in condition_text.lower()


class TestShiftFormSubmit:
    """Issue 5: shift-execute submit button is properly labeled."""

    def test_submit_button_has_save_icon_and_text(self):
        assert "Guardá ejecución del turno" in TEMPLATE
        # Should be inside the shift-form
        idx = TEMPLATE.find('id="shift-form"')
        end = TEMPLATE.find("</form>", idx)
        assert end != -1
        block = TEMPLATE[idx:end]
        assert "Guardá ejecución del turno" in block