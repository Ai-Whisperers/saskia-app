"""Customer timeline aggregator (2026-10-02).

Pulls from multiple sources:
  - Pedido events (migration 077)
  - Communication log (migration 078)
  - Loyalty ledger (Phase 13)
  - Customer.created_at / updated_at

Returns a single sorted list of timeline items, each shaped for
direct rendering in the cliente_detalle.html "Actividad" section.

The aggregator caps the result at MAX_ITEMS so the page stays snappy
even for high-activity customers. The remaining N items are summarized
as a single "+N más" entry to preserve context.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models_legacy import (
    CommunicationLog,
    Customer,
    Pedido,
    PedidoEvent,
)

# Local import to avoid a hard dep on the loyalty package at import time
try:
    from app.rms.models_legacy import LoyaltyTransaction
except Exception:  # pragma: no cover - loyalty may not be enabled
    LoyaltyTransaction = None  # type: ignore[assignment,misc]

# Local import for suscripciones (Phase 13)
try:
    from app.rms.models_legacy import Suscripcion
except Exception:  # pragma: no cover
    Suscripcion = None  # type: ignore[assignment,misc]


MAX_ITEMS = 25
"""Hard cap so the page doesn't blow up on power-users."""

TimelineKind = Literal[
    "customer_created",
    "customer_updated",
    "pedido_created",
    "pedido_status",
    "pedido_cancelled",
    "pedido_duplicated",
    "message_sent",
    "message_received",
    "loyalty_earned",
    "loyalty_redeemed",
    "suscripcion_created",
    "suscripcion_paused",
    "suscripcion_resumed",
    "suscripcion_cancelled",
]


@dataclass(frozen=True)
class TimelineItem:
    """One row in the customer activity feed."""

    ts: datetime
    kind: TimelineKind
    label: str
    detail: str = ""
    href: Optional[str] = None
    icon: str = "•"  # single char, used by the template

    def as_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts.isoformat() if self.ts else None,
            "ts_display": self.ts.strftime("%d/%m/%Y %H:%M") if self.ts else "—",
            "kind": self.kind,
            "label": self.label,
            "detail": self.detail,
            "href": self.href,
            "icon": self.icon,
        }


_PEDIDO_STATUS_LABELS = {
    "pending": "Pendiente",
    "confirmed": "Confirmado",
    "in_production": "En producción",
    "ready": "Listo",
    "delivered": "Entregado",
    "cancelled": "Anulado",
    "completed": "Completado",
}

_ICON_BY_KIND: dict[str, str] = {
    "customer_created": "+",
    "customer_updated": "✎",
    "pedido_created": "🧾",
    "pedido_status": "⏵",
    "pedido_cancelled": "✕",
    "pedido_duplicated": "⧉",
    "message_sent": "✉",
    "message_received": "↩",
    "loyalty_earned": "★",
    "loyalty_redeemed": "★",
    "suscripcion_created": "🔁",
    "suscripcion_paused": "⏸",
    "suscripcion_resumed": "▶",
    "suscripcion_cancelled": "✕",
}

_DETAIL_KEYS_TO_KEEP = (
    "from_status",
    "to_status",
    "line_count",
    "total_gs",
    "channel",
    "delta",
    "reason",
)


def _timeline_icon(kind: str) -> str:
    return _ICON_BY_KIND.get(kind, "•")


def _label_for_pedido_event(evt: PedidoEvent, pedido: Pedido | None) -> tuple[str, str]:
    """Translate a PedidoEvent row into (label, detail) for the timeline."""
    ped_label = f"Pedido #{pedido.id}" if pedido else "Pedido"
    payload = evt.payload_json or {}
    if evt.event_type == "created":
        return (
            f"{ped_label} creado",
            f"{payload.get('line_count', '?')} líneas"
        )
    if evt.event_type == "status_change":
        to_status = payload.get("to_status", "?")
        return (
            f"{ped_label} → {_PEDIDO_STATUS_LABELS.get(to_status, to_status)}",
            f"por {evt.actor}" if evt.actor and evt.actor != "system" else "",
        )
    if evt.event_type == "cancelled":
        return (
            f"{ped_label} anulado",
            payload.get("reason") or "",
        )
    if evt.event_type == "duplicated":
        return (
            f"{ped_label} duplicado",
            f"→ nuevo #{payload.get('new_pedido_id', '?')}",
        )
    if evt.event_type in ("line_added", "line_removed", "line_qty_changed", "line_price_changed"):
        verb = {
            "line_added": "Línea agregada",
            "line_removed": "Línea quitada",
            "line_qty_changed": "Cantidad editada",
            "line_price_changed": "Precio editado",
        }[evt.event_type]
        return (
            f"{ped_label} · {verb}",
            f"por {evt.actor}" if evt.actor and evt.actor != "system" else "",
        )
    if evt.event_type == "note_edited":
        return (f"{ped_label} · nota editada", "")
    if evt.event_type == "address_changed":
        return (f"{ped_label} · dirección cambiada", "")
    if evt.event_type == "window_changed":
        return (f"{ped_label} · ventana cambiada", "")
    if evt.event_type == "customer_changed":
        return (f"{ped_label} · cliente cambiado", "")
    if evt.event_type == "payment_intent_set":
        return (f"{ped_label} · intención de pago", "")
    return (f"{ped_label} · {evt.event_type}", "")


