"""tests/test_P26_margenes_margin_change_pct.py — regression test for P-26.

P-26: GET /reportes/margenes returned 500 with AttributeError because the
template insight_margenes.html uses `d.margin_change_pct` (in the
`sort(attribute='margin_change_pct', ...)` clause and in two `{% if d.margin_change_pct %}`
cells), but the MarginDrift dataclass never defined that attribute, so
Jinja raised `UndefinedError: ... object has no attribute 'margin_change_pct'`.

This test seeds the minimum data needed for margin_drift_all() to return
a non-empty list (≥2 sales in the last 30 days for a product with a
recipe-linked ingredient so margin can be computed), then GETs the page
and asserts it returns 200 (not 500) and contains the product name.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tests.factories import (
    ing_line,
    make_ingredient,
    make_product,
    make_recipe,
    make_sale,
)

pytestmark = [pytest.mark.smoke]


def test_margenes_page_renders_200_with_change_pct(client, session_factory):
    """P-26: /reportes/margenes must return 200, not 500."""
    with session_factory() as s:
        # Need ingredient + recipe line + product so margin_drift_all can
        # compute a non-null margin (current_cost basis = recipe cost).
        ing = make_ingredient(
            s, unit="kg", stock_qty=10.0, min_stock_qty=2.0, purchase_price_gs=3000
        )
        # wire one recipe line so current_cost is non-null
        rec = make_recipe(s, lines=[ing_line(ing, qty=0.3, unit="kg")],
                          yield_qty=12, yield_unit="und")
        prod = make_product(s, sale_price_gs=5000, recipe_id=rec.id)
        prod_name = prod.name

        # 3 sales at varying prices so price_change_pct is non-null
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for i, p in enumerate([5000, 5500, 6000]):
            make_sale(s, product=prod, qty=1, unit_price_gs=p,
                      at=now - timedelta(days=i * 5))
        s.commit()

    r = client.get("/reportes/margenes")
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:500]}"
    # The page must not contain an AttributeError/UndefinedError stack.
    assert "AttributeError" not in r.text
    assert "UndefinedError" not in r.text
    # Drift table must render this product (margin_change_pct branch hit).
    assert prod_name in r.text