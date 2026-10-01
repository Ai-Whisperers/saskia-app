"""tests/test_dashboard_enrollment_kpi.py — Loyalty enrollment KPI card.

Tier 3.1 (2026-10-01): the single most important loyalty health metric
is enrollment rate = % of sales in a window that had a customer attached.
Industry norm is 40-60%. Below 30% means friction or lack of prompting.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime, timezone

import pytest

from app.rms.config import ASUNCION_TZ
from app.rms.models import Customer, Sale


def _make_customer(s, name, phone=None):
    c = Customer(name=name, phone=phone or f"+5959{abs(hash(name)) % 100000000:08d}")
    s.add(c)
    s.flush()
    return c


def _make_sale(s, customer_id, product_id, qty=1.0, price=10000, when=None, voided=False):
    # Tier 3.1 test note: dashboard filters by Asuncion-local time,
    # so seed sales with local-time datetimes to ensure they land in
    # the "today" window. Without this, a sale at 02:00 UTC (e.g.
    # 23:00 PY the previous day) gets bucketed into the prior period.
    from app.rms.config import ASUNCION_TZ
    if when is None:
        when = datetime.now(ASUNCION_TZ)
    s.add(Sale(
        customer_id=customer_id, product_id=product_id, qty=qty,
        unit_price_gs=price, sold_at=when,
        voided_at=datetime.now(timezone.utc) if voided else None,
    ))
    s.flush()


def test_enrollment_card_empty_when_no_sales(client, session_factory, qseed):
    """No sales today → 'sin ventas' empty state."""
    r = client.get("/")
    assert r.status_code == 200
    assert "Clientes asociados" in r.text, "KPI card label missing"
    assert "sin ventas" in r.text


def test_enrollment_card_full_when_every_sale_has_customer(
    client, session_factory, qseed
):
    """All sales with a customer → 100%."""
    from tests.factories import make_sellable
    with session_factory() as s:
        product = make_sellable(s)
        c1 = _make_customer(s, "Cust1")
        c2 = _make_customer(s, "Cust2")
        now = datetime.now(ASUNCION_TZ)
        _make_sale(s, c1.id, product.id, when=now)
        _make_sale(s, c2.id, product.id, when=now)
        _make_sale(s, c1.id, product.id, when=now)
        s.commit()
    r = client.get("/")
    assert r.status_code == 200
    assert "100.0%" in r.text
    assert "3 de 3 ventas" in r.text


def test_enrollment_card_half_when_half_sales_have_customer(
    client, session_factory, qseed
):
    """Half with customer → 50.0%."""
    from tests.factories import make_sellable
    with session_factory() as s:
        product = make_sellable(s)
        c = _make_customer(s, "LoyalOne")
        now = datetime.now(ASUNCION_TZ)
        _make_sale(s, c.id, product.id, when=now)
        # Walk-in (no customer)
        s.add(Sale(
            customer_id=None, product_id=product.id, qty=1.0,
            unit_price_gs=10000, sold_at=now, voided_at=None,
        ))
        s.flush()
        s.commit()
    r = client.get("/")
    assert r.status_code == 200
    assert "50.0%" in r.text
    assert "1 de 2 ventas" in r.text


def test_enrollment_card_excludes_voided_sales(
    client, session_factory, qseed
):
    """Voided sales don't count in either numerator or denominator."""
    from tests.factories import make_sellable
    with session_factory() as s:
        product = make_sellable(s)
        c = _make_customer(s, "VoidTest")
        now = datetime.now(ASUNCION_TZ)
        _make_sale(s, c.id, product.id, when=now)
        _make_sale(s, None, product.id, when=now, voided=True)
        s.commit()
    r = client.get("/")
    assert r.status_code == 200
    # Should be 1 of 1 (the voided sale is excluded) → 100%
    assert "100.0%" in r.text
    assert "1 de 1 ventas" in r.text
