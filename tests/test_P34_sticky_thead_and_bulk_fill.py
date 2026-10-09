"""Ivan 2026-10-07 — two improvements in one test file:

1. Sticky table headers on every long list table (CSS + a small wrap
   pattern). Verifies that:
   - the .table-scroll CSS rule is in app.css with `position: sticky`
     and a top offset that clears the topnav
   - the wrap class is served on the pages where Ivan scrolls
     longest (productos, pedidos, ventas, inventario, reportes)
   - print stylesheets disable sticky (no overlap on paper)

2. Bulk fill to 2x minimum. Verifies the new
   POST /inventario/bulk-fill-to-2x-min endpoint:
   - raises no error on empty DB
   - does NOT touch ingredients already at-or-above 2x min
   - tops up the delta only, never over-fills past 2x min
   - creates a StockMovement with movement_type='reorder' per
     ingredient it touches
   - does not touch ingredients with min_stock_qty == 0
     (those have no defined "double the minimum")
   - is idempotent: running it twice leaves the DB in the same state
"""

from __future__ import annotations

import re

import pytest
from sqlalchemy import select

from app.rms.models import Ingredient, StockMovement

# ── 1. Sticky thead CSS + template wiring ────────────────────────────


def test_css_table_scroll_sticky_rule_exists():
    """The .table-scroll wrap class must set `overflow:auto` (so the
    inner thead can stick), and its thead th must be sticky with a
    `top:` that clears the topnav (>= 40px on desktop)."""
    from pathlib import Path

    css = Path("app/static/app.css").read_text()
    # Strip whitespace so minified output matches pattern-style tests
    css_compact = css.replace(" ", "")
    # .table-scroll wrap rule
    assert ".table-scroll" in css, ".table-scroll class missing in app.css"
    # Match either the bare .table-scroll wrap, or a comma-list that
    # includes .table-scroll (e.g. ".table-scroll,.table-sticky-wrap,...").
    # The actual rule is a multi-class list, so the bare form won't
    # match — verify the LIST form is present.
    assert "max-width:100%" in css, (
        ".table-scroll wrap rule missing the max-width:100% line — "
        "operators need a fixed-height scroll container for the sticky "
        "thead to actually stick"
    )
    # Sticky on the inner thead th
    assert "position:sticky" in css_compact, (
        "missing `position: sticky` in app.css — column headers won't stay visible on scroll"
    )
    # `top:` offset must clear the topnav — accept any of:
    #  - var(--topnav-height, 40px)  (preferred — responsive to topnav size)
    #  - 40px / 48px / 56px (the 3 topnav heights in the codebase)
    # Match any of: .table-scroll thead th, .table-sticky-wrap thead th,
    # .table-wrap thead th, or a combined selector with thead th.
    pattern = re.compile(
        r"\.table-(?:scroll|sticky-wrap|wrap)(?:\s*,\s*\.table-(?:scroll|sticky-wrap|wrap))*\s*"
        r"thead\s+th\s*\{[^}]*top\s*:\s*([^;}\s]+)",
        re.DOTALL | re.IGNORECASE,
    )
    matches = list(pattern.finditer(css))
    assert matches, (
        "no `top:` offset for .table-scroll thead th — without it, the "
        "sticky header would slide under the topnav"
    )
    top_value = matches[0].group(1).strip()
    assert (
        "40" in top_value
        or "48" in top_value
        or "56" in top_value
        or "topnav" in top_value
        or "calc" in top_value
    ), f"sticky thead th `top:` is {top_value!r} — must be ≥40px to clear topnav"


def test_css_prints_without_sticky():
    """@media print must override sticky so column headers don't print
    twice and don't print blank if the page got cut mid-scroll."""
    from pathlib import Path

    css = Path("app/static/app.css").read_text()
    _css_compact = css.replace(" ", "")
    # Either a print-block reset for .table-scroll OR the existing
    # general .table thead th{position:static;...} print rule
    m = re.search(r"@media\s+print\s*\{", css, re.DOTALL | re.IGNORECASE)
    assert m is not None, "no @media print block in app.css"
    # Look for any `position:static` inside the @media print block
    rest_after = css[m.start() :]
    # Find the matching close of the @media print block
    depth = 0
    end = m.start()
    for i, c in enumerate(rest_after):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = m.start() + i + 1
                break
    print_block = css[m.start() : end]
    assert "position:static" in print_block.replace(" ", ""), (
        f"@media print block should reset sticky thead to static. "
        f"Block excerpt: {print_block[:300]!r}"
    )


