"""tests/test_waste.py — verify app/rms/waste.py (E22).

Per docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md E22.

Covers:
- record_waste creates row + decrements stock
- cost is denormalized (qty * price_at_time)
- list_waste respects filters (date, reason, ingredient)
- waste_impact aggregates by reason + by ingredient
- waste_as_pct_of_revenue computes percentage
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.rms.models import Ingredient
from app.rms.models import Recipe, RecipeLine
from app.rms.waste import (
    WasteReason,
    list_waste,
    record_recipe_waste,
    record_waste,
    waste_as_pct_of_revenue,
    waste_impact,
)


def test_record_waste_creates_row_and_decrements_stock(session_factory):
    s = session_factory()
    try:
        ing = Ingredient(
            name="harina", unit="kg", stock_qty=10.0, purchase_price_gs=4500
        )
        s.add(ing)
        s.flush()
        log = record_waste(
            s,
            ingredient_id=ing.id,
            qty=0.5,
            reason=WasteReason.VENCIDA,
            recorded_by="test_user",
            notes="Olvíde en heladera",
        )
        s.commit()
        assert log.id is not None
        assert log.cost_gs == 2250  # 0.5 kg * 4500 Gs./kg
        assert ing.stock_qty == 9.5
    finally:
        s.close()


def test_record_waste_with_no_purchase_price_costs_zero(session_factory):
    """If purchase_price is NULL, cost is 0 (we don't know)."""
    s = session_factory()
    try:
        ing = Ingredient(name="x", unit="kg", stock_qty=5.0, purchase_price_gs=None)
        s.add(ing)
        s.flush()
        log = record_waste(
            s,
            ingredient_id=ing.id,
            qty=1.0,
            reason=WasteReason.QUEMADA,
        )
        s.commit()
        assert log.cost_gs == 0
    finally:
        s.close()


def test_record_waste_with_unknown_ingredient_raises(session_factory):
    s = session_factory()
    try:
        with pytest.raises(ValueError, match="not found"):
            record_waste(s, ingredient_id=99999, qty=1.0, reason=WasteReason.OTRA)
    finally:
        s.close()


def test_stock_does_not_go_negative(session_factory):
    """If waste > stock, stock floors at 0 (no negative)."""
    s = session_factory()
    try:
        ing = Ingredient(name="x", unit="kg", stock_qty=0.5, purchase_price_gs=1000)
        s.add(ing)
        s.flush()
        record_waste(s, ingredient_id=ing.id, qty=10.0, reason=WasteReason.OTRA)
        s.commit()
        assert ing.stock_qty == 0.0
    finally:
        s.close()


def test_list_waste_with_reason_filter(session_factory):
    s = session_factory()
    try:
        ing = Ingredient(name="x", unit="kg", stock_qty=10.0, purchase_price_gs=1000)
        s.add(ing)
        s.flush()
        record_waste(s, ingredient_id=ing.id, qty=1.0, reason=WasteReason.QUEMADA)
        record_waste(s, ingredient_id=ing.id, qty=1.0, reason=WasteReason.VENCIDA)
        record_waste(s, ingredient_id=ing.id, qty=1.0, reason=WasteReason.VENCIDA)
        s.commit()
        only_quemada = list_waste(s, reason=WasteReason.QUEMADA)
        assert len(only_quemada) == 1
        assert only_quemada[0].reason == "quemada"

        only_vencida = list_waste(s, reason=WasteReason.VENCIDA)
        assert len(only_vencida) == 2
    finally:
        s.close()


def test_list_waste_with_ingredient_filter(session_factory):
    s = session_factory()
    try:
        i1 = Ingredient(name="a", unit="kg", stock_qty=5.0, purchase_price_gs=1000)
        i2 = Ingredient(name="b", unit="kg", stock_qty=5.0, purchase_price_gs=2000)
        s.add_all([i1, i2])
        s.flush()
        record_waste(s, ingredient_id=i1.id, qty=1.0, reason=WasteReason.OTRA)
        record_waste(s, ingredient_id=i2.id, qty=1.0, reason=WasteReason.OTRA)
        s.commit()
        results = list_waste(s, ingredient_id=i1.id)
        assert len(results) == 1
        assert results[0].ingredient_id == i1.id
    finally:
        s.close()


def test_waste_impact_aggregates_by_reason_and_ingredient(session_factory):
    s = session_factory()
    try:
        i1 = Ingredient(name="harina", unit="kg", stock_qty=10.0, purchase_price_gs=4500)
        i2 = Ingredient(name="azúcar", unit="kg", stock_qty=10.0, purchase_price_gs=5200)
        s.add_all([i1, i2])
        s.flush()
        # harina: 1kg vencida (4500) + 0.5kg quemada (2250) = 6750
        record_waste(s, ingredient_id=i1.id, qty=1.0, reason=WasteReason.VENCIDA)
        record_waste(s, ingredient_id=i1.id, qty=0.5, reason=WasteReason.QUEMADA)
        # azúcar: 0.3kg derrame (1560)
        record_waste(s, ingredient_id=i2.id, qty=0.3, reason=WasteReason.DERRAME)
        s.commit()

        impact = waste_impact(s)
        assert impact.n_events == 3
        assert impact.total_cost_gs == 6750 + 1560
        assert impact.by_reason["vencida"] == 4500
        assert impact.by_reason["quemada"] == 2250
        assert impact.by_reason["derrame"] == 1560
        # by_ingredient ordered by cost desc
        assert impact.by_ingredient[0][0] == i1.id
        assert impact.by_ingredient[0][2] == 6750
        assert impact.by_ingredient[1][0] == i2.id
        assert impact.by_ingredient[1][2] == 1560
    finally:
        s.close()


def test_waste_impact_default_window_is_30_days(session_factory):
    """Default window: last 30 days."""
    s = session_factory()
    try:
        ing = Ingredient(name="x", unit="kg", stock_qty=10.0, purchase_price_gs=1000)
        s.add(ing)
        s.flush()
        # Old event: 60 days ago
        old_log = record_waste(s, ingredient_id=ing.id, qty=1.0, reason=WasteReason.OTRA)
        old_log.recorded_at = datetime.now(timezone.utc) - timedelta(days=60)
        # Recent event: today
        record_waste(s, ingredient_id=ing.id, qty=1.0, reason=WasteReason.OTRA)
        s.commit()

        impact = waste_impact(s)  # default = last 30 days
        # Only the recent one
        assert impact.n_events == 1
        assert impact.total_cost_gs == 1000
    finally:
        s.close()


def test_waste_as_pct_of_revenue(session_factory):
    s = session_factory()
    try:
        ing = Ingredient(name="x", unit="kg", stock_qty=10.0, purchase_price_gs=1000)
        s.add(ing)
        s.flush()
        record_waste(s, ingredient_id=ing.id, qty=2.0, reason=WasteReason.VENCIDA)
        s.commit()

        start = datetime.now(timezone.utc) - timedelta(days=2)
        end = datetime.now(timezone.utc) + timedelta(days=1)
        # 2kg * 1000 = 2000 Gs. waste
        # 100_000 Gs. revenue
        pct = waste_as_pct_of_revenue(s, start_date=start, end_date=end, revenue_gs=100_000)
        assert abs(pct - 2.0) < 0.01  # 2%

        pct_zero_revenue = waste_as_pct_of_revenue(
            s, start_date=start, end_date=end, revenue_gs=0
        )
        assert pct_zero_revenue == 0.0
    finally:
        s.close()



def test_record_recipe_waste_creates_one_log_per_ingredient(session_factory):
    """Whole-batch waste expands a recipe into per-ingredient WasteLog rows.

    Recipe: 12 muffins using 0.5 kg flour + 0.3 kg sugar + 4 und eggs.
    Batch_qty=2.0 wastes 2x the recipe → 1.0 kg flour, 0.6 kg sugar, 8 eggs.
    """
    s = session_factory()
    try:
        flour = Ingredient(name="flour", unit="kg", stock_qty=10.0, purchase_price_gs=2000)
        sugar = Ingredient(name="sugar", unit="kg", stock_qty=10.0, purchase_price_gs=1500)
        eggs = Ingredient(name="eggs", unit="und", stock_qty=100.0, purchase_price_gs=500)
        s.add_all([flour, sugar, eggs])
        s.flush()

        rec = Recipe(name="Muffin x12", yield_qty=12, yield_unit="und")
        s.add(rec)
        s.flush()
        s.add_all([
            RecipeLine(recipe_id=rec.id, line_kind="ingredient",
                       line_ref_id=flour.id, qty=0.5, line_unit="kg"),
            RecipeLine(recipe_id=rec.id, line_kind="ingredient",
                       line_ref_id=sugar.id, qty=0.3, line_unit="kg"),
            RecipeLine(recipe_id=rec.id, line_kind="ingredient",
                       line_ref_id=eggs.id, qty=4, line_unit="und"),
        ])
        s.flush()

        result = record_recipe_waste(
            s, recipe_id=rec.id, batch_qty=2.0, reason=WasteReason.QUEMADA
        )
        s.commit()

        assert result.recipe_id == rec.id
        assert result.batch_qty == 2.0
        assert len(result.waste_logs) == 3

        # Stock decremented
        s.refresh(flour); s.refresh(sugar); s.refresh(eggs)
        assert flour.stock_qty == pytest.approx(9.0)  # 10 - 1.0
        assert sugar.stock_qty == pytest.approx(9.4)  # 10 - 0.6
        assert eggs.stock_qty == pytest.approx(92.0)  # 100 - 8

        # Cost denormalized per ingredient
        # flour: 1.0 kg * 2000 = 2000
        # sugar: 0.6 kg * 1500 = 900
        # eggs:  8 und * 500  = 4000
        assert result.cost_gs == 2000 + 900 + 4000

        # All logs share the same reason + timestamp
        assert all(log.reason == "quemada" for log in result.waste_logs)
    finally:
        s.close()


def test_record_recipe_waste_rejects_unknown_recipe(session_factory):
    s = session_factory()
    try:
        with pytest.raises(ValueError, match="not found"):
            record_recipe_waste(
                s, recipe_id=99999, batch_qty=1.0, reason=WasteReason.OTRA
            )
    finally:
        s.close()


def test_record_recipe_waste_rejects_missing_yield(session_factory):
    s = session_factory()
    try:
        rec = Recipe(name="NoYield", yield_qty=None, yield_unit="und")
        s.add(rec); s.flush()
        with pytest.raises(ValueError, match="sin rendimiento"):
            record_recipe_waste(
                s, recipe_id=rec.id, batch_qty=1.0, reason=WasteReason.OTRA
            )
    finally:
        s.close()


def test_record_recipe_waste_rejects_zero_batch(session_factory):
    s = session_factory()
    try:
        rec = Recipe(name="x", yield_qty=12, yield_unit="und")
        s.add(rec); s.flush()
        with pytest.raises(ValueError, match="mayor a 0"):
            record_recipe_waste(
                s, recipe_id=rec.id, batch_qty=0.0, reason=WasteReason.OTRA
            )
    finally:
        s.close()
