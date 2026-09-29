"""tests/test_production.py — verify app/rms/production.py (E21).

Per docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md E21.

Covers:
- forecast_sales: 0 sales returns 0; N sales over N days returns avg
- plan_production: rows + lines computed; seasonal multiplier applied
- plan_production with manual_forecast overrides
- plan_production: stock_on_hand + qty_to_buy computed
- plan_production handles empty DB (returns empty plan)
- plan_production surfaces seasonal notes
"""
# allow-hardcoded-dates: production batch fixture uses fixed dates
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.rms.models import Recipe, RecipeLine, Sale
from app.rms.production import (
    forecast_sales,
    plan_production,
)
from tests.factories import make_ingredient, make_product


def test_forecast_sales_zero_when_no_history(session_factory):
    s = session_factory()
    try:
        prod = make_product(s, name="Muffin", sale_price_gs=2500)
        s.add(prod)
        s.commit()
        assert forecast_sales(s, product_id=prod.id, days_history=14) == 0.0
    finally:
        s.close()


def test_forecast_sales_average_over_window(session_factory):
    """14 sales over 14 days -> forecast = 1.0 per day."""
    s = session_factory()
    try:
        prod = make_product(s, name="Muffin", sale_price_gs=2500)
        s.add(prod)
        s.flush()
        now = datetime.now(timezone.utc)
        for i in range(14):
            s.add(Sale(
                sold_at=now - timedelta(days=i),
                product_id=prod.id,
                qty=1,
                unit_price_gs=2500,
            ))
        s.commit()
        f = forecast_sales(s, product_id=prod.id, days_history=14)
        assert abs(f - 1.0) < 0.01
    finally:
        s.close()


def test_forecast_excludes_voided(session_factory):
    """Voided sales excluded from forecast."""
    s = session_factory()
    try:
        prod = make_product(s, name="Muffin", sale_price_gs=2500)
        s.add(prod)
        s.flush()
        now = datetime.now(timezone.utc)
        for i in range(10):
            s.add(Sale(
                sold_at=now - timedelta(days=i),
                product_id=prod.id,
                qty=1,
                unit_price_gs=2500,
            ))
        # 5 voided
        for i in range(10, 15):
            s.add(Sale(
                sold_at=now - timedelta(days=i),
                product_id=prod.id,
                qty=1,
                unit_price_gs=2500,
                voided_at=now,
            ))
        s.commit()
        # Only the 10 non-voided count
        f = forecast_sales(s, product_id=prod.id, days_history=14)
        assert abs(f - (10/14)) < 0.01
    finally:
        s.close()


def test_plan_production_empty_db(session_factory):
    s = session_factory()
    try:
        plan = plan_production(s, for_date=date(2026, 12, 25))
        assert plan.rows == []
        assert plan.lines == []
        assert plan.total_ingredients_needed == 0
    finally:
        s.close()


def test_plan_production_computes_lines_from_recipes(session_factory):
    """Recipe expansion: 1 muffin recipe requires 0.3kg harina; if we
    forecast 10 muffins, we need 3kg harina."""
    s = session_factory()
    try:
        ing = make_ingredient(s, name="harina", unit="kg", stock_qty=0.0, purchase_price_gs=4500)
        rec = Recipe(name="Muffin", yield_qty=12.0, yield_unit="und")
        s.add_all([ing, rec])
        s.flush()
        s.add(RecipeLine(
            recipe_id=rec.id, line_kind="ingredient",
            line_ref_id=ing.id, qty=0.3,
        ))
        prod = make_product(s, name="Muffin", sale_price_gs=2500, recipe_id=rec.id)
        s.add(prod)
        s.flush()
        # 5 muffins sold today -> forecast ~0.36/day (rounded down)
        now = datetime.now(timezone.utc)
        for i in range(5):
            s.add(Sale(
                sold_at=now - timedelta(days=i),
                product_id=prod.id,
                qty=1,
                unit_price_gs=2500,
            ))
        s.commit()

        plan = plan_production(s, for_date=date(2026, 6, 1))  # no event
        assert len(plan.rows) == 1
        # PRO-02 fix: forecast_sales returns ~0.36 muffins, but we round UP
        # to a whole piece before display (a bakery cannot bake 0.1 of a muffin).
        assert plan.rows[0].qty_to_produce == 1
        # Ingredient requirement: forecast_qty * 0.3 kg/muffin (uses pre-rounding qty)
        assert len(plan.lines) == 1
        assert plan.lines[0].ingredient_name == "harina"
        assert plan.lines[0].unit == "kg"
        # Stock on hand is 0; need to buy
        assert plan.lines[0].qty_to_buy > 0
    finally:
        s.close()


