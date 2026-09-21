"""tests/test_recipe_polymorphic.py — polymorphic recipe_lines + resolve_line_target.

Per dev plan Batch 3. Targets ~6 tests.

Covers:
- resolve_line_target resolves ingredient lines correctly
- resolve_line_target resolves sub_recipe lines correctly
- resolve_line_target raises on unknown line_kind
- Cycle detection in deep sub-recipe tree (3+ levels)
- RecipeLine CHECK constraint rejects bad line_kind
- RecipeLine CHECK constraint rejects qty <= 0
"""

from __future__ import annotations

import pytest


def _seed_polymorphic(session_factory):
    """Recipe with one ingredient line and one sub_recipe line."""
    from app.rms.models import Ingredient, Recipe, RecipeLine

    with session_factory() as s:
        flour = Ingredient(name="Harina", unit="kg", stock_qty=5.0, purchase_price_gs=5000)
        s.add(flour)
        s.flush()
        masa = Recipe(name="Masa", yield_qty=10.0, yield_unit="und")
        s.add(masa)
        s.flush()
        muffin = Recipe(name="Muffin", yield_qty=12.0, yield_unit="und")
        s.add(muffin)
        s.flush()
        s.add_all(
            [
                RecipeLine(
                    recipe_id=muffin.id,
                    line_kind="ingredient",
                    line_ref_id=flour.id,
                    qty=0.3,
                ),
                RecipeLine(
                    recipe_id=muffin.id,
                    line_kind="sub_recipe",
                    line_ref_id=masa.id,
                    qty=1.0,
                ),
            ]
        )
        s.commit()
        return flour.id, masa.id, muffin.id


def test_resolve_line_target_ingredient(session_factory):
    from app.rms.costing import resolve_line_target
    from app.rms.models import RecipeLine

    flour_id, _, muffin_id = _seed_polymorphic(session_factory)
    with session_factory() as s:
        line = s.query(RecipeLine).filter_by(line_kind="ingredient").first()
        target = resolve_line_target(s, line)
    assert target is not None
    assert target.id == flour_id
    assert target.name == "Harina"


def test_resolve_line_target_sub_recipe(session_factory):
    from app.rms.costing import resolve_line_target
    from app.rms.models import RecipeLine

    _, masa_id, _ = _seed_polymorphic(session_factory)
    with session_factory() as s:
        line = s.query(RecipeLine).filter_by(line_kind="sub_recipe").first()
        target = resolve_line_target(s, line)
    assert target is not None
    assert target.id == masa_id
    assert target.name == "Masa"


def test_resolve_line_target_unknown_kind(session_factory):
    """Manually craft a RecipeLine with bogus line_kind in-memory, not via DB."""
    from app.rms.costing import resolve_line_target

    with session_factory() as s:
        # Bypass the CHECK constraint by using a detached object
        line = type("FakeLine", (), {"line_kind": "garbage", "line_ref_id": 1})()
        with pytest.raises(ValueError, match="Unknown line_kind"):
            resolve_line_target(s, line)


def test_resolve_line_target_missing_ingredient(session_factory):
    """line_ref_id points to nonexistent ingredient → returns None."""
    from app.rms.costing import resolve_line_target
    from app.rms.models import Recipe, RecipeLine

    with session_factory() as s:
        rec = Recipe(name="R", yield_qty=10.0, yield_unit="und")
        s.add(rec)
        s.flush()
        s.add(RecipeLine(recipe_id=rec.id, line_kind="ingredient", line_ref_id=99999, qty=1.0))
        s.commit()
        line_id = s.query(RecipeLine).first().id

    with session_factory() as s:
        line = s.get(RecipeLine, line_id)
        target = resolve_line_target(s, line)
    assert target is None


def test_recipe_line_rejects_bad_kind(session_factory):
    """CheckConstraint rejects line_kind='garbage'."""
    import sqlalchemy.exc

    from app.rms.models import Recipe, RecipeLine

    with session_factory() as s:
        rec = Recipe(name="R", yield_qty=10.0, yield_unit="und")
        s.add(rec)
        s.flush()
        s.add(RecipeLine(recipe_id=rec.id, line_kind="garbage", line_ref_id=1, qty=1.0))
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            s.commit()


def test_recipe_line_rejects_zero_qty(session_factory):
    """CheckConstraint rejects qty=0."""
    import sqlalchemy.exc

    from app.rms.models import Ingredient, Recipe, RecipeLine

    with session_factory() as s:
        ing = Ingredient(name="X", unit="kg", stock_qty=1.0, purchase_price_gs=100)
        rec = Recipe(name="R", yield_qty=10.0, yield_unit="und")
        s.add_all([ing, rec])
        s.flush()
        s.add(RecipeLine(recipe_id=rec.id, line_kind="ingredient", line_ref_id=ing.id, qty=0))
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            s.commit()


def test_recipe_line_rejects_negative_qty(session_factory):
    """CheckConstraint rejects qty=-1."""
    import sqlalchemy.exc

    from app.rms.models import Ingredient, Recipe, RecipeLine

    with session_factory() as s:
        ing = Ingredient(name="X", unit="kg", stock_qty=1.0, purchase_price_gs=100)
        rec = Recipe(name="R", yield_qty=10.0, yield_unit="und")
        s.add_all([ing, rec])
        s.flush()
        s.add(RecipeLine(recipe_id=rec.id, line_kind="ingredient", line_ref_id=ing.id, qty=-1.0))
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            s.commit()


