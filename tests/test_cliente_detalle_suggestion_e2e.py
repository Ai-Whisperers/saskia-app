"""End-to-end test: when an operator submits the suggestion-CTA form
on /clientes/{id}, the loyalty ledger gets a row with the REAL kind
(no longer 'unknown').

This is the test that would have caught the content-type bug if it
had existed when the suggestion-CTA feature shipped.
"""

from __future__ import annotations

import sqlalchemy

from app.rms.models import Customer, LoyaltyTransaction


def _kyrian_seed(session_factory):
    """Seed a customer with enough state to render the page."""
    from tests.factories import make_customer

    with session_factory() as s:
        c = make_customer(s, name="E2ESuggestion", phone="0983334455")
        s.commit()
        return c.id


def test_suggestion_form_post_writes_real_kind_in_ledger(client, qseed, session_factory):
    """T-2026-10-01: the form-encoded POST from /clientes/{id} now
    writes kind='cumple', not 'unknown'."""
    qseed("with_kyrian_full")

    # Find Kyrian
    with session_factory() as s:
        cid = s.execute(sqlalchemy.select(Customer.id)).scalar_one()
        s.expunge_all()

    # Operator taps "Aplicar sugerencia" — form submits with these
    # hidden inputs. The handler reads them via request.form() now.
    r = client.post(
        f"/clientes/api/{cid}/suggestion-applied",
        data={
            "kind": "cumple",
            "discount_pct": "15",
            "_csrf_token": "x",
        },
        # No headers — TestClient defaults to application/x-www-form-urlencoded
    )
    assert r.status_code == 200, r.text[:300]

    with session_factory() as s:
        rows = (
            s.execute(
                sqlalchemy.select(LoyaltyTransaction)
                .where(LoyaltyTransaction.customer_id == cid)
                .where(LoyaltyTransaction.reason == "suggestion_applied")
                .where(LoyaltyTransaction.notes.like("%cumple%"))
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1, f"expected 1 kind=cumple row, got {len(rows)}"
        assert "kind=cumple" in rows[0].notes
        assert "pct=15" in rows[0].notes


def test_suggestion_form_post_with_no_kind_logs_unknown(client, qseed, session_factory):
    """T-2026-10-01: missing/empty kind falls back to 'unknown' so a
    misconfigured form never crashes the telemetry endpoint."""
    qseed("with_kyrian_full")
    with session_factory() as s:
        cid = s.execute(sqlalchemy.select(Customer.id)).scalar_one()
        s.expunge_all()

    r = client.post(
        f"/clientes/api/{cid}/suggestion-applied",
        data={"_csrf_token": "x"},
    )
    assert r.status_code == 200

    with session_factory() as s:
        latest = (
            s.execute(
                sqlalchemy.select(LoyaltyTransaction)
                .where(LoyaltyTransaction.customer_id == cid)
                .where(LoyaltyTransaction.reason == "suggestion_applied")
                .order_by(LoyaltyTransaction.id.desc())
            )
            .scalars()
            .first()
        )
        assert latest is not None
        assert "kind=unknown" in (latest.notes or "")
