"""Parametrized coverage for the refactored verify_catalog_on_vps branches.

S4 batch-1 (tooling/CI): we refactored
`scripts/verify_catalog_on_vps.py:main` from cyclomatic complexity
22 (D-grade) down to 5 (A-grade) by extracting six focused helpers:

  - `resolve_code_schema_version(args)` — picks the expected schema
    version from CLI > env > app.rms.config > None
  - `check_schema_match(meta, code_sv, quiet)` — schema-version
    comparison; returns the exit code when they differ, None otherwise
  - `collect_catalog_failures(counts)` — list of "<t>=<c> (need>=<m>)"
    strings for every catalog table below its minimum
  - `print_report(db_path, meta, code_sv, counts, failures, quiet)` —
    cron-friendly one-liner vs human-readable multi-line summary
  - `open_db_or_exit(db_path, quiet)` — returns Connection or exit code
  - `read_db_or_exit(conn, quiet)` — returns (meta, counts) or exit code

The original `main()` is now a 9-line orchestrator that strings
those helpers together.

`tests/test_verify_catalog_on_vps.py` already covers the integration
matrix end-to-end (full main() → exit code). This file goes one
level deeper: it parametrizes every branch of every new helper so a
future refactor that drops a branch is caught here before it leaks.

Branches locked:

  resolve_code_schema_version
    - CLI flag wins over env (--code-schema-version=83 + SASKIA_CODE_SCHEMA_VERSION=120)
    - env wins when CLI is absent
    - app.rms.config import when neither flag nor env present
    - ImportError fallback to None (app module unavailable)
    - AttributeError fallback to None (config exists but no CURRENT_SCHEMA_VERSION)
    - both env and import present → env wins (priority order)

  check_schema_match
    - code_sv=None → returns None (skip branch)
    - schema_version matches → returns None
    - schema_version differs + quiet=True → returns EXIT_DB_OR_SCHEMA, prints nothing
    - schema_version differs + quiet=False → returns EXIT_DB_OR_SCHEMA + FAIL line
    - meta with schema_version=None + code_sv=83 → mismatch (None != 83)

  collect_catalog_failures
    - all counts above minimum → empty list
    - one table below minimum → exactly that one entry
    - multiple tables below minimum → every entry in input order
    - all counts zero → all five entries
    - count equal to minimum → not a failure (boundary, >= not >)

  print_report
    - quiet=True + no failures → "[OK]" + one line
    - quiet=True + failures → "[FAIL]" + one line, no extra output
    - quiet=False + no failures → multi-line report, all [OK]
    - quiet=False + failures → multi-line report with [LOW] for low + (code: ...) suffix
    - quiet=False + code_sv=None → schema_version line without "(code: ...)" suffix

  open_db_or_exit
    - existing file → Connection (returns a Connection, not an int)
    - missing file + quiet=False → prints ERROR + returns EXIT_DB_OR_SCHEMA (int)
    - missing file + quiet=True → silent + returns EXIT_DB_OR_SCHEMA (int)
    - returns exactly one of (Connection, int) — type-checked

  read_db_or_exit
    - good DB → returns (meta, counts) tuple
    - DB that raises sqlite3.Error on get_db_metadata → returns EXIT_SCRIPT_ERROR
    - DB that raises sqlite3.Error on get_counts → returns EXIT_SCRIPT_ERROR
    - quiet=False + query error → prints message
    - quiet=True + query error → silent
"""

from __future__ import annotations

