"""tests/test_production_scheduler.py — E32 production scheduler tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.rms.models import Ingredient, Product, Recipe, RecipeLine, Sale
from app.rms.production_scheduler import (
    ProductionDay,
    ProductionPlan,
    check_ingredient_availability,
    expected_daily_sales,
    ingredient_requirements,
    production_calendar,
    production_plan_for_day,
)


def _setup_simple_product(session):
    """Product with recipe yielding 10 units, using 1 ingredient 0.1/portion."""
    ing = Ingredient(name="psched_ing_xyz", unit="kg",
                     purchase_price_gs=1000, stock_qty=100)
    session.add(ing)
    session.flush()
    r = Recipe(name="psched_r_xyz", yield_qty=10, yield_unit="und")
    session.add(r)
    session.flush()
    session.add(RecipeLine(recipe_id=r.id, line_kind="ingredient",
                           line_ref_id=ing.id, qty=0.1))
    p = Product(name="psched_p_xyz", portion_label="und",
                sale_price_gs=5000, recipe_id=r.id)
    session.add(p)
    session.commit()
    return p, r, ing


# ---------------------------------------------------------------------------
# expected_daily_sales
# ---------------------------------------------------------------------------

def test_expected_daily_sales_no_sales(session_factory):
    with session_factory() as s:
        p, _, _ = _setup_simple_product(s)
        assert expected_daily_sales(s, p.id) == 0.0


def test_expected_daily_sales_computes(session_factory):
    with session_factory() as s:
        p, _, _ = _setup_simple_product(s)
        now = datetime.now(timezone.utc)
        for i in range(14):
            sale = Sale(sold_at=now - timedelta(days=i),
                        product_id=p.id, qty=1, unit_price_gs=5000)
            s.add(sale)
        s.commit()
        # 14 sales over 14 days = 1.0/day
        assert abs(expected_daily_sales(s, p.id) - 1.0) < 0.01


def test_expected_daily_sales_excludes_voided(session_factory):
    with session_factory() as s:
        p, _, _ = _setup_simple_product(s)
        now = datetime.now(timezone.utc)
        sale = Sale(sold_at=now, product_id=p.id, qty=10,
                    unit_price_gs=5000,
                    voided_at=now)  # voided
        s.add(sale)
        s.commit()
        assert expected_daily_sales(s, p.id) == 0.0


# ---------------------------------------------------------------------------
# production_plan_for_day
# ---------------------------------------------------------------------------

def test_production_plan_basic(session_factory):
    with session_factory() as s:
        p, _, _ = _setup_simple_product(s)
        now = datetime.now(timezone.utc)
        for i in range(14):
            sale = Sale(sold_at=now - timedelta(days=i),
                        product_id=p.id, qty=5, unit_price_gs=5000)
            s.add(sale)
        s.commit()
        plan = production_plan_for_day(s, p, safety_pct=0.20)
        # velocity = 5/day × 1.20 = 6.0, rounded → 6 units
        assert plan.target_qty == 6
        assert plan.batch_count >= 1


def test_production_plan_no_recipe_uses_default_yield(session_factory):
    with session_factory() as s:
        p = Product(name="no_recipe_p_xyz", portion_label="und",
                    sale_price_gs=1000)
        s.add(p)
        s.commit()
        plan = production_plan_for_day(s, p)
        # No sales → velocity=0 → target=max(1, 0) = 1
        assert plan.target_qty == 1


def test_production_plan_includes_reason(session_factory):
    with session_factory() as s:
        p, _, _ = _setup_simple_product(s)
        plan = production_plan_for_day(s, p)
        assert "velocity" in plan.reason
        assert "safety" in plan.reason


# ---------------------------------------------------------------------------
# ingredient_requirements + check_ingredient_availability
# ---------------------------------------------------------------------------

def test_ingredient_requirements(session_factory):
    with session_factory() as s:
        p, _, ing = _setup_simple_product(s)
        plan = ProductionPlan(product_id=p.id, product_name=p.name,
                              target_qty=10, reason="test", batch_count=1)
        reqs = ingredient_requirements(s, plan)
        assert len(reqs) == 1
        assert reqs[0][0] == ing.id
        # 1 batch × 0.1 kg per portion = 0.1 kg
        assert reqs[0][1] == 0.1


def test_ingredient_requirements_no_recipe_returns_empty(session_factory):
    with session_factory() as s:
        p = Product(name="no_r_p_xyz", portion_label="und",
                    sale_price_gs=1000)
        s.add(p)
        s.commit()
        plan = ProductionPlan(product_id=p.id, product_name=p.name,
                              target_qty=1, reason="test", batch_count=1)
        assert ingredient_requirements(s, plan) == []


def test_check_ingredient_availability_has_stock(session_factory):
    with session_factory() as s:
        p, _, ing = _setup_simple_product(s)
        ing.stock_qty = 100
        s.commit()
        plan = ProductionPlan(product_id=p.id, product_name=p.name,
                              target_qty=1, reason="test", batch_count=1)
        shortages = check_ingredient_availability(s, plan)
        assert shortages == []


def test_check_ingredient_availability_shortage(session_factory):
    with session_factory() as s:
        p, _, ing = _setup_simple_product(s)
        ing.stock_qty = 0.01  # Not enough for 0.1
        s.commit()
        plan = ProductionPlan(product_id=p.id, product_name=p.name,
                              target_qty=1, reason="test", batch_count=1)
        shortages = check_ingredient_availability(s, plan)
        assert len(shortages) == 1
        s_obj = shortages[0]
        assert s_obj.ingredient_id == ing.id
        assert s_obj.deficit > 0


# ---------------------------------------------------------------------------
# production_calendar
# ---------------------------------------------------------------------------

def test_production_calendar_returns_n_days(session_factory):
    with session_factory() as s:
        _setup_simple_product(s)
        cal = production_calendar(s, days=3)
        assert len(cal) == 3


def test_production_calendar_has_date_and_plans(session_factory):
    with session_factory() as s:
        _setup_simple_product(s)
        cal = production_calendar(s, days=1)
        day = cal[0]
        assert isinstance(day, ProductionDay)
        assert len(day.date) == 10  # YYYY-MM-DD
        assert isinstance(day.plans, list)


def test_production_calendar_handles_no_sales(session_factory):
    with session_factory() as s:
        _setup_simple_product(s)
        cal = production_calendar(s, days=5)
        # No sales → multiplier all 1.0, target=1 each.
        for day in cal:
            for plan in day.plans:
                assert plan.target_qty == 1


def test_production_calendar_includes_all_products(session_factory):
    with session_factory() as s:
        for i in range(3):
            s.add(Product(name=f"cal_p_{i}_xyz", portion_label="und",
                          sale_price_gs=1000))
        s.commit()
        cal = production_calendar(s, days=1)
        assert len(cal[0].plans) == 3
