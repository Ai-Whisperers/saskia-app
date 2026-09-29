"""P-19 / audit #19: /shopping-list 'Para qué' column shows meaningful text.

Audit finding: the 'Para qué' column was rendering 'Auto: stock X < mín Y'
which is a developer-internal debug string exposing internals to users and
giving no real reason WHY the item is being ordered.

This test verifies the column shows the ingredient name (the WHO) rather
than the debug stock placeholder.

The implementation (app/routers/shopping.py) currently sets
`purpose_text = f'Reposición: {ing.name}'` for low-stock auto-sync items.
"""
from __future__ import annotations

import pytest

pytestmark = [pytest.mark.smoke]


# These strings MUST NOT appear in the rendered shopping list.
# Each is a developer-internal placeholder that exposes internals to end
# users (counter staff, owner-finance).
FORBIDDEN_PURPOSE_FRAGMENTS = [
    "auto: stock",  # classic debug placeholder
    "stock < min",
    "stock < mín",
]


@pytest.mark.parametrize("forbidden", FORBIDDEN_PURPOSE_FRAGMENTS)
def test_shopping_list_does_not_show_debug_placeholders(client, forbidden):
    """P-19: shopping list must NOT show developer-debug strings."""
    r = client.get("/shopping-list")
    assert r.status_code == 200, f"got {r.status_code}"
    body = r.text.lower()
    assert forbidden.lower() not in body, (
        f"Found forbidden debug placeholder '{forbidden}' in shopping list. "
        f"The 'Para qué' column must show ingredient/recipe names, not debug strings."
    )


def test_shopping_list_has_para_que_column(client, session_factory):
    """P-19: shopping list has a 'Para qué' column header.

    Insert a real item so the table renders and the header is visible.
    """
    from app.rms.models import Ingredient, ShoppingListItem
    with session_factory() as s:
        ing = s.query(Ingredient).first()
        if ing is None:
            # No ingredient → can't render table → skip
            pytest.skip("No ingredient in test DB; cannot render shopping list table")
        s.add(ShoppingListItem(
            ingredient_id=ing.id,
            qty_to_buy=1.0,
            unit=ing.unit or "kg",
            purpose_text="Reposición: Test",
        ))
        s.commit()

    r = client.get("/shopping-list")
    assert r.status_code == 200
    # The header uses an encoded form ("Para qu&eacute;") and Unicode ("Para qué")
    assert ("Para qué" in r.text) or ("Para qu&eacute;" in r.text) or ("Para qu\xe9" in r.text), (
        "'Para qué' column header missing from /shopping-list. "
        "When at least one item exists, the table <thead> must contain this header."
    )


def test_sync_low_stock_sets_meaningful_purpose_text(client, session_factory):
    """P-19: low-stock auto-sync writes 'Reposición: {ing.name}', not 'Auto: stock'."""
    from tests.factories import make_ingredient

    with session_factory() as s:
        ing = make_ingredient(
            s,
            name=f"AuditTestHarina-{__import__('uuid').uuid4().hex[:6]}",
            stock_qty=1.0,
            min_stock_qty=10.0,
        )
        # Disable other ingredients' min_stock_qty so only `ing` triggers
        from app.rms.models import Ingredient
        for other in s.query(Ingredient).filter(Ingredient.id != ing.id).all():
            other.min_stock_qty = 0
        s.commit()
        ing_name = ing.name

    # POST sync-low-stock (redirect to GET list)
    r = client.post("/shopping-list/sync-low-stock", follow_redirects=True)
    assert r.status_code == 200

    # Read /shopping-list directly
    r = client.get("/shopping-list")
    assert r.status_code == 200
    body = r.text
    assert ing_name in body, (
        f"After sync-low-stock, ingredient name '{ing_name}' should appear on shopping list. "
        f"This confirms purpose_text contains the ingredient name (or 'Reposición: <name>')."
    )
    assert "Auto: stock" not in body, (
        "Forbidden 'Auto: stock' placeholder leaked into rendered list"
    )