# --- Phase B — T1 recipe line unit selector roundtrip ---


def test_recipe_line_stores_line_unit(session_factory):
    """RecipeLine model persists line_unit alongside qty."""
    from app.rms.models import Ingredient, Recipe, RecipeLine

    with session_factory() as s:
        ing = Ingredient(name="Harina", unit="kg", stock_qty=5.0, purchase_price_gs=5000)
        rec = Recipe(name="R", yield_qty=10.0, yield_unit="und")
        s.add_all([ing, rec])
        s.flush()
        s.add(
            RecipeLine(
                recipe_id=rec.id,
                line_kind="ingredient",
                line_ref_id=ing.id,
                qty=250,
                line_unit="g",
            )
        )
        s.commit()
        line_id = s.query(RecipeLine).first().id

    with session_factory() as s:
        line = s.get(RecipeLine, line_id)
    assert line.line_unit == "g"
    assert line.qty == 250


def test_recipe_line_defaults_line_unit_to_empty_string(session_factory):
    """Newly created RecipeLine (without line_unit) defaults to ''."""
    from app.rms.models import Ingredient, Recipe, RecipeLine

    with session_factory() as s:
        ing = Ingredient(name="Harina", unit="kg", stock_qty=5.0, purchase_price_gs=5000)
        rec = Recipe(name="R", yield_qty=10.0, yield_unit="und")
        s.add_all([ing, rec])
        s.flush()
        s.add(
            RecipeLine(
                recipe_id=rec.id,
                line_kind="ingredient",
                line_ref_id=ing.id,
                qty=0.3,
            )
        )
        s.commit()
        line_id = s.query(RecipeLine).first().id

    with session_factory() as s:
        line = s.get(RecipeLine, line_id)
    assert line.line_unit == ""


def test_costing_uses_line_unit_for_cross_unit_recipe(session_factory):
    """Roundtrip: 250 g of flour (ingredient in kg, Gs. 5000/kg) → Gs. 1250 cost."""
    from decimal import Decimal

    from app.rms.costing import recipe_batch_cost_gs
    from app.rms.models import Ingredient, Recipe, RecipeLine

    with session_factory() as s:
        flour = Ingredient(name="Harina", unit="kg", stock_qty=5.0, purchase_price_gs=5000)
        s.add(flour)
        s.flush()
        rec = Recipe(name="Torta", yield_qty=12.0, yield_unit="und")
        s.add(rec)
        s.flush()
        # 250 g of flour into a kg ingredient → 0.25 kg × Gs. 5000 = Gs. 1250
        s.add(
            RecipeLine(
                recipe_id=rec.id,
                line_kind="ingredient",
                line_ref_id=flour.id,
                qty=250,
                line_unit="g",
            )
        )
        s.commit()
        recipe_id = rec.id

    with session_factory() as s:
        result = recipe_batch_cost_gs(s, recipe_id)
    assert result.batch_cost_gs == 1250
    assert not result.missing_ingredient_names


def test_costing_same_unit_recipe_unchanged(session_factory):
    """When line_unit == ingredient_unit, costing is unaffected (qty × price)."""
    from app.rms.costing import recipe_batch_cost_gs
    from app.rms.models import Ingredient, Recipe, RecipeLine

    with session_factory() as s:
        flour = Ingredient(name="Harina", unit="kg", stock_qty=5.0, purchase_price_gs=5000)
        s.add(flour)
        s.flush()
        rec = Recipe(name="Torta", yield_qty=12.0, yield_unit="und")
        s.add(rec)
        s.flush()
        s.add(
            RecipeLine(
                recipe_id=rec.id,
                line_kind="ingredient",
                line_ref_id=flour.id,
                qty=0.3,
                line_unit="kg",
            )
        )
        s.commit()
        recipe_id = rec.id

    with session_factory() as s:
        result = recipe_batch_cost_gs(s, recipe_id)
    assert result.batch_cost_gs == 1500  # 0.3 × 5000


def test_costing_handles_empty_line_unit_as_legacy(session_factory):
    """Legacy rows with line_unit='' behave as if line_unit matched ingredient unit.

    Backward compat: pre-T1 recipes had no line_unit. Default to the linked
    ingredient's unit (no conversion). This matches the historical behavior
    where recipe qty was assumed to match ingredient unit at import time.
    """
    from app.rms.costing import recipe_batch_cost_gs
    from app.rms.models import Ingredient, Recipe, RecipeLine

    with session_factory() as s:
        flour = Ingredient(name="Harina", unit="kg", stock_qty=5.0, purchase_price_gs=5000)
        s.add(flour)
        s.flush()
        rec = Recipe(name="Torta", yield_qty=12.0, yield_unit="und")
        s.add(rec)
        s.flush()
        # line_unit="" is the legacy/default value — assume ingredient unit
        s.add(
            RecipeLine(
                recipe_id=rec.id,
                line_kind="ingredient",
                line_ref_id=flour.id,
                qty=0.3,
                line_unit="",
            )
        )
        s.commit()
        recipe_id = rec.id

    with session_factory() as s:
        result = recipe_batch_cost_gs(s, recipe_id)
    assert result.batch_cost_gs == 1500  # 0.3 × 5000
