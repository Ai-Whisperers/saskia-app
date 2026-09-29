"""Tests for DB-level CHECK constraints (migration 028).

The migration creates UPDATE-only triggers that reject yield_qty <= 0
when explicitly set. NULL is allowed at INSERT time (for drafts).
The non-null check fires on UPDATE so a draft recipe can later be
populated with a valid yield.
"""
import pytest
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.analytics


def test_recipe_yield_qty_zero_at_update_rejected(session_factory):
    """recipe UPDATE with yield_qty=0 is rejected by the trigger."""
    from app.rms.models import Recipe
    sf = session_factory
    with sf() as s:
        # Insert with NULL (draft) — allowed
        r = Recipe(name="Receta Draft", yield_qty=None, yield_unit="und")
        s.add(r); s.commit()
        rid = r.id

    # UPDATE to 0 — rejected
    with sf() as s:
        from sqlalchemy import update
        with pytest.raises(IntegrityError):
            s.execute(
                update(Recipe).where(Recipe.id == rid).values(yield_qty=0)
            )
            s.commit()


def test_recipe_yield_qty_negative_at_update_rejected(session_factory):
    """recipe UPDATE with yield_qty=-5 is rejected."""
    from sqlalchemy import update

    from app.rms.models import Recipe
    sf = session_factory
    with sf() as s:
        r = Recipe(name="Receta Draft 2", yield_qty=None, yield_unit="und")
        s.add(r); s.commit()
        rid = r.id

    with sf() as s:
        with pytest.raises(IntegrityError):
            s.execute(
                update(Recipe).where(Recipe.id == rid).values(yield_qty=-5)
            )
            s.commit()


def test_recipe_yield_qty_positive_at_update_allowed(session_factory):
    """recipe UPDATE with yield_qty=12 is allowed."""
    from sqlalchemy import update

    from app.rms.models import Recipe
    sf = session_factory
    with sf() as s:
        r = Recipe(name="Receta Draft OK", yield_qty=None, yield_unit="und")
        s.add(r); s.commit()
        rid = r.id

    with sf() as s:
        s.execute(
            update(Recipe).where(Recipe.id == rid).values(yield_qty=12)
        )
        s.commit()
    with sf() as s:
        from app.rms.models import Recipe as R
        assert s.get(R, rid).yield_qty == 12


def test_recipe_insert_with_null_yield_allowed(session_factory):
    """recipe INSERT with yield_qty=NULL is allowed (draft state)."""
    from app.rms.models import Recipe
    sf = session_factory
    with sf() as s:
        r = Recipe(name="Receta NULL Draft", yield_qty=None, yield_unit="und")
        s.add(r)
        s.commit()
        assert r.id is not None


def test_recipe_insert_with_positive_yield_allowed(session_factory):
    """recipe INSERT with yield_qty=12 is allowed (sanity)."""
    from app.rms.models import Recipe
    sf = session_factory
    with sf() as s:
        r = Recipe(name="Receta Direct", yield_qty=12, yield_unit="und")
        s.add(r)
        s.commit()
        assert r.id is not None


def test_recipe_line_qty_negative_at_update_rejected(session_factory):
    """recipe_line UPDATE with qty=-1 is rejected."""
    from sqlalchemy import update

    from app.rms.models import Ingredient, Recipe, RecipeLine
    sf = session_factory
    with sf() as s:
        ing = Ingredient(name="test_rl", unit="kg", stock_qty=10, min_stock_qty=1, purchase_price_gs=3000)
        s.add(ing); s.flush()
        rec = Recipe(name="r1_rl", yield_qty=12, yield_unit="und")
        s.add(rec); s.flush()
        rl = RecipeLine(recipe_id=rec.id, line_kind="ingredient", line_ref_id=ing.id, qty=0.3, line_unit="kg")
        s.add(rl); s.commit()
        rl_id = rl.id

    with sf() as s:
        from app.rms.models import RecipeLine as RL
        with pytest.raises(IntegrityError):
            s.execute(
                update(RL).where(RL.id == rl_id).values(qty=-1)
            )
            s.commit()
