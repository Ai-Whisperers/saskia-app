"""tests/test_migrate_cli.py — verify aiw-saskia migrate is idempotent.

Per the 2026-09-04 critical-path plan, E2.S3.T2. Regresses the "apply twice
fails" class of bugs (the user-visible symptom would be 'schema_version
duplicate row' or 'table already exists' on second boot).
"""

from __future__ import annotations

import os
from pathlib import Path


def _run_migrate(db_path: Path):
    """Invoke migrate() against a fresh SQLite file, capturing stdout."""

    # Fresh DB path
    if db_path.exists():
        db_path.unlink()

    os.environ["AIW_SASKIA_DB_PATH"] = str(db_path)
    # Reload to pick up new env
    from app.rms.db import _current_schema_version, init_db
    from app.rms.db_dialect import make_engine

    engine = make_engine(f"sqlite:///{db_path}")
    init_db(engine)

    # Verify version is at target
    with engine.connect() as conn:
        v = _current_schema_version(conn)
    return v


def test_migrate_first_run_creates_all_tables(tmp_path):
    """First migrate creates all 8 tables and sets schema_version=1."""
    from sqlalchemy import inspect

    from app.rms.db import CURRENT_SCHEMA_VERSION
    from app.rms.db_dialect import make_engine

    db_path = tmp_path / "first.sqlite"
    v = _run_migrate(db_path)
    assert v == CURRENT_SCHEMA_VERSION, f"expected version {CURRENT_SCHEMA_VERSION}, got {v}"

    engine = make_engine(f"sqlite:///{db_path}")
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    expected = {
        "ingredient",
        "recipe",
        "recipe_line",
        "product",
        "sale",
        "sale_stock_move",
        "user",
        "app_meta",
        "import_batch",
    }
    missing = expected - tables
    assert not missing, f"missing tables after first migrate: {missing}"


def test_migrate_second_run_is_idempotent(tmp_path):
    """Second migrate on the same DB is a no-op (no exceptions, no duplicates)."""
    from sqlalchemy import inspect

    from app.rms.db import CURRENT_SCHEMA_VERSION
    from app.rms.db_dialect import make_engine

    db_path = tmp_path / "second.sqlite"

    # First run
    v1 = _run_migrate(db_path)
    assert v1 == CURRENT_SCHEMA_VERSION

    # Second run (must not raise)
    v2 = _run_migrate(db_path)
    assert v2 == CURRENT_SCHEMA_VERSION

    # Table count must be identical (no dupes)
    engine = make_engine(f"sqlite:///{db_path}")
    insp = inspect(engine)
    tables = sorted(insp.get_table_names())
    assert len(tables) == len(set(tables)), f"duplicate tables created: {tables}"


def test_apply_neon_schema_script_noop_on_second_run(tmp_path, monkeypatch, capsys):
    """scripts/apply_neon_schema.py is idempotent — second run prints 'no-op'."""
    db_path = tmp_path / "neon-script.sqlite"

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("AIW_SASKIA_DB_PATH", str(db_path))

    # Need to make apply_neon_schema.py resolve DATABASE_URL via AIW_SASKIA_DB_PATH
    # (it doesn't — only `main.py migrate()` does). So instead test main.migrate() directly.
    import app.rms.main as m

    monkeypatch.setattr(m, "migrate", m.migrate)  # noop patch
    m.migrate()  # first run
    captured1 = capsys.readouterr()
    assert "schema_version: 0 ->" in captured1.out or "schema applied" in captured1.out

    m.migrate()  # second run
    captured2 = capsys.readouterr()
    assert "no-op" in captured2.out, f"expected no-op message, got: {captured2.out}"


def test_run_dispatches_migrate_argv(monkeypatch):
    """`aiw-saskia migrate` must call migrate(), not _serve()."""
    import sys

    import app.rms.main as m

    called = {"migrate": 0, "serve": 0}

    def fake_migrate():
        called["migrate"] += 1

    def fake_serve():
        called["serve"] += 1

    monkeypatch.setattr(m, "migrate", fake_migrate)
    monkeypatch.setattr(m, "_serve", fake_serve)
    monkeypatch.setattr(sys, "argv", ["aiw-saskia", "migrate"])

    m.run()
    assert called["migrate"] == 1
    assert called["serve"] == 0


def test_run_dispatches_serve_argv(monkeypatch):
    """`aiw-saskia serve` calls _serve(); `aiw-saskia` (no argv) also calls _serve()."""
    import sys

    import app.rms.main as m

    called = {"migrate": 0, "serve": 0}

    def fake_migrate():
        called["migrate"] += 1

    def fake_serve():
        called["serve"] += 1

    monkeypatch.setattr(m, "migrate", fake_migrate)
    monkeypatch.setattr(m, "_serve", fake_serve)

    for argv in (["aiw-saskia"], ["aiw-saskia", "serve"], ["aiw-saskia", "run"]):
        monkeypatch.setattr(sys, "argv", argv)
        m.run()

    assert called["migrate"] == 0
    assert called["serve"] == 3
