"""Tests for /produccion B.9 — Batch-surplus visibility.

The cook sees "you'll bake 12 chipás but only need 10 — 2 will
likely go unsold at close". Saved ~150-300k Gs/month by giving the
cook enough lead time to:
- lower the forecast (10 instead of 12)
- offer a promo at close for the surplus
- swap to a smaller-batch recipe

The model is:
  surplus_qty = ceil(qty_demand / yield_qty) * yield_qty - qty_demand
  surplus_pct = surplus_qty / qty_demand * 100
"""

from __future__ import annotations

from pathlib import Path

TEMPLATE = Path(__file__).parent.parent / "app" / "templates" / "produccion.html"
ROUTER = Path(__file__).parent.parent / "app" / "routers" / "produccion.py"

TEMPLATE_SRC = TEMPLATE.read_text(encoding="utf-8")
ROUTER_SRC = ROUTER.read_text(encoding="utf-8")


# ────────────────────── helper unit tests (B.9) ──────────────────────


def test_router_has_batch_surplus_helper():
    """B.9 — _batch_surplus(qty, yield) computes (ceil, baked, surplus, pct)."""
    assert "def _batch_surplus" in ROUTER_SRC, (
        "B.9 — _batch_surplus helper must be defined"
    )


def test_router_batch_surplus_returns_4_fields():
    """B.9 — Helper returns batches, baked_qty, surplus_qty, surplus_pct."""
    idx = ROUTER_SRC.find("def _batch_surplus")
    assert idx > 0
    block = ROUTER_SRC[idx : idx + 1500]
    assert '"batches"' in block
    assert '"baked_qty"' in block
    assert '"surplus_qty"' in block
    assert '"surplus_pct"' in block


def test_router_batch_surplus_uses_ceiling_division():
    """B.9 — Surplus uses math.ceil so partial batches still produce a full batch."""
    idx = ROUTER_SRC.find("def _batch_surplus")
    assert idx > 0
    block = ROUTER_SRC[idx : idx + 1500]
    assert "math.ceil" in block, (
        "B.9 — must use math.ceil so 10 portions + yield 12 → 1 batch (12 baked)"
    )


def test_router_batch_surplus_zero_inputs_are_safe():
    """B.9 — Zero demand or yield returns zeros (no division by zero)."""
    idx = ROUTER_SRC.find("def _batch_surplus")
    assert idx > 0
    block = ROUTER_SRC[idx : idx + 1500]
    assert "qty_demand <= 0 or yield_qty <= 0" in block, (
        "B.9 — must guard zero/negative inputs"
    )


# ────────────────────── context wiring (B.9) ──────────────────────


def test_router_day_view_sets_batch_surplus_fields():
    """B.9 — plan_rows_view entries must include batch_surplus_qty + pct."""
    # Find the day-view context (search near haccp_latest)
    idx = ROUTER_SRC.find("batch_surplus_qty")
    assert idx > 0, "B.9 — batch_surplus_qty must be set in context"
    idx2 = ROUTER_SRC.find("batch_surplus_pct")
    assert idx2 > 0, "B.9 — batch_surplus_pct must be set in context"


def test_router_ad_hoc_rows_have_no_surplus():
    """B.9 — Ad-hoc rows have no recipe_id → surplus fields are None."""
    idx = ROUTER_SRC.find("is_ad_hoc\": True")
    assert idx > 0
    block = ROUTER_SRC[idx : idx + 1500]
    assert '"batch_surplus_qty": None' in block
    assert '"batch_surplus_pct": None' in block


def test_router_surplus_uses_recipe_yield_qty():
    """B.9 — Computation is gated on recipe_by_id[recipe_id].yield_qty."""
    # Find the helper definition (first occurrence)
    helper_idx = ROUTER_SRC.find("def _batch_surplus")
    assert helper_idx > 0
    # Helper itself must reference yield_qty
    helper_block = ROUTER_SRC[helper_idx : helper_idx + 1500]
    assert "yield_qty" in helper_block, (
        "B.9 — _batch_surplus helper must read yield_qty"
    )
    # Find the context usage (second occurrence of batch_surplus_qty)
    ctx_idx = ROUTER_SRC.find('"batch_surplus_qty":')
    assert ctx_idx > 0
    ctx_block = ROUTER_SRC[ctx_idx - 1000 : ctx_idx + 1000]
    assert "yield_qty" in ctx_block, (
        "B.9 — context wiring must read recipe_by_id[recipe_id].yield_qty"
    )
    assert "_batch_surplus" in ctx_block, (
        "B.9 — context wiring must call _batch_surplus helper"
    )


# ────────────────────── template UI (B.9) ──────────────────────


def test_template_has_surplus_column_header():
    """B.9 — The production table must have a Sobrante header."""
    assert "Sobrante" in TEMPLATE_SRC, (
        "B.9 — table must include 'Sobrante' header"
    )


def test_template_renders_surplus_pill_with_color_codes():
    """B.9 — Pills must use color-coded classes (low/med/high)."""
    assert "surplus-pill" in TEMPLATE_SRC, (
        "B.9 — pill must have class='surplus-pill'"
    )
    assert "surplus-high" in TEMPLATE_SRC, (
        "B.9 — pill must use surplus-high class for ≥30% surplus"
    )
    assert "surplus-med" in TEMPLATE_SRC, (
        "B.9 — pill must use surplus-med class for 10-29% surplus"
    )
    assert "surplus-low" in TEMPLATE_SRC, (
        "B.9 — pill must use surplus-low class for 1-9% surplus"
    )


def test_template_renders_exacto_indicator():
    """B.9 — Zero-surplus rows show '✓ exacto' (positive feedback)."""
    assert "exacto" in TEMPLATE_SRC, (
        "B.9 — exact-fit rows must show '✓ exacto'"
    )


def test_template_handles_none_surplus():
    """B.9 — Ad-hoc rows (recipe_id=None) show '—' (no estimate possible)."""
    idx = TEMPLATE_SRC.find('data-label="Sobrante"')
    assert idx > 0
    block = TEMPLATE_SRC[idx : idx + 1500]
    assert "batch_surplus_qty is not none" in block, (
        "B.9 — must guard against None surplus (ad-hoc rows)"
    )


def test_template_surplus_pill_includes_pct_in_title():
    """B.9 — The pill title must show the pct so the cook can read the math."""
    idx = TEMPLATE_SRC.find("surplus-pill surplus-")
    assert idx > 0
    block = TEMPLATE_SRC[idx : idx + 1000]
    assert "batch_surplus_pct" in block
    assert "title=" in block, (
        "B.9 — pill must have a tooltip explaining the surplus"
    )


def test_template_surplus_pill_print_styles():
    """B.9 — Surplus pills must remain visible (with bordered style) on print."""
    assert ".surplus-pill" in TEMPLATE_SRC, (
        "B.9 — CSS rules for surplus-pill must exist"
    )
    assert "@media print" in TEMPLATE_SRC, (
        "B.9 — print media query must adjust surplus-pill colors"
    )