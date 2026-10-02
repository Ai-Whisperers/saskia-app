"""Tests for the customer_timeline service (Phase 17, 2026-10-02).

Aggregates events from PedidoEvent, CommunicationLog, LoyaltyTransaction,
Suscripcion, and Customer itself into a single chronological feed."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.rms.models import (
    CommunicationLog,
    Customer,
    LoyaltyTransaction,
    Pedido,
    PedidoEvent,
    Suscripcion,
)


def _make_customer(session, name: str = "Timeline Test") -> Customer:
    c = Customer(
        name=name,
        phone="+595 981 000 000",
        loyalty_points=0,
    )
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def test_timeline_empty_customer_returns_just_creation(session_factory):
    """A brand-new customer with no events returns only customer_created."""
    from app.services.customer_timeline import build_customer_timeline

    with session_factory() as s:
        c = _make_customer(s, "Empty Timeline")
        items = build_customer_timeline(s, c.id)

    assert len(items) == 1
    assert items[0]["kind"] == "customer_created"
    assert items[0]["label"] == "Cliente registrado"


def test_timeline_includes_pedido_events(session_factory):
    """Pedido created + status_change appear in the timeline."""
    from app.services.customer_timeline import build_customer_timeline

    with session_factory() as s:
        c = _make_customer(s, "Pedido Timeline")
        p = Pedido(
            customer_id=c.id,
            status="pending",
            promised_date=datetime.utcnow().date() + timedelta(days=1),
        )
        s.add(p)
        s.commit()
        s.refresh(p)
        s.add(PedidoEvent(
            pedido_id=p.id,
            ts=datetime.utcnow() - timedelta(hours=2),
            actor="demo",
            event_type="created",
            payload_json={"line_count": 3},
        ))
        s.add(PedidoEvent(
            pedido_id=p.id,
            ts=datetime.utcnow() - timedelta(hours=1),
            actor="demo",
            event_type="status_change",
            payload_json={"to_status": "confirmed"},
        ))
        s.commit()
        items = build_customer_timeline(s, c.id)

    kinds = [it["kind"] for it in items]
    assert "pedido_created" in kinds
    assert "pedido_status" in kinds
    # Newest first
    ts_pairs = [(it["ts"]) for it in items]
    assert ts_pairs == sorted(ts_pairs, reverse=True)


def test_timeline_includes_communication_log(session_factory):
    """Outbound WhatsApp + inbound email both surface as timeline items."""
    from app.services.customer_timeline import build_customer_timeline

    with session_factory() as s:
        c = _make_customer(s, "Comms Timeline")
        s.add(CommunicationLog(
            direction="outbound",
            channel="whatsapp",
            customer_id=c.id,
            body="Hola, tu pedido está listo",
            status="sent",
            ts_sent=datetime.utcnow() - timedelta(hours=4),
            actor="system",
        ))
        s.add(CommunicationLog(
            direction="inbound",
            channel="email",
            customer_id=c.id,
            body="Gracias!",
            status="received",
            ts_sent=datetime.utcnow() - timedelta(hours=2),
        ))
        s.commit()
        items = build_customer_timeline(s, c.id)

    labels = [it["label"] for it in items]
    assert any("WhatsApp" in lbl for lbl in labels)
    assert any("Email" in lbl for lbl in labels)
    kinds = [it["kind"] for it in items]
    assert "message_sent" in kinds
    assert "message_received" in kinds


def test_timeline_includes_loyalty_earn_and_redeem(session_factory):
    """Positive deltas → 'Puntos ganados', negative → 'Puntos canjeados'."""
    from app.services.customer_timeline import build_customer_timeline

    with session_factory() as s:
        c = _make_customer(s, "Loyalty Timeline")
        s.add(LoyaltyTransaction(
            customer_id=c.id,
            delta=10,
            reason="earn_sale",
            actor="system",
            recorded_at=datetime.utcnow() - timedelta(hours=3),
        ))
        s.add(LoyaltyTransaction(
            customer_id=c.id,
            delta=-5,
            reason="redeem",
            actor="demo",
            recorded_at=datetime.utcnow() - timedelta(hours=1),
        ))
        s.commit()
        items = build_customer_timeline(s, c.id)

    earn = [it for it in items if it["kind"] == "loyalty_earned"]
    redeem = [it for it in items if it["kind"] == "loyalty_redeemed"]
    assert len(earn) == 1
    assert "+10" in earn[0]["detail"]
    assert len(redeem) == 1
    assert "-5" in redeem[0]["detail"]


def test_timeline_includes_suscripcion_lifecycle(session_factory):
    """A suscripcion emits a 'suscripcion_created' event at minimum."""
    from app.services.customer_timeline import build_customer_timeline

    with session_factory() as s:
        c = _make_customer(s, "Sub Timeline")
        s.add(Suscripcion(
            customer_id=c.id,
            product_summary="1 kg chipa",
            cadence="semanal",
            price_gs=50000,
            status="activa",
        ))
        s.commit()
        items = build_customer_timeline(s, c.id)

    created = [it for it in items if it["kind"] == "suscripcion_created"]
    assert len(created) == 1
    assert "#1" in created[0]["detail"]


def test_timeline_cancelled_suscripcion_emits_event(session_factory):
    """A paused/cancelled suscripcion emits a status transition event."""
    from app.services.customer_timeline import build_customer_timeline

    with session_factory() as s:
        c = _make_customer(s, "Sub Pause")
        now = datetime.utcnow()
        s.add(Suscripcion(
            customer_id=c.id,
            product_summary="pan",
            cadence="semanal",
            price_gs=30000,
            status="pausada",
            created_at=now - timedelta(days=10),
            updated_at=now - timedelta(hours=6),
        ))
        s.commit()
        items = build_customer_timeline(s, c.id)

    paused = [it for it in items if it["kind"] == "suscripcion_paused"]
    assert len(paused) == 1


def test_timeline_respects_max_items(session_factory):
    """When there are more events than MAX_ITEMS, the list is capped."""
    from app.services.customer_timeline import build_customer_timeline, MAX_ITEMS
    import secrets

    with session_factory() as s:
        c = _make_customer(s, "Long Timeline")
        # 5 pedido events to add on top of the customer_created entry
        for i in range(5):
            p = Pedido(
                customer_id=c.id,
                status="pending",
                promised_date=datetime.utcnow().date(),
                public_token=secrets.token_urlsafe(16),
            )
            s.add(p)
            s.flush()
            s.add(PedidoEvent(
                pedido_id=p.id,
                ts=datetime.utcnow() - timedelta(hours=i),
                actor="demo",
                event_type="created",
                payload_json={"line_count": 1},
            ))
        s.commit()
        items = build_customer_timeline(s, c.id)

    assert len(items) <= MAX_ITEMS


def test_timeline_unknown_customer_returns_empty(session_factory):
    """Asking for a non-existent customer returns an empty list, not error."""
    from app.services.customer_timeline import build_customer_timeline

    with session_factory() as s:
        items = build_customer_timeline(s, 99999)
    assert items == []


def test_timeline_sorted_newest_first(session_factory):
    """Items are returned newest-first, regardless of source."""
    from app.services.customer_timeline import build_customer_timeline

    with session_factory() as s:
        c = _make_customer(s, "Sort Test")
        # Pedido from 1 hour ago
        p = Pedido(
            customer_id=c.id,
            status="pending",
            promised_date=datetime.utcnow().date(),
        )
        s.add(p)
        s.flush()
        s.add(PedidoEvent(
            pedido_id=p.id,
            ts=datetime.utcnow() - timedelta(hours=1),
            actor="demo",
            event_type="created",
            payload_json={},
        ))
        # Communication from 30 minutes ago
        s.add(CommunicationLog(
            direction="outbound",
            channel="note",
            customer_id=c.id,
            body="test",
            status="sent",
            ts_sent=datetime.utcnow() - timedelta(minutes=30),
        ))
        s.commit()
        items = build_customer_timeline(s, c.id)

    ts_list = [it["ts"] for it in items]
    assert ts_list == sorted(ts_list, reverse=True)
