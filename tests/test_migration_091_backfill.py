"""Tests for migration 091: backfill stock_movement.affected_recipe_id.

Validates:
- Schema reaches 91 after init_db
- Existing stock_movement rows where reference_type='sale' have their
  affected_recipe_id populated from sale_stock_move
- Re-running the migration is idempotent (no overwrite of existing
  values)
- Non-sale stock_movement rows are untouched
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text


def _make_sale_fixture(session, *, name_suffix: str = ""):
    """Create the FK chain Product → Sale → Recipe → Ingredient.

    Returns (ingredient, recipe, sale). The Sale's product FK is
    populated; the Recipe and Ingredient are minimal but real.
    """
    from app.rms.models import Ingredient, Product, Recipe, Sale

    ing = Ingredient(
        name=f"T091Ing{name_suffix}",
        unit="kg",
        stock_qty=10,
        purchase_price_gs=1000,
    )
    prod = Product(name=f"t091prod{name_suffix}", sale_price_gs=5000)
    rec = Recipe(name=f"r_t091{name_suffix}", yield_qty=1, yield_unit="und")
    session.add_all([ing, prod, rec])
    session.flush()
    sale = Sale(
        product_id=prod.id,
        qty=1,
        unit_price_gs=5000,
        sold_at=datetime.now(timezone.utc),
        voided_at=None,
    )
    session.add(sale)
    session.flush()
    return ing, rec, sale


def test_migration_091_bumps_schema_version(session_factory):
    """Fresh DB hits 91 after init_db."""
    with session_factory() as s:
        v = s.execute(text("SELECT value FROM app_meta WHERE key='schema_version'")).scalar()
    assert v is not None
    assert int(v) >= 91


def test_backfill_copies_affected_recipe_id(session_factory):
    """A pre-existing sale_stock_move row's affected_recipe_id lands
    on the matching stock_movement row after migration."""
    from app.rms.models import SaleStockMove, StockMovement

    with session_factory() as s:
        ing, rec, sale = _make_sale_fixture(s, name_suffix="_copy")

        # Simulate a sale-driven move written before 091 existed
        # (no affected_recipe_id on the StockMovement row).
        ssm = SaleStockMove(
            sale_id=sale.id,
            affected_recipe_id=rec.id,
            ingredient_id=ing.id,
            qty_delta=-1.0,
        )
        smv = StockMovement(
            ingredient_id=ing.id,
            movement_type="sale",
            qty=-1.0,
            reason=f"Venta #{sale.id}",
            reference_id=sale.id,
            reference_type="sale",
            affected_recipe_id=None,  # not yet backfilled
        )
        s.add_all([ssm, smv])
        s.commit()
        s.expire_all()  # forget cached state so we read fresh post-migration

        from app.rms.migrations._091_backfill_stock_movement_recipe import (
            _migration_091_backfill_stock_movement_recipe,
        )

        with s.connection() as conn:
            _migration_091_backfill_stock_movement_recipe(conn)
            s.commit()

        loaded = s.get(StockMovement, smv.id)
        assert loaded.affected_recipe_id == rec.id


def test_backfill_idempotent_overwrites_only_nulls(session_factory):
    """If a row already has a different affected_recipe_id, the
    backfill does not clobber it."""
    from app.rms.models import StockMovement

    with session_factory() as s:
        ing, original, sale = _make_sale_fixture(s, name_suffix="_idemp")

        # The StockMovement row already has a different recipe set —
        # the backfill must NOT overwrite it.
        smv = StockMovement(
            ingredient_id=ing.id,
            movement_type="sale",
            qty=-1.0,
            reason=f"Venta #{sale.id}",
            reference_id=sale.id,
            reference_type="sale",
            affected_recipe_id=original.id,
        )
        s.add(smv)
        s.commit()

        from app.rms.migrations._091_backfill_stock_movement_recipe import (
            _migration_091_backfill_stock_movement_recipe,
        )

        with s.connection() as conn:
            _migration_091_backfill_stock_movement_recipe(conn)
            s.commit()

        loaded = s.get(StockMovement, smv.id)
        assert loaded.affected_recipe_id == original.id


def test_backfill_skips_non_sale_movements(session_factory):
    """Adjustment movements (no reference) are untouched by the backfill."""
    from app.rms.models import StockMovement

    with session_factory() as s:
        from app.rms.models import Ingredient

        ing = Ingredient(name="T091Adj", unit="kg", stock_qty=5, purchase_price_gs=500)
        s.add(ing)
        s.flush()
        mvt = StockMovement(
            ingredient_id=ing.id,
            movement_type="adjustment",
            qty=1.0,
            reason="test",
            affected_recipe_id=None,
        )
        s.add(mvt)
        s.commit()

        from app.rms.migrations._091_backfill_stock_movement_recipe import (
            _migration_091_backfill_stock_movement_recipe,
        )

        with s.connection() as conn:
            _migration_091_backfill_stock_movement_recipe(conn)
            s.commit()

        loaded = s.get(StockMovement, mvt.id)
        assert loaded.affected_recipe_id is None


def test_migration_091_full_idempotent(tmp_path):
    """Re-running init_db on a 91 DB is a no-op."""
    from sqlalchemy import create_engine

    from app.rms.db import init_db

    db = tmp_path / "test91.db"
    engine = create_engine(f"sqlite:///{db}")
    init_db(engine)
    init_db(engine)  # second run
    with engine.connect() as conn:
        v = conn.execute(text("SELECT value FROM app_meta WHERE key='schema_version'")).scalar()
    assert int(v) == 91
