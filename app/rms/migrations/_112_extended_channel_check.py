"""Migration 112 (SASKIA-204, 2026-10-07): extend sale/pedido.channel CHECK to HEREBUS channels.

WHAT_NEXT #2 (P42 / SASKIA-204): Saskia's HEREBUS data has 4 sales
channels beyond the 6 baked into migration 111:
- retail      — cliente final, mostrador pero con factura
- wholesale   — ventas al por mayor (panaderías, distribuidores)
- distributor — venta directa a distribuidores (factura A)
- eventual   — venta eventual sin factura (eventos, ferias)

Before this migration the CHECK constraint
(_111_sale_channel_check.py) rejects any write with these values, so
they silently fall back to "mostrador" in the import_herebus_data.py
script (line 622: `... or "mostrador"`). That made revenue-by-channel
skew invisible: 346 sales say "mostrador" when 9 of them are actually
retail/wholesale.

MECHANICS:
- SQLite: DROP the 4 existing triggers from migration 111, then
  CREATE them with the extended IN list. The triggers are
  idempotent (`CREATE TRIGGER IF NOT EXISTS` won't recreate an
  existing one — so we DROP first by name).
- Postgres: model-level CheckConstraint in models_legacy.py needs
  the same extension. Migration is a no-op on Postgres; the model
  update is in app/rms/models_legacy.py.
- Re-running is a no-op once the new triggers/constraints are in
  place. Uses DROP TRIGGER IF EXISTS + CREATE TRIGGER IF NOT EXISTS.

DATA-CHECK BEFORE CONSTRAINT:
- Counts any existing rows whose `channel` is NOT in the extended
  allowed set. Same surface pattern as migration 111, but with the
  extended set.
- Raises if any are found. The current Sazon prod DB has 346
  `mostrador` + 6 `retail` + 3 `wholesale` (per HEREBUS report);
  all of these are in the extended allowed set, so this is a no-op.

LIMITS (kept small to fit the 2-hr scope):
- Does NOT run the re-classify script. The re-classify step is a
  separate script (scripts/reclassify_sale_channels.py) that the
  operator runs AFTER init_db to backfill the new channels from the
  HEREBUS VENTAS sheet.
- Does NOT add the /ventas filter UI. That's the next step
  (template change in app/templates/ventas.html + route handler in
  app/routers/sales.py).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

# Extended set of allowed channel values. Kept in sync with
# ``app/rms/models/channels.py`` (``Channel.allowed_values()``).
# If the enum ever gains a value, add it here AND to the Channel enum.
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
    # SASKIA-204: HEREBUS channels (added 2026-10-07)
    "retail",
    "wholesale",
    "distributor",
    "eventual",
)


def _existing_offenders(conn: Any, table: str, column: str, *, null_ok: bool) -> list[str]:
    """Return distinct offending values for the given (table, column)."""
    placeholders = ",".join(f":ch_{i}" for i in range(len(_ALLOWED_CHANNELS)))
    params = {f"ch_{i}": ch for i, ch in enumerate(_ALLOWED_CHANNELS)}
    raw_sql = (
        f"SELECT DISTINCT {column} FROM {table} "
        f"WHERE {column} IS NOT NULL "
        f"AND {column} NOT IN ({placeholders})"
    )
    rows = conn.execute(text(raw_sql), params).fetchall()
    return [str(r[0]) for r in rows]


def _migration_112_extended_channel_check(conn: Any) -> None:
    """Extend CHECK on sale.channel + pedido.channel via SQLite triggers.

    On Postgres the constraint lives in the model (CheckConstraint
    added to ``app/rms/models_legacy.py``); this function only does
    anything on SQLite.

    Strategy on SQLite:
    1. Drop the 4 triggers from migration 111 (if they exist).
    2. Re-create them with the extended _ALLOWED_CHANNELS list.

    Raises if pre-existing rows have values outside the extended set.
    """
    try:
        dialect_name = conn.dialect.name
    except Exception:
        dialect_name = "sqlite"

    if dialect_name != "sqlite":
        # Bump and exit — Postgres CHECK is in the model.
        from app.rms.db import _bump_schema_version

        _bump_schema_version(conn, 112)
        return

    # Pre-flight: surface any garbage already in the DB.
    sale_offenders = _existing_offenders(conn, "sale", "channel", null_ok=False)
    pedido_offenders = _existing_offenders(conn, "pedido", "channel", null_ok=True)
    if sale_offenders or pedido_offenders:
        msg = (
            f"sale.channel has values {sale_offenders!r}, "
            f"pedido.channel has values {pedido_offenders!r} — "
            f"none of which are in the extended Channel.allowed_values(). "
            f"Normalize these rows before re-running the migration."
        )
        raise RuntimeError(msg)

    # Build the WHEN clause once. SQLite triggers can't take bound
    # params, so the IN-list is rendered as a string literal of quoted
    # channel values. Safe — _ALLOWED_CHANNELS is module-level constant.
    in_clause = ",".join(f"'{ch}'" for ch in _ALLOWED_CHANNELS)
    allowed_str = ", ".join(_ALLOWED_CHANNELS)

    # Drop the old triggers from migration 111 (idempotent — only
    # drops if they exist). Use IF EXISTS so re-running is safe.
    for trig in (
        "sale_channel_check_insert",
        "sale_channel_check_update",
        "pedido_channel_check_insert",
        "pedido_channel_check_update",
    ):
        try:
            conn.execute(text(f"DROP TRIGGER IF EXISTS {trig}"))
        except Exception:
            # If we can't drop, we should not silently proceed —
            # re-creating would fail.
            from loguru import logger as _logger

            _logger.warning("migration 112: failed to drop trigger {}", trig)

    # sale.channel triggers (extended)
    conn.execute(
        text(
            f"""
            CREATE TRIGGER IF NOT EXISTS sale_channel_check_insert
            BEFORE INSERT ON sale
            FOR EACH ROW
            WHEN NEW.channel NOT IN ({in_clause})
            BEGIN
                SELECT RAISE(ABORT, 'sale.channel must be one of: {allowed_str}');
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
                SELECT RAISE(ABORT, 'sale.channel must be one of: {allowed_str}');
            END
            """
        )
    )

    # pedido.channel triggers (extended; column is nullable)
    conn.execute(
        text(
            f"""
            CREATE TRIGGER IF NOT EXISTS pedido_channel_check_insert
            BEFORE INSERT ON pedido
            FOR EACH ROW
            WHEN NEW.channel IS NOT NULL AND NEW.channel NOT IN ({in_clause})
            BEGIN
                SELECT RAISE(ABORT, 'pedido.channel must be one of: {allowed_str} (or NULL)');
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
                SELECT RAISE(ABORT, 'pedido.channel must be one of: {allowed_str} (or NULL)');
            END
            """
        )
    )

    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 112)


def run_post_migration(session: Any) -> dict[str, int]:
    """Post-migration hook for migration 112.

    Returns statistics about the extended constraint application.
    """
    stats: dict[str, int] = {}
    try:
        from sqlalchemy import func, select

        from app.rms.models import Pedido, Sale

        # Channel distribution — useful for the operator to see if
        # the re-classify script needs to be run.
        rows = session.execute(select(Sale.channel, func.count()).group_by(Sale.channel)).all()
        stats["sale_channel_distribution"] = dict(rows)
        stats["sale_total"] = session.scalar(select(func.count()).select_from(Sale)) or 0
        stats["pedido_total"] = session.scalar(select(func.count()).select_from(Pedido)) or 0
    except Exception as exc:  # best-effort telemetry; logger.debug IS the logging
        from loguru import logger as _logger

        _logger.debug("SASKIA-204 post_migration stats failed: {!r}", exc)
    return stats
