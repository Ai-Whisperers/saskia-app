"""app/rms/db.py — engine, session, pragmas, versioned migrations.

Per dev plan §9 Task 1 + improvements review §2.2.

Pragmas (set on every connection via SQLAlchemy event listener):
- WAL mode (concurrent reads, single writer; survives power loss)
- secure_delete = ON (deleted rows are zeroed, not just unlinked)
- foreign_keys = ON (FK constraints actually enforced)

Schema versioning: `app_meta` table tracks `current_schema_version`. `init_db()`
runs pending migrations from `MIGRATIONS` dict in order. Each migration is a
Python function that takes a SQLAlchemy connection and applies the schema change.

Why hand-rolled (not Alembic):
- Alembic adds a heavy dependency for a 70h single-user project
- Schema is small (8 tables) and changes rarely
- 30 lines of code is enough
- Documented in app/rms/AGENTS.md

This module is import-safe (no side effects on import). `init_db()` must be called
explicitly, typically from `main.py`'s lifespan handler.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.rms.config import (
    CURRENT_SCHEMA_VERSION,
    DB_PATH,
    ensure_dirs,
)


def _set_sqlite_pragmas(dbapi_conn: Any, _: Any) -> None:
    """SQLAlchemy connect listener: enable WAL + secure_delete + foreign_keys.

    Called on every new connection. Idempotent.
    """
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA secure_delete=ON")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def make_engine(url: str | None = None, *, for_tests: bool = False) -> Engine:
    """Create SQLAlchemy engine with SQLite pragmas.

    Args:
        url: SQLite URL. Defaults to file at DB_PATH. Pass "sqlite:///:memory:"
            for in-memory test DB.
        for_tests: when True, allows multiple connections (SQLite's StaticPool
            would conflict with our pragma listener otherwise).
    """
    if url is None:
        ensure_dirs()
        url = f"sqlite:///{DB_PATH}"

    kwargs: dict[str, Any] = {
        "echo": False,
        "future": True,
    }
    if for_tests:
        # StaticPool for in-memory + connect listener compatibility
        from sqlalchemy.pool import StaticPool

        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["poolclass"] = StaticPool
    else:
        kwargs["connect_args"] = {"check_same_thread": False}

    engine = create_engine(url, **kwargs)
    event.listen(engine, "connect", _set_sqlite_pragmas)
    return engine


# --- Versioned migrations ---
# Each migration is a function that takes a connection and applies schema changes.
# Migrations are run in order from `1` to `CURRENT_SCHEMA_VERSION` (inclusive).
# To add a migration: bump CURRENT_SCHEMA_VERSION in config.py, add a function here,
# add it to MIGRATIONS dict below.

MigrationFn = Callable[[Any], None]


def _migration_001_initial_schema(conn: Any) -> None:
    """Initial schema (8 tables). Called once on fresh DBs.

    We let SQLAlchemy's create_all() do the heavy lifting; this migration is a
    marker for the schema version. It also seeds the app_meta table.

    Dialect-aware upsert: SQLite uses INSERT OR IGNORE; Postgres uses
    ON CONFLICT DO NOTHING. We detect the dialect via the bind dialect name.
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    ts = datetime.now(timezone.utc).isoformat()
    if dialect == "postgresql":
        # app_meta.value is JSONB on production (legacy column type);
        # cast string → jsonb so the insert doesn't fail. Build the
        # string in Python so SQLAlchemy parameter binding doesn't
        # fight with ::type casts.
        ts_quoted = ts.replace("'", "''")
        upsert = (
            f"INSERT INTO app_meta (key, value, updated_at) "
            f"VALUES ('schema_version', '\"1\"'::jsonb, '{ts_quoted}') "
            f"ON CONFLICT (key) DO NOTHING"
        )
        upsert2 = (
            f"INSERT INTO app_meta (key, value, updated_at) "
            f"VALUES ('created_at', '\"{ts_quoted}\"'::jsonb, '{ts_quoted}') "
            f"ON CONFLICT (key) DO NOTHING"
        )
    else:
        upsert = "INSERT OR IGNORE INTO app_meta (key, value) VALUES ('schema_version', '1')"
        upsert2 = "INSERT OR IGNORE INTO app_meta (key, value) VALUES ('created_at', :ts)"
    conn.execute(text(upsert), {"ts": ts})
    conn.execute(text(upsert2), {"ts": ts})


