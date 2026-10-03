"""Tier 2.3 (2026-10-01) — partial-refund + partial-points tests.

Context: saskia-rms currently has NO partial-refund endpoint. ``void_sale``
voids the whole sale and ``reverse_points_for_void`` reverses ALL earn
ledger rows tied to that sale. This is fine for the MVP (small shop,
simple register) but it means a partial return has to be done by:
  (a) voiding the original sale (full points reversal), then
  (b) creating a new sale for the items the customer keeps.

That's awkward for the cashier and historically error-prone. The test
below asserts the BEHAVIOR we ship today (full reversal) and verifies
the round-trip math holds under a multi-line sale scenario. When the
product team lands partial-refund (Phase 5+), this test will be
amended — for now it pins the contract.

Tests:
  - partial_void_reverses_entire_earn_for_sale: void → all earn rows gone.
  - partial_void_redeems_reversal_row_signed_negative: ledger writes a
    -X row in 'void_reversal', NOT a 'manual_adjust'.
  - partial_void_balance_round_trip: customer's loyalty_points ends up
    back at its pre-sale value after a void.
  - partial_void_with_redeem_in_same_sale: customer earned 30 pts +
    redeemed 20 pts; void reverses just the earn (30), not the
    redeem (the customer already GOT the 20 Gs. × 1.000 discount).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy import select as _sa_select
from sqlalchemy.orm import sessionmaker

# Headless test env: no .env, no printer, no cron.
os.environ.setdefault("SASKIA_ENV", "test")
os.environ.setdefault("RANDOM_SEED", "42")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.rms.customers import (
    award_points,
    redeem_points,
    reverse_points_for_void,
)
from app.rms.models import Base, Customer, LoyaltyTransaction


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _make_customer(session, name="Test Cust", balance=0):
    c = Customer(
        name=name,
        phone="0981123456",
        loyalty_points=balance,
    )
    session.add(c)
    session.flush()
    return c


def test_partial_void_reverses_entire_earn_for_sale(session):
    c = _make_customer(session)
    # Award on 30.000 Gs. sale (1 pt / 1.000 Gs. = 30 pts).
    award_points(session, c, total_gs=30_000, sale_id=1)
    session.commit()
    assert c.loyalty_points == 30

    reversed_pts = reverse_points_for_void(session, c, sale_id=1)
    session.commit()

    assert reversed_pts == 30, "full earn should be reversed in one shot"
    assert c.loyalty_points == 0, "balance should round-trip to pre-sale value"


def test_partial_void_redeems_reversal_row_signed_negative(session):
    c = _make_customer(session)
    # 15 pts earned.
    award_points(session, c, total_gs=15_000, sale_id=42)
    session.commit()

    reverse_points_for_void(session, c, sale_id=42)
    session.commit()

    rows = session.scalars(
        _sa_select(LoyaltyTransaction)
        .where(LoyaltyTransaction.sale_id == 42)
        .order_by(LoyaltyTransaction.id)
    ).all()
    reasons = [r.reason for r in rows]
    deltas = [r.delta for r in rows]

    assert reasons == ["earn_sale", "void_reversal"], (
        f"expected exactly earn_sale + void_reversal, got {reasons}"
    )
    assert deltas == [15, -15], (
        f"void_reversal delta must be the negation of earn, got {deltas}"
    )


def test_partial_void_balance_round_trip(session):
    """Earn 50 → void → balance returns to 0 (start). And again with
    starting balance of 100: should land at 100."""
    c1 = _make_customer(session, name="No-Balance")
    award_points(session, c1, total_gs=50_000, sale_id=1)
    session.commit()
    reverse_points_for_void(session, c1, sale_id=1)
    session.commit()
    assert c1.loyalty_points == 0

    c2 = _make_customer(session, name="Has-Balance", balance=100)
    award_points(session, c2, total_gs=50_000, sale_id=2)
    session.commit()
    assert c2.loyalty_points == 150
    reverse_points_for_void(session, c2, sale_id=2)
    session.commit()
    assert c2.loyalty_points == 100, (
        "void should add back to the customer's pre-sale balance, "
        "not reset to 0"
    )


def test_partial_void_with_redeem_in_same_sale(session):
    """Customer earned 30 pts AND redeemed 20 pts on the same sale.
    Void → only the 30 earn is reversed. The 20 redeem ledger row
    stays (the customer got the discount; we don't claw it back on
    a void because there's no concept of a partial discount clawback
    in the current schema)."""
    c = _make_customer(session, balance=20)
    award_points(session, c, total_gs=30_000, sale_id=99)  # +30 pts
    redeem_points(session, c, points_to_redeem=20, sale_id=99)  # -20 pts
    session.commit()
    # After earn + redeem: balance = 20 (start) + 30 - 20 = 30
    assert c.loyalty_points == 30

    reversed_pts = reverse_points_for_void(session, c, sale_id=99)
    session.commit()

    # The reversal is for the EARN (30), not the redeem. The redeem
    # row stays because the customer received the discount.
    assert reversed_pts == 30, (
        f"void should reverse only the earn portion, got {reversed_pts}"
    )
    assert c.loyalty_points == 0, (
        f"expected 0 after full reversal (start=20, +30, -20, -30 void), "
        f"got {c.loyalty_points}"
    )

    rows = session.scalars(
        _sa_select(LoyaltyTransaction)
        .where(LoyaltyTransaction.sale_id == 99)
        .order_by(LoyaltyTransaction.id)
    ).all()
    reasons = [r.reason for r in rows]
    deltas = [r.delta for r in rows]
    # earn_sale (+30), redeem (-20), void_reversal (-30)
    assert reasons == ["earn_sale", "redeem", "void_reversal"]
    assert deltas == [30, -20, -30]
