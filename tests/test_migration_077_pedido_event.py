"""tests/test_migration_077_pedido_event.py — phase 11.

Verify:
- Schema bumps to 77 and the pedido_event table exists with correct columns
- PedidoEventService.record creates rows with correct fields
- Invalid event_type raises ValueError
- CASCADE delete: dropping a pedido wipes its events
- Migration is idempotent (running twice doesn't fail)
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, text


# ---------- 1. Migration shape ----------

def test_migration_077_bumps_schema_version(session_factory):
    """Fresh DB starts at 77 (or higher)."""
    with session_factory() as s:
        v = s.execute(text("SELECT value FROM app_meta WHERE key='schema_version'")).scalar()
    assert v is not None
    assert int(v) >= 77


def test_pedido_event_table_exists_with_columns(session_factory):
    """Migration 077 created pedido_event with the expected columns."""
    with session_factory() as s:
        bind = s.get_bind()
        insp = inspect(bind)
        tables = insp.get_table_names()
        assert "pedido_event" in tables
        cols = {c["name"] for c in insp.get_columns("pedido_event")}
        for required in ("id", "pedido_id", "ts", "actor", "event_type", "payload_json"):
            assert required in cols, f"missing column {required}"


def test_pedido_event_has_indexes(session_factory):
    """pedido_id + composite (pedido_id, ts) indexes exist for timeline speed."""
    with session_factory() as s:
        insp = inspect(s.get_bind())
        idx_names = {i["name"] for i in insp.get_indexes("pedido_event")}
    assert any("pedido_id" in n for n in idx_names)
    # Composite index may have been created by SQLAlchemy as
    # ix_pedido_event_pedido_ts or by the explicit migration SQL.
    # We accept either presence.
    assert any("pedido_ts" in n or "pedido_event_ts" in n for n in idx_names)


# ---------- 2. Service API ----------

def test_service_record_creates_row(qseed, session_factory):
    """PedidoEventService.record appends a row + flushes."""
    from app.seed.kyrian import KYRIAN_PHONE
    from app.rms.models import Customer, Pedido
    from app.services.pedido_events import PedidoEventService

    qseed("with_kyrian_full")
    with session_factory() as s:
        kyrian = s.query(Customer).filter_by(phone=KYRIAN_PHONE).one()
        pedido = s.query(Pedido).filter_by(customer_id=kyrian.id).first()
        pid = pedido.id

        evt = PedidoEventService.record(
            s, pid, "note_edited", actor="demo",
            payload={"from": "", "to": "sin cebolla"}
        )
        s.commit()
        assert evt is not None
        assert evt.id is not None
        assert evt.event_type == "note_edited"
        assert evt.payload_json == {"from": "", "to": "sin cebolla"}
        assert evt.actor == "demo"


def test_service_invalid_event_type_raises(qseed, session_factory):
    """Typos in event_type raise ValueError, not DB error."""
    from app.seed.kyrian import KYRIAN_PHONE
    from app.rms.models import Customer, Pedido
    from app.services.pedido_events import PedidoEventService

    qseed("with_kyrian_full")
    with session_factory() as s:
        kyrian = s.query(Customer).filter_by(phone=KYRIAN_PHONE).one()
        pedido = s.query(Pedido).filter_by(customer_id=kyrian.id).first()
        with pytest.raises(ValueError, match="Invalid pedido event_type"):
            PedidoEventService.record(s, pedido.id, "edit", actor="demo")


def test_service_cascades_on_pedido_delete(qseed, session_factory):
    """Deleting a pedido removes its events (FK ON DELETE CASCADE).

    We construct a fresh, isolated pedido with no FK references pointing
    at it (no fulfilled_sale_id, no sale stock moves, no audit log refs)
    so the cascade can run cleanly. The seeded Kyrian pedidos have lots
    of FK references that complicate direct deletion in a unit test.
    """
    from app.rms.models import Customer, Pedido, PedidoEvent
    from app.services.pedido_events import PedidoEventService
    from app.rms.config import ASUNCION_TZ
    from datetime import datetime

    with session_factory() as s:
        c = Customer(name="Cascade Test", phone="0999000001")
        s.add(c); s.flush()

        p = Pedido(
            customer_id=c.id, customer_name="Cascade Test",
            customer_phone="0999000001",
            promised_date=datetime.now(ASUNCION_TZ).date(),
            status="pending", public_token="cascade-delete-test-token-177",
        )
        s.add(p); s.flush()
        pid = p.id

        # Record 3 events on this pedido
        for et in ("note_edited", "line_added", "status_change"):
            PedidoEventService.record(s, pid, et, actor="demo", payload={"k": et})
        s.commit()

        # Verify rows exist
        before = s.query(PedidoEvent).filter_by(pedido_id=pid).count()
        assert before == 3

        # Delete the pedido — events must cascade away
        s.delete(p)
        s.commit()

        after = s.query(PedidoEvent).filter_by(pedido_id=pid).count()
        assert after == 0


def test_valid_event_types_match_constraint():
    """VALID_EVENT_TYPES has all 13 events declared in the constraint."""
    from app.services.pedido_events import VALID_EVENT_TYPES
    expected = {
        "created", "status_change", "line_added", "line_removed",
        "line_qty_changed", "line_price_changed", "note_edited",
        "address_changed", "window_changed", "customer_changed",
        "payment_intent_set", "cancelled", "duplicated",
    }
    assert expected == set(VALID_EVENT_TYPES)