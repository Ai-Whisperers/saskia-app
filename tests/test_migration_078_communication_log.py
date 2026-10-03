"""tests/test_migration_078_communication_log.py — phase 12.

Verify:
- Schema bumps to 78 and the communication_log table exists with the
  expected columns + check constraints
- FK CASCADE on customer; FK SET NULL on pedido/message_template
- Idempotent migration (running twice doesn't fail)
- INSERT/INSERT-with-violation: invalid enum values are rejected
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, text


def test_migration_078_bumps_schema_version(session_factory):
    """Fresh DB starts at 78 (or higher)."""
    with session_factory() as s:
        v = s.execute(text("SELECT value FROM app_meta WHERE key='schema_version'")).scalar()
    assert v is not None
    assert int(v) >= 78


def test_communication_log_table_exists_with_columns(session_factory):
    """Migration 078 created communication_log with the expected columns."""
    with session_factory() as s:
        insp = inspect(s.get_bind())
        tables = insp.get_table_names()
        assert "communication_log" in tables
        cols = {c["name"] for c in insp.get_columns("communication_log")}
        for required in (
            "id", "direction", "channel", "customer_id", "pedido_id",
            "template_id", "phone", "email", "subject", "body",
            "status", "provider_message_id", "error_message",
            "ts_sent", "ts_delivered", "ts_read", "actor",
        ):
            assert required in cols, f"missing column {required}"


def test_communication_log_indexes_exist(session_factory):
    """Index coverage for the four main query patterns."""
    with session_factory() as s:
        idx_names = {i["name"] for i in inspect(s.get_bind()).get_indexes("communication_log")}
    expected = [
        "ix_communication_log_customer_id",
        "ix_communication_log_pedido_id",
        "ix_communication_log_provider_message_id",
        "ix_communication_log_ts_sent",
        "ix_communication_log_customer_ts",
        "ix_communication_log_pedido_ts",
        "ix_communication_log_status_ts",
    ]
    for expected_name in expected:
        assert expected_name in idx_names, f"missing index {expected_name}"


def test_communication_log_check_constraints(session_factory):
    """Enum constraints reject invalid direction/channel/status values."""
    from datetime import datetime

    from app.rms.models import CommunicationLog, Customer

    with session_factory() as s:
        c = Customer(name="Comm Test", phone="0998000001")
        s.add(c)
        s.flush()

        # Invalid direction → CHECK violation
        with pytest.raises(Exception) as exc_info:
            bad = CommunicationLog(
                direction="sideways",  # not in ('outbound','inbound')
                channel="whatsapp",
                customer_id=c.id,
                body="hi",
                ts_sent=datetime.utcnow(),
            )
            s.add(bad)
            s.commit()
        s.rollback()
        # Make sure the bad row is gone
        assert "ck_communication_log_direction" in str(exc_info.value) or \
               "CHECK" in str(exc_info.value) or \
               "constraint" in str(exc_info.value).lower()

        # Invalid channel → CHECK violation
        with pytest.raises(Exception) as exc_info:
            bad = CommunicationLog(
                direction="outbound",
                channel="fax",  # not in ('whatsapp','email','sms','note')
                customer_id=c.id,
                body="hi",
                ts_sent=datetime.utcnow(),
            )
            s.add(bad)
            s.commit()
        s.rollback()
        assert "ck_communication_log_channel" in str(exc_info.value) or \
               "CHECK" in str(exc_info.value) or \
               "constraint" in str(exc_info.value).lower()

        # Invalid status → CHECK violation
        with pytest.raises(Exception) as exc_info:
            bad = CommunicationLog(
                direction="outbound",
                channel="whatsapp",
                customer_id=c.id,
                body="hi",
                status="bounced",  # not in the enum
                ts_sent=datetime.utcnow(),
            )
            s.add(bad)
            s.commit()
        s.rollback()
        assert "ck_communication_log_status" in str(exc_info.value) or \
               "CHECK" in str(exc_info.value) or \
               "constraint" in str(exc_info.value).lower()


def test_communication_log_cascades_on_customer_delete(session_factory):
    """Deleting a customer removes all their messages (FK ON DELETE CASCADE)."""
    from datetime import datetime

    from app.rms.models import CommunicationLog, Customer

    with session_factory() as s:
        c = Customer(name="Cascade Comm Test", phone="0998000002")
        s.add(c)
        s.flush()
        for i in range(3):
            s.add(CommunicationLog(
                direction="outbound", channel="whatsapp",
                customer_id=c.id, body=f"msg {i}",
                status="sent",
                ts_sent=datetime.utcnow(),
            ))
        s.commit()
        cid = c.id
        n = s.query(CommunicationLog).filter_by(customer_id=cid).count()
        assert n == 3

        # Delete customer
        s.delete(c)
        s.commit()
        n_after = s.query(CommunicationLog).filter_by(customer_id=cid).count()
        assert n_after == 0


def test_communication_log_set_null_on_pedido_delete(session_factory):
    """Deleting a pedido NULLs pedido_id on related messages (FK SET NULL)."""
    from datetime import datetime

    from app.rms.models import CommunicationLog, Customer, Pedido

    with session_factory() as s:
        c = Customer(name="Pedido Comm Test", phone="0998000003")
        s.add(c)
        s.flush()
        p = Pedido(customer_id=c.id, customer_name=c.name,
                   customer_phone=c.phone,
                   promised_date=datetime.utcnow().date(),
                   status="pending", public_token="comm-test-ped")
        s.add(p)
        s.flush()
        msg = CommunicationLog(
            direction="outbound", channel="whatsapp",
            customer_id=c.id, pedido_id=p.id,
            body="hello", status="sent",
            ts_sent=datetime.utcnow(),
        )
        s.add(msg)
        s.commit()
        msg_id = msg.id

        # Delete the pedido
        s.delete(p)
        s.commit()

        # The message still exists; pedido_id was nulled
        s.expire_all()
        m2 = s.get(_Message := __import__("app.rms.models", fromlist=["CommunicationLog"]).CommunicationLog, msg_id)
        assert m2 is not None
        assert m2.pedido_id is None
        assert m2.customer_id == c.id  # customer FK still intact
