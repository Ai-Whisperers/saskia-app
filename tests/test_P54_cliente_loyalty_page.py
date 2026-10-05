"""P5: /clientes/{id}/loyalty shows the full ledger (not capped at 5).

P4.1's 'Ver todo (N)' link points to this page. The route must
return 200, render all N transactions (no cap), and link back to
the customer detail page so the operator can return to the main view.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.rms.models import LoyaltyTransaction
from tests.factories import make_customer


def test_cliente_loyalty_page_renders_full_ledger(client, session_factory):
    """P5: full loyalty ledger view (no 5-cap)."""
    s = session_factory()
    try:
        cust = make_customer(s, name=f"loyalty-page-{uuid.uuid4().hex[:6]}")
        now = datetime.now(timezone.utc)
        # Create 12 transactions to exceed the 5-cap.
        for i in range(12):
            s.add(LoyaltyTransaction(
                customer_id=cust.id,
                delta=10 if i % 2 == 0 else -5,
                reason="earn_sale" if i % 2 == 0 else "redeem",
                recorded_at=now - timedelta(hours=i),
            ))
        s.commit()
        cid = cust.id
    finally:
        s.close()

    r = client.get(f"/clientes/{cid}/loyalty")
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:200]}"
    body = r.text

    # The body has a table row per transaction. Counting the rendered
    # delta strings is brittle (CSS classes / empty-state text may
    # contain the substring), so instead we check that the table has
    # at least 12 <tr> elements in <tbody>.
    import re as _re
    tbody_match = _re.search(r"<tbody>(.*?)</tbody>", body, _re.DOTALL)
    assert tbody_match, "expected a <tbody> in the page"
    row_count = len(_re.findall(r"<tr", tbody_match.group(1)))
    assert row_count >= 12, f"expected >= 12 transaction rows; got {row_count}"

    # Link back to the customer detail page.
    assert f'href="/clientes/{cid}"' in body, "expected back-link to /clientes/{id}"


def test_cliente_loyalty_page_empty_state(client, session_factory):
    """P5: empty state when the customer has no transactions."""
    s = session_factory()
    try:
        cust = make_customer(s, name=f"loyalty-empty-{uuid.uuid4().hex[:6]}")
        s.commit()
        cid = cust.id
    finally:
        s.close()

    r = client.get(f"/clientes/{cid}/loyalty")
    assert r.status_code == 200
    body = r.text
    # No transactions rendered; an empty-state hint must be present.
    assert "+10" not in body, "should not have any +10 entries"
    # Empty-state message.
    assert "Sin movimientos" in body or "vacío" in body.lower() or "aún" in body.lower(), (
        "expected empty-state message when no transactions exist"
    )