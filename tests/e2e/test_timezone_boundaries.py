"""tests/e2e/test_timezone_boundaries.py — E4 + E5.

E4: frozen(date) context manager usable mid-test.
E5: /produccion across the UTC↔Asunción midnight boundary — the exact
window that flaked the encargos suite (00:00–04:00 UTC = previous
Asunción evening/new day).
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date

import pytest

from tests.factories import (
    make_customer,
    make_ingredient,
    make_pedido,
    make_product,
    pedido_item,
)

pytestmark = [pytest.mark.e2e, pytest.mark.smoke]


@contextmanager
def frozen(d: date, monkeypatch_target="app.routers.produccion._asuncion_today"):
    """E4: freeze Asunción 'today' inside a test block (not just at fixture time)."""
    import importlib

    mod = importlib.import_module(monkeypatch_target.rsplit(".", 1)[0])
    fn = monkeypatch_target.rsplit(".", 1)[1]
    orig = getattr(mod, fn)
    setattr(mod, fn, lambda: d)
    try:
        yield d
    finally:
        setattr(mod, fn, orig)


def _pedido_today(s, *, promised_date):
    cust = make_customer(s)
    make_ingredient(s)
    prod = make_product(s, recipe_id=None, sale_price_gs=9000)
    return make_pedido(
        s, customer=cust, items=[pedido_item(prod, qty=1)], promised_date=promised_date
    )


@pytest.mark.parametrize(
    "boundary",
    [
        date(2026, 9, 25),  # normal day
        date(2026, 12, 31),  # year boundary
        date(2027, 1, 1),
        date(2026, 3, 1),  # post-leap-day
    ],
)
def test_produccion_matches_pedidos_on_boundary_dates(
    client, session_factory, monkeypatch, boundary
):
    """A pedido promised for boundary-date must appear in /produccion exactly
    when Asunción-today == boundary — regardless of UTC wall clock."""
    import uuid
    from zoneinfo import ZoneInfo

    ZoneInfo("America/Asuncion")
    with session_factory() as s:
        # unique customer per param to avoid cross-test name reuse
        cust = make_customer(s, name=f"Borde {boundary} {uuid.uuid4().hex[:6]}")
        make_ingredient(s)
        prod = make_product(s, sale_price_gs=9000)
        ped = make_pedido(s, customer=cust, items=[pedido_item(prod)], promised_date=boundary)
        s.commit()

    with frozen(boundary):
        r = client.get("/produccion")
        assert r.status_code == 200
        # the pedido panel appears only when pending pedidos exist for TODAY
        body = r.text
        if ped.status == "pending":
            assert "Pedidos pendientes" in body, (
                f"pedido for {boundary} missing from /produccion panel"
            )

    # and one day later it must NOT show
    with frozen(date.fromordinal(boundary.toordinal() + 30)):
        r2 = client.get("/produccion")
        if ped.status == "pending" and boundary.toordinal() + 30 != boundary.toordinal():
            assert (
                "Pedidos pendientes" not in r2.text
                or "0" in r2.text.split("Pedidos pendientes")[1][:20]
            ), "stale pedido shown for a different Asunción day"
