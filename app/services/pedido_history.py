"""app.services.pedido_history — phase 4 timeline for /pedidos/{id}.

Build a coherent timeline of everything that happened to a pedido:
  - Status transitions (from AuditLog with action like write.pedido.status)
  - Sale events (fulfilled → which Sale row + total)
  - Loyalty events (points earned/redeemed from LoyaltyTransaction)
  - Create event (from AuditLog write.pedido.create)

Used by:
- pedido_detail handler to render a timeline + recent pedidos for
  the customer
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.rms.models import (
    AuditLog,
    Customer,
    LoyaltyTransaction,
    Pedido,
    Sale,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class TimelineEvent:
    """One entry in a pedido's timeline."""

    when: datetime
    kind: str  # 'created' | 'status' | 'fulfilled' | 'loyalty' | 'cancelled'
    label: str  # human-readable label
    detail: str | None = None
    actor: str | None = None  # username / user_id

    def to_dict(self) -> dict:
        return {
            "when": self.when.isoformat() if self.when else None,
            "kind": self.kind,
            "label": self.label,
            "detail": self.detail,
            "actor": self.actor,
        }


def build_pedido_timeline(session: Session, pedido: Pedido) -> list[TimelineEvent]:
    """Build the chronological event list for one pedido.

    Combines AuditLog rows (status transitions, creates, edits) with
    Sale rows (fulfillment) and LoyaltyTransaction rows (point events).
    Returns the events sorted by occurred_at ascending.
    """
    events: list[TimelineEvent] = []

    # Audit rows for this pedido
    audit_rows = session.execute(
        select(AuditLog)
        .where(
            AuditLog.target_type == "pedido",
            AuditLog.target_id == str(pedido.id),
        )
        .order_by(AuditLog.occurred_at)
    ).scalars().all()

    for row in audit_rows:
        if row.action == "write.pedido.create":
            events.append(TimelineEvent(
                when=row.occurred_at,
                kind="created",
                label="Pedido creado",
                actor=row.user_id,
            ))
        elif row.action == "write.pedido.status":
            new_status = (row.detail or {}).get("new_status", "?")
            old_status = (row.detail or {}).get("old_status", "?")
            events.append(TimelineEvent(
                when=row.occurred_at,
                kind="status",
                label=f"{old_status} → {new_status}",
                detail=(row.detail or {}).get("reason"),
                actor=row.user_id,
            ))
        elif row.action == "write.pedido.duplicate":
            events.append(TimelineEvent(
                when=row.occurred_at,
                kind="duplicate",
                label=f"Duplicado de pedido #{(row.detail or {}).get('original_id', '?')}",
                actor=row.user_id,
            ))

    # Sale row for this pedido (if linked via shared customer + promised_date
    # window — we don't have a direct FK, so we approximate via customer
    # within ±1 hour of the pedido's promised_time). Best effort.
    # Note: Sales don't have linked_pedido_id yet — see kyrian_analysis
    # "Missing schema entities". Until we add that column, we skip this
    # branch to avoid false positives.
    sale = None
    if sale is not None:
        events.append(TimelineEvent(
            when=sale.sold_at,
            kind="fulfilled",
            label=f"Venta #{sale.id} generada",
            detail=f"Gs. {sale.total_gs:,}".replace(",", "."),
            actor=sale.user_id,
        ))

    # Loyalty transactions for this customer around this pedido's lifetime
    if pedido.customer_id:
        lt_rows = session.execute(
            select(LoyaltyTransaction)
            .where(
                LoyaltyTransaction.customer_id == pedido.customer_id,
                LoyaltyTransaction.recorded_at >= pedido.created_at,
            )
            .order_by(LoyaltyTransaction.recorded_at)
        ).scalars().all()
        for lt in lt_rows:
            sign = "+" if lt.points_delta > 0 else ""
            events.append(TimelineEvent(
                when=lt.recorded_at,
                kind="loyalty",
                label=f"Puntos {sign}{lt.points_delta}",
                detail=lt.reason,
            ))

    # Sort by occurred_at ascending (None last). Use a key that handles None.
    events.sort(key=lambda e: e.when or datetime.min)
    return events


@dataclass
class CustomerPedidoSummary:
    """Compact representation of a pedido for the customer's history list."""

    id: int
    status: str
    promised_date: str | None
    total_gs: int
    line_count: int
    is_current: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "promised_date": self.promised_date,
            "total_gs": self.total_gs,
            "line_count": self.line_count,
            "is_current": self.is_current,
        }


def customer_recent_pedidos(
    session: Session,
    customer_id: int,
    *,
    limit: int = 8,
    exclude_pedido_id: int | None = None,
) -> list[CustomerPedidoSummary]:
    """Return the customer's most-recent pedidos as compact summaries.

    Useful for showing "Otros pedidos de este cliente" on the detail page
    so the operator can quickly jump to history.
    """
    q = (
        select(Pedido)
        .where(Pedido.customer_id == customer_id)
        .order_by(Pedido.promised_date.desc(), Pedido.id.desc())
        .limit(limit)
    )
    if exclude_pedido_id is not None:
        # Use a NOT-EQUAL filter via Python (excludes the current pedido)
        pedidos = [p for p in session.execute(q).scalars().all() if p.id != exclude_pedido_id][:limit]
    else:
        pedidos = session.execute(q).scalars().all()

    out: list[CustomerPedidoSummary] = []
    for p in pedidos:
        total = sum(int(ln.qty * ln.unit_price_gs) for ln in p.lines)
        out.append(CustomerPedidoSummary(
            id=p.id,
            status=p.status,
            promised_date=p.promised_date.isoformat() if p.promised_date else None,
            total_gs=total,
            line_count=len(p.lines),
        ))
    return out
