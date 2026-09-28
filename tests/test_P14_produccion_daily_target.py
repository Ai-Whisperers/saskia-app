"""tests/test_P14_produccion_daily_target.py — regression test for /produccion 500.

P-14: the day-view render() did not pass `daily_target` to the template, so
the `{% if daily_target is not none %}` branch in produccion.html:102 raised
Jinja UndefinedError (Undefined is not None), causing a 500 on /produccion.

This test reproduces the bug. It should fail BEFORE the fix (500) and pass
AFTER (200, "Meta diaria" present in the body, no UndefinedError).
"""
from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from tests.factories import make_ingredient, make_product, make_recipe, make_sale


def test_produccion_day_view_returns_200_with_daily_target(client, session_factory):
    """P-14: /produccion (day view) must return 200 with daily_target in context."""
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        ing = make_ingredient(s, unit="kg", stock_qty=10.0, min_stock_qty=2.0)
        rec = make_recipe(s, yield_qty=12, yield_unit="und")
        prod = make_product(s, sale_price_gs=2500, recipe=rec)
        # One sale on "today" so daily_actual is non-zero and the % branch renders.
        make_sale(s, product=prod, qty=3)
        s.commit()
    finally:
        s.close()

    r = client.get("/produccion?view=day")
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:500]}"
    # No Jinja UndefinedError surfaced in the rendered body (P-14 symptom).
    assert "UndefinedError" not in r.text
    # Template branch reached — meta-diaria card rendered.
    assert "Meta diaria" in r.text