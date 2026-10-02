"""Phase 17 (2026-10-02): cliente_detalle page renders the new
activity timeline (replaces the hardcoded 3-item list)."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import text


@pytest.fixture
def customer_with_activity(session_factory):
    """Seed a customer with one of each timeline source."""
    from app.rms.models import (
        CommunicationLog,
        Customer,
        LoyaltyTransaction,
        Pedido,
        PedidoEvent,
    )
    import secrets

    with session_factory() as s:
        c = Customer(
            name="Timeline Render Test",
            phone="+595 981 555 555",
            loyalty_points=42,
        )
        s.add(c)
        s.flush()
        s.commit()
        s.refresh(c)

        # Pedido event
        p = Pedido(
            customer_id=c.id,
            status="pending",
            promised_date=datetime.utcnow().date() + timedelta(days=1),
            public_token=secrets.token_urlsafe(16),
        )
        s.add(p)
        s.flush()
        s.add(PedidoEvent(
            pedido_id=p.id,
            ts=datetime.utcnow() - timedelta(hours=2),
            actor="demo",
            event_type="created",
            payload_json={"line_count": 2},
        ))

        # Communication log
        s.add(CommunicationLog(
            direction="outbound",
            channel="whatsapp",
            customer_id=c.id,
            body="Tu pedido está listo",
            status="sent",
            ts_sent=datetime.utcnow() - timedelta(hours=1),
            actor="system",
        ))

        # Loyalty earn
        s.add(LoyaltyTransaction(
            customer_id=c.id,
            delta=8,
            reason="earn_sale",
            actor="system",
            recorded_at=datetime.utcnow() - timedelta(minutes=30),
        ))

        s.commit()
        return c.id


def test_cliente_detalle_renders_timeline(client, customer_with_activity):
    """GET /clientes/{id} renders the timeline ul with mixed event kinds."""
    r = client.get(f"/clientes/{customer_with_activity}")
    assert r.status_code == 200
    html = r.text
    assert 'data-testid="customer-timeline"' in html
    # At least one of each kind we seeded
    assert 'data-kind="customer_created"' in html
    assert 'data-kind="pedido_created"' in html
    assert 'data-kind="message_sent"' in html
    assert 'data-kind="loyalty_earned"' in html


def test_cliente_detalle_timeline_links_to_pedido(client, customer_with_activity):
    """Pedido items in the timeline link to /pedidos/{id}."""
    r = client.get(f"/clientes/{customer_with_activity}")
    assert r.status_code == 200
    html = r.text
    assert "/pedidos/" in html


def test_cliente_detalle_timeline_renders_for_new_customer(client, session_factory):
    """A new customer with no extra events still shows customer_created."""
    from app.rms.models import Customer
    with session_factory() as s:
        c = Customer(name="New Customer Test", phone="+595 981 666 666", loyalty_points=0)
        s.add(c)
        s.commit()
        s.refresh(c)
        cid = c.id

    r = client.get(f"/clientes/{cid}")
    assert r.status_code == 200
    html = r.text
    # customer_created is always in the timeline for an existing customer
    assert 'data-testid="customer-timeline"' in html
    assert 'data-kind="customer_created"' in html
    # No other kinds yet
    assert 'data-kind="pedido_created"' not in html
    assert 'data-kind="message_sent"' not in html


def test_cliente_api_includes_timeline(client, customer_with_activity):
    """The JSON detail endpoint exposes the timeline array."""
    r = client.get(f"/clientes/api/{customer_with_activity}")
    assert r.status_code == 200
    data = r.json()
    assert "timeline" in data
    assert isinstance(data["timeline"], list)
    assert len(data["timeline"]) >= 4  # customer_created + pedido + comm + loyalty
    kinds = {it["kind"] for it in data["timeline"]}
    assert "customer_created" in kinds
    assert "pedido_created" in kinds
    assert "message_sent" in kinds
    assert "loyalty_earned" in kinds


def test_cliente_api_timeline_sorted_newest_first(client, customer_with_activity):
    """The JSON timeline is sorted newest-first."""
    r = client.get(f"/clientes/api/{customer_with_activity}")
    data = r.json()
    ts = [it["ts"] for it in data["timeline"] if it["ts"]]
    assert ts == sorted(ts, reverse=True)


def test_cliente_api_timeline_includes_href(client, customer_with_activity):
    """Items with a natural link (pedido, message) get an href."""
    r = client.get(f"/clientes/api/{customer_with_activity}")
    data = r.json()
    has_href = [it for it in data["timeline"] if it.get("href")]
    assert len(has_href) >= 1
    for it in has_href:
        assert it["href"].startswith("/")
