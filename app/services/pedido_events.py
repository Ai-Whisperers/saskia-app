"""app/services/pedido_events.py — Phase 11 service for recording pedido events.

This wraps the PedidoEvent table so the rest of the codebase can write
events with one helper call and never has to construct SQLAlchemy rows
directly. All writes are best-effort: if the pedido_event table isn't
there (e.g. on a stale DB before migration 077 ran), the helper logs
and returns None instead of failing the user request.

Event types are constrained by the CK_pedido_event_type constraint
(defined in models_legacy). Adding a new event_type means:
  1. Update the models_legacy CheckConstraint
  2. Add the literal to VALID_EVENT_TYPES below
  3. Add a translation in the timeline UI (templates/pedido_detalle.html)

Examples
--------
    # Record on creation (called from /pedidos POST handler)
    PedidoEventService.record(
        session, pedido_id, "created",
        actor="demo",
        payload={"order_total_gs": 75000, "n_lines": 3},
    )

    # Record status change (called from /pedidos/{id}/fulfill, /cancel, etc.)
    PedidoEventService.record(
        session, pedido_id, "status_change",
        actor="demo",
        payload={"from": "pending", "to": "fulfilled",
                 "fulfilled_sale_id": 456},
    )

    # Record line edit (called from /pedidos/{id}/line/{n}/edit POST)
    PedidoEventService.record(
        session, pedido_id, "line_qty_changed",
        actor="demo",
        payload={"line_id": 17, "product_id": 4,
                 "from_qty": 2.0, "to_qty": 3.0},
    )

Notes
-----
- The actor string defaults to 'system' for non-interactive writes
  (e.g. cron jobs, migrations, sale fulfillment).
- The session is expected to flush the pedido before this is called so
  pedido_id is valid. If pedido_id is missing (transient Object), the
  helper still works: we record the event after the caller flushes.
- This service does not auto-flush: it appends to session and lets the
  caller control transaction boundaries.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from sqlalchemy.exc import OperationalError, ProgrammingError

from app.rms.config import ASUNCION_TZ
from app.rms.models import PedidoEvent

# Keep in lock-step with the CK_pedido_event_type constraint
# (see app/rms/models_legacy.py PedidoEvent class).
VALID_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "created",
        "status_change",
        "line_added",
        "line_removed",
        "line_qty_changed",
        "line_price_changed",
        "note_edited",
        "address_changed",
        "window_changed",
        "customer_changed",
        "payment_intent_set",
        "cancelled",
        "duplicated",
    }
)


class PedidoEventService:
    """Thin writer for the PedidoEvent timeline."""

    @staticmethod
    def record(
        session: Any,
        pedido_id: int,
        event_type: str,
        *,
        actor: str = "system",
        payload: Mapping[str, Any] | None = None,
        ts: datetime | None = None,
    ) -> PedidoEvent | None:
        """Append a PedidoEvent row to the session.

        Returns the PedidoEvent instance on success, or None if the
        underlying table is missing (e.g. pre-migration-077 DB) — in
        which case the write is silently skipped so callers don't have
        to special-case migration lag.

        Raises ValueError on invalid event_type to catch typos early.
        """
        if event_type not in VALID_EVENT_TYPES:
            raise ValueError(
                f"Invalid pedido event_type {event_type!r}; "
                f"must be one of {sorted(VALID_EVENT_TYPES)}"
            )

        evt = PedidoEvent(
            pedido_id=pedido_id,
            ts=ts or datetime.now(ASUNCION_TZ),
            actor=actor[:64],  # match VARCHAR(64)
            event_type=event_type,
            payload_json=dict(payload or {}),
        )
        try:
            session.add(evt)
            session.flush()
        except (OperationalError, ProgrammingError) as exc:
            # Table missing (pre-migration-077) or other schema issue —
            # roll back the add so the caller's transaction stays clean.
            session.rollback()
            from app.rms.db import logger  # local import to avoid cycle

            logger.debug(
                "PedidoEventService.record skipped for pedido %s: %s",
                pedido_id,
                exc,
            )
            return None
        return evt
