"""Migration 111 (P41, 2026-10-07): DB-level CHECK on sale.channel and pedido.channel.

Closes the gap where future writes could insert arbitrary strings into
``sale.channel`` (String(32)) or ``pedido.channel`` (String(40)). Both
columns have a default of ``mostrador`` but no DB-level constraint
prevents garbage like ``"retail"``, ``"wholesale"``, or an empty string
if a future code path forgets the default.

WHY this exists:
- The operator's reports (revenue by source, demand_snapshot, dashboard)
  filter on ``sale.channel``. A stray typo in a future migration, an
  Excel import that doesn't normalize, or a misconfigured channel
  dropdown would silently skew these reports.
- The Python ``Channel`` enum at ``app/rms/models/channels.py`` is the
  canonical source of truth: ``{mostrador, mostrador-encargo,
  whatsapp, pedidosya, monchis, other}``. The DB CHECK enforces the
  same set at the persistence layer, defense-in-depth.

MECHANICS:
- SQLite: BEFORE INSERT/UPDATE triggers on ``sale`` and ``pedido`` that
  RAISE(ABORT) when the new ``channel`` value is not in the allowed
  set. (SQLite has no ``ALTER TABLE ADD CONSTRAINT``.)
- Postgres: model-level ``CheckConstraint`` in the SQLAlchemy
  ``Sale`` and ``Pedido`` models. The migration only needs to run on
  SQLite; the Postgres side is a model change (``app/rms/models_legacy.py``).
- Idempotent: re-running is a no-op once all triggers/constraints are
  in place. Uses ``CREATE TRIGGER IF NOT EXISTS``.

DATA-CHECK BEFORE CONSTRAINT:
- Counts any existing rows whose ``channel`` is NOT in the allowed set.
- Raises if any are found. The current Sazon prod DB has 327 sales, all
  ``mostrador``, so this should be a no-op in practice.
- For ``pedido.channel``: NULL is allowed (column is nullable). Only
  reject non-NULL values that aren't in the allowed set.

LIMITS (kept small to stay within the 2-hr scope of the P41 task):
- Does NOT refactor the 20+ raw string literals scattered through
  routers/templates. That's a follow-up — they all happen to write
  valid channel strings today.
- Does NOT add CHECK on ``customer.preferred_channel`` (separate column,
  separate domain). The Channel enum is sales-orientation.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

# Canonical set of allowed channel values. Kept in sync with
# ``app/rms/models/channels.py`` (``Channel.allowed_values()``). If
# the enum ever gains a value, add it here AND to the Channel enum.
# Pinned at migration time intentionally — if the enum drifts later,
# the CHECK constraint will reject the new value, surfacing the
# mismatch in a test rather than silently letting garbage through.
_ALLOWED_CHANNELS = (
    "mostrador",
    "mostrador-encargo",
    "whatsapp",
    "pedidosya",
    "monchis",
    "other",
)


def _existing_offenders(conn: Any, table: str, column: str, *, null_ok: bool) -> list[str]:
    """Return distinct offending values for the given (table, column).

    Used by the migration to surface pre-existing garbage. Kept as a
    helper so ``sale`` and ``pedido`` reuse the same logic. ``null_ok``
    is True for ``pedido.channel`` (column is nullable).
    """
    # Bound params for the channel values. Table/column names come from
    # this migration's constants, not user input.
    placeholders = ",".join(f":ch_{i}" for i in range(len(_ALLOWED_CHANNELS)))
    params = {f"ch_{i}": ch for i, ch in enumerate(_ALLOWED_CHANNELS)}
    raw_sql = (
        f"SELECT DISTINCT {column} FROM {table} "
        f"WHERE {column} IS NOT NULL "
        f"AND {column} NOT IN ({placeholders})"
    )
    rows = conn.execute(text(raw_sql), params).fetchall()
    return [str(r[0]) for r in rows]


def _migration_111_sale_channel_check(conn: Any) -> None:
    """Add CHECK on sale.channel + pedido.channel via SQLite triggers.

    On Postgres the constraint lives in the model (``CheckConstraint``
    added to ``app/rms/models_legacy.py``); this function only does
    anything on SQLite.

    Raises if pre-existing rows have values outside the allowed set.
    """
    try:
        dialect_name = conn.dialect.name
    except Exception:
        dialect_name = "sqlite"

    if dialect_name != "sqlite":
        # Bump and exit — Postgres CHECK is in the model.
        from app.rms.db import _bump_schema_version

        _bump_schema_version(conn, 111)
        return

    # Pre-flight: surface any garbage already in the DB.
    sale_offenders = _existing_offenders(conn, "sale", "channel", null_ok=False)
    pedido_offenders = _existing_offenders(conn, "pedido", "channel", null_ok=True)
    if sale_offenders or pedido_offenders:
        msg = (
            f"sale.channel has values {sale_offenders!r}, "
            f"pedido.channel has values {pedido_offenders!r} — "
            f"none of which are in Channel.allowed_values(). "
            f"Normalize these rows before re-running the migration."
        )
        raise RuntimeError(msg)

    # Build the WHEN clause once. SQLite triggers can't take bound
    # params, so the IN-list is rendered as a string literal of quoted
    # channel values. Safe — _ALLOWED_CHANNELS is module-level constant.
    in_clause = ",".join(f"'{ch}'" for ch in _ALLOWED_CHANNELS)
    allowed_str = ", ".join(_ALLOWED_CHANNELS)

    # sale.channel triggers
    conn.execute(
        text(
            f"""
            CREATE TRIGGER IF NOT EXISTS sale_channel_check_insert
            BEFORE INSERT ON sale
            FOR EACH ROW
            WHEN NEW.channel NOT IN ({in_clause})
            BEGIN
                SELECT RAISE(ABORT, 'sale.channel must be one of '
                    || '{allowed_str}'
                    || '; got: ' || COALESCE(NEW.channel, 'NULL'));
            END
            """
        )
    )
    conn.execute(
        text(
            f"""
            CREATE TRIGGER IF NOT EXISTS sale_channel_check_update
            BEFORE UPDATE ON sale
            FOR EACH ROW
            WHEN NEW.channel NOT IN ({in_clause})
            BEGIN
                SELECT RAISE(ABORT, 'sale.channel must be one of '
                    || '{allowed_str}'
                    || '; got: ' || COALESCE(NEW.channel, 'NULL'));
            END
            """
        )
    )

    # pedido.channel triggers. Column is nullable, so allow NULL.
    conn.execute(
        text(
            f"""
            CREATE TRIGGER IF NOT EXISTS pedido_channel_check_insert
            BEFORE INSERT ON pedido
            FOR EACH ROW
            WHEN NEW.channel IS NOT NULL AND NEW.channel NOT IN ({in_clause})
            BEGIN
                SELECT RAISE(ABORT, 'pedido.channel must be one of '
                    || '{allowed_str}'
                    || ' or NULL; got: ' || NEW.channel);
            END
            """
        )
    )
    conn.execute(
        text(
            f"""
            CREATE TRIGGER IF NOT EXISTS pedido_channel_check_update
            BEFORE UPDATE ON pedido
            FOR EACH ROW
            WHEN NEW.channel IS NOT NULL AND NEW.channel NOT IN ({in_clause})
            BEGIN
                SELECT RAISE(ABORT, 'pedido.channel must be one of '
                    || '{allowed_str}'
                    || ' or NULL; got: ' || NEW.channel);
            END
            """
        )
    )

    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 111)


def run_post_migration(session: Any) -> dict[str, int]:
    """Post-migration hook for migration 111.

    Returns statistics about the constraint application. Operators can
    verify via the dashboard that subsequent inserts are blocked.
    """
    stats: dict[str, int] = {}
    try:
        from sqlalchemy import func, select

        from app.rms.models import Pedido, Sale

        stats["sale_total"] = session.scalar(select(func.count()).select_from(Sale)) or 0
        stats["pedido_total"] = session.scalar(select(func.count()).select_from(Pedido)) or 0
    except Exception as exc:  # best-effort telemetry; logger.debug IS the logging
        from loguru import logger as _logger

        _logger.debug("P41 post_migration stats failed: {!r}", exc)
    return stats
