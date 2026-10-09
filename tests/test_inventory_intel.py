"""tests/test_inventory_intel.py — E29 inventory intelligence tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.rms.inventory_intel import (
    days_of_stock,
    dead_stock,
    inventory_status,
    inventory_status_all,
    low_stock_alerts,
    overstocked,
    reorder_point,
    stock_value_gs,
)
from app.rms.models import (
    Ingredient,
    IngredientVariant,
    Product,
    Recipe,
    RecipeLine,
    Sale,
    StockMovement,
)

# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------


def test_days_of_stock_normal():
    assert days_of_stock(1.0, 0.1) == 10.0


def test_days_of_stock_zero_consumption_returns_none():
    assert days_of_stock(5.0, 0.0) is None


def test_days_of_stock_negative_consumption_returns_none():
    assert days_of_stock(5.0, -0.5) is None


def test_reorder_point_normal():
    # 0.5 × 3 × 1.2 = 1.8 (float math)
    assert reorder_point(0.5, 3, 0.2) == pytest.approx(1.8)


def test_reorder_point_no_safety():
    assert reorder_point(1.0, 2, 0.0) == 2.0


def test_reorder_point_zero_consumption():
    assert reorder_point(0.0, 5, 0.5) == 0.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _add_ingredient_with_consumption(
    s, name, stock_qty=1.0, purchase_price_gs=1000, lead_time_days=3, moves=10, qty_delta=-0.1
):
    """Create ingredient + recipe + sale + N SaleStockMove rows.

    When stock_qty < 0, fall back to raw SQL + temporary trigger drop
    (mirrors the approach in test_dashboard_stock_led.py) because
    migration 084's stock_qty >= 0 constraint makes negative stock
    unreachable through the ORM.
    """
    r = Recipe(name=f"r_for_{name}", yield_qty=10, yield_unit="und")
    s.add(r)
    s.flush()
    p = Product(name=f"p_for_{name}", portion_label="und", sale_price_gs=1000, recipe_id=r.id)
    s.add(p)
    s.flush()
    if stock_qty < 0:
        # Bypass path: raw SQL + drop+recreate the safety trigger.
        from sqlalchemy import text as _sa_text

        s.execute(_sa_text("DROP TRIGGER IF EXISTS ingredient_stock_qty_positive_insert"))
        try:
            ing = Ingredient(
                name=name,
                unit="kg",
                stock_qty=stock_qty,
                purchase_price_gs=purchase_price_gs,
                lead_time_days=lead_time_days,
            )
            s.add(ing)
            s.flush()
        finally:
            s.execute(
                _sa_text(
                    "CREATE TRIGGER IF NOT EXISTS ingredient_stock_qty_positive_insert "
                    "BEFORE INSERT ON ingredient "
                    "FOR EACH ROW WHEN NEW.stock_qty < 0 "
                    "BEGIN SELECT RAISE(ABORT, 'ingredient.stock_qty must be >= 0'); END"
                )
            )
    else:
        ing = Ingredient(
            name=name,
            unit="kg",
            stock_qty=stock_qty,
            purchase_price_gs=purchase_price_gs,
            lead_time_days=lead_time_days,
        )
        s.add(ing)
        s.flush()
    s.add(RecipeLine(recipe_id=r.id, line_kind="ingredient", line_ref_id=ing.id, qty=0.1))
    sale = Sale(sold_at=datetime.now(timezone.utc), product_id=p.id, qty=1, unit_price_gs=1000)
    s.add(sale)
    s.flush()
    for _ in range(moves):
        s.add(
            StockMovement(
                ingredient_id=ing.id,
                movement_type="sale",
                qty=qty_delta,
                reason=f"Venta #{sale.id}",
                reference_id=sale.id,
                reference_type="sale",
                affected_recipe_id=r.id,
            )
        )
    s.commit()
    return ing


# ---------------------------------------------------------------------------
# inventory_status — one ingredient
# ---------------------------------------------------------------------------


def test_inventory_status_basic(session_factory):
    with session_factory() as s:
        ing = _add_ingredient_with_consumption(
            s, "inv_xyz", stock_qty=5.0, moves=10, qty_delta=-0.1
        )
        st = inventory_status(s, ing)
        assert st.ingredient_id == ing.id
        assert st.stock_qty == 5.0
        assert st.needs_reorder is False


def test_inventory_status_needs_reorder(session_factory):
    with session_factory() as s:
        ing = _add_ingredient_with_consumption(
            s, "low_xyz", stock_qty=0.05, moves=100, qty_delta=-0.1
        )
        st = inventory_status(s, ing)
        assert st.needs_reorder is True


def test_inventory_status_negative_stock_qty(session_factory):
    with session_factory() as s:
        ing = _add_ingredient_with_consumption(s, "neg_xyz", stock_qty=-1.0)
        st = inventory_status(s, ing)
        assert st.days_of_stock is not None
        assert st.days_of_stock < 0


def test_inventory_status_all(session_factory):
    with session_factory() as s:
        for i in range(3):
            s.add(Ingredient(name=f"all_xyz_{i}", unit="kg", stock_qty=1.0, purchase_price_gs=100))
        s.commit()
        statuses = inventory_status_all(s)
        assert len(statuses) == 3


# ---------------------------------------------------------------------------
# dead_stock
# ---------------------------------------------------------------------------


def test_dead_stock_no_data(session_factory):
    with session_factory() as s:
        ing = Ingredient(name="new_xyz", unit="kg", stock_qty=1.0, purchase_price_gs=100)
        s.add(ing)
        s.commit()
        result = dead_stock(s, days_threshold=30)
        assert any(d.ingredient_id == ing.id for d in result)


def test_dead_stock_recently_used_excluded(session_factory):
    with session_factory() as s:
        ing = Ingredient(
            name="recent_xyz",
            unit="kg",
            stock_qty=1.0,
            purchase_price_gs=100,
            last_consumed_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
        s.add(ing)
        s.commit()
        result = dead_stock(s, days_threshold=30)
        assert not any(d.ingredient_id == ing.id for d in result)


def test_dead_stock_old_consumed_included(session_factory):
    with session_factory() as s:
        ing = Ingredient(
            name="old_xyz",
            unit="kg",
            stock_qty=1.0,
            purchase_price_gs=100,
            last_consumed_at=datetime.now(timezone.utc) - timedelta(days=60),
        )
        s.add(ing)
        s.commit()
        result = dead_stock(s, days_threshold=30)
        assert any(d.ingredient_id == ing.id for d in result)


def test_dead_stock_zero_stock_excluded(session_factory):
    with session_factory() as s:
        ing = Ingredient(name="empty_xyz", unit="kg", stock_qty=0, purchase_price_gs=100)
        s.add(ing)
        s.commit()
        result = dead_stock(s)
        assert not any(d.ingredient_id == ing.id for d in result)


# ---------------------------------------------------------------------------
# overstocked
# ---------------------------------------------------------------------------


def test_overstocked_detects(session_factory):
    with session_factory() as s:
        ing = _add_ingredient_with_consumption(
            s, "over_xyz", stock_qty=100.0, moves=1, qty_delta=-1.0
        )
        result = overstocked(s, multiplier=3.0, window_days=30)
        assert any(o.ingredient_id == ing.id for o in result)


def test_overstocked_normal_stock_excluded(session_factory):
    with session_factory() as s:
        ing = _add_ingredient_with_consumption(
            s, "normal_xyz", stock_qty=1.0, moves=30, qty_delta=-1.0
        )
        result = overstocked(s, multiplier=3.0, window_days=30)
        assert not any(o.ingredient_id == ing.id for o in result)


# ---------------------------------------------------------------------------
# stock_value_gs
# ---------------------------------------------------------------------------


def test_stock_value_gs_basic(session_factory):
    with session_factory() as s:
        s.add(Ingredient(name="v1_xyz", unit="kg", stock_qty=2.0, purchase_price_gs=1000))
        s.add(Ingredient(name="v2_xyz", unit="kg", stock_qty=3.0, purchase_price_gs=500))
        s.commit()
        # 2*1000 + 3*500 = 3500
        assert stock_value_gs(s) == 3500


def test_stock_value_gs_empty(session_factory):
    with session_factory() as s:
        assert stock_value_gs(s) == 0


def test_stock_value_gs_uses_preferred_variant_price(session_factory):
    """SASKIA-210-audit: a preferred variant's price IS the effective cost.

    Parent price 1000 with preferred variant at 1200 → valuation uses
    1200. A non-preferred variant's price is ignored.
    """
    with session_factory() as s:
        ing = Ingredient(name="v_pref_xyz", unit="kg", stock_qty=2.0, purchase_price_gs=1000)
        s.add(ing)
        s.flush()
        s.add(
            IngredientVariant(
                ingredient_id=ing.id,
                package_size=25,
                package_unit="kg",
                notes="saco 25kg",
                purchase_price_gs=1200,
                preferred=True,
            )
        )
        other = Ingredient(name="v_other_xyz", unit="kg", stock_qty=1.0, purchase_price_gs=800)
        s.add(other)
        s.flush()
        s.add(
            IngredientVariant(
                ingredient_id=other.id,
                package_size=1,
                package_unit="kg",
                notes="variante no preferida",
                purchase_price_gs=9999,
                preferred=False,
            )
        )
        s.commit()
        # 2*1200 (preferred variant) + 1*800 (parent fallback) = 3200
        assert stock_value_gs(s) == 3200


# ---------------------------------------------------------------------------
# low_stock_alerts
# ---------------------------------------------------------------------------


def test_low_stock_alerts_returns_critical_first(session_factory):
    with session_factory() as s:
        ing_critical = _add_ingredient_with_consumption(
            s, "crit_xyz", stock_qty=0.01, moves=50, qty_delta=-0.1
        )
        ing_stable = _add_ingredient_with_consumption(
            s, "stable_xyz", stock_qty=100.0, moves=1, qty_delta=-0.1
        )
        alerts = low_stock_alerts(s, top_n=5)
        # Critical should be in alerts.
        assert any(a.ingredient_id == ing_critical.id for a in alerts)
        # Stable should NOT.
        assert not any(a.ingredient_id == ing_stable.id for a in alerts)