def _label_for_comms(msg: CommunicationLog) -> tuple[str, str]:
    direction = "Enviado" if msg.direction == "outbound" else "Recibido"
    channel = {
        "whatsapp": "WhatsApp",
        "email": "Email",
        "sms": "SMS",
        "note": "Nota",
    }.get(msg.channel, msg.channel.title())
    detail = msg.subject or (msg.body[:60] + "…" if len(msg.body) > 60 else msg.body)
    return (
        f"{direction} · {channel}",
        detail or "",
    )


def _label_for_loyalty(entry: Any) -> tuple[str, str]:
    delta = getattr(entry, "delta", 0) or 0
    if delta > 0:
        return ("Puntos ganados", f"+{delta} pts · {entry.reason or ''}")
    return ("Puntos canjeados", f"{delta} pts · {entry.reason or ''}")


def _label_for_suscripcion(s: Any, evt_kind: str) -> tuple[str, str]:
    if evt_kind == "suscripcion_created":
        return ("Suscripción creada", f"#{s.id} · {s.frequency or 'semanal'}")
    if evt_kind == "suscripcion_paused":
        return ("Suscripción pausada", f"#{s.id}")
    if evt_kind == "suscripcion_resumed":
        return ("Suscripción reanudada", f"#{s.id}")
    if evt_kind == "suscripcion_cancelled":
        return ("Suscripción cancelada", f"#{s.id}")
    return (f"Suscripción #{s.id}", "")


