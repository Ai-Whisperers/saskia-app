"""Tests for migration 091: backfill stock_movement.affected_recipe_id.

After BACKLOG #1 was completed in this session (migration 092 dropped
the sale_stock_move table), migration 091 is a no-op on FRESH
databases (the source table no longer exists). For pre-92 databases
that ran migrations 1-90 in place, the backfill copies
affected_recipe_id from sale_stock_move into stock_movement rows.

The tests below cover the fresh-DB scenario (the table-existence
probe + idempotency). The pre-90 → 92 in-place upgrade scenario is
not directly testable here because recreating a legacy schema is
out of scope for the test suite.
"""

from __future__ import annotations

from sqlalchemy import create_engine, text


def _init_db_to_92():
    """Helper: build a fresh in-memory DB at schema 92."""
    engine = create_engine("sqlite:///:memory:")
    from app.rms.db import init_db

    init_db(engine)
    return engine


def test_migration_091_bumps_schema_version(session_factory):
    """Fresh DB hits 91+ after init_db."""
    with session_factory() as s:
        v = s.execute(text("SELECT value FROM app_meta WHERE key='schema_version'")).scalar()
    assert v is not None
    assert int(v) >= 91


def test_backfill_is_noop_on_fresh_db(session_factory):
    """Migration 091 is a no-op on a fresh post-092 DB.

    Guards the table-existence probe that prevents the migration from
    failing on a clean install.
    """
    from app.rms.migrations._091_backfill_stock_movement_recipe import (
        _migration_091_backfill_stock_movement_recipe,
    )

    with session_factory() as s:
        with s.connection() as conn:
            _migration_091_backfill_stock_movement_recipe(conn)
            s.commit()
        # No error raised — that's the assertion.


def test_migration_091_full_idempotent(tmp_path):
    """Re-running init_db on a 92 DB is a no-op."""
    db = tmp_path / "test91.db"
    engine = create_engine(f"sqlite:///{db}")
    from app.rms.db import init_db

    init_db(engine)
    init_db(engine)  # second run
    with engine.connect() as conn:
        v = conn.execute(text("SELECT value FROM app_meta WHERE key='schema_version'")).scalar()
    assert int(v) == 92
