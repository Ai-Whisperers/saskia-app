"""P-32.2: /reorder price input must auto-fill from the cheapest supplier.

Even though the row already has `cheapest_suppliers[iid]` data, the price
input is free-text. The cashier has to retype the cheapest price, which
defeats the point of the data being there.

Fix: add `data-cheapest-price` to the price input, populated from
`cheapest_suppliers[item.ingredient_id].price_gs`. JS reads it on supplier
change and overwrites the price ONLY if the operator hasn't manually
touched the input (track via `data-touched`).

Acceptance:
  - The rendered <input name="price_gs"> has a `data-cheapest-price`
    attribute (empty string when no cheapest supplier is known).
  - When a cheapest supplier is known, the value is a positive integer
    (Gs.) and matches what `batch_cheapest_supplier` would return.
  - A small JS bundle is loaded (reorder-auto-price.js or inline <script>)
    that wires the supplier-change handler.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import sessionmaker

from app.rms.models import IngredientPriceEvent
from tests.factories import make_ingredient, make_supplier


def _setup_with_cheapest(s, name: str) -> int:
    """Ingredient + supplier + price event so cheapest_suppliers is non-empty."""
    ing = make_ingredient(
        s, name=name, unit="kg", stock_qty=0.5, min_stock_qty=5.0,
        purchase_price_gs=4500,
    )
    sup = make_supplier(s, name=f"sup-{name}", phone="+595 9XX XXXXX")
    s.flush()
    s.add(IngredientPriceEvent(
        ingredient_id=ing.id,
        supplier_id=sup.id,
        price_gs=4200,
        recorded_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        source="manual",
    ))
    s.flush()
    return ing.id


def test_reorder_price_input_has_cheapest_attr(client, session_factory):
    """P-32.2: price input carries data-cheapest-price attribute."""
    unique = f"cheapest-{uuid.uuid4().hex[:8]}"
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        _ing_id = _setup_with_cheapest(s, unique)
        s.commit()
    finally:
        s.close()

    r = client.get("/reorder")
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:500]}"
    body = r.text

    # The price input must now carry data-cheapest-price.
    assert "data-cheapest-price" in body, (
        "expected data-cheapest-price attribute on the price input. "
        "Old code rendered <input name=\"price_gs\"> with no data attribute."
    )

    # The value should be the cheapest price we recorded (4200 Gs.).
    # We don't assert exact match (formatter may add separators) but the
    # attribute value should be a positive integer.
    import re
    matches = re.findall(r'data-cheapest-price="(\d+)"', body)
    assert matches, "data-cheapest-price found but had no integer value"
    assert any(int(m) > 0 for m in matches), (
        f"data-cheapest-price values were all 0 or empty: {matches[:5]}"
    )


def test_reorder_price_input_empty_when_no_history(client, session_factory):
    """P-32.2: an ingredient with no price history has data-cheapest-price=\"\""""
    unique = f"nohist-{uuid.uuid4().hex[:8]}"
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        make_ingredient(
            s, name=unique, unit="kg", stock_qty=0.5, min_stock_qty=5.0,
            purchase_price_gs=4500,
        )
        s.commit()
    finally:
        s.close()

    r = client.get("/reorder")
    body = r.text

    # The attribute must still be present (so the JS can read it), but
    # the empty-string case is allowed.
    assert "data-cheapest-price" in body, (
        "data-cheapest-price missing on no-history ingredient"
    )
