"""Tier 7.1 (2026-10-01) — /ventas/historial venta → pedido conversion.

Adds a 'Pedido' action button to each row in the ventas history table
when the sale:
  - has a customer (s.customer_id is not None)
  - is not voided

The button links to /pedidos/nuevo with customer_id + from_sale params
so /pedidos/nuevo can pre-fill the new pedido with the same customer +
a note describing the source sale.

Closes the gap where an operator had to manually copy a customer from a
sale into a pedido to escalate a one-off sale into a recurring order.
"""

from __future__ import annotations

import datetime as _dt


def _kyrian_customer_id(session_factory):
    """Return the Kyrian customer id from the with_kyrian_full seed."""
    with session_factory() as s:
        from app.rms.models import Customer

        c = s.execute(
            __import__("sqlalchemy").select(Customer).where(Customer.name.ilike("%kyrian%"))
        ).scalar_one_or_none()
        assert c is not None, "Kyrian customer must exist in with_kyrian_full"
        return c.id


def test_historial_renders_for_kyrian(client, qseed):
    """Sanity: /ventas/historial returns 200 with the seed data."""
    qseed("with_kyrian_full")
    r = client.get("/ventas/historial")
    assert r.status_code == 200


def test_historial_row_with_customer_has_pedido_btn(client, qseed, session_factory):
    """A non-voided sale with a customer shows a 'Pedido' button
    pointing at /pedidos/nuevo with customer_id + from_sale params."""
    qseed("with_kyrian_full")
    cid = _kyrian_customer_id(session_factory)
    # Find a non-voided sale for this customer
    with session_factory() as s:
        from app.rms.models import Sale

        sale = s.execute(
            __import__("sqlalchemy")
            .select(Sale)
            .where(Sale.customer_id == cid)
            .where(Sale.voided_at.is_(None))
            .limit(1)
        ).scalar_one_or_none()
        assert sale is not None
        sale_id = sale.id

    r = client.get("/ventas/historial")
    assert r.status_code == 200
    body = r.text
    # The conversion button must be present
    expected_href = f"/pedidos/nuevo?customer_id={cid}&from_sale={sale_id}"
    assert expected_href in body, (
        f"Expected conversion href {expected_href!r} somewhere in ventas.html"
    )


def test_historial_voided_sale_no_conversion_btn(client, qseed, session_factory):
    """A voided sale does NOT show the conversion button (even if it
    has a customer). Conversion is for active, real orders only."""
    qseed("with_kyrian_full")
    cid = _kyrian_customer_id(session_factory)
    # Void one of Kyrian's sales
    with session_factory() as s:
        from app.rms.models import Sale

        sale = s.execute(
            __import__("sqlalchemy")
            .select(Sale)
            .where(Sale.customer_id == cid)
            .where(Sale.voided_at.is_(None))
            .limit(1)
        ).scalar_one_or_none()
        assert sale is not None
        now = _dt.datetime.now(_dt.timezone.utc)
        s.execute(
            __import__("sqlalchemy")
            .update(Sale)
            .where(Sale.id == sale.id)
            .values(voided_at=now, void_reason="test void")
        )
        s.commit()
        sale_id = sale.id

    r = client.get("/ventas/historial")
    body = r.text
    bad_href = f'/pedidos/nuevo?customer_id={cid}&from_sale={sale_id}"'
    assert bad_href not in body, f"Voided sale {sale_id} should not have a conversion CTA"


def test_historial_cash_sale_no_conversion_btn(client, qseed, session_factory):
    """A sale with no customer (cash sale) does NOT show the conversion
    button — you can't create a pedido for a non-customer."""
    qseed("with_kyrian_full")
    # Create a cash sale with no customer
    with session_factory() as s:
        from app.rms.models import Product, Sale

        product = s.execute(__import__("sqlalchemy").select(Product).limit(1)).scalar_one_or_none()
        assert product is not None
        sale = Sale(
            product_id=product.id,
            qty=1,
            unit_price_gs=product.sale_price_gs,
            payment_method="efectivo",
            channel="mostrador",
            customer_id=None,
            sold_at=_dt.datetime.now(_dt.timezone.utc),
        )
        s.add(sale)
        s.commit()
        cash_sale_id = sale.id

    r = client.get("/ventas/historial")
    body = r.text
    # Cash sale has no customer_id, so no "from_sale=" link with it
    bad_href = f"from_sale={cash_sale_id}"
    assert bad_href not in body, (
        f"Cash sale {cash_sale_id} (no customer) should not show conversion"
    )
