"""Tests for T-3: pedido board shows customer phone + click-to-detail link.

The pedido board (/pedidos/board) renders one card per active pedido. T-3:
- Add customer phone to each card (linked via tel:)
- Add an "Abrir" link to /pedidos/{id} so the whole card navigates to pedido detail.
"""

from datetime import date, timedelta

from app.rms.models import Customer, Pedido


def _seed_pedido_with_customer(session_factory):
    """Insert one pending pedido with a customer that has a phone."""
    from app.rms.models import PedidoLine, Product

    sf = session_factory
    with sf() as s:
        cust = Customer(
            name="Test Board",
            phone="0981-555-010",
        )
        s.add(cust)
        s.flush()
        p = Product(name="BoardTestProd", sale_price_gs=15000)
        s.add(p)
        s.flush()
        ped = Pedido(
            customer_id=cust.id,
            customer_name=cust.name,
            customer_phone=cust.phone,
            promised_date=date.today() + timedelta(days=1),
            promised_time="14:00",
            status="pending",
        )
        s.add(ped)
        s.flush()
        s.add(PedidoLine(pedido_id=ped.id, product_id=p.id, qty=1, unit_price_gs=15000))
        s.commit()
        return ped.id, cust.phone


def test_pedido_board_renders_customer_phone(client, session_factory):
    """T-3 — pedido with customer.phone must show the phone in the board card."""
    _pid, phone = _seed_pedido_with_customer(session_factory)
    r = client.get("/pedidos/board")
    assert r.status_code == 200
    assert phone in r.text, f"phone {phone!r} missing from /pedidos/board"
    assert 'href="tel:' in r.text, "tel: link missing from /pedidos/board"


def test_pedido_board_has_click_to_detail_link(client, session_factory):
    """T-3 — each pedido card must have an 'Abrir' anchor to /pedidos/{id}."""
    pid, _ = _seed_pedido_with_customer(session_factory)
    r = client.get("/pedidos/board")
    assert r.status_code == 200
    assert f'href="/pedidos/{pid}"' in r.text, f"click-to-detail link missing for pedido {pid}"
    # The Abrir text is in the new card-open-link element.
    assert "Abrir" in r.text, "Abrir text missing from /pedidos/board"


def test_pedido_board_no_phone_does_not_break(client, session_factory):
    """T-3 — pedido without customer.phone should render the card without phone block."""
    from app.rms.models import PedidoLine, Product

    sf = session_factory
    with sf() as s:
        p = Product(name="BoardNoPhone", sale_price_gs=10000)
        s.add(p)
        s.flush()
        ped = Pedido(
            customer_name="Walk-in",
            customer_phone=None,
            promised_date=date.today(),
            status="pending",
        )
        s.add(ped)
        s.flush()
        s.add(PedidoLine(pedido_id=ped.id, product_id=p.id, qty=1, unit_price_gs=10000))
        s.commit()
    r = client.get("/pedidos/board")
    assert r.status_code == 200
    # Card still renders the click-to-detail even without customer.phone.
    assert 'href="/pedidos/' in r.text
    # No tel: link for this card.
    body = r.text
    assert body.count("tel:") == 0 or all("BoardNoPhone" not in seg for seg in body.split("tel:"))
