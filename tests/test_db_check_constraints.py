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


# ── Migration 083 (2026-10-01) — INSERT-side guards ──────────────────
# Migration 028 only added UPDATE triggers. INSERT of a negative
# `yield_qty` or `qty` slipped through. Migration 083 closes that gap.


def test_recipe_insert_with_zero_yield_rejected(session_factory):
    """INSERT recipe with yield_qty=0 must raise IntegrityError."""
    from app.rms.models import Recipe
    sf = session_factory
    with sf() as s:
        r = Recipe(name="Receta Zero Yield", yield_qty=0, yield_unit="und")
        s.add(r)
        with pytest.raises(IntegrityError):
            s.commit()
        s.rollback()


def test_recipe_insert_with_negative_yield_rejected(session_factory):
    """INSERT recipe with yield_qty=-3 must raise IntegrityError.

    Regression for the migration 028 gap: UPDATE trigger did not cover
    INSERT, so raw SQL INSERT INTO recipe (..., yield_qty, ...) VALUES
    (..., -3, ...) used to slip past the constraint.
    """
    from app.rms.models import Recipe
    sf = session_factory
    with sf() as s:
        r = Recipe(name="Receta Negative Yield", yield_qty=-3, yield_unit="und")
        s.add(r)
        with pytest.raises(IntegrityError):
            s.commit()
        s.rollback()


def test_recipe_line_insert_with_zero_qty_rejected(session_factory):
    """INSERT recipe_line with qty=0 must raise IntegrityError."""
    from app.rms.models import Ingredient, Recipe, RecipeLine
    sf = session_factory
    with sf() as s:
        ing = Ingredient(name="test_rl_zero", unit="kg", stock_qty=10,
                         min_stock_qty=1, purchase_price_gs=3000)
        s.add(ing); s.flush()
        rec = Recipe(name="r_zero_qty", yield_qty=12, yield_unit="und")
        s.add(rec); s.flush()
        rl = RecipeLine(recipe_id=rec.id, line_kind="ingredient",
                        line_ref_id=ing.id, qty=0, line_unit="kg")
        s.add(rl)
        with pytest.raises(IntegrityError):
            s.commit()
        s.rollback()


def test_recipe_line_insert_with_negative_qty_rejected(session_factory):
    """INSERT recipe_line with qty=-0.5 must raise IntegrityError.

    Regression for migration 028 gap — INSERT-side guard now in place
    via migration 083.
    """
    from app.rms.models import Ingredient, Recipe, RecipeLine
    sf = session_factory
    with sf() as s:
        ing = Ingredient(name="test_rl_neg", unit="kg", stock_qty=10,
                         min_stock_qty=1, purchase_price_gs=3000)
        s.add(ing); s.flush()
        rec = Recipe(name="r_neg_qty", yield_qty=12, yield_unit="und")
        s.add(rec); s.flush()
        rl = RecipeLine(recipe_id=rec.id, line_kind="ingredient",
                        line_ref_id=ing.id, qty=-0.5, line_unit="kg")
        s.add(rl)
        with pytest.raises(IntegrityError):
            s.commit()
        s.rollback()


def test_migration_083_idempotent_re_run(session_factory):
    """Migration 083 must be idempotent — CREATE TRIGGER IF NOT EXISTS.

    Re-running the migration on a DB that already has the triggers
    must not raise. init_db() takes an Engine; the migration function
    itself takes a Connection (as called from inside engine.begin()).
    """
    from app.rms.db import init_db, MIGRATIONS, _migration_083_recipe_yield_qty_insert_guard

    sf = session_factory
    bind = sf.kw["bind"]
    # Migrations expect a Connection; wrap the engine.
    with bind.begin() as conn:
        # Second invocation: no-op due to IF NOT EXISTS.
        _migration_083_recipe_yield_qty_insert_guard(conn)
    # init_db expects an Engine.
    init_db(bind)
    assert 83 in MIGRATIONS