def build_customer_timeline(
    session: Session,
    customer_id: int,
    *,
    limit: int = MAX_ITEMS,
) -> list[dict]:
    """Build the chronological activity feed for one customer.

    Returns a list of dicts ready for the template (timestamps as
    ISO strings + display strings, label/detail/href filled in).
    The list is sorted newest-first.
    """
    customer = session.get(Customer, customer_id)
    if customer is None:
        return []

    items: list[TimelineItem] = []

    # --- Customer-level events ---
    if customer.created_at:
        items.append(
            TimelineItem(
                ts=customer.created_at,
                kind="customer_created",
                label="Cliente registrado",
                detail="",
            )
        )
    if customer.updated_at and customer.created_at:
        # updated_at uses onupdate=datetime.utcnow, so it can drift by a few
        # milliseconds from created_at on a freshly-inserted customer.
        # Treat anything within 1 second as "same instant" → no event.
        delta = (customer.updated_at - customer.created_at).total_seconds()
        if delta > 1.0:
            items.append(
                TimelineItem(
                    ts=customer.updated_at,
                    kind="customer_updated",
                    label="Perfil actualizado",
                    detail="",
                )
            )

    # --- Pedido events ---
    pedido_ids = session.execute(
        select(Pedido.id).where(Pedido.customer_id == customer_id)
    ).scalars().all()
    pedido_index: dict[int, Pedido] = {}
    if pedido_ids:
        pedido_rows = session.execute(
            select(Pedido).where(Pedido.id.in_(pedido_ids))
        ).scalars().all()
        pedido_index = {p.id: p for p in pedido_rows}

    if pedido_ids:
        events = session.execute(
            select(PedidoEvent)
            .where(PedidoEvent.pedido_id.in_(pedido_ids))
            .order_by(PedidoEvent.ts.desc())
        ).scalars().all()
        for evt in events:
            pedido = pedido_index.get(evt.pedido_id)
            label, detail = _label_for_pedido_event(evt, pedido)
            kind: TimelineKind
            if evt.event_type == "created":
                kind = "pedido_created"
            elif evt.event_type == "cancelled":
                kind = "pedido_cancelled"
            elif evt.event_type == "duplicated":
                kind = "pedido_duplicated"
            else:
                kind = "pedido_status"
            items.append(
                TimelineItem(
                    ts=evt.ts,
                    kind=kind,
                    label=label,
                    detail=detail,
                    href=f"/pedidos/{evt.pedido_id}" if pedido else None,
                )
            )

    # --- Communication log ---
    comms = session.execute(
        select(CommunicationLog)
        .where(CommunicationLog.customer_id == customer_id)
        .order_by(CommunicationLog.ts_sent.desc())
    ).scalars().all()
    for msg in comms:
        label, detail = _label_for_comms(msg)
        items.append(
            TimelineItem(
                ts=msg.ts_sent,
                kind="message_sent" if msg.direction == "outbound" else "message_received",
                label=label,
                detail=detail,
                href=f"/pedidos/{msg.pedido_id}" if msg.pedido_id else None,
            )
        )

    # --- Loyalty ledger ---
    if LoyaltyTransaction is not None:
        loyalty = session.execute(
            select(LoyaltyTransaction)
            .where(LoyaltyTransaction.customer_id == customer_id)
            .order_by(LoyaltyTransaction.recorded_at.desc())
        ).scalars().all()
        for entry in loyalty:
            delta = entry.delta or 0
            if delta > 0:
                kind_l = "loyalty_earned"
                verb = "Puntos ganados"
                detail = f"+{delta} pts"
            else:
                kind_l = "loyalty_redeemed"
                verb = "Puntos canjeados"
                detail = f"{delta} pts"
            if entry.reason:
                reason_labels = {
                    "earn_sale": "por venta",
                    "redeem": "canje",
                    "void_reversal": "reversión",
                    "manual_adjust": "ajuste manual",
                    "suggestion_applied": "sugerencia aplicada",
                }
                detail += f" · {reason_labels.get(entry.reason, entry.reason)}"
            items.append(
                TimelineItem(
                    ts=entry.recorded_at or datetime.utcnow(),
                    kind=kind_l,
                    label=verb,
                    detail=detail,
                )
            )

    # --- Suscripciones (Phase 13) ---
    # Suscripcion doesn't have paused_at/resumed_at/cancelled_at columns
    # — it has a status field ('activa' | 'pausada' | 'cancelada') that
    # mutates through updates. We approximate the timeline by emitting
    # the create + the most recent status transition (derived from
    # updated_at whenever status != 'activa' on a fresh row).
    if Suscripcion is not None:
        subs = session.execute(
            select(Suscripcion)
            .where(Suscripcion.customer_id == customer_id)
        ).scalars().all()
        for s in subs:
            if getattr(s, "created_at", None):
                items.append(
                    TimelineItem(
                        ts=s.created_at,
                        kind="suscripcion_created",
                        label=f"Suscripción creada",
                        detail=f"#{s.id} · {s.cadence}",
                        href=f"/suscripciones#{s.id}",
                    )
                )
            if s.updated_at and s.created_at and s.updated_at > s.created_at:
                if s.status == "pausada":
                    items.append(
                        TimelineItem(
                            ts=s.updated_at,
                            kind="suscripcion_paused",
                            label="Suscripción pausada",
                            detail=f"#{s.id}",
                            href=f"/suscripciones#{s.id}",
                        )
                    )
                elif s.status == "cancelada":
                    items.append(
                        TimelineItem(
                            ts=s.updated_at,
                            kind="suscripcion_cancelled",
                            label="Suscripción cancelada",
                            detail=f"#{s.id}",
                            href=f"/suscripciones#{s.id}",
                        )
                    )
                elif s.status == "activa":
                    items.append(
                        TimelineItem(
                            ts=s.updated_at,
                            kind="suscripcion_resumed",
                            label="Suscripción reactivada",
                            detail=f"#{s.id}",
                            href=f"/suscripciones#{s.id}",
                        )
                    )

    # --- Sort newest-first, dedupe, cap ---
    items.sort(key=lambda i: i.ts or datetime.min, reverse=True)
    items = items[:limit]
    return [it.as_dict() for it in items]
