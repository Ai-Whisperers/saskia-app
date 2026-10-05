"""Tests for /produccion empty-state + shift-save feedback (P0:D.3, P0:B.5, P0:B.8, C.5, C.6).

P0:D.3 — When plan_rows_view is empty, the cook sees the existing
  empty-state-cold-start card (Tier 4-G) that offers cold-start CTAs:
  - /produccion/manana (create plan for tomorrow)
  - /ventas/nueva (register first sale)
  - quick-seed buttons (+1 producto)

P0:B.5 — On successful shift-execute (?shift_saved=N), a flash banner
  appears AND a short WebAudio chime plays (880→1320 Hz, 120 ms). Muteable
  via localStorage `saskia.audio.muted=1`. Skipped if the user has
  prefers-reduced-motion set.

P0:B.8 — Each confidence pill has a Spanish tooltip explaining why
  the number is what it is (forecast source + heuristic breakdown).

C.5 — Inline cost + margin on each /produccion row. RecipePricing's
  cost_per_unit_gs and retail_gs are surfaced as plan_rows_view
  fields and rendered as a "Costo / Margen" cell. Hidden on print.

C.6 — Allergen + difficulty micro-badges on each row. Recipe's
  difficulty (1-5) renders as ⭐ stars; recipe.allergens renders
  as a comma-separated list capped at 3 + ellipsis on hover.

Verified by hand at:
https://saskia-vps.paragu-ai.com/produccion?for_date=1900-01-01
(after `flask --app app.rms.main resetdb`).

These tests inspect the template source rather than live-rendering
because the kyrian seed always populates at least one product, so
plan_production returns a non-empty plan_rows_view even for ancient
dates. The empty-state fires only in the operator's first-day
scenario.
"""

from __future__ import annotations

from pathlib import Path

TEMPLATE = Path(__file__).parent.parent / "app" / "templates" / "produccion.html"
SRC = TEMPLATE.read_text(encoding="utf-8")


# ---------------------------------------------------------------- P0:D.3
def test_produccion_template_has_cold_start_card():
    """The empty-state-cold-start card (Tier 4-G) is wired into the page."""
    assert "empty-state-cold-start" in SRC, "Tier 4-G cold-start card must exist in produccion.html"
    assert "/produccion/manana" in SRC, (
        "Cold-start must link to /produccion/manana (create first plan)"
    )
    assert "/ventas/nueva" in SRC, "Cold-start must link to /ventas/nueva (register first sale)"
    assert "quick-seed" in SRC, "Tier 4-G quick-seed (+1 producto) buttons must exist"


def test_produccion_template_else_branch_handles_cold_start_kinds():
    """The {% else %} for plan_rows_view switches on cold_start_kind."""
    cold_start_idx = SRC.find("empty-state-cold-start")
    assert cold_start_idx > 0, "cold-start card not in template"
    window = SRC[max(0, cold_start_idx - 2000) : cold_start_idx + 4000]
    assert "cold_start_kind" in window, "cold_start_kind switch must surround the card"
    assert "no_sales" in window, "no_sales branch must exist"
    assert "no_template" in window, "no_template branch must exist"
    assert "cold_plan" in window, "cold_plan branch must exist"


# ---------------------------------------------------------------- P0:B.5
def test_produccion_template_has_shift_saved_flash_banner():
    """The `{% if shift_saved %}` flash banner exists and shows the count."""
    assert "{% if shift_saved" in SRC, (
        "P0:B.5 — `{% if shift_saved %}` flash banner block must exist"
    )
    assert "Turno guardado" in SRC, "P0:B.5 — flash banner must say 'Turno guardado'"


def test_produccion_template_has_audio_chime_script():
    """A WebAudio oscillator chime plays on shift_saved > 0."""
    m_start = SRC.find("{% if shift_saved")
    assert m_start > 0
    # Whole block until the matching {% endif %}
    block = SRC[m_start : m_start + 5000]
    assert "AudioContext" in block, "P0:B.5 — chime must use WebAudio AudioContext"
    assert "createOscillator" in block, (
        "P0:B.5 — chime must use createOscillator (no asset to ship)"
    )
    assert "saskia.audio.muted" in block, "P0:B.5 — chime must respect localStorage mute toggle"
    assert "prefers-reduced-motion" in block, (
        "P0:B.5 — chime must skip when prefers-reduced-motion is set"
    )


# ---------------------------------------------------------------- P0:B.8
def test_produccion_template_has_confidence_pill_tooltip_breakdown():
    """Each confidence pill's `title=` includes forecast source + heuristic."""
    m = SRC.find("{% set source_label = {")
    assert m > 0, "P0:B.8 — source_label map must be defined in template"
    window = SRC[m : m + 2500]
    for tier in ("conf-high", "conf-medium", "conf-low", "conf-zero"):
        assert tier in window, f"P0:B.8 — pill tier {tier} missing"
    assert window.count("{{ source_label }}") >= 3, (
        f"P0:B.8 — source_label must appear in most pill tooltips "
        f"(found {window.count('{{ source_label }}')})"
    )


# ---------------------------------------------------------------- C.5
def test_produccion_template_has_cost_margin_column():
    """C.5 — Inline 'Costo / Margen' column on /produccion rows."""
    assert "Costo / Margen" in SRC, "C.5 — column header 'Costo / Margen' must exist"
    # Must reference cost_per_unit_gs and retail_gs (the RecipePricing fields)
    assert "cost_per_unit_gs" in SRC, "C.5 — template must read r.cost_per_unit_gs to render cost"
    assert "retail_gs" in SRC, "C.5 — template must read r.retail_gs to compute margin"
    # The cost cell must be hidden on print (no-print class)
    assert 'class="num no-print" data-label="Costo / Margen"' in SRC, (
        "C.5 — cost column must be hidden on print via .no-print class"
    )


def test_produccion_template_renders_margin_percentage():
    """C.5 — Margin % is shown in a small caption below the cost line."""
    assert "% margen" in SRC, "C.5 — must show 'XX% margen' caption next to the cost"


# ---------------------------------------------------------------- C.6
def test_produccion_template_has_allergen_badge():
    """C.6 — Allergen badge on each row, capped at 3 + ellipsis."""
    assert "allergen-badge" in SRC, "C.6 — allergen badge class must exist in template"
    assert "data-allergens=" in SRC, (
        "C.6 — allergen badge must carry data-allergens for testability"
    )
    # Allergen list is split by comma and capped
    assert "split(',')" in SRC and "|length > 3" in SRC, (
        "C.6 — allergen list must be split by comma and capped at 3 + ellipsis"
    )
    # ⚠️ prefix for visibility
    assert "⚠️" in SRC, "C.6 — allergen badge must use warning emoji for visibility"


def test_produccion_template_has_difficulty_badge():
    """C.6 — Difficulty badge on each row, ⭐ stars for 1-5 scale."""
    assert "difficulty-badge" in SRC, "C.6 — difficulty badge class must exist in template"
    assert "data-difficulty=" in SRC, (
        "C.6 — difficulty badge must carry data-difficulty for testability"
    )
    # Range loop renders one ⭐ per difficulty level
    assert "for i in range(r.recipe_difficulty)" in SRC, (
        "C.6 — difficulty must render as N stars via for-loop"
    )
    assert "⭐" in SRC, "C.6 — difficulty stars must use ⭐ glyph"
    # Difficulty class is rendered via interpolation: difficulty-{{ r.recipe_difficulty }}
    assert "difficulty-{{ r.recipe_difficulty }}" in SRC, (
        "C.6 — difficulty must use interpolated class hook for color tier"
    )
