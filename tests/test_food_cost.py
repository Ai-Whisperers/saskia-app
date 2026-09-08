"""tests/test_food_cost.py — E33 true food cost tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.rms.food_cost import (
    FoodCostReport,
    actual_ingredient_consumption,
    food_cost_report,
    sales_revenue,
    theoretical_food_cost,
    waste_cost,
)
from app.rms.models import (
    Ingredient,
    Product,
    Recipe,
    RecipeLine,
    Sale,
    SaleStockMove,
    WasteLog,
)


def _setup_recipe_chain(session, name="fc_xyz"):
    """Recipe with 1 ingredient 0.1kg @ 1000 Gs/kg. Yield 10."""
    ing = Ingredient(name=f"{name}_ing", unit="kg",
                     purchase_price_gs=1000)
    session.add(ing)
    session.flush()
    r = Recipe(name=f"{name}_r", yield_qty=10, yield_unit="und")
    session.add(r)
    session.flush()
    session.add(RecipeLine(recipe_id=r.id, line_kind="ingredient",
                           line_ref_id=ing.id, qty=0.1))
    p = Product(name=f"{name}_p", portion_label="und",
                sale_price_gs=5000, recipe_id=r.id)
    session.add(p)
    session.commit()
    return p, r, ing


# ---------------------------------------------------------------------------
# sales_revenue
# ---------------------------------------------------------------------------

def test_sales_revenue_empty(session_factory):
    with session_factory() as s:
        assert sales_revenue(s,
                            datetime.now(timezone.utc) - timedelta(days=10),
                            datetime.now(timezone.utc)) == 0


def test_sales_revenue_computes(session_factory):
    with session_factory() as s:
        p, _, _ = _setup_recipe_chain(s)
        now = datetime.now(timezone.utc)
        # 3 sales × qty=2 × price=5000 = 30000
        for _ in range(3):
            s.add(Sale(sold_at=now, product_id=p.id, qty=2,
                       unit_price_gs=5000))
        s.commit()
        rev = sales_revenue(s, now - timedelta(hours=1), now + timedelta(hours=1))
        assert rev == 30000


def test_sales_revenue_excludes_voided(session_factory):
    with session_factory() as s:
        p, _, _ = _setup_recipe_chain(s)
        now = datetime.now(timezone.utc)
        s.add(Sale(sold_at=now, product_id=p.id, qty=10,
                   unit_price_gs=5000, voided_at=now))
        s.commit()
        rev = sales_revenue(s, now - timedelta(hours=1),
                            now + timedelta(hours=1))
        assert rev == 0


# ---------------------------------------------------------------------------
# theoretical_food_cost
# ---------------------------------------------------------------------------

def test_theoretical_food_cost_computes(session_factory):
    with session_factory() as s:
        p, _, _ = _setup_recipe_chain(s)
        now = datetime.now(timezone.utc)
        # Recipe batch=10 × 100 Gs = 100 Gs/batch. Per portion: 100/10 = 10 Gs.
        s.add(Sale(sold_at=now, product_id=p.id, qty=1, unit_price_gs=5000))
        s.commit()
        cost = theoretical_food_cost(s, now - timedelta(hours=1),
                                     now + timedelta(hours=1))
        assert cost == 10  # 1 portion × 10 Gs/portion


def test_theoretical_food_cost_no_recipe_returns_zero(session_factory):
    with session_factory() as s:
        p = Product(name="fc_no_r_xyz", portion_label="und",
                    sale_price_gs=1000)
        s.add(p)
        s.flush()
        now = datetime.now(timezone.utc)
        s.add(Sale(sold_at=now, product_id=p.id, qty=5, unit_price_gs=1000))
        s.commit()
        cost = theoretical_food_cost(s, now - timedelta(hours=1),
                                     now + timedelta(hours=1))
        assert cost == 0


# ---------------------------------------------------------------------------
# actual_ingredient_consumption
# ---------------------------------------------------------------------------

def test_actual_consumption_computes(session_factory):
    with session_factory() as s:
        p, _, ing = _setup_recipe_chain(s)
        now = datetime.now(timezone.utc)
        sale = Sale(sold_at=now, product_id=p.id, qty=1, unit_price_gs=5000)
        s.add(sale)
        s.flush()
        # 5 negative moves of 0.1kg = 0.5kg × 1000 Gs/kg = 500
        for _ in range(5):
            s.add(SaleStockMove(sale_id=sale.id, affected_recipe_id=p.recipe_id,
                                ingredient_id=ing.id, qty_delta=-0.1))
        s.commit()
        cost = actual_ingredient_consumption(s, now - timedelta(hours=1),
                                             now + timedelta(hours=1))
        assert cost == 500


def test_actual_consumption_ignores_positive_moves(session_factory):
    """Voided sales have positive qty_delta — should NOT count as consumption."""
    with session_factory() as s:
        p, _, ing = _setup_recipe_chain(s)
        now = datetime.now(timezone.utc)
        sale = Sale(sold_at=now, product_id=p.id, qty=1, unit_price_gs=5000)
        s.add(sale)
        s.flush()
        s.add(SaleStockMove(sale_id=sale.id, affected_recipe_id=p.recipe_id,
                            ingredient_id=ing.id, qty_delta=+0.5))  # void
        s.commit()
        cost = actual_ingredient_consumption(s, now - timedelta(hours=1),
                                             now + timedelta(hours=1))
        assert cost == 0


# ---------------------------------------------------------------------------
# waste_cost
# ---------------------------------------------------------------------------

def test_waste_cost_empty(session_factory):
    with session_factory() as s:
        assert waste_cost(s,
                         datetime.now(timezone.utc) - timedelta(days=1),
                         datetime.now(timezone.utc)) == 0


def test_waste_cost_computes(session_factory):
    with session_factory() as s:
        _, _, ing = _setup_recipe_chain(s)
        now = datetime.now(timezone.utc)
        s.add(WasteLog(ingredient_id=ing.id, qty=1.0, reason="spillage",
                       cost_gs=2000, recorded_at=now))
        s.add(WasteLog(ingredient_id=ing.id, qty=0.5, reason="spoiled",
                       cost_gs=500, recorded_at=now))
        s.commit()
        cost = waste_cost(s, now - timedelta(hours=1),
                          now + timedelta(hours=1))
        assert cost == 2500


# ---------------------------------------------------------------------------
# food_cost_report (integration)
# ---------------------------------------------------------------------------

def test_food_cost_report_basic(session_factory):
    with session_factory() as s:
        p, _, ing = _setup_recipe_chain(s)
        now = datetime.now(timezone.utc)
        sale = Sale(sold_at=now, product_id=p.id, qty=2, unit_price_gs=5000)
        s.add(sale)
        s.flush()
        s.add(SaleStockMove(sale_id=sale.id, affected_recipe_id=p.recipe_id,
                            ingredient_id=ing.id, qty_delta=-0.2))
        s.commit()

        report = food_cost_report(s, period_days=30)
        assert isinstance(report, FoodCostReport)
        # Revenue = 2 × 5000 = 10000
        assert report.sales_revenue_gs == 10000
        # Theoretical = 2 portions × (100 Gs/batch / 10 yield) = 20 Gs
        assert report.theoretical_food_cost_gs == 20
        # Actual = 0.2 kg × 1000 = 200
        assert report.actual_food_cost_gs == 200
        # Waste = 0
        assert report.waste_cost_gs == 0
        # Theoretical % = 20/10000 × 100 = 0.2%
        assert report.theoretical_food_cost_pct == pytest.approx(0.2)
        # Actual % = 200/10000 = 2%
        assert report.actual_food_cost_pct == 2.0


def test_food_cost_report_no_revenue(session_factory):
    with session_factory() as s:
        report = food_cost_report(s, period_days=30)
        assert report.sales_revenue_gs == 0
        assert report.theoretical_food_cost_pct == 0.0


def test_food_cost_report_period_format(session_factory):
    with session_factory() as s:
        report = food_cost_report(s, period_days=7)
        assert len(report.period_start) == 10  # YYYY-MM-DD
        assert len(report.period_end) == 10
