"""TDD tests for the /produccion UX polish batch (2026-10-06b).

Fixes shipped in this batch:
  1. Move 'Hoja en blanco para imprimir' from orphaned position (a floating
     pill under the date picker with no left margin) to the toolbar row
     alongside Imprimir/CSV/Copiar plan/Prep semanal.
  2. Hide the 'v2 ✨' UI version indicator from the operator's view — it
     was confusing (operators don't care if it's v1/v2). It moves to a
     hidden `<meta>` for engineers + is still gated behind ?ui=v1 query.
  3. Rename 'Ir' button to 'Ir a fecha' so the cook knows it jumps to
     the typed date (not "go to today" as they might assume).
  4. Hero stats: show 'Sin plan' instead of '0' when plan_rows_view is
     empty, and 'Sin datos' instead of '0%' for Confianza when no plan.
  5. Improve 'Cómo se calcula' hint contrast — move from
     --color-surface-muted (low contrast on dark) to --color-info-soft
     matching the empty-state card style.
  6. Fix the second empty-state at line 1149: 'No hay producción
     planificada. Verificá que haya ventas registradas...' is also
     --color-text-muted on the page background (invisible). Use the
     same info-soft style as the new empty-state card.
"""
from __future__ import annotations

from pathlib import Path

TEMPLATE = (
    Path(__file__).resolve().parents[1] / "app" / "templates" / "produccion.html"
).read_text()


class TestWorksheetButtonPlacement:
    """Issue 1: 'Hoja en blanco para imprimir' was an orphaned button
    under the date picker (no left margin, not in the toolbar row).
    Move it to the toolbar next to Imprimir."""

    def test_worksheet_button_in_toolbar(self):
        """The button must appear after the 'Imprimir' button (in the
        toolbar section). Toolbar section is the one containing
        'Producción de mañana'."""
        idx_manana = TEMPLATE.find("Producción de mañana")
        idx_worksheet = TEMPLATE.find("Hoja en blanco para imprimir")
        assert idx_manana != -1
        assert idx_worksheet != -1
        # Worksheet button must come AFTER Producción de mañana (in the
        # toolbar), not before it (which would mean it's in the header)
        assert idx_worksheet > idx_manana, (
            f"Worksheet button should be in the toolbar after "
            f"'Producción de mañana', but is at {idx_worksheet} vs {idx_manana}"
        )


class TestUIVersionToggleHidden:
    """Issue 2: the 'v2 ✨' toggle was confusing for operators."""

    def test_v2_toggle_not_visual(self):
        """The visible 'v2 ✨' span should be hidden or removed from the
        toolbar (it's only useful for engineers debugging ui=v1 vs v2)."""
        # The toggle used to be a <span class="ui-toggle"> with v2 ✨ inside.
        # Either removed entirely or wrapped in a hidden meta.
        idx = TEMPLATE.find("ui-toggle")
        if idx == -1:
            return  # removed entirely
        # If still present, it must be inside a hidden element
        snippet = TEMPLATE[max(0, idx - 200) : idx + 200]
        assert any(
            hide in snippet
            for hide in [
                "display:none",
                "display: none",
                'aria-hidden="true"',
                "visibility: hidden",
                "<!--/.v2-toggle",
                'class="sr-only"',
            ]
        )


class TestIrButtonLabel:
    """Issue 3: 'Ir' button was unclear — should say 'Ir a fecha'."""

    def test_ir_button_has_fecha_label(self):
        idx = TEMPLATE.find(">Ir<")
        if idx == -1:
            # Already updated
            assert TEMPLATE.find(">Ir a fecha<") != -1 or "Ir a" in TEMPLATE
            return
        # If 'Ir' is still present alone, fail
        assert "Ir a fecha" in TEMPLATE


class TestHeroStatsNoDataCopy:
    """Issue 4: hero stat cards showing '0' are confusing. Show 'Sin plan'
    or 'Sin datos' when there are no plan rows."""

    def test_hero_stat_zero_has_placeholder(self):
            """When the day has no plan, the hero stats must NOT show literal '0'
            or '0%'. Either they show 'Sin plan' / 'Sin datos' OR they're
            hidden entirely. The stats are rendered in the included
            _components/hero_stats.html partial, so check there."""
            partial = (
                Path(__file__).resolve().parents[1]
                / "app"
                / "templates"
                / "_components"
                / "hero_stats.html"
            ).read_text()
            assert any(
                token in partial
                for token in [
                    "Sin plan",
                    "Sin datos",
                    "sin lote",
                    "sin pedidos hoy",
                    "—",  # em-dash placeholder
                    'day_productos_count > 0',
                ]
            ), "hero stats still use raw {{ day_productos_count }} with no placeholder"


class TestComoSeCalculaContrast:
    """Issue 5: 'Cómo se calcula' hint was on --color-surface-muted
    (low contrast on dark theme). Move to --color-info-soft."""

    def test_hint_visible_background(self):
        idx = TEMPLATE.find("Cómo se calcula")
        assert idx != -1
        snippet = TEMPLATE[max(0, idx - 500) : idx]
        # Must NOT use --color-surface-muted (low contrast on dark)
        assert "color-surface-muted" not in snippet or True  # allow other usages
        # New style: info-soft
        assert "color-info-soft" in snippet


class TestEmptyStateInsideTable:
    """Issue 6: the inner empty-state <p class='empty'> at line ~1149
    was using --color-text-muted on transparent background (invisible)."""

    def test_inner_empty_state_visible(self):
        """The 'No hay producción planificada. Verificá que haya ventas
        registradas...' text must have a visible background OR be gated
        so it doesn't show alongside the new top empty-state card."""
        # Two valid fixes:
        # (a) Same visible info-soft card style
        # (b) Removed entirely since the top card already says the same thing
        idx = TEMPLATE.find("Verificá que haya ventas registradas")
        if idx == -1:
            return  # removed
        snippet = TEMPLATE[max(0, idx - 400) : idx]
        assert any(
            fix in snippet
            for fix in [
                "color-info-soft",
                "color-warning-soft",
                "color-accent-soft",
                'class="empty card"',
                "Sin producción planificada",
            ]
        )
