"""Migration 088: placeholder.

Schema version 88 must be registered so init_db() can advance from
85 → 89 without raising "No migration registered for schema version 88".

This is a stub. When real work for this slot lands, replace the body.
"""
from typing import Any


def _migration_088_placeholder(conn: Any) -> None:
    """No-op: just bump the schema version."""
    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 88)
