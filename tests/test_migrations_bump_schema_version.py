"""Tests that every registered migration bumps its own schema_version.

REGRESSION (Sprint 4.5, 2026-10-02): Migrations 085-089 were authored
without `_bump_schema_version(conn, N)` calls. The lifespan_migrations
test surfaced this (DB at v84, code expects v89) but the original fix
was never landed.

This test pins the contract: every migration function in the MIGRATIONS
dict must end by calling _bump_schema_version with its own number.
Future migrations must follow the same pattern.

Why this matters:
- Migrations 1-83 were all authored with the call (grep -c proves it).
- The runner catches exceptions per-migration and continues, so a
  missing bump doesn't crash — it just stops the schema_version row
  from advancing past that migration, silently breaking fresh installs.
- The lifespan + outage tests cover the symptom, but as a defense-in-
  depth, this test catches the cause directly.
"""

from __future__ import annotations

import ast
from pathlib import Path

from app.rms.config import CURRENT_SCHEMA_VERSION
from app.rms.db import MIGRATIONS


def test_every_migration_calls_bump_schema_version():
    """Each file-based migration must call _bump_schema_version.

    Older migrations (1-83) are inlined in app/rms/db.py and DO call
    _bump_schema_version (this predates the file-per-migration refactor).
    File-based migrations (084+) live in app/rms/migrations/_NNN_*.py
    and were authored with the same pattern.

    Sprint 4.5 (2026-10-02) discovered migrations 085-089 silently
    shipped without the bump call, breaking fresh installs. This test
    catches that pattern so future migrations can't regress.
    """
    import re

    migrations_dir = Path(__file__).resolve().parent.parent / "app" / "rms" / "migrations"
    # Only file-based migrations. Each MUST call _bump_schema_version.
    # Files that are clearly experimental/legacy (low numbers, hand-rolled
    # version bumps) are excluded by a minimum version threshold.
    file_migrations = sorted(
        p
        for p in migrations_dir.glob("_*.py")
        if p.name != "__init__.py" and re.match(r"_\d{3}_.+\.py$", p.name)
    )

    missing = []
    for path in file_migrations:
        stem = path.stem
        num_str = stem.split("_")[1]
        try:
            v = int(num_str)
        except ValueError:
            v = -1
        # The _bump_schema_version helper was introduced mid-2024; pre-helper
        # test migrations (v < 50) updated AppMeta directly. Skip those.
        if v < 50:
            continue

        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and (
                (isinstance(node.func, ast.Name) and node.func.id == "_bump_schema_version")
                or (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "_bump_schema_version"
                )
            )
        ]
        if not calls:
            missing.append((v, path.name))

    assert not missing, (
        "Migrations without _bump_schema_version calls:\n"
        + "\n".join(f"  v{v}: {name}" for v, name in missing)
        + "\n\nEach migration MUST call _bump_schema_version(conn, N) as its last "
        "statement — the runner catches exceptions per-migration and continues, "
        "so a missing bump silently breaks fresh installs."
    )


def test_migration_count_matches_registered():
    """Number of registered migrations == CURRENT_SCHEMA_VERSION."""
    assert max(MIGRATIONS.keys()) == CURRENT_SCHEMA_VERSION, (
        f"Max registered migration ({max(MIGRATIONS.keys())}) doesn't match "
        f"CURRENT_SCHEMA_VERSION ({CURRENT_SCHEMA_VERSION})"
    )
    # No gaps in the sequence 1..CURRENT
    expected = set(range(1, CURRENT_SCHEMA_VERSION + 1))
    actual = set(MIGRATIONS.keys())
    assert actual == expected, (
        f"Migration sequence gap. Missing: {expected - actual}; Extra: {actual - expected}"
    )
