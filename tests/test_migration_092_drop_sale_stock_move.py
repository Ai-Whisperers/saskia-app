"""Tests for migration 092: drop sale_stock_move (BACKLOG #1 complete).

Validates:
- Schema reaches 92 after init_db
- The sale_stock_move table does NOT exist after init_db
- The stock_movement table still exists and is queryable
- init_db is idempotent on a 92 DB
- The SaleStockMove class still exists as an abstract stub (so legacy
  imports keep working) but is not usable as a row-insertable mapper
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, text


def test_migration_092_bumps_schema_version(session_factory):
    """Fresh DB hits 92 after init_db."""
    with session_factory() as s:
        v = s.execute(text("SELECT value FROM app_meta WHERE key='schema_version'")).scalar()
    assert v is not None
    assert int(v) >= 92


def test_sale_stock_move_table_does_not_exist(session_factory):
    """The legacy table was dropped by migration 092."""
    inspector = inspect(session_factory().get_bind())
    tables = inspector.get_table_names()
    assert "sale_stock_move" not in tables, (
        "migration 092 should have dropped sale_stock_move, but the table still exists."
    )


def test_stock_movement_table_still_exists(session_factory):
    """The consolidated read-path table is still present."""
    inspector = inspect(session_factory().get_bind())
    tables = inspector.get_table_names()
    assert "stock_movement" in tables


def test_sale_stock_move_class_is_abstract_stub():
    """The SaleStockMove class is preserved as an abstract stub so
    `from app.rms.models import SaleStockMove` keeps working, but it
    cannot be used to create a row."""
    from app.rms.models import SaleStockMove

    # Instantiating raises (the guard in the abstract class).
    with pytest.raises(TypeError) as exc:
        SaleStockMove(
            sale_id=1,
            affected_recipe_id=1,
            ingredient_id=1,
            qty_delta=-1.0,
        )
    assert "deprecated" in str(exc.value).lower() or "092" in str(exc.value)


def test_migration_092_full_idempotent(tmp_path):
    """Re-running init_db on a CURRENT_SCHEMA_VERSION DB is a no-op."""
    db = tmp_path / "test92.db"
    engine = create_engine(f"sqlite:///{db}")
    from app.rms.config import CURRENT_SCHEMA_VERSION
    from app.rms.db import init_db

    init_db(engine)
    init_db(engine)  # second run
    with engine.connect() as conn:
        v = conn.execute(text("SELECT value FROM app_meta WHERE key='schema_version'")).scalar()
    assert int(v) == CURRENT_SCHEMA_VERSION
