"""app/rms/db_url.py — low-level DB URL helpers.

Extracted from app/rms/db.py on 2026-10-09 to break a lazy-import
cycle: backup.py needed `_get_db_url_safe` (for backup manifests
that don't leak the password), and db.py needed `backup_database`
(for pre-migration snapshots). Both were imported inside function
bodies, which is a tolerated cycle pattern but a future trap.

This module is the "lowest layer" in the rms/ dependency graph:
it has zero rms/ dependencies. It depends only on stdlib
(os, urllib.parse) and the `AIW_RMS_DB_URL` env var.

Used by:
- app/rms/db.py: not anymore (moved out, was previously defined here)
- app/rms/backup.py: `_get_db_url_safe` for the manifest's
  db_url_safe field (no password leak in operator-stored backups)
- app/rms/config.py: the canonical DB URL builder; we DO NOT
  import from there to avoid a config -> db_url import (config is
  higher layer than this).
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit, urlunsplit


def db_url_safe() -> str:
    """Return the database URL with credentials stripped.

    Returns something like "postgresql+psycopg2://***@host/db" for
    a remote URL, or "sqlite:///<local>" for SQLite. Used in
    backup manifests so the file does not leak the password.

    The function is intentionally defensive: any error returns
    "<unknown>" rather than raising, because callers (notably
    the backup manifest writer) must not fail if the env var is
    misconfigured — the backup is still valuable without the URL.
    """
    url = os.environ.get("AIW_RMS_DB_URL", "sqlite:///./sazon.db")
    if url.startswith("sqlite"):
        return "sqlite:///<local>"
    try:
        parts = urlsplit(url)
        if parts.username or parts.password:
            netloc = "***@" + parts.netloc.split("@", 1)[-1]
            return urlunsplit((parts.scheme, netloc, parts.path, parts.query, ""))
        return url
    except Exception:
        return "<unknown>"


# Backward-compat alias for the historical private name. The 2026-10-09
# refactor renamed `_get_db_url_safe` to `db_url_safe` (drop the leading
# underscore, since this is now a public module). The private name is
# kept as a deprecated alias so any caller that happened to import the
# underscore-prefixed version (we grepped; there were none outside db.py
# and backup.py) continues to work.
_get_db_url_safe = db_url_safe
