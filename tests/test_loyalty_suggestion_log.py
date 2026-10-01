"""tests/test_loyalty_suggestion_log.py — Tier 3.2.

Pin the contract: when the cashier taps a suggestion, a
LoyaltyTransaction(reason='suggestion_applied') row is appended.
The endpoint is fire-and-forget from the JS — failure should NEVER
crash the picker UX.

Tests:
  - happy path: 200 + ledger row with reason='suggestion_applied'
  - notes carry the suggestion kind + pct for analytics
  - 404 when customer doesn't exist (no crash)
  - empty payload still logs (kind=unknown fallback)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest


def test_suggestion_applied_writes_ledger_row(client, session_factory):
    """Happy path: POST logs a suggestion_applied row."""
    from app.rms.models import Customer, LoyaltyTransaction
    from sqlalchemy import select as _sa_select

    with session_factory() as s:
        c = Customer(name="Test Cust", phone="0981123456", loyalty_points=50)
        s.add(c)
        s.commit()
        cid = c.id
    r = client.post(
        f"/clientes/api/{cid}/suggestion-applied",
        json={"kind": "cumple_cerca", "discount_pct": 15},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    body = r.json()
    assert body.get("ok") is True
    with session_factory() as s2:
        rows = s2.scalars(
            _sa_select(LoyaltyTransaction)
            .where(LoyaltyTransaction.customer_id == cid)
        ).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.reason == "suggestion_applied"
    assert row.delta == 0  # no balance change
    assert "cumple_cerca" in row.notes
    assert "pct=15" in row.notes


def test_suggestion_applied_404_when_customer_missing(client, session_factory):
    """Stale picker → 404, no crash."""
    r = client.post(
        "/clientes/api/99999/suggestion-applied",
        json={"kind": "cumple_cerca"},
    )
    assert r.status_code == 404
    assert r.json().get("error") == "not_found"


def test_suggestion_applied_does_not_crash_on_bad_payload(
    client, session_factory
):
    """Empty payload → still 200, falls back to defaults (kind=unknown)."""
    from app.rms.models import Customer, LoyaltyTransaction
    from sqlalchemy import select as _sa_select

    with session_factory() as s:
        c = Customer(name="Test Cust 2", phone="0981567890", loyalty_points=0)
        s.add(c)
        s.commit()
        cid = c.id
    r = client.post(
        f"/clientes/api/{cid}/suggestion-applied",
        json={},
    )
    assert r.status_code == 200
    with session_factory() as s2:
        rows = s2.scalars(
            _sa_select(LoyaltyTransaction)
            .where(LoyaltyTransaction.customer_id == cid)
        ).all()
    assert len(rows) == 1
    assert rows[0].reason == "suggestion_applied"
    assert "kind=unknown" in rows[0].notes
