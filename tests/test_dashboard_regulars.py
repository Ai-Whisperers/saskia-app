"""tests/test_dashboard_regulars.py — Coffee regulars card on /inicio.

Prelaunch roadmap 2026-09-17 item: "Coffee regulars" card on dashboard.

Definition: customers with 2+ non-voided sales in the last 30 days.
Top 5 by visit count shown; total count surfaced via "Ver los N habituales".
"""
# allow-hardcoded-dates: relative offsets only (timedelta from now).
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime, timedelta, timezone

from app.rms.models import Customer, Sale


def _make_customer(s, name, phone=None):
    c = Customer(name=name, phone=phone or f"+5959{abs(hash(name)) % 100000000:08d}")
    s.add(c)
    s.flush()
    return c


def _make_sale(s, customer_id, product_id, qty=1.0, price=10000, when=None):
    s.add(Sale(
        customer_id=customer_id, product_id=product_id, qty=qty,
        unit_price_gs=price, sold_at=when or datetime.now(timezone.utc),
        voided_at=None,
    ))
    s.flush()


def test_regulars_card_hidden_when_no_regulars(client, session_factory, qseed):
    """No customers with 2+ sales → empty state copy."""
    from tests.factories import make_sellable
    with session_factory() as s:
        product = make_sellable(s)
        # one customer with 1 sale only
        c = _make_customer(s, "OneVisitOnly")
        _make_sale(s, c.id, product_id=product.id, when=datetime.now(timezone.utc))
        s.commit()
    r = client.get("/")
    assert r.status_code == 200
    assert "Clientes habituales" in r.text
    assert "Sin habituales aún" in r.text


def test_regulars_lists_top_by_visit_count(client, session_factory, qseed):
    """Customers with 2+ recent sales appear, sorted desc by visit count."""
    from tests.factories import make_sellable
    with session_factory() as s:
        product = make_sellable(s)
        alice = _make_customer(s, "Alice-3visits")
        bob = _make_customer(s, "Bob-2visits")
        # Alice: 3 sales
        for _ in range(3):
            _make_sale(s, alice.id, product_id=product.id)
        # Bob: 2 sales
        for _ in range(2):
            _make_sale(s, bob.id, product_id=product.id)
        s.commit()
    r = client.get("/")
    assert r.status_code == 200
    # Both names appear
    assert "Alice-3visits" in r.text
    assert "Bob-2visits" in r.text
    # Visit count text: "3 visitas" / "2 visitas"
    assert "3 visitas" in r.text
    assert "2 visitas" in r.text


def test_regulars_excludes_one_time_buyers(client, session_factory, qseed):
    """Customers with only 1 sale in 30d are NOT regulars."""
    from tests.factories import make_sellable
    with session_factory() as s:
        product = make_sellable(s)
        regular = _make_customer(s, "RegularPerson")
        occasional = _make_customer(s, "OccasionalPerson")
        # Regular: 2 sales
        _make_sale(s, regular.id, product_id=product.id)
        _make_sale(s, regular.id, product_id=product.id)
        # Occasional: 1 sale only
        _make_sale(s, occasional.id, product_id=product.id)
        s.commit()
    r = client.get("/")
    assert r.status_code == 200
    assert "RegularPerson" in r.text
    assert "OccasionalPerson" not in r.text


def test_regulars_excludes_old_sales(client, session_factory, qseed):
    """Sales older than 30 days don't count toward 'regular' status."""
    from tests.factories import make_sellable
    with session_factory() as s:
        product = make_sellable(s)
        stale = _make_customer(s, "StaleCustomer")
        # 5 sales but all 60+ days old
        for _ in range(5):
            _make_sale(
                s, stale.id, product_id=product.id,
                when=datetime.now(timezone.utc) - timedelta(days=60),
            )
        s.commit()
    r = client.get("/")
    assert r.status_code == 200
    assert "StaleCustomer" not in r.text


def test_regulars_excludes_voided_sales(client, session_factory, qseed):
    """Voided sales don't count."""
    from tests.factories import make_sellable
    with session_factory() as s:
        product = make_sellable(s)
        cancelled = _make_customer(s, "CancelledCustomer")
        # 3 sales but all voided
        for _ in range(3):
            sale = Sale(
                customer_id=cancelled.id, product_id=product.id, qty=1.0,
                unit_price_gs=10000, sold_at=datetime.now(timezone.utc),
                voided_at=datetime.now(timezone.utc),
            )
            s.add(sale)
        s.commit()
    r = client.get("/")
    assert r.status_code == 200
    assert "CancelledCustomer" not in r.text


def test_regulars_links_to_customer_profile(client, session_factory, qseed):
    """Each regular row is a link to /clientes/{id}."""
    from tests.factories import make_sellable
    with session_factory() as s:
        product = make_sellable(s)
        c = _make_customer(s, "ClickableCustomer")
        for _ in range(2):
            _make_sale(s, c.id, product_id=product.id)
        s.commit()
    r = client.get("/")
    assert r.status_code == 200
    assert 'href="/clientes/' in r.text
    assert "ClickableCustomer" in r.text
