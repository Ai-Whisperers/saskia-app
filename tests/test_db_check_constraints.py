"""Tests for DB-level CHECK constraints (migration 028)."""

import pytest
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.analytics


def test_recipe_yield_qty_zero_rejected_by_db(session_factory):
    """recipe.yield_qty=0 must be rejected (CHECK via SQLite trigger)."""
    from app.rms.models import Recipe
    sf = session_factory
    with sf() as s:
        r = Recipe(name="Receta Yield 0", yield_qty=0, yield_unit="und")
        s.add(r)
        with pytest.raises(IntegrityError):
            s.commit()


def test_recipe_yield_qty_negative_rejected(session_factory):
    """recipe.yield_qty=-5 must be rejected."""
    from app.rms.models import Recipe
    sf = session_factory
    with sf() as s:
        r = Recipe(name="Receta Yield -5", yield_qty=-5, yield_unit="und")
        s.add(r)
        with pytest.raises(IntegrityError):
            s.commit()


def test_recipe_yield_qty_positive_allowed(session_factory):
    """recipe.yield_qty=12 must be allowed (sanity)."""
    from app.rms.models import Recipe
    sf = session_factory
    with sf() as s:
        r = Recipe(name="Receta Yield 12", yield_qty=12, yield_unit="und")
        s.add(r)
        s.commit()
        assert r.id is not None


def test_recipe_line_qty_zero_rejected(session_factory):
    """recipe_line.qty=0 must be rejected."""
    from app.rms.models import Recipe, RecipeLine, Ingredient
    sf = session_factory
    with sf() as s:
        ing = Ingredient(name="test", unit="kg", stock_qty=10, min_stock_qty=1, purchase_price_gs=3000)
        s.add(ing); s.flush()
        rec = Recipe(name="r1", yield_qty=12, yield_unit="und")
        s.add(rec); s.flush()
        rl = RecipeLine(recipe_id=rec.id, line_kind="ingredient", line_ref_id=ing.id, qty=0, line_unit="kg")
        s.add(rl)
        with pytest.raises(IntegrityError):
            s.commit()


def test_recipe_line_qty_negative_rejected(session_factory):
    """recipe_line.qty=-1 must be rejected."""
    from app.rms.models import Recipe, RecipeLine, Ingredient
    sf = session_factory
    with sf() as s:
        ing = Ingredient(name="test", unit="kg", stock_qty=10, min_stock_qty=1, purchase_price_gs=3000)
        s.add(ing); s.flush()
        rec = Recipe(name="r1", yield_qty=12, yield_unit="und")
        s.add(rec); s.flush()
        rl = RecipeLine(recipe_id=rec.id, line_kind="ingredient", line_ref_id=ing.id, qty=-1, line_unit="kg")
        s.add(rl)
        with pytest.raises(IntegrityError):
            s.commit()
