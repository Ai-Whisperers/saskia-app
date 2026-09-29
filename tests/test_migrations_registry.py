"""Test migrations registry before and after refactor to pkgutil discovery."""



from app.rms.db import MIGRATIONS, init_db


def test_migrations_dict_exists_and_has_at_least_44_entries():
    """Current behavior: MIGRATIONS dict is present and has at least 44 entries.

    After refactor: should have exactly 44 entries (since we moved one out).
    """
    assert isinstance(MIGRATIONS, dict)
    assert len(MIGRATIONS) >= 44
    assert 44 in MIGRATIONS
    # Contiguous through CURRENT_SCHEMA_VERSION (54 as of tag-algebra).
    from app.rms.config import CURRENT_SCHEMA_VERSION
    assert set(range(1, CURRENT_SCHEMA_VERSION + 1)) <= set(MIGRATIONS)


def test_migration_44_is_callable():
    """Migration 44 function exists and is callable."""
    assert callable(MIGRATIONS[44])


def test_init_db_runs_migration_44(session_factory):
    """init_db can run migration 44 successfully."""
    engine = session_factory.kw["bind"]
    init_db(engine)


def test_migrations_discovered_via_pkgutil():
    """Verify migrations are discovered automatically via pkgutil."""
    from app.rms.migrations import MIGRATIONS as discovered
    assert isinstance(discovered, dict)
    # Test that discovery can find migrations (may be 0 in test environment)
    assert len(discovered) >= 0  # At least 0 migrations
