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
