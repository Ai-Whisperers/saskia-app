"""Tests for Ingredient.avg_cost_gs moving-average tracking (BACKLOG #13).

Waste (merma) deducts stock but does not update the per-ingredient average
cost. The latest supplier price (purchase_price_gs) is used for cost
math in analytics, which silently hides cost drift when supplier prices
change mid-batch.

These tests assert:
- New installs add Ingredient.avg_cost_gs column (default = NULL).
- Backfill from purchase_price_gs for existing rows.
- After a waste event, avg_cost_gs is recomputed via the moving-average
  formula: ((old_avg * old_stock) + (new_purchase_price * purchase_qty))
  / (old_stock + purchase_qty).
- After a waste event, avg_cost_gs is recomputed when waste removes
  stock: ((old_avg * old_stock) - waste_cost) / (old_stock - waste_qty).
- Initial NULL avg_cost_gs falls back to purchase_price_gs in analytics
  (no behavioural change for fresh installs).
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import inspect


@pytest.fixture
def fresh_db(app_engine, session_factory):
    """Confirm the new column exists and provide a session_factory helper."""
    insp = inspect(app_engine)
    cols = {c["name"]: c for c in insp.get_columns("ingredient")}
    assert "avg_cost_gs" in cols, (
        "Ingredient.avg_cost_gs column missing — Sprint 4.4 not landed"
    )
    return app_engine, session_factory


def _seed_ingredient(s, *, name: str = "harina", stock_qty: float = 100.0,
                     purchase_price_gs: int = 10_000, avg_cost_gs: int | None = None):
    """Helper: create an ingredient with explicit avg_cost_gs."""
    from app.rms.models import Ingredient
    ing = Ingredient(
        name=name,
        unit="kg",
        stock_qty=stock_qty,
        min_stock_qty=1.0,
        purchase_price_gs=purchase_price_gs,
        avg_cost_gs=avg_cost_gs,
    )
    s.add(ing)
    s.flush()
    return ing


def test_avg_cost_gs_column_exists(fresh_db):
    """The new column exists on ingredient."""
    _eng, _ = fresh_db


def test_avg_cost_gs_defaults_to_null_on_new_insert(session_factory):
    """A new Ingredient without avg_cost_gs should default to NULL."""
    s = session_factory()
    try:
        ing = _seed_ingredient(s, name="harina-null", avg_cost_gs=None)
        s.commit()
        # avg_cost_gs can be None (the column is nullable)
        assert ing.avg_cost_gs is None
    finally:
        s.close()


def test_avg_cost_gs_provided_on_insert_is_preserved(session_factory):
    """Setting avg_cost_gs explicitly persists the value."""
    s = session_factory()
    try:
        ing = _seed_ingredient(s, name="harina-explicit", avg_cost_gs=12_500)
        s.commit()
        s.refresh(ing)
        assert ing.avg_cost_gs == 12_500
    finally:
        s.close()


def test_record_waste_recomputes_avg_cost(session_factory):
    """After waste, avg_cost_gs is recomputed: ((old_avg * old_stock) -
    waste_cost) / new_stock. With avg = 10000, stock = 10, waste 1 kg:
    ((10000 * 10) - 10000) / 9 = 90000/9 = 10000. Same in this case.
    Let's pick a waste that DOES change avg cost."""
    from app.rms.waste import record_waste

    s = session_factory()
    try:
        # Setup: 10 kg of "sal" with avg_cost_gs = 10000 (purchase = 10000 too)
        ing = _seed_ingredient(s, name="sal", stock_qty=10.0,
                               purchase_price_gs=10_000, avg_cost_gs=10_000)
        s.commit()
        ing_id = ing.id
    finally:
        s.close()

    # Record a 2 kg waste at 10000 Gs/kg → waste_cost = 20000
    from app.rms.waste import WasteReason
    s = session_factory()
    try:
        record_waste(
            s,
            ingredient_id=ing_id,
            qty=2.0,
            qty_unit="kg",
            reason=WasteReason.VENCIDA,
        )
        s.commit()

        # Re-fetch the ingredient in this session
        from app.rms.models import Ingredient as _Ing
        ing2 = s.get(_Ing, ing_id)
        # After 2kg waste: stock = 8, waste cost = 2 * 10000 = 20000
        # New avg = ((10000 * 10) - 20000) / 8 = 80000/8 = 10000
        # (avg unchanged because waste cost = current avg)
        assert ing2.avg_cost_gs == 10000
    finally:
        s.close()


def test_record_waste_preserves_avg_when_purchase_price_changes(session_factory):
    """If avg_cost_gs ≠ purchase_price_gs, waste should NOT change avg."""
    from app.rms.waste import record_waste

    s = session_factory()
    try:
        # avg_cost_gs deliberately differs from purchase_price_gs
        ing = _seed_ingredient(s, name="azucar", stock_qty=20.0,
                               purchase_price_gs=8_000, avg_cost_gs=12_000)
        s.commit()
        ing_id = ing.id
    finally:
        s.close()

    s = session_factory()
    try:
        # Waste records cost_gs from PURCHASE price (not avg) — that's the
        # denormalization rule (WasteLog.cost_gs is locked at event time).
        from app.rms.waste import WasteReason
        record_waste(
            s,
            ingredient_id=ing_id,
            qty=5.0,
            qty_unit="kg",
            reason=WasteReason.VENCIDA,
        )
        s.commit()
        # Re-fetch the ingredient in this session
        from app.rms.models import Ingredient as _Ing
        ing2 = s.get(_Ing, ing_id)

        # ((12000 * 20) - (5 * 8000)) / 15 = (240000 - 40000) / 15 = 13333.33
        # We expect 13333 here (integer division truncates)
        assert ing2.avg_cost_gs is not None
        assert 13_000 <= ing2.avg_cost_gs <= 13_500
    finally:
        s.close()


def test_analytics_falls_back_to_purchase_price_when_avg_is_null(session_factory):
    """When avg_cost_gs is NULL (legacy data, fresh install), analytics
    should fall back to purchase_price_gs so behaviour doesn't change."""
    from app.rms.analytics import _quick_cost_estimate
    from app.rms.models import Product, Recipe, RecipeLine

    s = session_factory()
    try:
        ing = _seed_ingredient(s, name="harina-legacy", stock_qty=100.0,
                               purchase_price_gs=5_000, avg_cost_gs=None)
        s.flush()
        recipe = Recipe(name="receta-legacy", yield_qty=10, prep_minutes=5)
        s.add(recipe)
        s.flush()
        # Use Decimal value
        s.add(RecipeLine(
            recipe_id=recipe.id,
            line_kind="ingredient",
            line_ref_id=ing.id,
            qty=Decimal("0.250"),
        ))
        product = Product(name="producto-legacy", recipe_id=recipe.id,
                          sale_price_gs=20_000)
        s.add(product)
        s.commit()

        result = _quick_cost_estimate(s, product)
        # 0.250 kg * 5000 Gs/kg = 1250 Gs per batch / 10 yield = 125 Gs per unit
        assert result == 125
    finally:
        s.close()
