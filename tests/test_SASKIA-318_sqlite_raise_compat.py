"""SASKIA-318: SQLite RAISE() compat + fail-closed migration runner.

Regression guards for the 2026-10-08 prod incident:

1. RAISE(ABORT, <expr>) with a concatenated expression requires SQLite
   >= 3.47.0 (2024-10-21). The prod container ships 3.46.1 where the
   CREATE TRIGGER in migrations 111/112 failed with
   ``near "||": syntax error``. Migrations must only use STRING LITERAL
   messages in RAISE().

2. The migration runner used to log-and-continue on a failed migration,
   letting later migrations apply on top of a broken earlier one and
   permanently hiding the gap (channel triggers were lost this way).
   The runner must fail closed.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.rms import db as db_mod
from app.rms.db import init_db, schema_version


def _fresh_db(tmp_path: Path, name: str = "chain.sqlite") -> str:
    db = tmp_path / name
    return f"sqlite:///{db}"


def test_migrations_111_112_use_only_literal_raise() -> None:
    """RAISE message in migrations must be a single string literal — no
    `||` concatenation (requires SQLite >= 3.47.0; prod ships 3.46.1)."""
    import app.rms.migrations._111_sale_channel_check as m111
    import app.rms.migrations._112_extended_channel_check as m112

    for mod in (m111, m112):
        src = Path(mod.__file__).read_text()
        assert "CREATE TRIGGER" in src
        for line in src.splitlines():
            if "RAISE(ABORT" in line:
                assert "||" not in line, (
                    f"{mod.__name__}: RAISE uses an expression message "
                    f"(requires SQLite >= 3.47): {line.strip()!r}"
                )


def test_channel_triggers_created_and_enforced(tmp_path: Path) -> None:
    """End-to-end: full chain on a fresh DB must leave the 4 channel
    triggers in place and enforcing (the incident: chain reported v114
    but the triggers were missing)."""
    url = _fresh_db(tmp_path)
    engine = create_engine(url)
    init_db(engine)
    db_file = url.replace("sqlite:///", "")
    conn = sqlite3.connect(db_file)
    try:
        trigs = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE '%channel_check%'"
            ).fetchall()
        }
        assert trigs == {
            "sale_channel_check_insert",
            "sale_channel_check_update",
            "pedido_channel_check_insert",
            "pedido_channel_check_update",
        }, f"channel triggers missing after full chain: {sorted(trigs)}"
        # enforcement smoke: bogus channel must abort
        cols = [r[1] for r in conn.execute("PRAGMA table_info(sale)").fetchall()]
        assert "channel" in cols
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO sale (channel) VALUES ('bogus_channel')")
    finally:
        conn.close()


def test_migration_runner_fails_closed_on_broken_migration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing migration must abort init_db, NOT be skipped while later
    versions still apply (the incident: v112 failed, v113/v114 applied)."""
    url = _fresh_db(tmp_path, "failclosed.sqlite")
    engine = create_engine(url)
    init_db(engine)

    with engine.connect() as probe:
        current = schema_version(probe)

    def _boom(conn):  # simple failure stub
        conn.execute(text("CREATE TABLE this_is_fine (x INT)"))
        raise RuntimeError("simulated migration crash")

    monkeypatch.setitem(db_mod.MIGRATIONS, current + 1, _boom)
    monkeypatch.setattr(db_mod, "CURRENT_SCHEMA_VERSION", current + 1)

    with pytest.raises(RuntimeError, match=r"migration v\d+ failed"):
        init_db(engine)

    # The failed migration must NOT have been silently skipped:
    with engine.connect() as probe:
        after = schema_version(probe)
    assert after == current, "version advanced past a failed migration"
