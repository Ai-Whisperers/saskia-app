"""Parametrized substring-in-body checks for tests/test_produccion_polish.py.

Phase 2 increment #3 (S1 batch2 parametrize expansion): demo the dedup
pattern on the largest file in the suite (1013 lines). The most repeated
shape is `assert <literal> in TEMPLATE_BODY` / `CSS_BODY` across many tests.
This file subsumes them into a single driver + a `_CASES` list.

ADDITIVE only — the originals in test_produccion_polish.py remain
untouched. If a future batch confirms identical behavior across N runs, the
originals can be deleted in a follow-up commit.

Each case:
    - id          : short label (becomes the parametrized test id).
    - body        : 'template' | 'css' — which of TEMPLATE_BODY / CSS_BODY to check.
    - literal     : substring expected in the chosen body.
    - description : human-readable explanation used as a hint on failure.

The driver runs each case as one pytest test row. The `id` doubles as
documentation and lets `--collect-only` show the per-check names.

N cases subsume the simple `assert literal in BODY` originals. The two
regex-blocks in TestWhiteBackgroundBugFixes (`.step-btn { ... }` and
`.production-row--has-pedido { ... }` style-rule parsing) are intentionally
left in the original file — they don't fit the simple substring-in-body
driver shape.
"""

from __future__ import annotations

import pytest

from tests.test_produccion_polish import CSS_BODY, IMPROVEMENTS_BODY, TEMPLATE_BODY  # noqa: F401

_BODIES = {
    "template": TEMPLATE_BODY,
    "css": CSS_BODY,
}


# ─── Parametrize rows ─────────────────────────────────────────────
#
# Each row is one complete spec for one originally hand-written
# 'assert <literal> in BODY' test. Adding a new check = one dict entry.
_CASES: list[dict] = [
    # C1 — table overflow + ingredients link card.
    {
        "id": "products_table_wrapped_in_scrollable",
        "body": "template",
        "literal": 'class="production-table-scroll"',
        "description": "products table must wrap in .production-table-scroll",
    },
    {
        "id": "products_overflow_x_auto",
        "body": "template",
        "literal": "overflow-x: auto",
        "description": "wrapper CSS sets overflow-x to auto",
    },
    {
        "id": "ingredients_link_card_section",
        "body": "template",
        "literal": 'data-section="ingredients-link-card"',
        "description": "ingredients section is a link card",
    },
    {
        "id": "ingredients_link_to_prep_recipes",
        "body": "template",
        "literal": "/produccion/prep-recipes",
        "description": "link card points to /produccion/prep-recipes",
    },
    {
        "id": "ingredients_link_to_shopping_list",
        "body": "template",
        "literal": "/shopping-list",
        "description": "link card points to /shopping-list",
    },
    # C3 — META cell visual hierarchy.
    {
        "id": "meta_cell_count_class",
        "body": "template",
        "literal": "meta-cell__count",
        "description": "META column uses .meta-cell__count (big)",
    },
    {
        "id": "meta_cell_unit_class",
        "body": "template",
        "literal": "meta-cell__unit",
        "description": "META column uses .meta-cell__unit (small)",
    },
    {
        "id": "meta_cell_lote_label",
        "body": "template",
        "literal": "lote",
        "description": "META column says 'lote' or 'lotes'",
    },
    # M4 — conf banner divider.
    {
        "id": "conf_banner_divider_class",
        "body": "template",
        "literal": "conf-banner-divider",
        "description": "conf banner divider present",
    },
    # M9 — collapsible 'Cómo se calcula'.
    {
        "id": "cal_box_class",
        "body": "template",
        "literal": "cal-box",
        "description": "'Cómo se calcula' hint collapsible block exists",
    },
    # V6 — HACCP chips wrap.
    {
        "id": "haccp_chips_flex_wrap",
        "body": "template",
        "literal": "flex-wrap: wrap",
        "description": "HACCP chips wrap on narrow viewports",
    },
    # V* — bulk action hierarchy.
    {
        "id": "bulk_action_primary_strong",
        "body": "template",
        "literal": '<strong class="bulk-action-primary">',
        "description": "bulk action label uses .bulk-action-primary",
    },
    # V* — zero-demand collapsible.
    {
        "id": "zero_demand_block_class",
        "body": "template",
        "literal": "zero-demand-block",
        "description": "zero-demand collapsible block present",
    },
    {
        "id": "zero_demand_block_empty_msg",
        "body": "template",
        "literal": "Sin demanda reciente",
        "description": "zero-demand block shows empty-state copy",
    },
    # V* — date picker auto-submit / filter toolbar.
    {
        "id": "data_row_filter_products",
        "body": "template",
        "literal": 'data-row-filter="products"',
        "description": "filter input attaches to row data-row-filter attribute",
    },
    {
        "id": "filter_placeholder_spanish",
        "body": "template",
        "literal": "Filtrar por nombre",
        "description": "filter placeholder is Spanish-friendly",
    },
    # Filter wiring (originally `assert "applyNameFilter" in TEMPLATE_BODY or "row-filter" in TEMPLATE_BODY`).
    {
        "id": "filter_wiring_apply_name_filter",
        "body": "template",
        "literal": "applyNameFilter",
        "description": "row-filter wiring present via applyNameFilter",
    },
]


@pytest.mark.parametrize("spec", _CASES, ids=lambda s: s["id"])
def test_substring_in_body(spec: dict) -> None:
    """Subsumes the simple `assert literal in BODY` tests from the original."""
    body = _BODIES[spec["body"]]
    assert spec["literal"] in body, (
        f"{spec['description']!r}: literal {spec['literal']!r} not found in {spec['body']} body"
    )
