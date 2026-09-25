"""Costing fix tests — yield percentage + direct labor in unit cost (2026-09-24).

Math under test:
  unit = (batch + labor) / (yield_qty × yield_pct)

- yield_percentage NULL → 1.0 (backward compat: identical to old formula)
- yield 0.85 → cost rises by 1/0.85 ≈ 17.6%
- out-of-range yield (1.5, 0.05) → clamped to no-loss (data noise guard)
- direct_labor_minutes × rate/60 added; NULL rate or minutes → no labor
"""

from __future__ import annotations

from app.rms.costing import recipe_unit_cost_gs
from app.rms.models import ComplianceInfo, Ingredient, Recipe, RecipeLine


_SEQ = [0]


def _setup_recipe(session, *, yield_pct=None, labor_min=None, price=1000, qty=1000, yield_qty=10):
    _SEQ[0] += 1
    n = _SEQ[0]
    ing = Ingredient(name=f"Harina costo {n}", unit="g", stock_qty=10, purchase_price_gs=price)
    session.add(ing)
    session.flush()
    r = Recipe(
        name=f"Pan costo {n}", yield_qty=yield_qty, yield_unit="und",
        yield_percentage=yield_pct, direct_labor_minutes=labor_min,
    )
    session.add(r)
    session.flush()
    session.add(RecipeLine(recipe_id=r.id, line_kind="ingredient", line_ref_id=ing.id, qty=qty))
    session.commit()
    return r


def test_null_yield_backward_compatible(session_factory):
    """No yield/labor → same number the old formula produced."""
    with session_factory() as s:
        r = _setup_recipe(s, price=1000, qty=1000, yield_qty=10)
        # batch = 1000 g... wait: qty in line units (g) vs price per unit base.
        # price is per unit; line qty g → batch = 1000 × price-per-g? No:
        # purchase_price_gs is per Ingredient.unit (g here) → batch = 1000 × 1000? 
        # Keep the test relative instead of absolute.
        res = recipe_unit_cost_gs(s, r.id)
        assert res.batch_cost_gs is not None
        base = res.batch_cost_gs
        # Old formula: batch / yield_qty. New with defaults must equal it
        # (yield 1.0, labor 0).
        from app.rms.costing import recipe_batch_cost_gs
        batch = recipe_batch_cost_gs(s, r.id).batch_cost_gs
        assert base == _old_formula(batch, 10)


def _old_formula(batch, yield_qty):
    from decimal import Decimal
    from app.rms.money import to_int_gs
    return to_int_gs(Decimal(str(batch)) / Decimal(str(yield_qty)))


def test_yield_loss_raises_cost(session_factory):
    with session_factory() as s:
        r_full = _setup_recipe(s, price=2000, qty=500, yield_qty=10)
        c_full = recipe_unit_cost_gs(s, r_full.id).batch_cost_gs

    with session_factory() as s2:
        r_lossy = _setup_recipe(s2, price=2000, qty=500, yield_qty=10, yield_pct=0.5)
        c_lossy = recipe_unit_cost_gs(s2, r_lossy.id).batch_cost_gs

    # 50% loss → double the per-unit cost (± rounding)
    assert abs(c_lossy - 2 * c_full) <= 2


def test_out_of_range_yield_clamped(session_factory):
    with session_factory() as s:
        r = _setup_recipe(s, price=2000, qty=500, yield_qty=10, yield_pct=1.7)
        c_bad = recipe_unit_cost_gs(s, r.id).batch_cost_gs
    with session_factory() as s2:
        r2 = _setup_recipe(s2, price=2000, qty=500, yield_qty=10, yield_pct=None)
        c_ok = recipe_unit_cost_gs(s2, r2.id).batch_cost_gs
    assert c_bad == c_ok  # clamped to no-loss, not ×1/1.7


def test_labor_added(session_factory):
    with session_factory() as s:
        ci = s.get(ComplianceInfo, 1)
        if ci is None:
            ci = ComplianceInfo(id=1)
            s.add(ci)
        ci.labor_cost_per_hour_gs = 60000
        s.commit()
        r_no = _setup_recipe(s, price=2000, qty=500, yield_qty=10)
        c_no = recipe_unit_cost_gs(s, r_no.id).batch_cost_gs
        assert c_no is not None

    with session_factory() as s2:
        ci = s2.get(ComplianceInfo, 1) or ComplianceInfo(id=1)
        ci.labor_cost_per_hour_gs = 60000
        s2.add(ci)
        s2.commit()
        r_yes = _setup_recipe(s2, price=2000, qty=500, yield_qty=10, labor_min=60)
        c_yes = recipe_unit_cost_gs(s2, r_yes.id).batch_cost_gs

    # 60 min × G.60.000/h = G.60.000 per batch ÷ 10 units = +G.6.000/unit
    assert c_yes is not None and c_no is not None
    assert c_yes - c_no >= 5995


def test_labor_missing_rate_no_crash(session_factory):
    with session_factory() as s:
        r = _setup_recipe(s, price=2000, qty=500, yield_qty=10, labor_min=90)
        c = recipe_unit_cost_gs(s, r.id).batch_cost_gs
        assert c is not None  # no compliance row → no labor, no crash
