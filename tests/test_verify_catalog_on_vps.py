"""tests/test_verify_catalog_on_vps.py — Phase 14 (2026-10-01).

Validates the decision matrix of scripts/verify_catalog_on_vps.py
(read-only VPS catalog verifier). The matrix below is the spec —
any future change must keep these mappings or update this test
FIRST.
"""
import importlib.util
import sqlite3
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "verify_catalog_on_vps.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "verify_catalog_on_vps", SCRIPT_PATH
    )
    if spec is None or spec.loader is None:  # pragma: no cover
        raise RuntimeError(f"could not load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["verify_catalog_on_vps"] = module
    spec.loader.exec_module(module)
    return module


def _make_db(tmp_path: Path, *, schema_version="83", counts=None) -> str:
    """Create a minimal rms.sqlite with the required schema + counts.

    counts: dict like {"ingredient": 76, "recipe": 22, ...}
    """
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE app_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT INTO app_meta (key, value) VALUES (?, ?)",
        ("schema_version", schema_version),
    )
    counts = counts or {}
    # Create each tracked table with a single integer-id column so
    # we can insert COUNT rows.
    for table in ("ingredient", "recipe", "supplier",
                  "delivery_zone", "customer"):
        conn.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)")
        for i in range(counts.get(table, 0)):
            conn.execute(f"INSERT INTO {table} (id) VALUES (?)", (i + 1,))
    conn.commit()
    conn.close()
    return str(db_path)


def test_ok_when_schema_matches_and_counts_meet_minimums(tmp_path, capsys):
    mod = _load_module()
    db = _make_db(
        tmp_path,
        schema_version="83",
        counts={"ingredient": 76, "recipe": 22, "supplier": 8,
                "delivery_zone": 6, "customer": 12},
    )
    rc = mod.main(["--db", db, "--code-schema-version", "83"])
    assert rc == 0


def test_schema_mismatch_returns_1(tmp_path):
    mod = _load_module()
    db = _make_db(tmp_path, schema_version="82", counts={})
    rc = mod.main(["--db", db, "--code-schema-version", "83"])
    assert rc == 1


def test_catalog_below_minimums_returns_2(tmp_path):
    mod = _load_module()
    db = _make_db(
        tmp_path,
        schema_version="83",
        counts={"ingredient": 50, "recipe": 22, "supplier": 8,
                "delivery_zone": 6, "customer": 12},
    )
    rc = mod.main(["--db", db, "--code-schema-version", "83"])
    assert rc == 2


def test_db_not_found_returns_1():
    mod = _load_module()
    rc = mod.main(["--db", "/nonexistent/path/rms.sqlite"])
    assert rc == 1


def test_quiet_one_line_output(tmp_path, capsys):
    mod = _load_module()
    db = _make_db(
        tmp_path,
        schema_version="83",
        counts={"ingredient": 76, "recipe": 22, "supplier": 8,
                "delivery_zone": 6, "customer": 12},
    )
    rc = mod.main(["--db", db, "--code-schema-version", "83", "--quiet"])
    captured = capsys.readouterr()
    lines = [l for l in captured.out.split("\n") if l.strip()]
    assert len(lines) == 1
    assert lines[0].startswith("vps-catalog-verify[OK]")


def test_quiet_marks_fail_when_counts_low(tmp_path, capsys):
    mod = _load_module()
    db = _make_db(
        tmp_path,
        schema_version="83",
        counts={"ingredient": 5},  # way below minimum 70
    )
    rc = mod.main(["--db", db, "--code-schema-version", "83", "--quiet"])
    captured = capsys.readouterr()
    assert "[FAIL]" in captured.out
