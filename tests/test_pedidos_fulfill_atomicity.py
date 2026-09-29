"""Atomicity tests for pedido fulfillment.

Per SASKIA_TEST_PLAN.md §5 #12 — POST /pedidos/{id}/fulfill must atomically:
- Validate pedido is in fulfillable status
- Create Sale + SaleStockMove rows for each line
- Decrement ingredient stock
- Update pedido status to fulfilled
- Double-fulfill must return 4xx
"""
from __future__ import annotations

from datetime import date

from app.rms.models import Pedido, PedidoLine, Product, Sale


def test_pedidos_fulfill_creates_sale(authed_client, session_factory):
    """P2 #1: POST /pedidos/{id}/fulfill must create a Sale row."""

    with session_factory() as s:
        product = Product(
            name="Atomicity Pedido Product 1",
            portion_label="1 und",
            sale_price_gs=5000,
            is_available=True,
        )
        s.add(product)
        s.commit()
        s.refresh(product)

        pedido = Pedido(
            customer_name="Atomicity Customer 1",
            promised_date=date.today(),
            channel="mostrador",
            status="pending",
        )
        s.add(pedido)
        s.commit()
        s.refresh(pedido)

        line = PedidoLine(
            pedido_id=pedido.id,
            product_id=product.id,
            qty=2,
            unit_price_gs=5000,
        )
        s.add(line)
        s.commit()

        pedido_id = pedido.id

    r = authed_client.post(f"/pedidos/{pedido_id}/fulfill", follow_redirects=False)

    assert r.status_code in (200, 303), f"Fulfill returned {r.status_code}"

    with session_factory() as s:
        sales = s.execute(Sale.__table__.select()).fetchall()
        # At least one sale should now exist
        assert len(sales) >= 1, "Fulfill did not create Sale row"


def test_pedidos_double_fulfill_returns_409(authed_client, session_factory):
    """P2 #2: Second POST /pedidos/{id}/fulfill must return 409 (already fulfilled)."""

    with session_factory() as s:
        product = Product(
            name="Atomicity Pedido Product 2",
            portion_label="1 und",
            sale_price_gs=5000,
            is_available=True,
        )
        s.add(product)
        s.commit()
        s.refresh(product)

        pedido = Pedido(
            customer_name="Atomicity Customer 2",
            promised_date=date.today(),
            channel="mostrador",
            status="pending",
        )
        s.add(pedido)
        s.commit()
        s.refresh(pedido)

        line = PedidoLine(
            pedido_id=pedido.id,
            product_id=product.id,
            qty=1,
            unit_price_gs=5000,
        )
        s.add(line)
        s.commit()
        pedido_id = pedido.id

    # First fulfill
    r1 = authed_client.post(f"/pedidos/{pedido_id}/fulfill", follow_redirects=False)
    assert r1.status_code in (200, 303), f"First fulfill returned {r1.status_code}"

    # Second fulfill — must fail with 409 (already fulfilled)
    r2 = authed_client.post(f"/pedidos/{pedido_id}/fulfill", follow_redirects=False)
    assert r2.status_code == 409, (
        f"Second fulfill returned {r2.status_code}, expected 409. "
        f"Pedido is already fulfilled; double-fulfill should be blocked."
    )


def test_pedidos_fulfill_updates_status(authed_client, session_factory):
    """P2 #3: POST /pedidos/{id}/fulfill must update pedido.status to 'fulfilled'."""

    with session_factory() as s:
        product = Product(
            name="Atomicity Pedido Product 3",
            portion_label="1 und",
            sale_price_gs=5000,
            is_available=True,
        )
        s.add(product)
        s.commit()
        s.refresh(product)

        pedido = Pedido(
            customer_name="Atomicity Customer 3",
            promised_date=date.today(),
            channel="mostrador",
            status="confirmed",  # not pending - different starting state
        )
        s.add(pedido)
        s.commit()
        s.refresh(pedido)

        line = PedidoLine(
            pedido_id=pedido.id,
            product_id=product.id,
            qty=1,
            unit_price_gs=5000,
        )
        s.add(line)
        s.commit()
        pedido_id = pedido.id

    r = authed_client.post(f"/pedidos/{pedido_id}/fulfill", follow_redirects=False)
    assert r.status_code in (200, 303), f"Fulfill returned {r.status_code}"

    with session_factory() as s:
        pedido_after = s.get(Pedido, pedido_id)
        assert pedido_after.status == "fulfilled", (
            f"Pedido status not updated: {pedido_after.status}"
        )


def test_pedidos_fulfill_404_for_unknown(authed_client):
    """P2 #4: POST /pedidos/{unknown_id}/fulfill must return 404, not 500."""
    r = authed_client.post("/pedidos/9999999/fulfill", follow_redirects=False)
    assert r.status_code in (404, 422), (
        f"Unknown pedido fulfill returned {r.status_code}, expected 404"
    )
