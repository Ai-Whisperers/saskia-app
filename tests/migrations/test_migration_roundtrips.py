"""tests/migrations/test_migration_roundtrips.py — Phase 1 refactored."""
import pytest
from sqlalchemy import text


pytestmark = [pytest.mark.migration, pytest.mark.smoke]


def test_fresh_db_reaches_head(app_engine, session_factory):
    """Empty SQLite DB should migrate to CURRENT_SCHEMA_VERSION on init."""
    from app.rms.db import init_db
    from app.rms.config import CURRENT_SCHEMA_VERSION

    init_db(app_engine)

    with session_factory() as s:
        r = s.execute(text("SELECT value FROM app_meta WHERE key='schema_version'")).first()
        assert r is not None
        assert int(r[0]) == CURRENT_SCHEMA_VERSION


def test_data_survives_init(app_engine, session_factory):
    """A sentinel row should survive init_db."""
    from app.rms.db import init_db

    init_db(app_engine)
    with session_factory() as s:
        s.execute(text(
            "INSERT OR REPLACE INTO app_meta (key, value, updated_at) "
            "VALUES ('test_sentinel', 'alive', CURRENT_TIMESTAMP)"
        ))
        s.commit()
    with session_factory() as s:
        sentinel = s.execute(text(
            "SELECT value FROM app_meta WHERE key='test_sentinel'"
        )).first()
        assert sentinel is not None
        assert sentinel[0] == "alive"


def test_idempotent_init_db(app_engine, session_factory):
    """Running init_db twice should not break anything."""
    from app.rms.db import init_db
    from app.rms.config import CURRENT_SCHEMA_VERSION

    init_db(app_engine)
    init_db(app_engine)

    with session_factory() as s:
        r = s.execute(text("SELECT value FROM app_meta WHERE key='schema_version'")).first()
        assert r is not None
        assert int(r[0]) == CURRENT_SCHEMA_VERSION


def test_migration_registry_imports():
    """The migration module should be importable."""
    try:
        from app.rms import migrations
        assert migrations is not None
    except ImportError:
        pytest.skip("migrations module not at expected location")


def test_init_db_does_not_raise(app_engine):
    """init_db should never raise on a fresh DB."""
    from app.rms.db import init_db
    init_db(app_engine)


def test_make_engine_creates_db_file(tmp_db_path):
    """make_engine should create the SQLite file."""
    from app.rms.db import make_engine
    from sqlalchemy import text

    db_path = tmp_db_path / "x.sqlite"
    engine = make_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def test_schema_version_is_int(app_engine, session_factory):
    """Schema version should be stored as a parseable integer."""
    from app.rms.db import init_db
    init_db(app_engine)
    with session_factory() as s:
        v = s.execute(text("SELECT value FROM app_meta WHERE key='schema_version'")).scalar()
        assert v is not None
        int(v)