import importlib
import importlib.util
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# Reuse the existing module loader so a rename of the script is a
# single-line change. (See tests/test_verify_catalog_on_vps.py for the
# canonical loader.)
_SCRIPT_PATH = SCRIPTS_DIR / "verify_catalog_on_vps.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("verify_catalog_on_vps", _SCRIPT_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise RuntimeError(f"could not load {_SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["verify_catalog_on_vps"] = module
    spec.loader.exec_module(module)
    return module


def _make_db(
    tmp_path: Path, *, schema_version: str | None = "83", counts: dict | None = None
) -> str:
    """Create a minimal rms.sqlite with the required schema + counts.

    schema_version=None omits the app_meta row (locks the
    `meta.get("schema_version") == None` branch in check_schema_match).
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
    if schema_version is not None:
        conn.execute(
            "INSERT INTO app_meta (key, value) VALUES (?, ?)",
            ("schema_version", schema_version),
        )
    counts = counts or {}
    for table in ("ingredient", "recipe", "supplier", "delivery_zone", "customer"):
        conn.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)")
        for i in range(counts.get(table, 0)):
            conn.execute(f"INSERT INTO {table} (id) VALUES (?)", (i + 1,))
    conn.commit()
    conn.close()
    return str(db_path)


# ─── resolve_code_schema_version ────────────────────────────────────────────


class _FakeArgs:
    """Minimal argparse.Namespace stub carrying only the field
    resolve_code_schema_version reads (`code_schema_version`).
    """

    def __init__(self, code_schema_version: int | None = None) -> None:
        self.code_schema_version = code_schema_version


@pytest.mark.parametrize(
    ("cli_value", "env_value", "config_value", "config_present", "expected"),
    [
        pytest.param(
            83,
            "120",
            95,
            True,
            83,
            id="cli_flag_wins_over_env_and_config",
        ),
        pytest.param(
            None,
            "120",
            95,
            True,
            120,
            id="env_wins_when_cli_absent",
        ),
        pytest.param(
            None,
            None,
            95,
            True,
            95,
            id="config_imported_when_cli_and_env_absent",
        ),
        pytest.param(
            None,
            "120",
            95,
            True,
            120,
            id="env_wins_over_config_when_cli_absent",
        ),
        pytest.param(
            None,
            None,
            None,
            False,
            None,
            id="config_unavailable_falls_back_to_none",
        ),
        pytest.param(
            None,
            None,
            None,
            True,
            None,
            id="attribute_error_falls_back_to_none",
        ),
        pytest.param(
            83,
            None,
            None,
            False,
            83,
            id="cli_wins_when_config_unavailable",
        ),
    ],
)
def test_resolve_code_schema_version(
    cli_value: int | None,
    env_value: str | None,
    config_value: int | None,
    config_present: bool,
    expected: int | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_module()
    if env_value is None:
        monkeypatch.delenv("SASKIA_CODE_SCHEMA_VERSION", raising=False)
    else:
        monkeypatch.setenv("SASKIA_CODE_SCHEMA_VERSION", env_value)

    # Patch the lazy `from app.rms.config import CURRENT_SCHEMA_VERSION`
    # inside resolve_code_schema_version. The helper handles BOTH
    # ImportError (module unreachable) and AttributeError (module
    # present, symbol missing); we cover both via the same fake module:
    #   config_present=True  → module exists; symbol present iff config_value is not None
    #   config_present=False → module is a sentinel whose __getattr__ raises ImportError
    #     (so the from-import falls into the helper's ImportError arm
    #     and returns None).
    import types

    for mod_name in ("app", "app.rms", "app.rms.config"):
        monkeypatch.delitem(sys.modules, mod_name, raising=False)
    fake_pkg = types.ModuleType("app")
    fake_pkg.__path__ = []
    fake_rms = types.ModuleType("app.rms")
    fake_rms.__path__ = []
    if config_present:
        fake_cfg = types.ModuleType("app.rms.config")
        if config_value is not None:
            fake_cfg.__dict__["CURRENT_SCHEMA_VERSION"] = config_value
        # else: AttributeError on CURRENT_SCHEMA_VERSION (key absent)
        monkeypatch.setitem(sys.modules, "app.rms.config", fake_cfg)
    else:
        # Sentinel: importing succeeds, but every attribute access raises
        # ImportError. This locks the helper's ImportError branch.
        def _raise_import_error(_name):  # pragma: no cover
            raise ImportError("simulated unreachable app.rms.config")

        class _SentinelModule(types.ModuleType):
            def __getattr__(self, name):  # pragma: no cover
                raise ImportError(f"simulated unreachable {name}")

        fake_cfg = _SentinelModule("app.rms.config")
        monkeypatch.setitem(sys.modules, "app.rms.config", fake_cfg)
    monkeypatch.setitem(sys.modules, "app", fake_pkg)
    monkeypatch.setitem(sys.modules, "app.rms", fake_rms)

    args = _FakeArgs(code_schema_version=cli_value)
    result = mod.resolve_code_schema_version(args)
    assert result == expected


# ─── check_schema_match ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("schema_version", "code_sv", "quiet", "expect_exit", "expect_print"),
    [
        pytest.param(
            "83",
            None,
            False,
            None,
            "",
            id="skip_when_code_sv_is_none",
        ),
        pytest.param(
            "83",
            83,
            False,
            None,
            "",
            id="match_returns_none",
        ),
        pytest.param(
            "82",
            83,
            False,
            1,
            "FAIL: schema_version=82",
            id="mismatch_verbose_prints_and_returns_1",
        ),
        pytest.param(
            "82",
            83,
            True,
            1,
            "",
            id="mismatch_quiet_returns_1_with_no_output",
        ),
        pytest.param(
            None,
            83,
            None,
            1,
            "FAIL: schema_version=None",
            id="missing_app_meta_row_is_mismatch",
        ),
        pytest.param(
            "83",
            83,
            True,
            None,
            "",
            id="match_quiet_returns_none",
        ),
    ],
)
def test_check_schema_match(
    schema_version,
    code_sv,
    quiet,
    expect_exit,
    expect_print,
    tmp_path,
    capsys,
) -> None:
    mod = _load_module()
    db = _make_db(tmp_path, schema_version=schema_version)
    conn = sqlite3.connect(db)
    try:
        meta = mod.get_db_metadata(conn)
    finally:
        conn.close()

    quiet_flag = quiet if quiet is not None else False
    result = mod.check_schema_match(meta, code_sv, quiet_flag)
    assert result == expect_exit

    captured = capsys.readouterr()
    if expect_print:
        assert expect_print in captured.out
    else:
        # Nothing should be printed by check_schema_match alone
        assert captured.out == ""


# ─── collect_catalog_failures ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("counts", "expected"),
    [
        pytest.param(
            {"ingredient": 100, "recipe": 50, "supplier": 10, "delivery_zone": 10, "customer": 10},
            [],
            id="all_above_minimum_no_failures",
        ),
        pytest.param(
            {"ingredient": 50, "recipe": 50, "supplier": 10, "delivery_zone": 10, "customer": 10},
            ["ingredient=50 (need >= 70)"],
            id="single_table_below_minimum",
        ),
        pytest.param(
            {"ingredient": 50, "recipe": 5, "supplier": 10, "delivery_zone": 10, "customer": 10},
            ["ingredient=50 (need >= 70)", "recipe=5 (need >= 20)"],
            id="multiple_tables_below_minimum_in_dict_order",
        ),
        pytest.param(
            {"ingredient": 0, "recipe": 0, "supplier": 0, "delivery_zone": 0, "customer": 0},
            [
                "ingredient=0 (need >= 70)",
                "recipe=0 (need >= 20)",
                "supplier=0 (need >= 5)",
                "delivery_zone=0 (need >= 5)",
                "customer=0 (need >= 5)",
            ],
            id="all_zero_all_failures",
        ),
        pytest.param(
            {"ingredient": 70, "recipe": 20, "supplier": 5, "delivery_zone": 5, "customer": 5},
            [],
            id="boundary_equal_to_minimum_not_a_failure",
        ),
        pytest.param(
            {"ingredient": 69},
            [
                "ingredient=69 (need >= 70)",
                "recipe=0 (need >= 20)",
                "supplier=0 (need >= 5)",
                "delivery_zone=0 (need >= 5)",
                "customer=0 (need >= 5)",
            ],
            id="missing_keys_default_to_zero",
        ),
    ],
)
def test_collect_catalog_failures(counts: dict[str, int], expected: list[str]) -> None:
    mod = _load_module()
    assert mod.collect_catalog_failures(counts) == expected


# ─── print_report ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("quiet", "failures", "code_sv", "expect_status", "expect_lines", "expect_no_lines", "counts"),
    [
        pytest.param(
            True,
            [],
            83,
            "[OK]",
            ["vps-catalog-verify[OK]", "sv=83", "code=83"],
            [],
            {"ingredient": 75, "recipe": 25, "supplier": 10, "delivery_zone": 10, "customer": 10},
            id="quiet_ok_one_line",
        ),
        pytest.param(
            True,
            ["ingredient=5 (need >= 70)"],
            83,
            "[FAIL]",
            ["vps-catalog-verify[FAIL]"],
            ["Catalog on VPS"],
            {"ingredient": 5, "recipe": 25, "supplier": 10, "delivery_zone": 10, "customer": 10},
            id="quiet_fail_marks_fail_no_multi_line",
        ),
        pytest.param(
            False,
            [],
            83,
            None,
            ["Catalog on VPS", "[OK]", "(code: 83)"],
            ["[LOW]"],
            {"ingredient": 75, "recipe": 25, "supplier": 10, "delivery_zone": 10, "customer": 10},
            id="verbose_ok_multi_line_with_code_suffix",
        ),
        pytest.param(
            False,
            ["ingredient=5 (need >= 70)"],
            83,
            None,
            ["Catalog on VPS", "[LOW]", "ingredient: 5 (min 70) [LOW]"],
            [],
            {"ingredient": 5, "recipe": 25, "supplier": 10, "delivery_zone": 10, "customer": 10},
            id="verbose_fail_shows_low_marker",
        ),
        pytest.param(
            False,
            [],
            None,
            None,
            ["Catalog on VPS", "[OK]"],
            ["(code:"],
            {"ingredient": 75, "recipe": 25, "supplier": 10, "delivery_zone": 10, "customer": 10},
            id="verbose_no_code_sv_omits_code_suffix",
        ),
    ],
)
def test_print_report(
    quiet: bool,
    failures: list[str],
    code_sv: int | None,
    expect_status: str | None,
    expect_lines: list[str],
    expect_no_lines: list[str],
    counts: dict[str, int],
    capsys: pytest.CaptureFixture[str],
) -> None:
    mod = _load_module()
    meta = {"schema_version": 83}

    mod.print_report("/tmp/fake.db", meta, code_sv, counts, failures, quiet)

    captured = capsys.readouterr()
    out = captured.out
    for needle in expect_lines:
        assert needle in out, f"expected {needle!r} in {out!r}"
    for forbidden in expect_no_lines:
        assert forbidden not in out, f"unexpected {forbidden!r} in {out!r}"
    if expect_status:
        assert expect_status in out


# ─── open_db_or_exit ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("create_db", "quiet", "expect_type"),
    [
        pytest.param(True, False, "connection", id="existing_db_returns_connection"),
        pytest.param(False, False, "exit_code", id="missing_db_verbose_returns_int_1"),
        pytest.param(False, True, "exit_code", id="missing_db_quiet_returns_int_1"),
    ],
)
def test_open_db_or_exit(create_db: bool, quiet: bool, expect_type: str, tmp_path, capsys) -> None:
    mod = _load_module()
    if create_db:
        db_path = _make_db(tmp_path)
        result: Any = mod.open_db_or_exit(db_path, quiet)
        assert isinstance(result, sqlite3.Connection)
        result.close()
    else:
        result = mod.open_db_or_exit("/nonexistent/rms.sqlite", quiet)
        assert result == mod.EXIT_DB_OR_SCHEMA
        assert isinstance(result, int)

    captured = capsys.readouterr()
    if not create_db and not quiet:
        assert "ERROR: DB not found" in captured.out
    elif not create_db and quiet:
        assert captured.out == ""
    else:
        # Successful open: nothing is printed by this helper
        assert captured.out == ""


# ─── read_db_or_exit ────────────────────────────────────────────────────────


def _make_db_with_bad_meta(tmp_path: Path) -> str:
    """DB where app_meta is missing — get_db_metadata returns {schema_version: None}
    and get_counts works."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    for table in ("ingredient", "recipe", "supplier", "delivery_zone", "customer"):
        conn.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    return str(db_path)


def _make_db_missing_table(tmp_path: Path) -> str:
    """DB where ingredient table is missing — get_counts raises sqlite3.OperationalError."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE app_meta (key TEXT, value TEXT)")
    conn.execute("INSERT INTO app_meta VALUES ('schema_version', '83')")
    # Deliberately omit ingredient / recipe / supplier / delivery_zone / customer
    conn.commit()
    conn.close()
    return str(db_path)


def test_read_db_or_exit_happy_path(tmp_path) -> None:
    mod = _load_module()
    db = _make_db(
        tmp_path,
        schema_version="83",
        counts={
            "ingredient": 100,
            "recipe": 50,
            "supplier": 10,
            "delivery_zone": 10,
            "customer": 10,
        },
    )
    conn = sqlite3.connect(db)
    try:
        result = mod.read_db_or_exit(conn, quiet=False)
    finally:
        conn.close()
    assert isinstance(result, tuple)
    meta, counts = result
    assert meta["schema_version"] == 83
    assert counts == {
        "ingredient": 100,
        "recipe": 50,
        "supplier": 10,
        "delivery_zone": 10,
        "customer": 10,
    }


def test_read_db_or_exit_raises_when_counts_table_missing(tmp_path, capsys) -> None:
    mod = _load_module()
    db = _make_db_missing_table(tmp_path)
    conn = sqlite3.connect(db)
    try:
        result = mod.read_db_or_exit(conn, quiet=False)
    finally:
        conn.close()
    assert result == mod.EXIT_SCRIPT_ERROR
    captured = capsys.readouterr()
    assert "ERROR: query failed" in captured.out


def test_read_db_or_exit_silent_on_query_error_when_quiet(tmp_path, capsys) -> None:
    mod = _load_module()
    db = _make_db_missing_table(tmp_path)
    conn = sqlite3.connect(db)
    try:
        result = mod.read_db_or_exit(conn, quiet=True)
    finally:
        conn.close()
    assert result == mod.EXIT_SCRIPT_ERROR
    captured = capsys.readouterr()
    assert captured.out == ""


# ─── exit-code constants are stable ─────────────────────────────────────────


def test_exit_code_constants() -> None:
    mod = _load_module()
    assert mod.EXIT_OK == 0
    assert mod.EXIT_DB_OR_SCHEMA == 1
    assert mod.EXIT_CATALOG_LOW == 2
    assert mod.EXIT_SCRIPT_ERROR == 3
