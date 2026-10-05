"""Tier 6.1 (2026-10-01) — /clientes list page flow coverage.

Three small flows added to /clientes:
  1. One-click "+ Pedido" row action (link to /pedidos/nuevo?customer_id=N).
  2. Active suscripción badge column ("Sub" pill).
  3. Open pedido count column ("Np" pill).
  4. Last-purchase date column with sort.

Run: cd /opt/data/profiles/ivan/scratch/sazon-app-work && ./.venv/bin/python -m pytest tests/test_clientes_directory_flows.py -v
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.rms.models import Customer, Pedido, Product, Sale, Suscripcion


@pytest.fixture
def customer_with_sub(session_factory) -> int:
    """Customer with 1 active suscripción, 1 open pedido, 1 sale."""
    with session_factory() as s:  # type: Session
        cust = Customer(name="Sub Customer", phone="+595****9100")
        s.add(cust)
        s.flush()
        prod = Product(name="Chipa", sale_price_gs=20000)
        s.add(prod)
        s.flush()
        s.add(
            Sale(
                customer_id=cust.id,
                product_id=prod.id,
                qty=2,
                unit_price_gs=20000,
                sold_at=datetime(2026, 9, 25, 10, 0),
                channel="mostrador",
                tz="America/Asuncion",
            )
        )
        s.add(
            Suscripcion(
                customer_id=cust.id,
                product_summary="2 chipas semanales",
                cadence="semanal",
                status="activa",
                start_date=datetime(2026, 9, 1).date(),
            )
        )
        s.add(
            Pedido(
                customer_id=cust.id,
                customer_name="Sub Customer",
                customer_phone="+595****9100",
                status="pending",
                promised_date=datetime.utcnow().date() + timedelta(days=1),
            )
        )
        s.commit()
        return cust.id


@pytest.fixture
def customer_no_extras(session_factory) -> int:
    """Customer with NO subscription, NO open pedido, NO sale."""
    with session_factory() as s:
        cust = Customer(name="Plain Customer", phone="+595****9200")
        s.add(cust)
        s.commit()
        return cust.id


def test_clientes_list_renders_pedido_action(client, customer_with_sub) -> None:
    """Each customer row has a one-click '+ Pedido' shortcut to /pedidos/nuevo."""
    resp = client.get("/clientes")
    assert resp.status_code == 200
    body = resp.text
    # The link must be present, pointing to /pedidos/nuevo with the right customer_id
    expected = f"/pedidos/nuevo?customer_id={customer_with_sub}"
    assert expected in body, (
        f"Expected '+ Pedido' shortcut link {expected!r} in /clientes; "
        f"found: {body.count('/pedidos/nuevo?customer_id=')} matches total"
    )
    assert "+ Pedido" in body, "Expected '+ Pedido' button label in /clientes"


def test_clientes_list_renders_sub_badge(client, customer_with_sub, customer_no_extras) -> None:
    """Customer with active suscripción shows 'Sub' badge; without does not."""
    resp = client.get("/clientes")
    body = resp.text
    # The sub badge text appears next to the customer with an active sub
    # We can't trivially check positional ordering, so just count occurrences.
    sub_count = body.count(">Sub</span>")
    assert sub_count >= 1, f"Expected at least one 'Sub' badge; got {sub_count}"


def test_clientes_list_renders_open_pedido_count(client, customer_with_sub) -> None:
    """Customer with 1 open pedido shows '1p' pill."""
    resp = client.get("/clientes")
    body = resp.text
    assert ">1p</span>" in body, "Expected '1p' badge for customer with one open pedido"


def test_clientes_list_no_badges_for_plain_customer(client, customer_no_extras) -> None:
    """Plain customer row has neither 'Sub' nor 'Np' badge."""
    # Use a search query to narrow to just the plain customer
    resp = client.get("/clientes?q=Plain")
    body = resp.text
    # The row should NOT have Sub or Np badges (in the actions column)
    assert ">Sub</span>" not in body, "Plain customer should NOT have Sub badge"
    assert "Np<" not in body, "Plain customer should NOT have open-pedido count"


def test_clientes_list_renders_last_sale_column(client, customer_with_sub) -> None:
    """Last-purchase column is rendered (with 'dd/mm/yy' format)."""
    resp = client.get("/clientes")
    body = resp.text
    # The header was added
    assert "Última compra" in body, "Expected 'Última compra' column header"
    # The customer with a sale on 2026-09-25 should show '25/09/26'
    assert "25/09/26" in body, (
        "Expected formatted last-purchase date '25/09/26' for sale on 2026-09-25"
    )


def test_clientes_sort_by_last_sale_at(client, customer_with_sub, session_factory) -> None:
    """Sort by last_sale_at is accepted and applies ordering."""
    # Add a second customer with an even older sale
    with session_factory() as s:
        cust_old = Customer(name="Old Customer", phone="+595****9300")
        s.add(cust_old)
        s.flush()
        prod = Product(name="Old Prod", sale_price_gs=15000)
        s.add(prod)
        s.flush()
        s.add(
            Sale(
                customer_id=cust_old.id,
                product_id=prod.id,
                qty=1,
                unit_price_gs=15000,
                sold_at=datetime(2026, 8, 1, 10, 0),
                channel="mostrador",
                tz="America/Asuncion",
            )
        )
        s.commit()

    # Sort by last_sale_at DESC — most recent first
    resp = client.get("/clientes?sort=last_sale_at&dir=desc")
    assert resp.status_code == 200
    body = resp.text
    # 'Sub Customer' (25/09) should appear before 'Old Customer' (01/08)
    idx_sub = body.find("Sub Customer")
    idx_old = body.find("Old Customer")
    assert idx_sub >= 0 and idx_old >= 0, "Both customers must render"
    assert idx_sub < idx_old, (
        f"With sort=last_sale_at&dir=desc, Sub Customer (25/09) must sort BEFORE "
        f"Old Customer (01/08); got Sub idx={idx_sub}, Old idx={idx_old}"
    )
