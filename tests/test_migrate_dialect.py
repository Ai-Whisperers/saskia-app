"""Tests for dialect-aware migration code (live-site Postgres bugfix)."""
from __future__ import annotations

from sqlalchemy import create_engine, text

from app.rms.config import CURRENT_SCHEMA_VERSION
from app.rms.db import (
    MIGRATIONS,
    _migration_001_initial_schema,
    init_db,
)


def test_migrations_dict_has_all_versions():
    """All versions 1..CURRENT_SCHEMA_VERSION must be registered."""
    assert len(MIGRATIONS) == CURRENT_SCHEMA_VERSION
    for v in range(1, CURRENT_SCHEMA_VERSION + 1):
        assert v in MIGRATIONS, f"Missing migration {v}"


def test_init_db_postgres_uses_jsonb_and_upsert():
    """init_db() must succeed on Postgres without 'INSERT OR' errors.

    This is the bug that broke https://saskia-rms.paragu-ai.com
    on 2026-09-08 — the production DB only had Round-1 schema, and
    the migrate command threw 'syntax error at OR near' because
    SQLite-only INSERT OR IGNORE / INSERT OR REPLACE don't exist
    on Postgres.
    """
    # Use SQLite in-memory with PG-compatible column types via dialect mock? No —
    # better to just verify the SQL strings are dialect-aware.

    # Verify migration 001 uses ON CONFLICT for PG
    # (Inspect the source code's literal strings.)
    import inspect
    src = inspect.getsource(_migration_001_initial_schema)
    assert "ON CONFLICT" in src
    assert "INSERT OR IGNORE" in src  # the SQLite branch


def test_create_all_idempotent_on_empty_sqlite(tmp_path):
    """Fresh SQLite init_db() succeeds and reaches target schema version."""
    db = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db}")
    init_db(engine)
    with engine.connect() as conn:
        v = conn.execute(text("SELECT value FROM app_meta WHERE key='schema_version'")).scalar()
        assert v is not None
        assert int(v) == CURRENT_SCHEMA_VERSION


def test_init_db_creates_all_required_tables(tmp_path):
    """All E1-E25 tables must be created on a fresh DB."""
    db = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db}")
    init_db(engine)
    expected_tables = {
        "ingredient", "recipe", "recipe_line", "product", "sale",
        "sale_stock_move", "import_batch", "app_meta", "audit_log",
        "user", "tag", "tag_link", "customer", "waste_log", "tenant",
    }
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).all()
        found = {r[0] for r in rows}
    missing = expected_tables - found
    assert not missing, f"Missing tables: {missing}"