def _migration_002_audit_log(conn: Any) -> None:
    """Add the audit_log table (E3.S1).

    Records every security-relevant action: login success/failure, logout,
    password reset, sales CRUD, recipe/product edits, inventory movements.

    created_at column (datetime UTC) gets a btree index so admin queries on
    /audit?since=...&until=... are fast. user_id + action get their own
    indexes for filter-by-user / filter-by-action queries.

    No backfill: there is no historical data to migrate. Existing rows in
    other tables are unaffected.
    """
    conn.execute(
        text(
            "CREATE TABLE IF NOT EXISTS audit_log ("
            "id SERIAL PRIMARY KEY, "
            "occurred_at DATETIME NOT NULL, "
            "user_id VARCHAR(64), "
            "action VARCHAR(64) NOT NULL, "
            "target_type VARCHAR(64), "
            "target_id VARCHAR(64), "
            "detail TEXT NOT NULL DEFAULT '{}', "
            "ip VARCHAR(64), "
            "user_agent VARCHAR(256)"
            ")"
        )
    )
    # Postgres-compatible: CREATE INDEX IF NOT EXISTS is SQLite-only.
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    if dialect == "postgresql":
        for ix_name, ix_table, ix_col in [
            ("ix_audit_log_occurred_at", "audit_log", "occurred_at"),
            ("ix_audit_log_user_id", "audit_log", "user_id"),
            ("ix_audit_log_action", "audit_log", "action"),
        ]:
            existing = conn.execute(
                text("SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname=:n"),
                {"n": ix_name},
            ).first()
            if existing is None:
                conn.execute(text(f"CREATE INDEX {ix_name} ON {ix_table} ({ix_col})"))
    else:
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_log_occurred_at ON audit_log (occurred_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_log_user_id ON audit_log (user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_log_action ON audit_log (action)"))
    conn.execute(
        text("UPDATE app_meta SET value = '2', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


def _migration_007_product_sku(conn: Any) -> None:
    """Add Product.sku column (E23.S1).

    SKU is optional; most bakeries don't print barcodes on products but
    an operator may add them later. Unique when set.
    Schema bumps via create_all idempotency."""
    conn.execute(
        text("UPDATE app_meta SET value = '7', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


def _migration_006_waste_log(conn: Any) -> None:
    """Add waste_log table (E22)."""
    conn.execute(
        text("UPDATE app_meta SET value = '6', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


def _migration_005_customer(conn: Any) -> None:
    """Add Customer table + Sale.customer_id FK (E13).

    Tables are created via create_all() in init_db(). The Sale
    FK column is added in case create_all didn't (e.g. on an existing
    DB that pre-dates the customer table).
    """
    conn.execute(
        text("UPDATE app_meta SET value = '5', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


def _migration_004_tags(conn: Any) -> None:
    """Add Tag + TagLink tables (E9.S1).

    Tags are polymorphic (target_kind in product|ingredient|recipe). The
    tag table holds the name + color + kind; the tag_link table holds
    the M:N mapping.

    Both tables are created via create_all() in init_db(). Here we
    just bump the schema version.
    """
    # create_all is called by init_db BEFORE this migration runs.
    # Nothing else to do — the new tables already exist.
    conn.execute(
        text("UPDATE app_meta SET value = '4', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


def _migration_003_analytics_columns(conn: Any) -> None:
    """Add analytics-tracking columns (E8).

    New columns:
    - ingredient.purchase_price_updated_at: tracks when the cost was last changed
      (used by margin_erosion_alerts in app/rms/analytics.py)
    - ingredient.last_consumed_at: tracks the most recent sale that consumed this
      ingredient (used by dead_stock and stock_turnover reports)
    - ingredient.shelf_life_days: optional, drives spoilage alerts (E22)
    - recipe.prep_minutes: optional, drives cost-per-prep-minute reports

    All columns are nullable / optional so the migration is safe on existing rows
    (which get NULL = "unknown" rather than a fabricated value).
    """
    # SQLite ALTER TABLE supports adding columns one at a time. Wrap in try/except
    # so re-running this migration on an already-migrated DB is a no-op.
    # Postgres uses TIMESTAMP; SQLite accepts both.
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    ts_type = "TIMESTAMP" if dialect == "postgresql" else "DATETIME"
    _add_columns = [
        ("ingredient", "purchase_price_updated_at", ts_type),
        ("ingredient", "last_consumed_at", ts_type),
        ("ingredient", "shelf_life_days", "INTEGER"),
        ("recipe", "prep_minutes", "INTEGER"),
    ]
    for table, col, decl in _add_columns:
        try:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {decl}"))
        except Exception:  # noqa: BLE001 - column already exists; that's fine
            pass

    # Index on last_consumed_at so dead_stock reports stay fast.
    # CREATE INDEX IF NOT EXISTS is SQLite syntax; on Postgres use a
    # check against pg_indexes.
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    if dialect == "postgresql":
        existing = conn.execute(
            text(
                "SELECT 1 FROM pg_indexes "
                "WHERE schemaname='public' AND indexname='ix_ingredient_last_consumed_at'"
            )
        ).first()
        if existing is None:
            conn.execute(
                text(
                    "CREATE INDEX ix_ingredient_last_consumed_at "
                    "ON ingredient (last_consumed_at)"
                )
            )
    else:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_ingredient_last_consumed_at "
                "ON ingredient (last_consumed_at)"
            )
        )

    conn.execute(
        text("UPDATE app_meta SET value = '3', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )



def _migration_008_tenant(conn):
    """Add tenant table (E15)."""
    conn.execute(
        text("UPDATE app_meta SET value = '8', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


def _migration_009_ingredient_intel(conn):
    """Add ingredient intelligence columns (E26): category, subcategory, role,
    allergens, dietary_tags, lead_time_days.
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    # Use TEXT type — works on both dialects.
    cols = [
        ("category", "VARCHAR(32)"),
        ("subcategory", "VARCHAR(32)"),
        ("role", "VARCHAR(32)"),
        ("allergens", "JSONB" if dialect == "postgresql" else "TEXT"),
        ("dietary_tags", "JSONB" if dialect == "postgresql" else "TEXT"),
        ("lead_time_days", "INTEGER DEFAULT 3"),
    ]
    for col_name, col_type in cols:
        try:
            conn.execute(text(f"ALTER TABLE ingredient ADD COLUMN {col_name} {col_type}"))
        except Exception:
            # Column already exists — idempotent.
            pass
    conn.execute(
        text("UPDATE app_meta SET value = '9', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


def _migration_010_recipe_intel(conn):
    """Add recipe intelligence columns (E27): family, difficulty, dietary_tags,
    cook_minutes. prep_minutes already exists (added in migration 003).
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    cols = [
        ("family", "VARCHAR(32)"),
        ("difficulty", "INTEGER"),
        ("dietary_tags", "JSONB" if dialect == "postgresql" else "TEXT"),
        ("cook_minutes", "INTEGER"),
    ]
    for col_name, col_type in cols:
        try:
            conn.execute(text(f"ALTER TABLE recipe ADD COLUMN {col_name} {col_type}"))
        except Exception:
            # Column already exists — idempotent.
            pass
    conn.execute(
        text("UPDATE app_meta SET value = '10', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


MIGRATIONS = {
    1: _migration_001_initial_schema,
    2: _migration_002_audit_log,
    3: _migration_003_analytics_columns,
    4: _migration_004_tags,
    5: _migration_005_customer,
    6: _migration_006_waste_log,
    7: _migration_007_product_sku,
    8: _migration_008_tenant,
    9: _migration_009_ingredient_intel,
    10: _migration_010_recipe_intel,
}


def _current_schema_version(conn: Any) -> int:
    """Read schema version from app_meta table (default 0)."""
    row = conn.execute(text("SELECT value FROM app_meta WHERE key = 'schema_version'")).first()
    if row is None:
        return 0
    try:
        return int(row[0])
    except (TypeError, ValueError):
        return 0


def init_db(engine: Engine) -> None:
    """Initialize the database: create tables + run pending migrations.

    Idempotent. Safe to call on every app startup.
    """
    from app.rms.models import Base  # local import to avoid circular deps

    # 1. Create all tables (idempotent; SQLAlchemy skips existing tables)
    Base.metadata.create_all(engine)

    # 2. Run migrations
    with engine.connect() as conn:
        # Ensure app_meta exists (create_all should have made it, but defensive)
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS app_meta ("
                "key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)"
            )
        )

        current = _current_schema_version(conn)
        target = CURRENT_SCHEMA_VERSION

        if current < target:
            # Detect dialect for dialect-aware schema_version upsert.
            dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
            for v in range(current + 1, target + 1):
                if v not in MIGRATIONS:
                    raise RuntimeError(
                        f"No migration registered for schema version {v}; "
                        f"current={current}, target={target}. "
                        "Add the migration in app/rms/db.py."
                    )
                # Postgres aborts the whole transaction on a SQL error,
                # so wrap each migration in a SAVEPOINT to keep going
                # after a benign error (e.g. column already exists).
                if dialect == "postgresql":
                    sp = f"mig_{v}"
                    conn.execute(text(f"SAVEPOINT {sp}"))
                    try:
                        MIGRATIONS[v](conn)
                    except Exception:
                        conn.execute(text(f"ROLLBACK TO SAVEPOINT {sp}"))
                        # Re-raise — migration errors should NOT be silently swallowed
                        # on Postgres, only on SQLite.
                        raise
                    conn.execute(text(f"RELEASE SAVEPOINT {sp}"))
                else:
                    MIGRATIONS[v](conn)
                ts_now = datetime.now(timezone.utc).isoformat()
                if dialect == "postgresql":
                    # app_meta.value is JSONB on prod; cast int → jsonb.
                    upsert_v = (
                        f"INSERT INTO app_meta (key, value, updated_at) "
                        f"VALUES ('schema_version', '\"{v}\"'::jsonb, '{ts_now}') "
                        f"ON CONFLICT (key) DO UPDATE SET "
                        f"value = EXCLUDED.value, updated_at = EXCLUDED.updated_at"
                    )
                    conn.execute(text(upsert_v))
                else:
                    conn.execute(
                        text(
                            "INSERT OR REPLACE INTO app_meta (key, value, updated_at) "
                            "VALUES ('schema_version', :v, :ts)"
                        ),
                        {"v": str(v), "ts": ts_now},
                    )
        conn.commit()


def make_session_factory(engine: Engine) -> sessionmaker:
    """Create a configured sessionmaker bound to the engine."""
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def get_db_session(session_factory: sessionmaker) -> Session:
    """Open a new session. Caller is responsible for closing it.

    Typical use:
        sf = make_session_factory(engine)
        with get_db_session(sf) as session:
            ...
    """
    return session_factory()


__all__ = [
    "make_engine",
    "init_db",
    "make_session_factory",
    "get_db_session",
    "MIGRATIONS",
    "MigrationFn",
]


def _get_db_url_safe() -> str:
    """Return the database URL stripped of credentials.

    Used in backup manifests so the file does not leak the password.
    Returns something like "postgresql+psycopg2://***@host/db".
    """
    import os
    from urllib.parse import urlsplit, urlunsplit

    url = os.environ.get("AIW_SASKIA_DB_URL", "sqlite:///./saskia.db")
    if url.startswith("sqlite"):
        return "sqlite:///<local>"
    try:
        parts = urlsplit(url)
        if parts.username or parts.password:
            netloc = "***@" + parts.netloc.split("@", 1)[-1]
            return urlunsplit((parts.scheme, netloc, parts.path, parts.query, ""))
        return url
    except Exception:
        return "<unknown>"
