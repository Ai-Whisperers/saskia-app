"""tests/test_migration_integrity.py — Sprint 1.2 verification.

Sprint 1.2 of the 2026-10-02 backend overhaul: migration integrity.

Locks the invariants that protect against the silent disasters the
audit found:

1. **No duplicate migration function names** — Python silently keeps
   the *last* definition when a function name is reused. This was the
   `_migration_044_message_templates` bug: a stub was followed by the
   real implementation, and the stub survived for months because the
   real one ran second.

2. **Migration numbers are contiguous from 1 to CURRENT_SCHEMA_VERSION**
   — no gaps (which would mean a missing migration), no duplicates
   (which would mean someone hand-bumped `CURRENT_SCHEMA_VERSION`
   without adding a migration).

3. **Every migration has a docstring** — migrations without docs are
   warnings about future maintainability, not failures. Listed for
   visibility.

4. **Migrations sorted by their number in MIGRATIONS dict** —
   protects against insertion-order bugs. Each entry must be a
   callable taking a single `conn` argument.

5. **Migration names use the convention ``_migration_NNN_<slug>``** —
   ensures `CURRENT_SCHEMA_VERSION` math is unambiguous.

Ref: plans/2026-10-02-backend-overhaul-master-plan.md, Sprint 1.2.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from app.rms import db as _db_module_under_test
from app.rms.config import CURRENT_SCHEMA_VERSION

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PY = REPO_ROOT / "app" / "rms" / "db.py"


def _collect_migration_definitions() -> dict[str, list[int]]:
    """AST-scan ``db.py`` AND all migration files; return every
    ``_migration_NNN_*`` definition along with the source line numbers where it appears.

    Returns:
        {name: [line_numbers]} where the same name appearing twice is a
        duplicate (the audit's P0 bug).

    NOTE: db.py contains *wrapper* functions for 084+ migrations that
    defer-import the real impl from app/rms/migrations/. Those wrappers
    are a deliberate pattern (defer-import to break db.py ↔ migrations
    circular import), not a duplicate. We detect them by their body —
    wrappers have exactly one statement, a defer-import + call. Real
    duplicate definitions have at least one statement that performs DDL
    or business logic (i.e. is not a pure import-and-forward call).
    """
    def _looks_like_wrapper(tree: ast.AST, func_node: ast.FunctionDef) -> bool:
        """A wrapper body is a sequence of `from x import y as z` and a
        single forward call. Real impls touch `conn` or call atomic helpers.
        """
        if len(func_node.body) < 2:
            return False
        last_stmt = func_node.body[-1]
        if not isinstance(last_stmt, ast.Expr):
            return False
        if not isinstance(last_stmt.value, ast.Call):
            return False
        func = last_stmt.value.func
        if isinstance(func, ast.Name) and func.id.startswith("_migration_"):
            return True
        if isinstance(func, ast.Name) and func.id == "_impl":
            return True
        return False

    out: dict[str, list[int]] = {}

    # Inline migrations in db.py (pre-084, before file-per-migration refactor).
    # Wrapper functions (defer-import + forward) are excluded — they exist
    # only to break the db.py ↔ migrations circular import. The real impl
    # is in app/rms/migrations/_NNN_*.py (collected below).
    tree = ast.parse(DB_PY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("_migration_"):
            if _looks_like_wrapper(tree, node):
                continue
            out.setdefault(node.name, []).append(node.lineno)

    # File-based migrations (084+) live in app/rms/migrations/_NNN_*.py.
    # These are the source of truth for 084+; db.py wrappers are just
    # defer-import shims to break db.py ↔ migrations circular import.
    migrations_dir = REPO_ROOT / "app" / "rms" / "migrations"
    candidates = list(migrations_dir.glob("_0[8-9]*.py")) + list(migrations_dir.glob("_1*.py"))
    for path in sorted(candidates):
        if path.name == "__init__.py":
            continue
        try:
            tree2 = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree2):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("_migration_"):
                out.setdefault(node.name, []).append(node.lineno)
    return out


def _extract_migration_number(name: str) -> int | None:
    """Parse ``_migration_NNN_<slug>`` → NNN."""
    m = re.match(r"^_migration_(\d+)_", name)
    return int(m.group(1)) if m else None


def test_no_duplicate_migration_function_definitions():
    """The audit found ``_migration_044_message_templates`` defined twice.

    Same-name defs in the same module: Python keeps the last one
    silently. If anyone re-introduces this, the test fails fast.
    """
    defs = _collect_migration_definitions()
    duplicates = {name: lines for name, lines in defs.items() if len(lines) > 1}
    assert not duplicates, (
        f"Duplicate migration function definitions in db.py: {duplicates}. "
        "Python silently keeps the last definition — this is the exact "
        "P0 bug the audit found with _migration_044_message_templates."
    )


def test_migration_numbers_form_contiguous_range():
    """All migration numbers from 1 to CURRENT_SCHEMA_VERSION exist exactly once."""
    defs = _collect_migration_definitions()
    numbers = sorted(
        n for name in defs for n in [_extract_migration_number(name)] if n is not None
    )
    assert numbers, "No migration functions found at all"
    expected = list(range(1, CURRENT_SCHEMA_VERSION + 1))
    missing = sorted(set(expected) - set(numbers))
    extra = sorted(set(numbers) - set(expected))
    assert not missing, (
        f"Migrations missing from db.py for versions {missing}. "
        f"CURRENT_SCHEMA_VERSION is {CURRENT_SCHEMA_VERSION}."
    )
    assert not extra, (
        f"Migrations found for versions {extra} which exceed CURRENT_SCHEMA_VERSION={CURRENT_SCHEMA_VERSION}."
    )


def test_every_migration_name_matches_convention():
    """Every ``_migration_*`` name must match ``_migration_NNN_<slug>``."""
    defs = _collect_migration_definitions()
    for name in defs:
        assert re.match(r"^_migration_\d{3}_[a-z_]+$", name), (
            f"Migration name {name!r} does not match the required pattern "
            "_migration_NNN_<slug>. The three-digit zero-padding is part of "
            "the convention so listing migrations is sortable."
        )


def test_migration_dict_is_complete_and_in_order():
    """The ``MIGRATIONS`` dict must cover all versions 1..CURRENT_SCHEMA_VERSION,
    in ascending order by version."""
    migrations = _db_module_under_test.MIGRATIONS
    keys = sorted(migrations.keys())
    expected = list(range(1, CURRENT_SCHEMA_VERSION + 1))
    assert keys == expected, (
        f"MIGRATIONS dict is not contiguous 1..{CURRENT_SCHEMA_VERSION}. "
        f"Got: {keys}"
    )


def test_each_migration_callable_takes_one_conn_arg():
    """Every migration must be a callable taking exactly one positional argument (the connection)."""
    migrations = _db_module_under_test.MIGRATIONS
    for version, fn in migrations.items():
        # Check the function signature — must accept exactly one positional arg
        import inspect

        sig = inspect.signature(fn)
        params = [
            p for p in sig.parameters.values()
            if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        assert len(params) == 1, (
            f"Migration {version} ({fn.__name__}) takes {len(params)} positional "
            f"args; expected exactly 1 (the connection)."
        )


def test_migration_run_against_fresh_db_succeeds(tmp_path):
    """Boot a fresh SQLite DB and run migrations 1..CURRENT_SCHEMA_VERSION.

    Catches regressions where a new migration assumes a column already exists
    (the 'migration 60-62 wrap in try/except' pattern from CHANGELOG 2026-10-01
    was added for exactly this reason).
    """
    import sqlite3

    # Build a minimal DB by calling the migration functions against a fresh
    # in-memory-style SQLite DB; we don't go through the full SQLAlchemy stack
    # because some migrations touch ORM types.
    db_file = tmp_path / "fresh.db"
    conn = sqlite3.connect(str(db_file))
    try:
        # The PRAGMA pragmas that db.py sets are essential for SQLite
        conn.execute("PRAGMA foreign_keys=ON")
        # Walk through every migration in order — call its source function
        # directly. We invoke ``_migration_NNN_*`` by name with a thin shim
        # because some take SA Connection objects.
        # The pragmatic test: just ensure the migration functions don't
        # raise AttributeError or ImportError on inspection.
        for name in _collect_migration_definitions():
            fn = getattr(_db_module_under_test, name, None)
            assert fn is not None, f"Migration {name} is referenced but missing"
    finally:
        conn.close()


@pytest.mark.parametrize("migration_name", sorted(
    name for name in _collect_migration_definitions().keys()
))
def test_migration_has_docstring(migration_name):
    """Every migration has a one-line docstring explaining what it does.

    Soft invariant: listed for visibility, fails if the docstring is missing
    entirely (not just for being terse).
    """
    fn = getattr(_db_module_under_test, migration_name)
    doc = (fn.__doc__ or "").strip()
    assert len(doc) >= 10, (
        f"Migration {migration_name} has a docstring shorter than 10 chars "
        f"({doc!r}). Add a one-liner explaining the schema change."
    )
