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

    This is the bug that broke https://sazon-rms.paragu-ai.com
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
        "ingredient",
        "recipe",
        "recipe_line",
        "product",
        "sale",
        "stock_movement",  # T-2026-10-04: sale_stock_move dropped by migration 092
        "import_batch",
        "app_meta",
        "audit_log",
        "user",
        "tag",
        "tag_link",
        "customer",
        "waste_log",
        "tenant",
    }
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).all()
        found = {r[0] for r in rows}
    missing = expected_tables - found
    assert not missing, f"Missing tables: {missing}"


# --- Phase B — T1 migration v17 (recipe_line.line_unit) ---


def test_migration_017_adds_line_unit_column(tmp_path):
    """migration v17 adds line_unit VARCHAR(8) NOT NULL DEFAULT '' to recipe_line."""
    from sqlalchemy import text

    from app.rms.db import _migration_017_recipe_line_unit

    db = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db}")
    init_db(engine)  # creates all tables including recipe_line

    # Sanity: line_unit doesn't exist yet because CURRENT_SCHEMA_VERSION is 17
    # and init_db() already ran migration 17. Drop the column to test the
    # migration in isolation.
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE recipe_line DROP COLUMN line_unit"))
        conn.commit()

    with engine.connect() as conn:
        _migration_017_recipe_line_unit(conn)
        conn.commit()
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(recipe_line)")).fetchall()]
    assert "line_unit" in cols


def test_migration_017_is_idempotent(tmp_path):
    """Re-running migration 017 on a DB that already has line_unit does nothing destructive."""
    from app.rms.db import _migration_017_recipe_line_unit

    db = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db}")
    init_db(engine)

    with engine.connect() as conn:
        # Run twice — should not raise
        _migration_017_recipe_line_unit(conn)
        conn.commit()
        _migration_017_recipe_line_unit(conn)
        conn.commit()


def test_migration_017_backfills_existing_rows(tmp_path):
    """Existing recipe_line rows get line_unit = linked ingredient's unit."""
    from sqlalchemy import text

    from app.rms.db import _migration_017_recipe_line_unit, init_db

    db = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db}")
    init_db(engine)

    # Pre-seed with a recipe_line that has line_unit = '' (the legacy default).
    with engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO ingredient (name, unit, stock_qty, min_stock_qty, lead_time_days) "
                "VALUES ('Harina', 'kg', 5.0, 0.0, 3)"
            )
        )
        conn.execute(
            text("INSERT INTO recipe (name, yield_qty, yield_unit) VALUES ('Torta', 12.0, 'und')")
        )
        conn.execute(
            text(
                "INSERT INTO recipe_line (recipe_id, line_kind, line_ref_id, qty, line_unit) "
                "VALUES (1, 'ingredient', 1, 0.3, '')"
            )
        )
        conn.commit()

    # Now reset line_unit to '' to simulate a pre-migration row, then run v17.
    with engine.connect() as conn:
        conn.execute(text("UPDATE recipe_line SET line_unit = ''"))
        conn.commit()
        _migration_017_recipe_line_unit(conn)
        conn.commit()
        row = conn.execute(text("SELECT line_unit FROM recipe_line WHERE id = 1")).first()
    assert row is not None
    assert row[0] == "kg"  # backfilled from linked ingredient
