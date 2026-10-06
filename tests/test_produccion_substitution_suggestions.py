"""Tests for /produccion C.4 — model-based recipe-substitution suggestions.

When the plan is short on an ingredient, the cook can either:
- Order more (the existing /reorder CTA), or
- Bake a different product whose recipe doesn't need the short ingredient.

C.4 surfaces option (2) using the existing product_similarity module:
for every ingredient with stock_on_hand < qty_required, we find
products whose recipe doesn't include it, filtered by Jaccard
similarity ≥ 0.3 to the original product (so the substitute tastes
similar).

The UI renders a collapsible "Sustitutos sugeridos" block under the
existing low-stock alert. Each suggestion has up to 3 ranked
substitutes, each with the Jaccard similarity as a percentage.
"""

from __future__ import annotations

from pathlib import Path

TEMPLATE = Path(__file__).parent.parent / "app" / "templates" / "produccion.html"
# Sazon-Improvement v2 (2026-10-06) Phase E: _build_substitution_suggestions
# now lives in app/routers/produccion/analytics.py, but the call from
# the worksheet handler is in _full.py. We read BOTH so the test finds
# the function AND its caller.
ROUTER = Path(__file__).parent.parent / "app" / "routers" / "produccion" / "analytics.py"
ROUTER_CALLERS = Path(__file__).parent.parent / "app" / "routers" / "produccion" / "_full.py"

TEMPLATE_SRC = TEMPLATE.read_text(encoding="utf-8")
ROUTER_SRC = ROUTER.read_text(encoding="utf-8") + ROUTER_CALLERS.read_text(encoding="utf-8")


# ────────────────────── router helper (C.4) ──────────────────────


def test_router_has_substitution_helper():
    """C.4 — The router must define _build_substitution_suggestions."""
    assert "_build_substitution_suggestions" in ROUTER_SRC, (
        "C.4 — _build_substitution_suggestions must be defined"
    )


def test_router_substitution_helper_imports_product_similarity():
    """C.4 — Uses the model-based product_similarity module (not LLM)."""
    # Find the helper body
    idx = ROUTER_SRC.find("def _build_substitution_suggestions")
    assert idx > 0
    block = ROUTER_SRC[idx : idx + 4000]
    assert "product_similarity" in block, "C.4 — helper must import from app.rms.product_similarity"
    assert "jaccard_similarity" in block, "C.4 — helper must use jaccard_similarity for ranking"
    assert "product_ingredient_set" in block, (
        "C.4 — helper must use product_ingredient_set to diff recipes"
    )


def test_router_substitution_helper_skips_low_similarity():
    """C.4 — Cutoff at Jaccard < 0.3 to keep suggestions taste-relevant."""
    idx = ROUTER_SRC.find("def _build_substitution_suggestions")
    assert idx > 0
    block = ROUTER_SRC[idx : idx + 5000]
    assert "sim < 0.3" in block or "similarity < 0.3" in block, (
        "C.4 — helper must filter substitutes with similarity < 0.3"
    )


def test_router_substitution_helper_skips_recipes_using_short_ingredient():
    """C.4 — Substitute products must NOT use the short ingredient."""
    idx = ROUTER_SRC.find("def _build_substitution_suggestions")
    assert idx > 0
    block = ROUTER_SRC[idx : idx + 5000]
    assert "also needs the short ingredient" in block or "ing_id in other_set[1]" in block, (
        "C.4 — helper must skip substitutes that also use the short ingredient"
    )


def test_router_substitution_helper_returns_top_n():
    """C.4 — Cap at top_n (default 3) so they can decide fast."""
    idx = ROUTER_SRC.find("def _build_substitution_suggestions")
    assert idx > 0
    block = ROUTER_SRC[idx : idx + 5000]
    assert "top_n" in block, "C.4 — helper must accept top_n parameter and slice"


def test_router_day_view_passes_substitution_suggestions():
    """C.4 — Day view context must include substitution_suggestions."""
    # Sazon-Improvement v2 (2026-10-06) Phase E: search for the day-view
    # context key (the value `"substitution_suggestions":` inside a dict
    # literal) — not the function definition, which now lives in
    # analytics.py and would match first.
    idx = ROUTER_SRC.find('"substitution_suggestions":')
    assert idx > 0, "C.4 — context must set substitution_suggestions per day"
    block = ROUTER_SRC[max(0, idx - 800) : idx + 800]
    assert "_build_substitution_suggestions(" in block, (
        "C.4 — substitution_suggestions must be computed via _build_substitution_suggestions"
    )
    assert "plan.lines" in block, "C.4 — must iterate plan.lines to find short ingredients"
    # Must filter by stock_on_hand - qty_required < 0
    assert "stock_on_hand - ln.qty_required" in block, (
        "C.4 — must filter ingredients where stock < required"
    )


# ────────────────────── template UI (C.4) ──────────────────────


def test_template_renders_substitution_block():
    """C.4 — The day view must render the substitution_suggestions block."""
    assert "substitution_suggestions" in TEMPLATE_SRC, (
        "C.4 — template must reference substitution_suggestions"
    )
    assert "Sustitutos sugeridos" in TEMPLATE_SRC, (
        "C.4 — template must show 'Sustitutos sugeridos' label"
    )


def test_template_substitution_block_is_collapsible():
    """C.4 — The substitution block uses <details> to stay out of the way."""
    # Find the substitution section
    idx = TEMPLATE_SRC.find("Sustitutos sugeridos")
    assert idx > 0
    # Backtrack to find <details>
    block = TEMPLATE_SRC[max(0, idx - 400) : idx]
    assert "<details" in block, (
        "C.4 — substitution block must be wrapped in <details> so cooks can collapse"
    )


def test_template_substitution_pills_show_similarity_pct():
    """C.4 — Each pill must display 'similitud X%' from the model output."""
    idx = TEMPLATE_SRC.find("Sustitutos sugeridos")
    assert idx > 0
    block = TEMPLATE_SRC[idx : idx + 2500]
    assert "sub.similarity" in block, "C.4 — pills must read substitute.similarity"
    # Format the percentage
    assert "* 100" in block or "100}}" in block, (
        "C.4 — pills must render similarity × 100 as a percentage"
    )


def test_template_handles_empty_substitutes():
    """C.4 — When the model finds no substitute, show a clear fallback."""
    idx = TEMPLATE_SRC.find("Sustitutos sugeridos")
    assert idx > 0
    block = TEMPLATE_SRC[idx : idx + 2500]
    assert "Sin sustitutos" in block, (
        "C.4 — template must render 'Sin sustitutos cercanos' fallback"
    )


def test_template_block_visible_without_low_stock():
    """C.4 — Substitution suggestions can show even when low_stock_ingredients
    is empty (e.g. plan is short but ingredient's stock field is undefined)."""
    # The if-condition must include substitution_suggestions
    assert "low_stock_ingredients or substitution_suggestions" in TEMPLATE_SRC, (
        "C.4 — alert if-condition must include substitution_suggestions"
    )


def test_template_substitute_pills_have_data_product_id():
    """C.4 — Pills carry data-product-id for click-tracking + future wire-up."""
    idx = TEMPLATE_SRC.find("Sustitutos sugeridos")
    assert idx > 0
    block = TEMPLATE_SRC[idx : idx + 2500]
    assert 'class="substitute-pill"' in block, (
        "C.4 — pills must have class='substitute-pill' for CSS/test targeting"
    )
    assert "data-product-id" in block, (
        "C.4 — pills must carry data-product-id so JS can wire click handlers"
    )
