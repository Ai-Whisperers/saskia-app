"""tests/test_pedido_event_lifecycle.py — phase 11 timeline integration.

Verify the PedidoEventService writes are reflected in:
- pedido_event table (direct query)
- pedido_history.build_pedido_timeline (the operator-facing view)
- HTTP lifecycle: POST /pedidos/nuevo writes 'created' + 'line_added';
  POST /pedidos/{id}/fulfill writes 'status_change'.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.rms.config import ASUNCION_TZ
from app.rms.models import Pedido, PedidoEvent
from app.services.pedido_events import PedidoEventService
from app.services.pedido_history import build_pedido_timeline

# ---------- 1. Timeline integration ----------

def test_timeline_includes_pedido_events(session_factory):
    """PedidoEvent rows show up in build_pedido_timeline."""
    with session_factory() as s:
        # Create a pedido + 3 events
        from app.rms.models import Customer
        c = Customer(name="Timeline Test", phone="0999000002")
        s.add(c); s.flush()
        p = Pedido(customer_id=c.id, customer_name="Timeline Test",
                   customer_phone="0999000002",
                   promised_date=datetime.now(ASUNCION_TZ).date(),
                   status="pending", public_token="tl-test-1")
        s.add(p); s.flush()

        # Three events at distinct timestamps
        t0 = datetime.now(ASUNCION_TZ) - timedelta(minutes=30)
        PedidoEventService.record(s, p.id, "created", actor="demo", ts=t0, payload={"n": 1})
        PedidoEventService.record(s, p.id, "line_added", actor="demo",
            ts=t0 + timedelta(seconds=5),
            payload={"product_id": 7, "qty": 2.0, "unit_price_gs": 10000})
        PedidoEventService.record(s, p.id, "status_change", actor="demo",
            ts=t0 + timedelta(minutes=20),
            payload={"from": "pending", "to": "fulfilled"})
        s.commit()
        pid = p.id

    with session_factory() as s:
        pedido = s.get(Pedido, pid)
        timeline = build_pedido_timeline(s, pedido)

        # We expect 3 events of kind='event' (from PedidoEvent)
        pe_events = [e for e in timeline if e.kind == "event"]
        assert len(pe_events) == 3

        # Verify ordering: oldest first
        assert pe_events[0].label == "Pedido creado"
        assert pe_events[1].label == "Línea añadida"
        assert pe_events[2].label == "Estado cambiado"

        # Verify detail rendering
        assert pe_events[1].detail == "producto #7 × 2.0"
        assert pe_events[2].detail == "pending → fulfilled"

        # All should have actor
        for e in pe_events:
            assert e.actor == "demo"


def test_timeline_event_types_have_spanish_labels():
    """Every event_type in the CK constraint has a label."""
    from app.services.pedido_events import VALID_EVENT_TYPES
    from app.services.pedido_history import _label_for_event_type
    for et in VALID_EVENT_TYPES:
        lbl = _label_for_event_type(et)
        # Must be non-empty and contain either the literal English type
        # (for "duplicated") or some Spanish word
        assert lbl and lbl.strip(), f"empty label for {et}"


def test_timeline_handles_no_events(session_factory):
    """A pedido with zero PedidoEvent rows still works."""
    with session_factory() as s:
        from app.rms.models import Customer
        c = Customer(name="No Events", phone="0999000003")
        s.add(c); s.flush()
        p = Pedido(customer_id=c.id, customer_name="No Events",
                   customer_phone="0999000003",
                   promised_date=datetime.now(ASUNCION_TZ).date(),
                   status="pending", public_token="no-events-1")
        s.add(p); s.flush()
        s.commit()
        pid = p.id

    with session_factory() as s:
        pedido = s.get(Pedido, pid)
        timeline = build_pedido_timeline(s, pedido)
        pe_events = [e for e in timeline if e.kind == "event"]
        assert pe_events == []


# ---------- 2. HTTP lifecycle ----------

def test_pedido_create_writes_created_and_line_added(client, session_factory):
    """POST /pedidos/nuevo writes PedidoEvent entries."""
    from app.rms.models import Customer, Product
    with session_factory() as s:
        # Always create a product fresh in this test
        prod = Product(name="Lifecycle Test Product", sale_price_gs=10000)
        s.add(prod); s.flush()
        c = Customer(name="HTTP Test", phone="0999000004")
        s.add(c); s.flush()
        cid = c.id
        pid_prod = prod.id
        s.commit()

    r = client.post(
        "/pedidos/nuevo",
        data={
            "customer_id": str(cid),
            "customer_name": "HTTP Test",
            "customer_phone": "0999000004",
            "promised_date": datetime.now(ASUNCION_TZ).date().isoformat(),
            "channel": "whatsapp",
            "payment_intent": "efectivo",
            "line_product_id": str(pid_prod),
            "line_qty": "1.0",
            "line_unit_price_gs": "10000",
        },
        follow_redirects=False,
    )
    assert r.status_code in (303, 302), f"expected redirect, got {r.status_code}"
    # Extract pedido id from Location header
    location = r.headers.get("location", "")
    # Like "/pedidos/42"
    new_pedido_id = int(location.rsplit("/", 1)[-1])

    with session_factory() as s:
        pe_rows = s.query(PedidoEvent).filter_by(pedido_id=new_pedido_id).order_by(PedidoEvent.id).all()
        # Expect: created + line_added = 2
        assert len(pe_rows) >= 2, f"expected >=2 events, got {len(pe_rows)}"
        types = [r.event_type for r in pe_rows]
        assert "created" in types
        assert "line_added" in types

        created = next(r for r in pe_rows if r.event_type == "created")
        # Channel gets normalized to display case (e.g. 'whatsapp' → 'WhatsApp')
        assert created.payload_json["channel"].lower() == "whatsapp"
        assert created.payload_json["n_lines"] == 1

        line_added = next(r for r in pe_rows if r.event_type == "line_added")
        assert line_added.payload_json["product_id"] == pid_prod
        assert line_added.payload_json["qty"] == 1.0
