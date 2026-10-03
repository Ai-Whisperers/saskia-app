"""app/rms/loyalty/ledger.py — points math, ledger writes, balance reconciliation.

Single source of truth for:
  - POINTS_PER_GS conversion (1 point per 1000 Gs. spent)
  - LoyaltyTransaction ledger writes (earn / redeem / void_reversal / suggestion_applied / manual_adjust)
  - Customer.loyalty_points cached balance update

Public helpers: points_for_sale, award_points, redeem_points,
reverse_points_for_void, reconcile_loyalty_balance.

Tier rules (LoyaltyTier, TIER_THRESHOLDS, tier_for_spend) live in tiers.py.
Suggestion-card logic lives in suggestions.py.

Tier 4.1 (2026-10-01): extracted from app/rms/customers.py.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.rms.models import Customer

# Default loyalty rule: points per guaraní spent.
# ════════════════════════════════════════════════════════════════════════
# Loyalty conversion rules (tunable from one place)
# ════════════════════════════════════════════════════════════════════════
#
# Two independent constants — DO NOT make them the inverse of each other:
#
#   POINTS_PER_GS_EARN   = 1 / 1000  →  1 point earned per 1,000 Gs spent
#   POINTS_VALUE_GS       = 100       →  1 redeemed point = 100 Gs off
#
# Effective lifetime-spend return rate with these values:
#   (POINTS_VALUE_GS) / (1 / POINTS_PER_GS_EARN) = 100 / 1000 = 10%
#
# Pre-2026-10-01 bug: a single POINTS_PER_GS = 1/1000 was used for both,
# so 1,000 Gs spent earned 1 pt AND 1 pt redeemed = 1,000 Gs. That was
# a 100% effective return rate — the cashier could refund 95% of a
# customer's lifetime spend by redeeming their balance. Reviewer caught
# this in the live CRM walkthrough. The constants are now split.
#
# The POS redeem UI and the recibo PDF format the discount as
#   points_to_redeem * POINTS_VALUE_GS
# so changing POINTS_VALUE_GS here changes the live floor behavior
# instantly (no other code edits required).
POINTS_PER_GS_EARN = 1 / 1000  # pts earned per Gs spent
POINTS_VALUE_GS = 100           # Gs discount per redeemed point


# Kept as a module alias so legacy imports (`from app.rms.loyalty.ledger
# import POINTS_PER_GS`) keep working — but the value now reflects only
# the earn rate, which matches its name. Callers that want the redeem
# value should use POINTS_VALUE_GS.
POINTS_PER_GS = POINTS_PER_GS_EARN


def points_for_sale(total_gs: int, points_per_gs: float = POINTS_PER_GS_EARN) -> int:
    """Convert guaraní spent to loyalty points (rounded down).

    Uses POINTS_PER_GS_EARN by default. Caller can override for testing.
    """
    return int(total_gs * points_per_gs)


def discount_gs_for_points(points_to_redeem: int) -> int:
    """Convert a redemption amount to Gs discount at POINTS_VALUE_GS."""
    if points_to_redeem < 0:
        raise ValueError("points_to_redeem must be >= 0")
    return points_to_redeem * POINTS_VALUE_GS


def effective_return_rate() -> float:
    """Return the % of lifetime-spend a customer can reclaim via points.

    Used in the customer-detail page footer + admin diagnostics. With
    the default constants this is 10%.
    """
    return (POINTS_VALUE_GS * POINTS_PER_GS_EARN) * 100.0


def _record_ledger(
    session: Session,
    customer: Customer,
    delta: int,
    reason: str,
    *,
    sale_id: int | None = None,
    actor: str = "system",
    notes: str | None = None,
) -> int:
    """Internal: write a LoyaltyTransaction row + update the cached balance.

    Returns the absolute value of ``delta`` (positive int for UI display).
    Both callers in this module use the return value of the underlying
    public helper; this is the single write-path so all delta math stays
    in one place.
    """
    from app.rms.models import LoyaltyTransaction  # local import — circular-safe

    row = LoyaltyTransaction(
        customer_id=customer.id,
        delta=delta,
        reason=reason,
        sale_id=sale_id,
        actor=actor,
        notes=notes,
        recorded_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(row)
    customer.loyalty_points = (customer.loyalty_points or 0) + delta
    session.flush()
    return abs(delta)


def award_points(
    session: Session,
    customer: Customer,
    total_gs: int,
    *,
    sale_id: int | None = None,
    actor: str = "system",
) -> int:
    """Increment customer.loyalty_points for a sale; returns the points awarded.

    Wired into the sale-creation path (2026-10-01). Writes a
    LoyaltyTransaction ledger row with ``reason='earn_sale'`` so the
    audit trail is reconstructible.

    Sale.total_gs (int Gs.) is what the operator actually paid, so we
    earn on the post-discount amount (this matches industry norm —
    you earn on what you spent, not on sticker price).
    """
    pts = points_for_sale(total_gs)
    if pts <= 0:
        return 0
    _record_ledger(
        session,
        customer,
        delta=pts,
        reason="earn_sale",
        sale_id=sale_id,
        actor=actor,
        notes=f"earn on sale of {total_gs:,} Gs",
    )
    return pts


def redeem_points(
    session: Session,
    customer: Customer,
    points_to_redeem: int,
    *,
    sale_id: int | None = None,
    actor: str = "operator",
    notes: str | None = None,
) -> tuple[int, int]:
    """Redeem points; returns (points_redeemed, discount_gs).

    1 point = POINTS_VALUE_GS (currently 100 Gs). At the default
    POINTS_PER_GS_EARN of 1/1000 (1 pt per 1,000 Gs spent), this gives
    a 10% lifetime-spend return rate — see ledger.py top-of-file for
    the derivation. If the floor tunes either constant, the new
    effective rate is one line away.

    Writes a LoyaltyTransaction ledger row with ``reason='redeem'``.

    Raises ValueError if customer doesn't have enough points.
    """
    if points_to_redeem <= 0:
        raise ValueError("points_to_redeem must be > 0")
    if (customer.loyalty_points or 0) < points_to_redeem:
        raise ValueError(
            f"Insufficient points: have {customer.loyalty_points}, want {points_to_redeem}"
        )
    discount = discount_gs_for_points(points_to_redeem)
    _record_ledger(
        session,
        customer,
        delta=-points_to_redeem,
        reason="redeem",
        sale_id=sale_id,
        actor=actor,
        notes=notes or f"canje por {discount:,} Gs de descuento",
    )
    return points_to_redeem, discount


def reverse_points_for_void(
    session: Session,
    customer: Customer,
    sale_id: int,
    actor: str = "system",
) -> int:
    """When a sale that earned points is voided, reverse the points.

    Looks up the original ``earn_sale`` ledger row(s) for this sale,
    writes a ``void_reversal`` row with the NEGATED delta, and
    updates the cached balance. If multiple earn_sale rows exist
    for one sale (shouldn't happen, but defensive), reverses all.

    Returns the total points reversed (positive int).
    """
    from sqlalchemy import select as _sa_select

    from app.rms.models import LoyaltyTransaction

    original = session.scalars(
        _sa_select(LoyaltyTransaction).where(
            LoyaltyTransaction.sale_id == sale_id,
            LoyaltyTransaction.reason == "earn_sale",
        )
    ).all()
    if not original:
        return 0
    total_to_reverse = sum(row.delta for row in original)
    _record_ledger(
        session,
        customer,
        delta=-total_to_reverse,
        reason="void_reversal",
        sale_id=sale_id,
        actor=actor,
        notes=f"void de sale #{sale_id} revirtió {total_to_reverse} puntos",
    )
    return abs(total_to_reverse)


def reconcile_loyalty_balance(session: Session, customer: Customer) -> int:
    """Rebuild customer.loyalty_points from SUM(loyalty_transaction.delta).

    Returns the new balance. Useful for ops when the cached column
    drifts from the ledger (e.g. after a manual SQL edit or an
    old-version bug). Idempotent.
    """
    from sqlalchemy import func as _sa_func
    from sqlalchemy import select as _sa_select

    from app.rms.models import LoyaltyTransaction

    total = session.scalar(
        _sa_select(_sa_func.coalesce(_sa_func.sum(LoyaltyTransaction.delta), 0)).where(
            LoyaltyTransaction.customer_id == customer.id
        )
    )
    customer.loyalty_points = int(total or 0)
    session.flush()
    return customer.loyalty_points


__all__ = [
    "POINTS_PER_GS",
    "award_points",
    "points_for_sale",
    "reconcile_loyalty_balance",
    "redeem_points",
    "reverse_points_for_void",
]
