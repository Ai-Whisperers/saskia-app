"""tests/test_schema_version_helper.py — schema version drift detector."""

from app.rms.db import (
    CURRENT_SCHEMA_VERSION,
    app_meta_read,
    app_meta_write,
    schema_version,
    schema_version_mismatch,
)


def test_schema_version_returns_int(session_factory):
    """schema_version(conn) returns the current row's value as int."""
    from app.rms.db import init_db

    engine = session_factory.kw["bind"]
    init_db(engine)
    with session_factory() as s:
        v = schema_version(s.connection())
    assert isinstance(v, int)
    assert v == CURRENT_SCHEMA_VERSION


def test_schema_version_mismatch_returns_diff(session_factory):
    """schema_version_mismatch(conn) returns 0 when versions match."""
    from app.rms.db import init_db

    engine = session_factory.kw["bind"]
    init_db(engine)
    with session_factory() as s:
        diff = schema_version_mismatch(s.connection())
    assert diff == 0


def test_schema_version_mismatch_returns_positive_when_drift(session_factory):
    """schema_version_mismatch returns CURRENT - DB when DB is behind."""
    from app.rms.db import init_db

    engine = session_factory.kw["bind"]
    init_db(engine)
    # Force DB schema to an older version
    with session_factory() as s:
        app_meta_write(s.connection(), "schema_version", str(CURRENT_SCHEMA_VERSION - 1))
        diff = schema_version_mismatch(s.connection())
    assert diff == 1


def test_app_meta_write_creates_row_if_missing(session_factory):
    """app_meta_write INSERTs a new row when key doesn't exist."""
    with session_factory() as s:
        s.commit()
    with session_factory() as s:
        app_meta_write(s.connection(), "custom_key_test", "hello")
        s.commit()
    with session_factory() as s:
        assert app_meta_read(s.connection(), "custom_key_test") == "hello"


def test_app_meta_write_updates_existing_row(session_factory):
    """app_meta_write UPDATES an existing key (upsert behavior)."""
    from app.rms.db import init_db

    engine = session_factory.kw["bind"]
    init_db(engine)
    with session_factory() as s:
        app_meta_write(s.connection(), "test_key", "first")
        s.commit()
        app_meta_write(s.connection(), "test_key", "second")
        s.commit()
        assert app_meta_read(s.connection(), "test_key") == "second"


def test_schema_version_reads_jsonb_int(session_factory):
    """Regression for 2026-10-03 smoke failure:
    on Postgres, app_meta.value is JSONB; the migration runner writes
    `f'"{version}"'` (a JSON string). Reading it back via
    `SELECT value` returns the JSON-decoded value, which on Postgres
    for a string-wrapped number is the unquoted integer — and the
    int() conversion was failing because row[0] was a string
    containing JSON quotes.

    The fix: JSON-decode the value if it's a string before calling
    int(). This test simulates both the SQLite (text '97') and the
    Postgres JSONB (text '"97"') shapes.
    """
    import json as _json
    from datetime import datetime, timezone

    from app.rms.db import _current_schema_version, init_db

    engine = session_factory.kw["bind"]
    init_db(engine)

    # Case 1: value is plain text "97" (SQLite).
    with session_factory() as s:
        app_meta_write(s.connection(), "schema_version", "97")
        s.commit()
        v = _current_schema_version(s.connection())
    assert v == 97, f"expected 97, got {v}"

    # Case 2: value is JSON-encoded text '"97"' (Postgres JSONB round-trip).
    ts = datetime.now(timezone.utc).isoformat()
    with session_factory() as s:
        conn = s.connection()
        dialect = conn.dialect.name
        from sqlalchemy import text as _text
        if dialect == "postgresql":
            conn.execute(_text(
                "INSERT INTO app_meta (key, value, updated_at) "
                "VALUES ('schema_version', '\"97\"'::jsonb, :ts) "
                "ON CONFLICT (key) DO UPDATE SET value = '\"97\"'::jsonb, updated_at = :ts"
            ), {"ts": ts})
        else:
            conn.execute(_text(
                "INSERT OR REPLACE INTO app_meta (key, value, updated_at) "
                "VALUES ('schema_version', :v, :ts)"
            ), {"v": _json.dumps(97), "ts": ts})
        s.commit()
    # Read in a fresh session so the connection isn't closed.
    with session_factory() as s:
        v2 = _current_schema_version(s.connection())
    assert v2 == 97, f"expected 97 (from JSON-decoded value), got {v2}"