def test_plan_production_with_seasonal_multiplier(session_factory):
    """Multiplicador 2x duplica el forecast (PRO-02: both round UP to integer)."""
    s = session_factory()
    try:
        prod = make_product(s, name="Torta", sale_price_gs=25000, recipe_id=None)
        s.add(prod)
        s.flush()
        now = datetime.now(timezone.utc)
        for i in range(7):
            s.add(Sale(
                sold_at=now - timedelta(days=i),
                product_id=prod.id,
                qty=1,
                unit_price_gs=25000,
            ))
        s.commit()

        # Without seasonal (1.0): forecast = 7/14 = 0.5, rounds UP to 1
        plan_normal = plan_production(
            s, for_date=date(2026, 1, 1), seasonal_multiplier=1.0
        )
        # With 2x seasonal: forecast = 1.0, rounds UP to 1
        plan_double = plan_production(
            s, for_date=date(2026, 1, 1), seasonal_multiplier=2.0
        )
        # PRO-02: both are now whole integers. Before the ceiling rule
        # these would have been 0.5 and 1.0 (asserting 0.5 < 1.0).
        assert plan_normal.rows[0].qty_to_produce == 1
        assert plan_double.rows[0].qty_to_produce == 1

        # Use a scenario where the multiplier DOES bump the count:
        # 11 sales over 14d = 0.79, with 2x = 1.57 -> rounds up to 2.
        prod2 = make_product(s, name="Torta grande", sale_price_gs=50000, recipe_id=None)
        s.add(prod2)
        s.flush()
        for i in range(11):
            s.add(Sale(
                sold_at=now - timedelta(days=i % 14),
                product_id=prod2.id,
                qty=1,
                unit_price_gs=50000,
            ))
        s.commit()
        plan2_normal = plan_production(s, for_date=date(2026, 1, 1), seasonal_multiplier=1.0)
        plan2_double = plan_production(s, for_date=date(2026, 1, 1), seasonal_multiplier=2.0)
        # Find the Torta grande row (rows[0] is "Torta" because of insertion order)
        tgrande_normal = next(r for r in plan2_normal.rows if r.product_name == "Torta grande")
        tgrande_double = next(r for r in plan2_double.rows if r.product_name == "Torta grande")
        assert tgrande_normal.qty_to_produce == 1
        assert tgrande_double.qty_to_produce == 2
    finally:
        s.close()


def test_plan_production_with_manual_forecast_override(session_factory):
    """manual_forecast overrides the auto-computed forecast."""
    s = session_factory()
    try:
        prod = make_product(s, name="Torta", sale_price_gs=25000, recipe_id=None)
        s.add(prod)
        s.flush()
        # Some sales history
        now = datetime.now(timezone.utc)
        for i in range(3):
            s.add(Sale(
                sold_at=now - timedelta(days=i),
                product_id=prod.id,
                qty=1,
                unit_price_gs=25000,
            ))
        s.commit()

        plan = plan_production(
            s,
            for_date=date(2026, 1, 1),
            manual_forecast={prod.id: 50.0},  # operator override: 50 cakes
        )
        assert len(plan.rows) == 1
        assert plan.rows[0].qty_to_produce == 50.0
        assert plan.rows[0].forecast_source == "manual"
    finally:
        s.close()


def test_plan_production_stock_on_hand_subtracts_requirement(session_factory):
    """If stock on hand > qty_required, qty_to_buy = 0."""
    s = session_factory()
    try:
        ing = make_ingredient(s, name="harina", unit="kg", stock_qty=100.0, purchase_price_gs=4500)
        rec = Recipe(name="Muffin", yield_qty=12.0, yield_unit="und")
        s.add_all([ing, rec])
        s.flush()
        s.add(RecipeLine(
            recipe_id=rec.id, line_kind="ingredient",
            line_ref_id=ing.id, qty=0.05,  # 50g per muffin
        ))
        prod = make_product(s, name="Muffin", sale_price_gs=2500, recipe_id=rec.id)
        s.add(prod)
        s.flush()
        now = datetime.now(timezone.utc)
        # Few sales -> small forecast
        s.add(Sale(sold_at=now - timedelta(days=1), product_id=prod.id, qty=1, unit_price_gs=2500))
        s.commit()

        plan = plan_production(s, for_date=date(2026, 6, 1))
        # 0.05kg * forecast (0.07/day) = 0.0035kg required
        # Stock on hand 100kg > 0.0035kg -> qty_to_buy = 0
        assert plan.lines[0].stock_on_hand == 100.0
        assert plan.lines[0].qty_to_buy == 0.0
    finally:
        s.close()


def test_plan_production_surfaces_seasonal_note(session_factory):
    """When seasonal_multiplier > 1.0, a note is added."""
    s = session_factory()
    try:
        # On Christmas (3x) the note should appear
        plan = plan_production(s, for_date=date(2026, 12, 24))
        assert any("Multiplicador" in n for n in plan.notes)
        assert any("3.0" in n for n in plan.notes)
    finally:
        s.close()
