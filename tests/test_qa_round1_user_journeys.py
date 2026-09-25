"""tests/test_qa_round1_user_journeys.py — T9 QA gap closure (round 1).

Closes the two highest-value coverage gaps found by the QA plan
(docs/qa/round1-qa-plan.md §3):

G4 (UC3): the Q1 pipeline spans four modules — /reorder/registrar router →
  price_history → insights → three templates (inventario strip, reportes/
  precios, dashboard card). Every piece was green in isolation but no test
  proved they compose. This test drives the REAL restock POST three times
  at rising prices and asserts the whole chain in one pass.

G5 (UC1): a mixed-unit recipe (g against a kg ingredient, ml against an l
  ingredient) must produce the SAME normalized quantities through the
  costing walk and through plan_production — the T1 contract, asserted
  end-to-end in one journey instead of piecewise.

NOTE — coverage-gap closure, NOT TDD: the behavior shipped in Phases B–D.
These tests are expected to pass immediately; they exist to pin the
composition so a regression in any link fails loudly.

Refs: Saskia review round 1 (Thu 18-sep) — Q1 + T1. Spanish quotes in the
feature tests: 'cada vez que la clienta restockea tiene que cargar los
precios, y así puede ver en los paneles de gestión cuánto está ganando
realmente aunque los precios fluctúen'.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.rms.models import Ingredient, IngredientPriceEvent
from app.rms.production import plan_production


# --------------------------------------------------------------------------
# UC3 / G4 — restock → price event → strip + reporte + insight card, one pass
# --------------------------------------------------------------------------


def _seed_low_ingredient(session_factory) -> int:
    """Harina below min stock, starting price 5000 Gs/kg (no events yet)."""
    with session_factory() as s:
        ing = Ingredient(
            name="Harina journeys",
            unit="kg",
            stock_qty=1.0,
            min_stock_qty=5.0,
            max_stock_qty=10.0,
            purchase_price_gs=5000,
        )
        s.add(ing)
        s.commit()
        return ing.id


def _restock(client, ing_id: int, qty: str, price: str):
    return client.post(
        "/reorder/registrar",
        data={
            "ingredient_id": str(ing_id),
            "qty": qty,
            "price_gs": price,
            "notes": "",
        },
        follow_redirects=False,
    )


def test_restock_chain_price_event_to_insight_card(client, session_factory):
    """Three real restocks at rising prices must light up every Q1 surface.

    Prices 5000 → 5500 → 6000 → 7000: 30d avg = 5875, current = 7000
    → +19.1% stays BELOW the 20% threshold on the third post... so we use
    a fourth restock at 7500: avg(5000,5500,6000,7000,7500)=6200, current
    7500 → +21.0% crosses. The test asserts the card does NOT appear
    before crossing and DOES after — the exact user promise.
    """
    ing_id = _seed_low_ingredient(session_factory)

    # --- Before any restock: no card, no strip (baseline) ---
    r = client.get("/analisis")
    assert r.status_code == 200
    assert "Precios en alza" not in r.text

    # --- Restock 1..3: rising but below threshold ---
    assert _restock(client, ing_id, "2", "5000").status_code == 303
    assert _restock(client, ing_id, "2", "5500").status_code == 303
    assert _restock(client, ing_id, "2", "6000").status_code == 303

    with session_factory() as s:
        events = s.execute(
            select(IngredientPriceEvent).where(
                IngredientPriceEvent.ingredient_id == ing_id
            )
        ).scalars().all()
        assert [e.price_gs for e in events] == [5000, 5500, 6000]
        assert all(e.source == "restock" for e in events)
        ing = s.get(Ingredient, ing_id)
        assert ing.stock_qty == 7.0  # 1.0 + 2 + 2 + 2
        assert ing.purchase_price_gs == 6000  # denormalized to latest

    # /inventario shows the 90d strip + sparkline for 3 events
    r_inv = client.get("/inventario")
    assert r_inv.status_code == 200
    assert "90d:" in r_inv.text
    assert 'class="sparkline"' in r_inv.text
    assert "Harina journeys" in r_inv.text

    # /reportes/precios lists it with stats
    r_rep = client.get("/reportes/precios")
    assert r_rep.status_code == 200
    assert "Harina journeys" in r_rep.text

    # Dashboard: current 6000 vs avg(5000,5500,6000)=5500 → +9.1% — no card.
    r_mid = client.get("/")
    assert r_mid.status_code == 200
    assert "Precios en alza" not in r_mid.text

    # --- Restock 4: crosses the 20% threshold ---
    assert _restock(client, ing_id, "1", "7500").status_code == 303

    r_final = client.get("/analisis")
    assert r_final.status_code == 200
    assert "Precios en alza" in r_final.text
    assert "Harina journeys" in r_final.text
    assert "+25%" in r_final.text  # 7500 vs avg(5000,5500,6000,7500)=6000 = +25.0%

    with session_factory() as s:
        ing = s.get(Ingredient, ing_id)
        assert ing.stock_qty == 8.0
        assert ing.purchase_price_gs == 7500


# --------------------------------------------------------------------------
# UC1 / G5 — mixed-unit recipe: costing and plan must agree, one journey
# --------------------------------------------------------------------------


def test_mixed_unit_recipe_costs_and_plans_consistently(session_factory):
    """Recipe 'Pan' with mixed units (Saskia's T1 complaint):
    - harina stored in kg @ 5000 Gs/kg, recipe line 500 g
    - leche stored in l  @ 8000 Gs/l,  recipe line 250 ml
    - yield 12 und

    Batch cost via costing walk = 0.5×5000 + 0.25×8000 = 4500 Gs.
    plan_production for 24 portions (2 batches) must require exactly
    1.0 kg harina and 0.5 l leche — same normalization, both engines.
    """
    from app.rms.costing import recipe_batch_cost_gs
    from app.rms.models import Product, Recipe, RecipeLine

    s = session_factory()
    try:
        harina = Ingredient(
            name="Harina g", unit="kg", stock_qty=5.0, purchase_price_gs=5000
        )
        leche = Ingredient(
            name="Leche ml", unit="l", stock_qty=2.0, purchase_price_gs=8000
        )
        rec = Recipe(name="Pan mixto", yield_qty=12.0, yield_unit="und")
        s.add_all([harina, leche, rec])
        s.flush()
        s.add_all(
            [
                RecipeLine(
                    recipe_id=rec.id,
                    line_kind="ingredient",
                    line_ref_id=harina.id,
                    qty=500.0,
                    line_unit="g",
                ),
                RecipeLine(
                    recipe_id=rec.id,
                    line_kind="ingredient",
                    line_ref_id=leche.id,
                    qty=250.0,
                    line_unit="ml",
                ),
            ]
        )
        prod = Product(name="Pan mixto", sale_price_gs=8000, recipe_id=rec.id)
        s.add(prod)
        s.commit()
        product_id, recipe_id = prod.id, rec.id
    finally:
        s.close()

    # --- Costing engine: batch cost in Gs ---
    s = session_factory()
    try:
        result = recipe_batch_cost_gs(s, recipe_id)
        assert result.batch_cost_gs is not None, f"missing: {result.missing_ingredient_names}"
        assert result.batch_cost_gs == 4500, (
            f"expected 4500, got {result.batch_cost_gs}"
        )
    finally:
        s.close()

    # --- Planning engine: 24 portions = 2 batches ---
    s = session_factory()
    try:
        plan = plan_production(
            s,
            for_date=date(2026, 6, 1),
            manual_forecast={product_id: 24.0},
        )
        # lines are keyed by ingredient name in the plan output
        harina_line = next(
            (l for l in plan.lines if "Harina" in l.ingredient_name), None
        )
        leche_line = next(
            (l for l in plan.lines if "Leche" in l.ingredient_name), None
        )
        assert harina_line is not None, f"no harina line in {plan.lines}"
        assert leche_line is not None, f"no leche line in {plan.lines}"
        # 500 g × 2 batches = 1.0 kg (ingredient unit); 250 ml × 2 = 0.5 l
        assert abs(harina_line.qty_required - 1.0) < 1e-6, (
            f"harina {harina_line.qty_required}"
        )
        assert abs(leche_line.qty_required - 0.5) < 1e-6, (
            f"leche {leche_line.qty_required}"
        )
        # Cross-check: quantities priced at ingredient prices == 2 × batch cost
        priced = (
            harina_line.qty_required * 5000 + leche_line.qty_required * 8000
        )
        assert abs(priced - 2 * 4500) < 1e-6
    finally:
        s.close()
