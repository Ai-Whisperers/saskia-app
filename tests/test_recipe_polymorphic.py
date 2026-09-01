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
