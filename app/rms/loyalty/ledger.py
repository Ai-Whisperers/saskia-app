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
# 1 point per 1000 Gs. (mirrors redeem: 1 point = 1000 Gs. discount).
# To change: edit this constant only — every helper picks it up.
POINTS_PER_GS = 1 / 1000


def points_for_sale(total_gs: int, points_per_gs: float = POINTS_PER_GS) -> int:
    """Convert guaraní spent to loyalty points (rounded down)."""
    return int(total_gs * points_per_gs)


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

    1 point = 1000 Gs. (mirrors POINTS_PER_GS inverse). Note the
    effective 10% lifetime-spend return rate — documented in the
    prelaunch roadmap; Saskia can change the constants at the top of
    this module when she wants to tune.

    Writes a LoyaltyTransaction ledger row with ``reason='redeem'``.

    Raises ValueError if customer doesn't have enough points.
    """
    if points_to_redeem <= 0:
        raise ValueError("points_to_redeem must be > 0")
    if (customer.loyalty_points or 0) < points_to_redeem:
        raise ValueError(
            f"Insufficient points: have {customer.loyalty_points}, want {points_to_redeem}"
        )
    discount = points_to_redeem * 1000
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