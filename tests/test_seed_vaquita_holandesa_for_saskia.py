"""TDD: the Vaquita Holandesa seed must be loadable + idempotent for the
Saskia (saskia-vps) business.

Why this test exists:
- The user reported "0 de 0 productos" but the DB has 29 products.
- Root cause was a missing tenant record and stale browser cache.
- The operator-facing seed_vaquita_holandesa_for_saskia.py must REFUSE to run
  on a DB that already has user data, because seed_sazon(overwrite=False)
  is NOT idempotent at the row level: it appends NEW products with new
  names. Running it on a populated DB caused 29 duplicate products.
- This test guards against that regression.

We test the operator script's contract:
1. The script must mention Vaquita + Saskia + use overwrite=False.
2. Running the script on a DB with 29 products + 721 sales must
   REFUSE (exit 2), not silently append 29 NEW products.
3. Running seed_sazon on a FRESH empty DB is idempotent at the row level.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
SEED_SCRIPT = SCRIPTS_DIR / "seed_vaquita_holandesa_for_saskia.py"


def test_seed_script_exists():
    assert SEED_SCRIPT.exists(), (
        f"missing {SEED_SCRIPT}. The operator-facing script that loads "
        "the Vaquita Holandesa catalog into the Saskia business must exist."
    )


def test_seed_script_mentions_vaquita_and_saskia():
    text = SEED_SCRIPT.read_text()
    assert "Vaquita" in text, "script must reference La Vaquita Holandesa"
    assert "Saskia" in text, "script must reference the Saskia business"


def test_seed_script_calls_seed_sazon_with_overwrite_false():
    text = SEED_SCRIPT.read_text()
    assert "seed_sazon(" in text, "script must call seed_sazon()"
    assert "overwrite=False" in text, (
        "seed_sazon must be called with overwrite=False so it's idempotent"
    )


def test_seed_script_refuses_on_existing_user_data(tmp_path):
    """Regression: the sazon seed appends NEW products with new names
    even with overwrite=False. Running it on a DB that already has
    products + sales would create 29 NEW duplicates. The operator
    script must refuse this without --force.
    """
    db_path = tmp_path / "saskia-test.sqlite"

    # Seed a realistic DB that looks like the Saskia deployment
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    cur.executescript("""
        CREATE TABLE tenant (id INTEGER PRIMARY KEY, slug TEXT);
        CREATE TABLE app_meta (
                "key" VARCHAR(64) PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP
        );
        CREATE TABLE product (id INTEGER PRIMARY KEY, name TEXT, sku TEXT,
                               sale_price_gs INTEGER);
        CREATE TABLE recipe (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE ingredient (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE category (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE channel (id INTEGER PRIMARY KEY, code TEXT);
        CREATE TABLE delivery_zone (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE sale (id INTEGER PRIMARY KEY, product_id INTEGER,
                            qty FLOAT, sold_at TEXT);
    """)
    for i in range(29):
        cur.execute(
            "INSERT INTO product (name, sale_price_gs) VALUES (?, ?)",
            (f"Vaquita Product {i}", 1000 + i * 100),
        )
    for i in range(22):
        cur.execute("INSERT INTO recipe (name) VALUES (?)", (f"R{i}",))
    for i in range(76):
        cur.execute("INSERT INTO ingredient (name) VALUES (?)", (f"I{i}",))
    for i in range(721):
        cur.execute(
            "INSERT INTO sale (product_id, qty, sold_at) VALUES (?, 1, ?)",
            (i % 29 + 1, f"2026-10-{(i % 30) + 1:02d}"),
        )
    con.commit()
    con.close()

    # Run the operator script — must refuse (exit 2)
    import subprocess
    import sys as _sys

    env = {**os.environ, "AIW_SASKIA_DB_PATH": str(db_path)}
    # Use the same Python that's running this test (which has app.* deps)
    proc = subprocess.run(
        [_sys.executable, str(SEED_SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 2, (
        f"script must REFUSE on existing user data (exit 2), got "
        f"{proc.returncode}.\nstdout: {proc.stdout}\nstderr: {proc.stderr}"
    )
    combined = proc.stdout + proc.stderr
    assert "REFUSE" in combined, f"script must print REFUSE message, got: {combined}"


def test_seed_sazon_idempotent_in_empty_db(tmp_path):
    """Real-DB test: run seed_sazon twice on a FRESH empty DB and verify
    the product count doesn't grow on the second run.

    Skipped if sqlalchemy/app modules aren't importable (e.g. CI without
    the full venv). The script-only tests above guard the operator
    contract.
    """
    pytest.importorskip("app.rms.seed")
    db_path = tmp_path / "test.sqlite"
    os.environ["AIW_SASKIA_DB_PATH"] = str(db_path)
    try:
        from app.rms.db import make_engine, make_session_factory
        from app.rms.seed import seed_sazon

        engine = make_engine(f"sqlite:///{db_path}")
        from app.rms.models import Base  # type: ignore

        try:
            Base.metadata.create_all(engine)
        except Exception:
            pass
        SessionLocal = make_session_factory(engine)
        s1 = SessionLocal()
        try:
            seed_sazon(s1, overwrite=False)
        finally:
            s1.close()
        s2 = SessionLocal()
        try:
            from sqlalchemy import text

            n_after_first = s2.execute(text("SELECT COUNT(*) FROM product")).scalar()
            seed_sazon(s2, overwrite=False)
            n_after_second = s2.execute(text("SELECT COUNT(*) FROM product")).scalar()
        finally:
            s2.close()
        assert n_after_first == n_after_second, (
            f"seed_sazon not idempotent at row level: "
            f"first run {n_after_first} products, second run {n_after_second}"
        )
    finally:
        os.environ.pop("AIW_SASKIA_DB_PATH", None)