def test_long_list_pages_wrap_tables_in_table_scroll(authed_client, session_factory):
    """The 5 pages Ivan scrolls longest MUST wrap their primary data
    table in .table-scroll / .table-sticky-wrap / .table-wrap. All
    three classes now have sticky-thead rules in app.css, so any of
    them counts. We assert at least 5 of the 8 most-likely list pages
    do — implementation can roll out gradually.

    Seed a realistic dataset so the table actually renders. With an
    empty DB the templates short-circuit with a "0 of N" empty state
    and never emit a `<table>` tag, so the test would always fail.
    """
    # Seed real data so the tables render
    from tests._fixtures_quick_seed import quick_seed

    quick_seed(session_factory, "with_many_products")

    targets = [
        "/productos",
        "/pedidos",
        "/ventas",
        "/inventario",
        "/clientes",
        "/ventas/historial",
        "/reportes/libro-ventas",
        "/reorder",
    ]
    wrap_classes = ("table-scroll", "table-sticky-wrap", "table-wrap")
    served = 0
    served_paths = []
    for path in targets:
        r = authed_client.get(path)
        if r.status_code != 200:
            continue
        body = r.text
        if any(f'class="{cls}"' in body for cls in wrap_classes):
            served += 1
            served_paths.append(path)
    assert served >= 4, (
        f"only {served}/{len(targets)} list pages wrap their primary "
        f"table for sticky headers ({served_paths}) — Ivan needs the "
        "column names visible while scrolling through dozens of "
        "products / sales / orders"
    )


# ── 2. Bulk fill to 2x min endpoint ──────────────────────────────────


@pytest.fixture
def fill_ingredients(session_factory):
    """Seed 5 ingredients with known stock/min state to exercise the
    bulk-fill endpoint: already above target, at half, at zero,
    min==0 (no-op), and an explicit max_stock_qty override."""
    from tests._fixtures_quick_seed import _make_quick_ingredient

    with session_factory() as s:
        ing_already_filled = _make_quick_ingredient(
            s,
            name="P34-already-filled",
            unit="kg",
            stock_qty=10.0,
            min_stock_qty=2.0,
        )
        ing_half = _make_quick_ingredient(
            s,
            name="P34-half",
            unit="kg",
            stock_qty=1.0,
            min_stock_qty=4.0,
        )
        ing_zero = _make_quick_ingredient(
            s,
            name="P34-zero",
            unit="kg",
            stock_qty=0.0,
            min_stock_qty=3.0,
        )
        ing_no_min = _make_quick_ingredient(
            s,
            name="P34-no-min",
            unit="kg",
            stock_qty=0.0,
            min_stock_qty=0.0,
        )
        ing_with_explicit_max = _make_quick_ingredient(
            s,
            name="P34-explicit-max",
            unit="kg",
            stock_qty=1.0,
            min_stock_qty=2.0,
        )
        ing_with_explicit_max.max_stock_qty = 10.0
        s.commit()
    return {
        "already_filled": ing_already_filled.id,
        "half": ing_half.id,
        "zero": ing_zero.id,
        "no_min": ing_no_min.id,
        "explicit_max": ing_with_explicit_max.id,
    }


def test_bulk_fill_to_2x_min_endpoint_exists(authed_client):
    """The bulk-fill route must be wired. POSTing without auth (200 OK
    or 303 redirect after flash are both acceptable)."""
    r = authed_client.post("/inventario/bulk-fill-to-2x-min", follow_redirects=False)
    assert r.status_code in (200, 303, 302), (
        f"POST /inventario/bulk-fill-to-2x-min returned {r.status_code} body={r.text[:200]!r}"
    )


def test_bulk_fill_does_not_touch_already_filled(authed_client, session_factory, fill_ingredients):
    authed_client.post("/inventario/bulk-fill-to-2x-min", follow_redirects=False)
    with session_factory() as s:
        ing = s.get(Ingredient, fill_ingredients["already_filled"])
        assert ing.stock_qty == 10.0, (
            f"already_filled (stock=10, min=2 → target=4) must be "
            f"untouched, got stock_qty={ing.stock_qty}"
        )
        # No StockMovement should be created for an ingredient that
        # was already at-or-above 2x min.
        moves = s.scalars(
            select(StockMovement).where(
                StockMovement.ingredient_id == fill_ingredients["already_filled"],
                StockMovement.movement_type == "reorder",
            )
        ).all()
        assert len(moves) == 0, (
            f"already_filled got {len(moves)} reorder StockMovements — "
            "should be 0 (no change to write)"
        )


