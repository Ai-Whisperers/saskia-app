"""Migration 086: placeholder.

This migration slot was reserved by sibling work that has not yet
landed in app/rms/migrations/. Schema version 86 must be registered
so init_db() can advance from 85 → 89 without raising "No migration
registered for schema version 86".

Adding real work here when it lands is fine — the file just needs to
exist and bump the schema version. Re-run is a no-op.
"""
from typing import Any


def _migration_086_placeholder(conn: Any) -> None:
    """No-op: just bump the schema version.

    The placeholder does not alter any tables. Future work that needs
    a real schema change should replace this body.
    """
    # Local import to avoid the circular-import trap (db.py imports this
    # module at top, so any top-level import from db.py would fail).
    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 86)
