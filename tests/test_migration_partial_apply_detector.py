"""Tests for the migration partial-apply detector (Phase 14 backlog #4).

When a Postgres migration raises partway through (after some ALTERs
succeeded but before the schema_version bump), the DB is in an
inconsistent state. The detector in _init_db_inner re-reads
schema_version after a failed migration and raises RuntimeError if it
advanced anyway — preventing the next migration from assuming a clean
baseline.

We can't easily simulate "Postgres DDL partially applied + bump ran
before the error", so we test the hook with a hand-crafted engine +
monkeypatched schema_version function.
"""

from __future__ import annotations

import pytest

from app.rms import db as db_mod


@pytest.fixture
def fake_engine():
    """Minimal stand-in for an Engine — tracks connect() invocations."""

    class _Conn:
        def __init__(self, parent):
            self.parent = parent
            self.committed = False
            self.executed = []

        def commit(self):
            self.committed = True

        def close(self):
            pass

        def execute(self, stmt, *params):
            self.executed.append((stmt, params))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _Engine:
        def __init__(self):
            self.connections = []
            self._probe_returns = [0]  # initial probe: schema_version = 0

        def connect(self):
            c = _Conn(self)
            self.connections.append(c)
            return c

    return _Engine()


def test_migration_partial_apply_detected_and_raised(monkeypatch, fake_engine):
    """If a migration fails but schema_version advances, init_db raises."""
    monkeypatch.setattr(
        db_mod,
        "sync_backup_before_migration",
        lambda *a, **kw: None,  # unit test: the backup path is covered elsewhere
    )
    # Monkeypatch schema_version to first return 0 (initial probe),
    # then return 5 after the failing migration ran.
    calls = {"n": 0}

    def fake_schema_version(conn):
        calls["n"] += 1
        if calls["n"] == 1:
            return 0  # initial probe
        return 5  # post-failure probe — partial apply!

    monkeypatch.setattr(db_mod, "schema_version", fake_schema_version)
    monkeypatch.setattr(db_mod, "CURRENT_SCHEMA_VERSION", 6)

    # Register a migration that raises AFTER advancing the schema_version
    # (simulating the partial-apply bug). We register v5 only (so the loop
    # tries v5 once).
    def bad_migration_5(conn):
        # Simulate: ALTER succeeded + bump ran, then a later statement
        # raised (e.g. CREATE TRIGGER syntax). The schema_version bump is
        # already committed (somehow — Postgres with auto-commit DDL),
        # so the post-failure probe returns >= 5.
        # We emulate the bump by directly setting it.
        from app.rms.db import _bump_schema_version

        _bump_schema_version(conn, 5)
        # Now raise:
        raise RuntimeError("simulated: CREATE TRIGGER syntax error after bump")

    monkeypatch.setitem(db_mod.MIGRATIONS, 5, bad_migration_5)

    # We also need a dummy migration 6 so the loop doesn't complain at
    # the "v not in MIGRATIONS" check — but it'll never reach v6 because
    # the partial-apply raise aborts. Let's just register an empty v6.
    monkeypatch.setitem(db_mod.MIGRATIONS, 6, lambda c: None)

    # And a stub Base.metadata.create_all — only needs to not crash.
    class FakeMeta:
        def create_all(self, engine):
            pass

    class FakeBase:
        metadata = FakeMeta()

    # Run init_db; expect RuntimeError about partial apply
    with pytest.raises(RuntimeError, match="DDL PARTIAL APPLY"):
        db_mod._init_db_inner(fake_engine, "sqlite", FakeBase)


def test_migration_failure_without_advance_fails_closed(monkeypatch, fake_engine):
    """Migration fails but schema_version did NOT advance — init_db aborts
    (SASKIA-318 fail-closed: a chain must not skip a failed link; the old
    log-and-continue behavior silently dropped v112's triggers in prod)."""
    calls = {"n": 0}

    def fake_schema_version(conn):
        calls["n"] += 1
        return 0  # both probes return 0 — no advance

    monkeypatch.setattr(db_mod, "schema_version", fake_schema_version)
    monkeypatch.setattr(db_mod, "CURRENT_SCHEMA_VERSION", 5)
    monkeypatch.setattr(
        db_mod,
        "sync_backup_before_migration",
        lambda *a, **kw: None,  # unit test: the backup path is covered elsewhere
    )

    def bad_migration_5(conn):
        raise RuntimeError("simulated: full migration failure")

    monkeypatch.setitem(db_mod.MIGRATIONS, 5, bad_migration_5)

    class FakeMeta:
        def create_all(self, engine):
            pass

    class FakeBase:
        metadata = FakeMeta()

    with pytest.raises(RuntimeError, match="migration v5 failed"):
        db_mod._init_db_inner(fake_engine, "sqlite", FakeBase)


def test_migration_success_probes_cleanly(monkeypatch, fake_engine):
    """A successful migration advances schema_version → no detector fire."""
    calls = {"n": 0}

    def fake_schema_version(conn):
        calls["n"] += 1
        if calls["n"] == 1:
            return 0
        return 5  # bumped correctly

    monkeypatch.setattr(db_mod, "schema_version", fake_schema_version)
    monkeypatch.setattr(db_mod, "CURRENT_SCHEMA_VERSION", 5)
    monkeypatch.setattr(
        db_mod,
        "sync_backup_before_migration",
        lambda *a, **kw: None,  # unit test: the backup path is covered elsewhere
    )

    def good_migration_5(conn):
        from app.rms.db import _bump_schema_version

        _bump_schema_version(conn, 5)

    monkeypatch.setitem(db_mod.MIGRATIONS, 5, good_migration_5)

    class FakeMeta:
        def create_all(self, engine):
            pass

    class FakeBase:
        metadata = FakeMeta()

    # No raise — successful path.
    db_mod._init_db_inner(fake_engine, "sqlite", FakeBase)
