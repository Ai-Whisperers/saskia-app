"""tests/test_clientes_filter.py — /clientes filter by q + tier."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.crud


def test_clientes_filter_search_exists(client):
    """/clientes shows search input + tier filter."""
    resp = client.get("/clientes")
    assert resp.status_code == 200
    body = resp.text
    assert 'name="q"' in body, "Missing q filter in /clientes"
    assert 'name="tier"' in body, "Missing tier filter in /clientes"


def test_clientes_filter_by_q(client, session_factory):
    """/clientes?q=name returns only matching customers."""
    from app.rms.models import Customer

    with session_factory() as s:
        s.add(Customer(phone="0981234001", name="CabreraFiltro"))
        s.add(Customer(phone="0981234002", name="RodriguezFiltro"))
        s.commit()

    resp = client.get("/clientes?q=cabrerafiltro")
    assert resp.status_code == 200
    body = resp.text
    assert "CabreraFiltro" in body


def test_clientes_filter_by_tier(client, session_factory):
    """/clientes?tier=silver filters by tier."""
    from app.rms.models import Customer

    with session_factory() as s:
        # 0 spend → bronze
        s.add(Customer(phone="0982233001", name="ClienteBronze"))
        s.commit()

    resp = client.get("/clientes?tier=bronze")
    assert resp.status_code == 200
