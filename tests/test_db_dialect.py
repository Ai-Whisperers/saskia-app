"""tests/test_db_dialect.py — DATABASE_URL routing + engine factory."""

from __future__ import annotations


def test_get_database_url_default_is_sqlite(tmp_path, monkeypatch):
    """No DATABASE_URL → SQLite at AIW_SASKIA_DB_PATH."""
    from app.rms.db_dialect import get_database_url

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("AIW_SASKIA_DB_PATH", str(tmp_path / "test.sqlite"))
    url = get_database_url()
    assert url.startswith("sqlite:///")


def test_get_database_url_postgres_when_set(monkeypatch):
    """DATABASE_URL=postgres://... wins over the SQLite default."""
    from app.rms.db_dialect import get_database_url

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@host.example/db")
    assert get_database_url().startswith("postgresql")


def test_is_postgres_detects_postgres_urls():
    from app.rms.db_dialect import _is_postgres

    assert _is_postgres("postgresql://x") is True
    assert _is_postgres("postgres://x") is True
    assert _is_postgres("sqlite:///x") is False


def test_make_engine_creates_sqlite_engine_for_sqlite_url(tmp_path):
    """SQLite URL → SQLite engine."""
    from app.rms.db_dialect import make_engine

    engine = make_engine(f"sqlite:///{tmp_path}/test.sqlite")
    assert engine.dialect.name == "sqlite"


def test_make_engine_creates_postgres_engine_for_postgres_url():
    """Postgres URL → Postgres engine."""
    from app.rms.db_dialect import make_engine

    # Use the psycopg3 driver explicitly (SQLAlchemy 2.0 needs postgresql+psycopg://)
    engine = make_engine("postgresql+psycopg://user:pass@host.example/db")
    assert engine.dialect.name == "postgresql"


def test_get_metadata_returns_postgres_metadata_for_postgres(monkeypatch):
    """With DATABASE_URL=postgres, get_metadata returns Postgres metadata."""
    from app.rms import schema_postgres
    from app.rms.db_dialect import get_metadata

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@host/db")
    metadata = get_metadata()
    # SQLAlchemy MetaData objects compare by identity, so check via tables
    pg_tables = set(schema_postgres.Base.metadata.tables.keys())
    assert pg_tables.issubset(set(metadata.tables.keys()))


def test_get_metadata_returns_sqlite_metadata_by_default(monkeypatch):
    """No DATABASE_URL → SQLite metadata."""
    from app.rms import models
    from app.rms.db_dialect import get_metadata

    monkeypatch.delenv("DATABASE_URL", raising=False)
    metadata = get_metadata()
    assert metadata is models.Base.metadata
