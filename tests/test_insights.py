"""tests/test_insights.py — E34 dashboard insights panel tests."""

from __future__ import annotations

from app.rms.insights import InsightsPanel, build_insights
from app.rms.models import (
    Ingredient,
    Product,
    Recipe,
    RecipeLine,
)


def _setup_minimal(session):
    """Minimal seed: 1 product with recipe + 1 ingredient."""
    ing = Ingredient(name="ins_ing_xyz", unit="kg", purchase_price_gs=1000, stock_qty=10)
    session.add(ing)
    session.flush()
    r = Recipe(name="ins_r_xyz", yield_qty=10, yield_unit="und")
    session.add(r)
    session.flush()
    session.add(RecipeLine(recipe_id=r.id, line_kind="ingredient", line_ref_id=ing.id, qty=0.1))
    p = Product(name="ins_p_xyz", portion_label="und", sale_price_gs=5000, recipe_id=r.id)
    session.add(p)
    session.commit()
    return p, r, ing


def test_build_insights_returns_panel(session_factory):
    with session_factory() as s:
        _setup_minimal(s)
        panel = build_insights(s)
        assert isinstance(panel, InsightsPanel)
        assert panel.generated_at


def test_build_insights_inventory_capital(session_factory):
    with session_factory() as s:
        _, _, ing = _setup_minimal(s)
        ing.stock_qty = 5
        s.commit()
        panel = build_insights(s)
        # 5 × 1000 = 5000
        assert panel.inventory_capital_gs == 5000


def test_build_insights_menu_quadrants_keys(session_factory):
    with session_factory() as s:
        _setup_minimal(s)
        panel = build_insights(s)
        # All 4 quadrants present, even if empty.
        assert "star" in panel.menu_quadrants
        assert "puzzle" in panel.menu_quadrants
        assert "plowhorse" in panel.menu_quadrants
        assert "dog" in panel.menu_quadrants


def test_build_insights_production_tomorrow_is_list(session_factory):
    with session_factory() as s:
        _setup_minimal(s)
        panel = build_insights(s)
        assert isinstance(panel.production_tomorrow, list)


def test_build_insights_food_cost_is_report(session_factory):
    with session_factory() as s:
        _setup_minimal(s)
        panel = build_insights(s)
        # FoodCostReport dataclass
        assert hasattr(panel.food_cost, "sales_revenue_gs")
        assert hasattr(panel.food_cost, "theoretical_food_cost_gs")


def test_build_insights_rising_churning_are_lists(session_factory):
    with session_factory() as s:
        _setup_minimal(s)
        panel = build_insights(s)
        assert isinstance(panel.rising_products, list)
        assert isinstance(panel.churning_products, list)


def test_build_insights_peak_hour_int(session_factory):
    with session_factory() as s:
        _setup_minimal(s)
        panel = build_insights(s)
        assert isinstance(panel.sales_peak_hour, int)


def test_build_insights_no_data_does_not_raise(session_factory):
    """Empty DB → panel still builds, all zeros/lists."""
    with session_factory() as s:
        panel = build_insights(s)
        assert panel.inventory_capital_gs == 0
        assert panel.menu_quadrants["star"] == []
        assert panel.production_tomorrow == []
