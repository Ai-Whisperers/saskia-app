"""P-38: /pedidos must have a bulk-action toolbar (regression).

Audit shows bulk-fulfill + bulk-cancel forms ARE present (line 170, 175
of pedidos.html) but only render when there are pedidos. The original
P-38 plan was to ADD a new bulk-deliver route, but a previous session
already shipped bulk-fulfill + bulk-cancel. This test pins both.

Acceptance:
  - When pedidos exist, /pedidos contains forms pointing to
    /pedidos/bulk-fulfill and /pedidos/bulk-cancel.
  - A 'seleccionar todos' checkbox is present.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import sessionmaker

from app.rms.models import Customer, Pedido


def _make_pedido(s):
    """Create a minimal pedido so the bulk-toolbar renders."""
    cust = Customer(name=f"c-{uuid.uuid4().hex[:6]}", phone="+595 9XX")
    s.add(cust)
    s.flush()
    ped = Pedido(
        customer_id=cust.id, status="pending",
        promised_date=(datetime.now(timezone.utc) + timedelta(days=1)).date(),
        created_at=datetime.now(timezone.utc),
    )
    s.add(ped)
    s.flush()
    return ped.id


def test_pedidos_bulk_action_forms_present(client, session_factory):
    """P-38: /pedidos has bulk-fulfill + bulk-cancel forms when pedidos exist."""
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        _make_pedido(s)
        s.commit()
    finally:
        s.close()

    r = client.get("/pedidos")
    assert r.status_code == 200
    body = r.text

    assert "/pedidos/bulk-fulfill" in body, (
        "expected /pedidos/bulk-fulfill form on /pedidos list"
    )
    assert "/pedidos/bulk-cancel" in body, (
        "expected /pedidos/bulk-cancel form on /pedidos list"
    )
    assert 'id="select-all"' in body, (
        "expected 'select-all' checkbox on /pedidos list"
    )