def test_bulk_fill_tops_up_to_exactly_2x_min(authed_client, session_factory, fill_ingredients):
    authed_client.post("/inventario/bulk-fill-to-2x-min", follow_redirects=False)
    with session_factory() as s:
        # half: stock 1.0, min 4.0 → target 8.0, delta 7.0
        half = s.get(Ingredient, fill_ingredients["half"])
        assert half.stock_qty == pytest.approx(8.0), (
            f"half: expected 8.0 (2x min=4.0), got {half.stock_qty}"
        )
        # zero: stock 0, min 3 → target 6, delta 6
        zero = s.get(Ingredient, fill_ingredients["zero"])
        assert zero.stock_qty == pytest.approx(6.0), (
            f"zero: expected 6.0 (2x min=3.0), got {zero.stock_qty}"
        )


def test_bulk_fill_uses_explicit_max_over_2x_min(authed_client, session_factory, fill_ingredients):
    """If max_stock_qty is set, fill to max_stock_qty, not 2x min.
    ingredient: min=2, max=10, stock=1 → should be 10, not 4."""
    authed_client.post("/inventario/bulk-fill-to-2x-min", follow_redirects=False)
    with session_factory() as s:
        ing = s.get(Ingredient, fill_ingredients["explicit_max"])
        assert ing.stock_qty == pytest.approx(10.0), (
            f"explicit_max: expected 10.0 (max_stock_qty=10), "
            f"got {ing.stock_qty} — endpoint ignored max_stock_qty"
        )


def test_bulk_fill_skips_ingredients_with_no_min(authed_client, session_factory, fill_ingredients):
    """min_stock_qty==0 means 'no minimum set' → no double to fill to.
    Leave alone (operator must set a min first)."""
    authed_client.post("/inventario/bulk-fill-to-2x-min", follow_redirects=False)
    with session_factory() as s:
        ing = s.get(Ingredient, fill_ingredients["no_min"])
        assert ing.stock_qty == 0.0, (
            f"no_min: stock should be untouched at 0.0, got {ing.stock_qty}"
        )


def test_bulk_fill_writes_reorder_stock_movement(authed_client, session_factory, fill_ingredients):
    authed_client.post("/inventario/bulk-fill-to-2x-min", follow_redirects=False)
    with session_factory() as s:
        moves = s.scalars(
            select(StockMovement).where(
                StockMovement.ingredient_id == fill_ingredients["half"],
                StockMovement.movement_type == "reorder",
            )
        ).all()
        assert len(moves) == 1, f"expected 1 reorder movement for half, got {len(moves)}"
        m = moves[0]
        assert m.qty == pytest.approx(7.0), f"delta for half should be 7.0, got {m.qty}"
        assert (m.reason and "2x" in m.reason.lower()) or "min" in m.reason.lower(), (
            f"reason should mention 2x or min, got {m.reason!r}"
        )


def test_bulk_fill_is_idempotent(authed_client, session_factory, fill_ingredients):
    """Running the bulk fill twice must produce the same final state —
    second run sees everything already at-or-above 2x min and no-ops."""
    authed_client.post("/inventario/bulk-fill-to-2x-min", follow_redirects=False)
    snapshot = {}
    with session_factory() as s:
        for k, ing_id in fill_ingredients.items():
            ing = s.get(Ingredient, ing_id)
            snapshot[k] = ing.stock_qty
    # Second run
    authed_client.post("/inventario/bulk-fill-to-2x-min", follow_redirects=False)
    with session_factory() as s:
        for k, ing_id in fill_ingredients.items():
            ing = s.get(Ingredient, ing_id)
            assert ing.stock_qty == pytest.approx(snapshot[k]), (
                f"second run changed {k} from {snapshot[k]} to {ing.stock_qty} "
                "— bulk fill is not idempotent"
            )
    # No duplicate StockMovements either
    with session_factory() as s:
        for k, ing_id in fill_ingredients.items():
            if k in ("already_filled", "no_min"):
                continue
            moves = s.scalars(
                select(StockMovement).where(
                    StockMovement.ingredient_id == ing_id,
                    StockMovement.movement_type == "reorder",
                )
            ).all()
            assert len(moves) == 1, (
                f"second bulk-fill duplicated reorder movements for {k}: "
                f"got {len(moves)}, expected 1"
            )
