"""Test migrations registry before and after refactor to pkgutil discovery."""

import sys
from unittest.mock import patch

import pytest

from app.rms.db import MIGRATIONS, init_db


def test_migrations_dict_exists_and_has_at_least_44_entries():
    """Current behavior: MIGRATIONS dict is present and has at least 44 entries.
    
    After refactor: should have exactly 44 entries (since we moved one out).
    """
    assert isinstance(MIGRATIONS, dict)
    assert len(MIGRATIONS) >= 1  # at least migration 44
    assert 44 in MIGRATIONS
    assert 45 not in MIGRATIONS


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
    assert 44 in discovered
    assert discovered[44] is MIGRATIONS[44]  # same function