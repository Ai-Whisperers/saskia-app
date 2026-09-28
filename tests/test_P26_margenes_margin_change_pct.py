"""tests/test_P26_margenes_margin_change_pct.py — regression test for P-26.

P-26: GET /reportes/margenes returned 500 with TypeError because the
template insight_margenes.html sorted the drift list with:

    {% for d in drift | sort(attribute='margin_change_pct', reverse=true) %}

When any item has margin_change_pct=None (because the product's
current_cost basis is None — no recipe or no priced ingredients),
Jinja's `sort` filter fed `None` into Python's `sorted()`, which
crashed with:

    TypeError: '<' not supported between instances of 'float' and 'NoneType'

Reproducible condition:
- Product has ≥2 sales in the last 30 days (so margin_drift_all includes it)
- The product has NO recipe OR all recipe ingredients have batch_cost_gs=None
  → margin_drift_all returns margin_change_pct=None for that product

This test seeds:
  (a) one product WITH a priced recipe → margin_change_pct is a float
  (b) one product WITHOUT a recipe → margin_change_pct is None
Then GETs /reportes/margenes and asserts it returns 200 (not 500).
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


def test_margenes_page_handles_none_margin_change_pct(client, session_factory):
    """P-26: /reportes/margenes must return 200 even when some products have margin_change_pct=None.

    Regression for TypeError '<' not supported between float and NoneType
    raised by `drift | sort(attribute='margin_change_pct', ...)` when any
    item in the list has margin_change_pct=None.

    Setup: two products, one with priced recipe (margin_change_pct=float)
    and one with no recipe (margin_change_pct=None). The second one is
    the bug-trigger.
    """
    with session_factory() as s:
        # Product A: priced recipe → margin_change_pct is a float
        ing = make_ingredient(
            s, unit="kg", stock_qty=10.0, min_stock_qty=2.0, purchase_price_gs=3000
        )
        rec = make_recipe(s, lines=[ing_line(ing, qty=0.3, unit="kg")],
                          yield_qty=12, yield_unit="und")
        prod_priced = make_product(s, sale_price_gs=5000, recipe_id=rec.id)
        prod_priced_name = prod_priced.name

        # Product B: NO recipe → current_cost is None → margin_change_pct is None
        prod_norecipe = make_product(s, sale_price_gs=2000, recipe_id=None)
        prod_norecipe_name = prod_norecipe.name

        # 3 sales at varying prices for prod_priced so price_change_pct is non-null
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for i, p in enumerate([5000, 5500, 6000]):
            make_sale(s, product=prod_priced, qty=1, unit_price_gs=p,
                      at=now - timedelta(days=i * 5))

        # 2 sales for prod_norecipe — enough to be included in margin_drift_all
        for i, p in enumerate([2000, 2200]):
            make_sale(s, product=prod_norecipe, qty=1, unit_price_gs=p,
                      at=now - timedelta(days=i * 3))

        s.commit()

    r = client.get("/reportes/margenes")
    assert r.status_code == 200, (
        f"P-26 regression: /reportes/margenes returned {r.status_code} when "
        f"a product had margin_change_pct=None. Body[:500]: {r.text[:500]}"
    )
    # The page must not contain a TypeError stack trace
    assert "TypeError" not in r.text, f"TypeError leaked into page: {r.text[:500]}"
    # Both products should be rendered (the priced one with margin %, the
    # no-recipe one with "—" placeholders for margin cells).
    assert prod_priced_name in r.text, "priced product missing from drift table"
    assert prod_norecipe_name in r.text, "no-recipe product missing from drift table"