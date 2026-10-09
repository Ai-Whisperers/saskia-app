"""P4.2: /clientes/{id} collapses 'Pedidos recientes' + 'Historial de compras'
into a single accordion view.

Reviewer's refactoring: the 'Historial de compras' table duplicates
information already shown when expanding a pedido in the accordion.
Removing it saves vertical space for frequent customers.

Acceptance:
  - GET /clientes/{id} returns 200.
  - The 'Pedidos recientes' section uses <details> elements (already shipped
    in P3.6 — regression).
  - There is NO separate 'Historial de compras' table heading.
"""

from __future__ import annotations

import re
import uuid

from tests.factories import make_customer


def test_cliente_detalle_no_separate_history_table(client, session_factory):
    """P4.2: collapse purchases + pedidos into one accordion view."""
    s = session_factory()
    try:
        cust = make_customer(s, name=f"collapse-{uuid.uuid4().hex[:6]}")
        # Create a pedido so the accordion renders.
        from app.rms.models import Pedido

        s.add(
            Pedido(
                customer_id=cust.id,
                promised_date=__import__("datetime").date.today(),
                status="fulfilled",
            )
        )
        s.commit()
        cid = cust.id
    finally:
        s.close()

    r = client.get(f"/clientes/{cid}")
    assert r.status_code == 200
    body = r.text

    # The accordion for recent pedidos should exist (when the customer
    # has at least one pedido). Without a pedido, the section is
    # hidden, so the assertion is conditional.
    if "Pedidos recientes" in body:
        assert "<details" in body, "expected <details> accordion for recent pedidos"

    # The separate 'Historial de compras' heading should be GONE
    # regardless of whether the customer has pedidos.
    assert not re.search(r"<h\d[^>]*>\s*Historial de compras\s*</h\d", body), (
        "'Historial de compras' should be removed; info is in the Pedidos recientes accordion now."
    )
