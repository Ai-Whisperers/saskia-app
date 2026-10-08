"""# allow-hardcoded-dates: fixtures intentionally pin fixed dates (calendar edges, tz math, far-future sentinels); asserted relative to frozen or explicit anchors.
BACKLOG #27 (2026-10-01) — Sale.tz breakdown on /clientes/{id}.

Sale.tz is recorded for every sale but the column was never queried
on the cliente detail page. We expose a tz breakdown (most-used tz
first) for fraud-spotting and multi-location migration planning.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.rms.models import Customer, Product, Sale


@pytest.fixture
def tz_breakdown_customer(session_factory) -> int:
    """Create a customer with 4 sales across 2 timezones.

    3 sales in America/Asuncion (the default), 1 in America/Argentina/Buenos_Aires.
    """
    with session_factory() as s:  # type: Session
        cust = Customer(
            name="Tz Test Customer",
            phone="+595****0001",
            loyalty_points=0,
        )
        s.add(cust)
        s.flush()
        prod = Product(name="Tz Test Bread", sale_price_gs=10000)
        s.add(prod)
        s.flush()
        for i in range(3):
            s.add(
                Sale(
                    customer_id=cust.id,
                    product_id=prod.id,
                    qty=1,
                    unit_price_gs=10000,
                    tz="America/Asuncion",
                    sold_at=datetime(2026, 9, 1, 10 + i, 0),
                    channel="mostrador",
                )
            )
        s.add(
            Sale(
                customer_id=cust.id,
                product_id=prod.id,
                qty=2,
                unit_price_gs=10000,
                tz="America/Argentina/Buenos_Aires",
                sold_at=datetime(2026, 9, 5, 14, 0),
                channel="mostrador",
            )
        )
        s.commit()
        return cust.id


def test_cliente_detalle_renders_tz_breakdown(client, tz_breakdown_customer) -> None:
    """/clientes/{id} renders the Sale.tz breakdown with both timezones visible."""
    resp = client.get(f"/clientes/{tz_breakdown_customer}")
    assert resp.status_code == 200
    body = resp.text
    # Both timezones present
    assert "America/Asuncion" in body, "expected America/Asuncion in tz table"
    assert "America/Argentina/Buenos_Aires" in body, (
        "expected America/Argentina/Buenos_Aires in tz table"
    )
    # Heading visible
    assert "Zonas de compra" in body, "expected the 'Zonas de compra' section heading"


def test_tz_breakdown_sorted_most_used_first(client, tz_breakdown_customer) -> None:
    """The breakdown orders timezones by sales count DESC."""
    resp = client.get(f"/clientes/{tz_breakdown_customer}")
    body = resp.text
    # Asuncion (3 sales) should appear BEFORE Buenos_Aires (1 sale)
    idx_Asuncion = body.find("America/Asuncion")
    idx_ba = body.find("America/Argentina/Buenos_Aires")
    assert idx_Asuncion < idx_ba, (
        f"Asuncion (3 sales) must sort before Buenos_Aires (1 sale); "
        f"Asuncion idx={idx_Asuncion}, BA idx={idx_ba}"
    )


def test_cliente_with_no_sales_omits_tz_breakdown(client, session_factory) -> None:
    """A customer with no sales → no tz_breakdown section rendered."""
    from app.rms.models import Customer

    with session_factory() as s:
        cust = Customer(name="Empty Cust", phone="+595****0002")
        s.add(cust)
        s.commit()
        cust_id = cust.id
    resp = client.get(f"/clientes/{cust_id}")
    assert resp.status_code == 200
    assert "Zonas de compra" not in resp.text, (
        "Empty customer must NOT render the tz breakdown section"
    )
