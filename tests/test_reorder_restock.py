"""tests/test_reorder_restock.py — Phase D Q1-surface: /reorder restock flow.

Saskia's words: "cada vez que la clienta restockea tiene que cargar los
precios, y así puede ver en los paneles de gestión cuánto está ganando
realmente aunque los precios fluctúen."

Covers POST /reorder/registrar:
- creates an IngredientPriceEvent with source='restock'
- increments Ingredient.stock_qty
- validation: qty<=0 → 400, negative price → 400, unknown ingredient → 404
- rate limit: 429 after 10 writes in a minute
- redirect 303 back to /reorder
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.rms.models import Ingredient, IngredientPriceEvent


@pytest.fixture
def low_ingredient(session_factory):
    """Seed one ingredient below its min so it shows on /reorder."""
    with session_factory() as s:
        ing = Ingredient(
            name="Harina restock",
            unit="kg",
            stock_qty=1.0,
            min_stock_qty=5.0,
            max_stock_qty=10.0,
            purchase_price_gs=5000,
        )
        s.add(ing)
        s.commit()
        return ing.id


def _post(client, ing_id, qty="4", price="6000", notes=""):
    return client.post(
        "/reorder/registrar",
        data={
            "ingredient_id": str(ing_id),
            "qty": qty,
            "price_gs": price,
            "notes": notes,
        },
        follow_redirects=False,
    )


def test_post_registrar_creates_price_event_and_increments_stock(
    client, session_factory, low_ingredient
):
    r = _post(client, low_ingredient, qty="4", price="6000")
    assert r.status_code == 303, r.text
    assert r.headers["location"] == "/reorder"

    with session_factory() as s:
        ing = s.get(Ingredient, low_ingredient)
        assert ing.stock_qty == pytest.approx(5.0)  # 1.0 + 4.0
        events = s.execute(
            select(IngredientPriceEvent).where(
                IngredientPriceEvent.ingredient_id == low_ingredient
            )
        ).scalars().all()
        assert len(events) == 1
        assert events[0].price_gs == 6000
        assert events[0].source == "restock"
        # current price denormalized on the ingredient
        assert ing.purchase_price_gs == 6000


def test_post_registrar_rejects_zero_qty(client, low_ingredient):
    r = _post(client, low_ingredient, qty="0")
    assert r.status_code == 400


def test_post_registrar_rejects_negative_qty(client, low_ingredient):
    r = _post(client, low_ingredient, qty="-2")
    assert r.status_code == 400


def test_post_registrar_rejects_negative_price(client, low_ingredient):
    r = _post(client, low_ingredient, price="-100")
    assert r.status_code == 400


def test_post_registrar_unknown_ingredient_404(client):
    r = _post(client, 999999)
    assert r.status_code == 404


def test_post_registrar_rate_limited_after_burst(client, session_factory):
    """After 10 accepted writes the next POST must 429."""
    with session_factory() as s:
        ids = []
        for i in range(12):
            ing = Ingredient(
                name=f"Rate ing {i}",
                unit="kg",
                stock_qty=0.0,
                min_stock_qty=5.0,
                purchase_price_gs=1000,
            )
            s.add(ing)
            s.flush()
            ids.append(ing.id)
        s.commit()

    statuses = []
    for ing_id in ids:
        resp = _post(client, ing_id, qty="1", price="1000")
        statuses.append(resp.status_code)
        if resp.status_code == 429:
            break

    assert 429 in statuses, f"Expected a 429 in statuses, got: {statuses}"
    # First 10 must have gone through before the limit kicked in.
    assert statuses[:10] == [303] * 10, f"statuses: {statuses}"


def test_reorder_view_has_restock_form(client, low_ingredient):
    """GET /reorder shows the per-row Reponer form with prefilled inputs."""
    r = client.get("/reorder")
    assert r.status_code == 200
    assert "/reorder/registrar" in r.text
    assert 'name="qty"' in r.text
    assert 'name="price_gs"' in r.text
    # qty prefilled with suggested qty (max 10 - stock 1 = 9)
    assert 'value="9' in r.text
    # price prefilled with current purchase price
    assert "5000" in r.text
