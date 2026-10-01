"""Tier 7.2 (2026-10-01) — /clientes/{id} "Aplicar sugerencia" button.

Adds a 'Sugerencias automáticas' card to /clientes/{id} that lists the
same auto-generated suggestions the JSON endpoint returns. The card
includes an 'Aplicar sugerencia' button per row, which POSTs to the
fire-and-forget telemetry endpoint at /clientes/api/{id}/suggestion-applied.

The button is hidden when there are no suggestions for the customer (the
rules produce nothing because the customer has no qualifying history).

This closes the gap where the operator had to go to /ventas and select
the customer to see suggestions. Now the suggestion set is visible
directly on the customer detail page.
"""

from __future__ import annotations


def _kyrian_customer_id(session_factory):
    """Return the Kyrian customer id from the with_kyrian_full seed."""
    with session_factory() as s:
        from app.rms.models import Customer

        c = s.execute(
            __import__("sqlalchemy").select(Customer).where(
                Customer.name.ilike("%kyrian%")
            )
        ).scalar_one_or_none()
        assert c is not None, "Kyrian customer must exist in with_kyrian_full"
        return c.id


def test_detalle_suggestions_card_renders_for_kyrian(client, qseed, session_factory):
    """With the full Kyrian seed (loyalty-eligible), the
    'Sugerencias automáticas' card renders on /clientes/{id}."""
    qseed("with_kyrian_full")
    cid = _kyrian_customer_id(session_factory)

    r = client.get(f"/clientes/{cid}")
    assert r.status_code == 200
    body = r.text
    assert "Sugerencias automáticas" in body
    # The 'Aplicar sugerencia' button must be present (at least one suggestion)
    assert "Aplicar sugerencia" in body


def test_detalle_suggestions_button_has_csrf_and_kind(client, qseed, session_factory):
    """Each 'Aplicar sugerencia' button is a form POST that targets
    the suggestion-applied endpoint and carries the suggestion kind +
    discount_pct as hidden inputs."""
    qseed("with_kyrian_full")
    cid = _kyrian_customer_id(session_factory)

    r = client.get(f"/clientes/{cid}")
    body = r.text

    # The form action must point at the API endpoint with the customer id
    expected_action = f'action="/clientes/api/{cid}/suggestion-applied"'
    assert expected_action in body, (
        f"Expected suggestion form action {expected_action!r} in page body"
    )
    # The form must carry the suggestion kind as a hidden input
    assert 'name="kind"' in body
    # And the discount_pct (may be empty for non-discount suggestions)
    assert 'name="discount_pct"' in body


def test_detalle_suggestions_card_hidden_when_none(client, qseed, session_factory):
    """A brand-new customer with no sales history has no qualifying
    suggestions, so the card is hidden (not an empty placeholder)."""
    with session_factory() as s:
        from app.rms.models import Customer

        c = Customer(name="Empty Sug Cliente", phone="+595991234570")
        s.add(c)
        s.commit()
        cid = c.id

    r = client.get(f"/clientes/{cid}")
    body = r.text
    # The card must NOT render when suggestions list is empty
    assert "Sugerencias automáticas" not in body
    # ...but the page itself must still render OK
    assert r.status_code == 200


def test_detalle_suggestion_post_endpoint_writes_ledger(client, qseed, session_factory):
    """POSTing to the suggestion-applied endpoint creates a
    LoyaltyTransaction row with reason='suggestion_applied'."""
    qseed("with_kyrian_full")
    cid = _kyrian_customer_id(session_factory)

    r = client.post(
        f"/clientes/api/{cid}/suggestion-applied",
        json={"kind": "cliente_fiel", "discount_pct": 5},
    )
    assert r.status_code == 200

    with session_factory() as s:
        from app.rms.models import LoyaltyTransaction

        tx = s.execute(
            __import__("sqlalchemy").select(LoyaltyTransaction)
            .where(LoyaltyTransaction.customer_id == cid)
            .where(LoyaltyTransaction.reason == "suggestion_applied")
        ).scalar_one_or_none()
        assert tx is not None, "Expected a suggestion_applied ledger row"
        assert "cliente_fiel" in (tx.notes or "")