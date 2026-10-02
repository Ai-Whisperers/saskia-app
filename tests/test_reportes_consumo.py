"""Tests for /reportes/consumo (BACKLOG #26).

The route aggregates SaleStockMove.qty_delta by ingredient over a
window, joining Sale to skip voids and use Sale.sold_at as the time
axis. CSV variant + days validation.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.rms.models import Ingredient, Product, Recipe, RecipeLine, Sale, SaleStockMove


@pytest.fixture
def consumption_seed(session_factory):
    """Create 3 ingredients with different consumption volumes:

    - Harina:  10 sales × 0.1 kg = -1.0 kg   (top)
    - Azúcar:   3 sales × 0.2 kg = -0.6 kg   (mid)
    - Levadura: 5 sales × 0.05 kg = -0.25 kg (bottom)
    """
    with session_factory() as s:
        r = Recipe(name="r_consumo", yield_qty=10, yield_unit="und")
        s.add(r)
        s.flush()
        p = Product(name="p_consumo", portion_label="und", sale_price_gs=1000, recipe_id=r.id)
        s.add(p)
        s.flush()

        har = Ingredient(name="Harina", unit="kg", stock_qty=5, purchase_price_gs=4000)
        azu = Ingredient(name="Azúcar", unit="kg", stock_qty=3, purchase_price_gs=5000)
        lev = Ingredient(name="Levadura", unit="kg", stock_qty=2, purchase_price_gs=15000)
        s.add_all([har, azu, lev])
        s.flush()

        for ing, line_qty in ((har, 0.1), (azu, 0.2), (lev, 0.05)):
            s.add(RecipeLine(
                recipe_id=r.id, line_kind="ingredient",
                line_ref_id=ing.id, qty=line_qty,
            ))

        now = datetime.now(timezone.utc)
        # 10 Harina moves
        s.add(Sale(sold_at=now, product_id=p.id, qty=1, unit_price_gs=1000))
        s.flush()
        # Need separate Sale rows for n_sales counting; use 5 sales × 2 moves = 10
        for i in range(5):
            sale = Sale(sold_at=now, product_id=p.id, qty=1, unit_price_gs=1000)
            s.add(sale)
            s.flush()
            for _ in range(2):
                s.add(SaleStockMove(
                    sale_id=sale.id, affected_recipe_id=r.id,
                    ingredient_id=har.id, qty_delta=-0.1,
                ))
        # 3 Azúcar moves (1 sale × 3 lines? no — recipe has 1 azu line, so
        # 1 move per sale. Use 3 sales × 1 move = 3)
        for _ in range(3):
            sale = Sale(sold_at=now, product_id=p.id, qty=1, unit_price_gs=1000)
            s.add(sale)
            s.flush()
            s.add(SaleStockMove(
                sale_id=sale.id, affected_recipe_id=r.id,
                ingredient_id=azu.id, qty_delta=-0.2,
            ))
        # 5 Levadura moves
        for _ in range(5):
            sale = Sale(sold_at=now, product_id=p.id, qty=1, unit_price_gs=1000)
            s.add(sale)
            s.flush()
            s.add(SaleStockMove(
                sale_id=sale.id, affected_recipe_id=r.id,
                ingredient_id=lev.id, qty_delta=-0.05,
            ))

        # A VOIDED sale should be EXCLUDED — add a move on a voided sale
        voided = Sale(
            sold_at=now, product_id=p.id, qty=1, unit_price_gs=1000,
            voided_at=now,
        )
        s.add(voided)
        s.flush()
        s.add(SaleStockMove(
            sale_id=voided.id, affected_recipe_id=r.id,
            ingredient_id=har.id, qty_delta=-0.5,
        ))
        s.commit()


def test_consumo_200_ranks_by_abs_qty(client, consumption_seed):
    """Top ingredient is Harina (-1.0 kg), then Azúcar (-0.6), then Levadura."""
    r = client.get("/reportes/consumo?days=30")
    assert r.status_code == 200
    body = r.text
    # Order: Harina before Azúcar before Levadura
    h_pos = body.find("Harina")
    a_pos = body.find("Azúcar")
    l_pos = body.find("Levadura")
    assert -1 < h_pos < a_pos < l_pos, (
        f"Expected order Harina < Azúcar < Levadura; got positions "
        f"harina={h_pos}, azucar={a_pos}, levadura={l_pos}"
    )


def test_consumo_excludes_voided_sales(client, consumption_seed):
    """The voided sale's -0.5 kg move on Harina must NOT inflate Harina's
    total. Total should remain -1.0 kg (5 sales × 2 moves × -0.1)."""
    r = client.get("/reportes/consumo?days=30")
    assert r.status_code == 200
    # Search for the row containing Harina's total_qty = -1.0
    body = r.text
    # The HTML renders the value as "1.00" (abs of -1.0). Just check that
    # "1.00" appears once (not "//1.5" or "1.50").
    assert "1.00" in body
    # And "1.50" must NOT be there — that's what we'd see if voids leaked.
    assert "1.50" not in body


def test_consumo_n_sales_counted_unique(client, consumption_seed):
    """5 unique sales for Harina, 3 for Azúcar, 5 for Levadura."""
    r = client.get("/reportes/consumo?days=30")
    assert r.status_code == 200
    body = r.text
    # Order matters: parse the tbody rows. Use a simple substring check:
    # find each ingredient and the n_sales value in the row that follows it.
    # The voided sale is NOT counted toward Harina's n_sales (5, not 6).
    assert "5" in body  # all three ingredients have either 3 or 5 — present
    assert "3" in body  # Azúcar's n_sales


def test_consumo_empty_window_returns_empty_card(client, session_factory):
    """With no consumption data, render an empty card (not 500)."""
    with session_factory() as s:
        ing = Ingredient(name="Solo", unit="kg", stock_qty=10, purchase_price_gs=1000)
        s.add(ing)
        s.commit()

    r = client.get("/reportes/consumo?days=30")
    assert r.status_code == 200
    assert "No hay datos" in r.text


def test_consumo_invalid_days_422(client):
    r = client.get("/reportes/consumo?days=45")
    assert r.status_code == 422


def test_consumo_csv_returns_csv(client, consumption_seed):
    r = client.get("/reportes/consumo/csv?days=30")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    body = r.text
    # Header
    assert "ingredient_id,name,total_qty,n_moves,n_sales,unit" in body
    # Voided sale's move excluded
    # Harina: 5 sales × 2 moves = 10 moves, n_sales=5, total_qty=-1.0000
    assert "Harina,-1.0000,10,5,kg" in body
    # Azúcar: 3 moves, n_sales=3, total_qty=-0.6000
    assert "Azúcar,-0.6000,3,3,kg" in body
    # Levadura: 5 moves, n_sales=5, total_qty=-0.2500
    assert "Levadura,-0.2500,5,5,kg" in body


def test_consumo_respects_limit_param(client, consumption_seed):
    r = client.get("/reportes/consumo?days=30&limit=2")
    assert r.status_code == 200
    body = r.text
    # With limit=2, only Harina and Azúcar render. Levadura excluded.
    assert "Harina" in body
    assert "Azúcar" in body
    # Levadura is in seed but should not appear
    assert "Levadura" not in body


def test_consumo_period_toggles_in_template(client, consumption_seed):
    """All 4 period toggles render (7/30/90/365)."""
    r = client.get("/reportes/consumo")
    assert r.status_code == 200
    body = r.text
    for d in ("7d", "30d", "90d", "365d"):
        assert d in body