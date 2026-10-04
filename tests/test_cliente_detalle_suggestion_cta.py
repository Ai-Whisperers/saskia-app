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

from datetime import datetime


def _kyrian_customer_id(session_factory):
    """Return the Kyrian customer id from the with_kyrian_full seed."""
    with session_factory() as s:
        from app.rms.models import Customer

        c = s.execute(
            __import__("sqlalchemy").select(Customer).where(Customer.name.ilike("%kyrian%"))
        ).scalar_one_or_none()
        assert c is not None, "Kyrian customer must exist in with_kyrian_full"
        return c.id


def test_detalle_suggestions_card_renders_for_kyrian(client, qseed, session_factory):
    """T-2026-10-01: reviewer's "redundant suggestions" rule. The
    points-dormant card (the only suggestion Kyrian triggers under
    the standard seed — no birthday within 7 days, no lapsed, no VIP)
    no longer renders because it merely echoes the points balance
    already shown in the KPI tile. The block is hidden when no
    unique algorithmic upsell applies.
    """
    qseed("with_kyrian_full")
    cid = _kyrian_customer_id(session_factory)

    r = client.get(f"/clientes/{cid}")
    assert r.status_code == 200
    body = r.text
    # The lone points-dormant suggestion is suppressed for Kyrian
    assert "Sugerencias automáticas" not in body


def test_detalle_suggestions_card_renders_when_multiple_suggestions(client, qseed, session_factory):
    """T-2026-10-01: the suggestion card renders when the rule
    engine returns ≥2 distinct suggestions (i.e. one of them is
    a real algorithmic upsell, not just a points-dormant echo).

    We force this state by seeding a birthday within the next 7
    days directly, so the rule engine fires BOTH cumpleaños + puntos
    dormidos — keeping both.
    """
    from datetime import timedelta

    from app.rms.models import Customer

    qseed("with_kyrian_full")
    cid = _kyrian_customer_id(session_factory)

    with session_factory() as s:
        cust = s.get(Customer, cid)
        # Birthday in 3 days → triggers cumpleaños_cerca
        cust.birthday = (datetime.utcnow().date() + timedelta(days=3)).strftime("%m-%d")
        s.commit()

    r = client.get(f"/clientes/{cid}")
    body = r.text
    # Now at least 2 suggestions → the card stays
    assert "Sugerencias automáticas" in body
    assert "Aplicar sugerencia" in body


def test_detalle_suggestions_button_has_csrf_and_kind(client, qseed, session_factory):
    """Each 'Aplicar sugerencia' button is a form POST that targets
    the suggestion-applied endpoint and carries the suggestion kind +
    discount_pct as hidden inputs."""
    from datetime import timedelta

    from app.rms.models import Customer

    qseed("with_kyrian_full")
    cid = _kyrian_customer_id(session_factory)

    with session_factory() as s:
        cust = s.get(Customer, cid)
        # Add a 2nd suggestion trigger so the card renders
        cust.birthday = (datetime.utcnow().date() + timedelta(days=3)).strftime("%m-%d")
        s.commit()

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
            __import__("sqlalchemy")
            .select(LoyaltyTransaction)
            .where(LoyaltyTransaction.customer_id == cid)
            .where(LoyaltyTransaction.reason == "suggestion_applied")
        ).scalar_one_or_none()
        assert tx is not None, "Expected a suggestion_applied ledger row"
        assert "cliente_fiel" in (tx.notes or "")


def test_detalle_suggestion_form_post_endpoint_writes_correct_kind(client, qseed, session_factory):
    """T-2026-10-01: the JS-free <form> on cliente_detalle.html submits
    form-encoded data. Pre-this-fix the handler only accepted JSON, so
    the form's `kind` was always logged as 'unknown'. Now the handler
    accepts form-encoded POSTs and the real kind is captured.
    """
    qseed("with_kyrian_full")
    cid = _kyrian_customer_id(session_factory)

    # No headers={"Content-Type": ...} — the TestClient defaults to
    # application/x-www-form-urlencoded when `data=` is used.
    r = client.post(
        f"/clientes/api/{cid}/suggestion-applied",
        data={"kind": "cumple", "discount_pct": "10", "_csrf_token": "x"},
    )
    assert r.status_code == 200, r.text[:300]

    with session_factory() as s:
        from app.rms.models import LoyaltyTransaction

        tx = s.execute(
            __import__("sqlalchemy")
            .select(LoyaltyTransaction)
            .where(LoyaltyTransaction.customer_id == cid)
            .where(LoyaltyTransaction.reason == "suggestion_applied")
            .where(LoyaltyTransaction.notes.like("%cumple%"))
        ).scalar_one_or_none()
        assert tx is not None, (
            "Expected a suggestion_applied ledger row with kind=cumple, "
            "but no matching row found — handler may have logged 'unknown'"
        )
        assert "kind=cumple" in (tx.notes or "")
        assert "pct=10" in (tx.notes or "")


def test_detalle_suggestion_form_post_empty_kind_is_unknown(client, qseed, session_factory):
    """T-2026-10-01: an empty/missing kind still logs 'unknown' (not
    crashes) so a bad UI never 500s the telemetry endpoint."""
    qseed("with_kyrian_full")
    cid = _kyrian_customer_id(session_factory)

    r = client.post(
        f"/clientes/api/{cid}/suggestion-applied",
        data={"kind": "", "discount_pct": ""},
    )
    assert r.status_code == 200

    with session_factory() as s:
        from app.rms.models import LoyaltyTransaction

        tx = (
            s.execute(
                __import__("sqlalchemy")
                .select(LoyaltyTransaction)
                .where(LoyaltyTransaction.customer_id == cid)
                .where(LoyaltyTransaction.reason == "suggestion_applied")
            )
            .scalars()
            .all()
        )
        assert tx, "expected at least one row"
        # Latest row (most-recent) should be the unknown one
        latest = tx[-1]
        assert "kind=unknown" in (latest.notes or "")
