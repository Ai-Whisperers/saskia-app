"""app/rms/db_dialect.py — dialect-agnostic engine factory.

Reads DATABASE_URL env var. If unset, falls back to SQLite at DB_PATH
for local development and tests.

This replaces the hardcoded SQLite path in app/rms/db.py. The original
db.py is kept for tests (which need SQLite + tmp_db_path fixture).

Why both files exist:
- tests/conftest.py uses app.rms.db (SQLite, fast, ephemeral)
- Production app uses app.rms.db_dialect (Postgres via DATABASE_URL)
- Both call init_db(engine) which works on either dialect
- The model classes are duplicated (schema_postgres.py mirrors models.py)
  because cross-dialect polymorphism via `Base` is fragile.
  See app/rms/schema_postgres.py for why.

Production usage:
    DATABASE_URL=postgresql://user:pass@host/db uv run uvicorn ...

Test usage (default):
    uv run pytest  # uses SQLite tmp
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from app.rms.config import DB_PATH


def _is_postgres(url: str) -> bool:
    """True if the URL is a Postgres connection string."""
    return url.startswith(("postgresql://", "postgres://"))


def _set_sqlite_pragmas(dbapi_conn, _):
    """SQLite-specific pragmas. No-op for Postgres."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA secure_delete=ON")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def get_database_url() -> str:
    """Return the database URL, defaulting to local SQLite.

    Order of precedence:
    1. DATABASE_URL env var (production: Postgres)
    2. AIW_SASKIA_DB_PATH env var (test/dev: SQLite at custom path)
    3. config.DB_PATH (default: ~/.local/share/AIW-Saskia/rms.sqlite)
    """
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    # Fall through to SQLite path
    sqlite_path = Path(os.getenv("AIW_SASKIA_DB_PATH", str(DB_PATH)))
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{sqlite_path}"


def make_engine(url: str | None = None, *, for_tests: bool = False) -> Engine:
    """Create SQLAlchemy engine. SQLite or Postgres depending on URL.

    SQLite-specific pragmas only attach for sqlite URLs.
    """
    if url is None:
        url = get_database_url()

    kwargs: dict = {"echo": False, "future": True}

    if _is_postgres(url):
        # Production: Neon Postgres (free tier).
        # Use connection pool tuned for serverless / always-on.
        # pool_pre_ping handles stale connections (Render → Neon across NATs).
        kwargs["pool_pre_ping"] = True
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10
        kwargs["pool_recycle"] = 1800  # 30 min — match Neon idle timeout
    else:
        # Local SQLite.
        if for_tests:
            from sqlalchemy.pool import StaticPool

            kwargs["connect_args"] = {"check_same_thread": False}
            kwargs["poolclass"] = StaticPool
        else:
            kwargs["connect_args"] = {"check_same_thread": False}

    engine = create_engine(url, **kwargs)

    if not _is_postgres(url):
        event.listen(engine, "connect", _set_sqlite_pragmas)

    return engine


def get_metadata():
    """Return the right Base.metadata for the configured DATABASE_URL.

    Production Postgres → app.rms.schema_postgres.Base.metadata
    SQLite (tests/dev) → app.rms.models.Base.metadata

    Importing both modules unconditionally is fine — they have no side
    effects until Base.metadata.create_all() is called.
    """
    if _is_postgres(get_database_url()):
        from app.rms import schema_postgres

        return schema_postgres.Base.metadata
    from app.rms import models

    return models.Base.metadata


__all__ = ["get_database_url", "make_engine", "get_metadata", "_is_postgres"]
