"""Tests for migration 090: stock_movement.affected_recipe_id.

Verifies:
- Schema bumps to 90 and the column exists
- Column is nullable (non-sale movements don't have an affected recipe)
- Idempotent: re-running init_db doesn't fail
- Backfill helper (future work) will be able to read from sale_stock_move
"""

from __future__ import annotations

from sqlalchemy import inspect, text


def test_migration_090_bumps_schema_version(session_factory):
    """Fresh DB runs init_db through migration 090."""
    with session_factory() as s:
        v = s.execute(text("SELECT value FROM app_meta WHERE key='schema_version'")).scalar()
    assert v is not None
    assert int(v) >= 90


def test_stock_movement_has_affected_recipe_id_column(session_factory):
    """The column is declared on the ORM model and exists in the DB."""
    inspector = inspect(session_factory().get_bind())
    cols = {c["name"] for c in inspector.get_columns("stock_movement")}
    assert "affected_recipe_id" in cols


def test_stock_movement_affected_recipe_id_is_nullable(session_factory):
    """Non-sale movements (reorder/merma/adjustment/initial) don't have a recipe."""
    from app.rms.models import Ingredient, StockMovement

    with session_factory() as s:
        ing = Ingredient(name="TestNullable", unit="kg", stock_qty=10, purchase_price_gs=1000)
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
        loaded = s.get(StockMovement, mvt.id)
        assert loaded.affected_recipe_id is None


def test_stock_movement_affected_recipe_id_can_be_set(session_factory):
    """Sale movements CAN populate affected_recipe_id (future backfill target)."""
    from app.rms.models import Ingredient, Recipe, StockMovement

    with session_factory() as s:
        ing = Ingredient(name="TestSetable", unit="kg", stock_qty=10, purchase_price_gs=1000)
        s.add(ing)
        s.flush()
        rec = Recipe(name="r_test_setable", yield_qty=10, yield_unit="und")
        s.add(rec)
        s.flush()
        mvt = StockMovement(
            ingredient_id=ing.id,
            movement_type="sale",
            qty=-0.5,
            reason="test sale",
            affected_recipe_id=rec.id,
        )
        s.add(mvt)
        s.commit()
        loaded = s.get(StockMovement, mvt.id)
        assert loaded.affected_recipe_id == rec.id


def test_stock_movement_affected_recipe_id_has_index(session_factory):
    """Index on affected_recipe_id lets the future backfill/aggregation
    scan quickly."""
    inspector = inspect(session_factory().get_bind())
    indexes = {i["name"] for i in inspector.get_indexes("stock_movement")}
    assert "ix_stock_movement_affected_recipe_id" in indexes


def test_migration_090_idempotent(tmp_path):
    """Re-running init_db on a DB already at schema 92 is a no-op."""
    from sqlalchemy import create_engine

    from app.rms.db import init_db

    db = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db}")
    init_db(engine)
    # Second run: must not raise.
    init_db(engine)
    with engine.connect() as conn:
        v = conn.execute(text("SELECT value FROM app_meta WHERE key='schema_version'")).scalar()
    # Schema is now 92 (after migration 092 drop sale_stock_move).
    assert int(v) == 92
