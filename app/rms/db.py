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
    """
    # create_all is called by the caller before this migration runs (see init_db).
    # Here we just record the schema version.
    conn.execute(text("INSERT OR IGNORE INTO app_meta (key, value) VALUES ('schema_version', '1')"))
    conn.execute(
        text("INSERT OR IGNORE INTO app_meta (key, value) VALUES ('created_at', :ts)"),
        {"ts": "2026-09-01T00:00:00Z"},
    )


MIGRATIONS: dict[int, MigrationFn] = {
    1: _migration_001_initial_schema,
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
            for v in range(current + 1, target + 1):
                if v not in MIGRATIONS:
                    raise RuntimeError(
                        f"No migration registered for schema version {v}; "
                        f"current={current}, target={target}. "
                        "Add the migration in app/rms/db.py."
                    )
                MIGRATIONS[v](conn)
                conn.execute(
                    text(
                        "INSERT OR REPLACE INTO app_meta (key, value, updated_at) "
                        "VALUES ('schema_version', :v, :ts)"
                    ),
                    {"v": str(v), "ts": "2026-09-01T00:00:00Z"},
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
