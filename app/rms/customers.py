"""app/rms/customers.py — Customer directory + loyalty (E13).

Per docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md E13.

Adds:
- Customer model: name, phone (unique), email, notes, loyalty_points
- Sale.customer_id nullable FK to link sales to customers
- Loyalty rule: 1 point per 1000 Gs. spent (configurable)
- Customer tier based on lifetime spend (bronze/silver/gold)
- Pure-Python helpers (CRUD + history + tier + points)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.rms.models import Customer, Sale

logger = logging.getLogger(__name__)


class LoyaltyTier(str, Enum):
    """Customer tier based on lifetime spend (Gs.)."""

    BRONZE = "bronze"  # 0-100k
    SILVER = "silver"  # 100k-500k
    GOLD = "gold"  # 500k-1M
    PLATINUM = "platinum"  # 1M+


# Tier thresholds (Gs.)
TIER_THRESHOLDS = {
    LoyaltyTier.BRONZE: 0,
    LoyaltyTier.SILVER: 100_000,
    LoyaltyTier.GOLD: 500_000,
    LoyaltyTier.PLATINUM: 1_000_000,
}

# Default loyalty rule: points per guaraní spent
POINTS_PER_GS = 1 / 1000  # 1 point per 1000 Gs.


@dataclass
class CustomerStats:
    """Computed snapshot of a customer's activity."""

    customer_id: int
    name: str
    phone: str | None
    email: str | None
    loyalty_points: int
    lifetime_spend_gs: int
    last_sale_at: datetime | None
    n_sales: int
    tier: LoyaltyTier


# --- CRUD ---


def ensure_customer(
    session: Session,
    name: str,
    phone: str | None = None,
    email: str | None = None,
    notes: str | None = None,
    cedula: str | None = None,
) -> Customer:
    """Find-or-create a customer by phone (or name if no phone).

    Phone is the de-facto unique key. If two customers have the same
    name but different phones, they're treated as different people.

    If cedula is provided and an existing customer has the same
    cedula (non-empty match), update that row instead of creating a
    duplicate.
    """
    if cedula and cedula.strip():
        cedula_clean = cedula.strip()
        existing = session.execute(
            select(Customer).where(Customer.cedula == cedula_clean)
        ).scalar_one_or_none()
        if existing is not None:
            if name and name != existing.name:
                existing.name = name
            if phone and phone != existing.phone:
                existing.phone = phone
            if email and email != existing.email:
                existing.email = email
            if notes and notes != existing.notes:
                existing.notes = notes
            if cedula_clean and cedula_clean != existing.cedula:
                existing.cedula = cedula_clean
            return existing
    if phone:
        existing = session.execute(
            select(Customer).where(Customer.phone == phone)
        ).scalar_one_or_none()
        if existing is not None:
            # Warn if this is a duplicate-phone merge (two customers with same phone)
            if name and name != existing.name:
                logger.warning(
                    "ensure_customer: duplicate phone merge — phone=%r existing_name=%r incoming_name=%r",
                    phone, existing.name, name,
                )
            # Update name/email/notes/cedula if newly provided
            if name and name != existing.name:
                existing.name = name
            if email and email != existing.email:
                existing.email = email
            if notes and notes != existing.notes:
                existing.notes = notes
            cedula_clean = (cedula or "").strip() or None
            if cedula_clean and cedula_clean != existing.cedula:
                existing.cedula = cedula_clean
            return existing
    cust = Customer(name=name, phone=phone, email=email, notes=notes, cedula=(cedula or "").strip() or None)
    session.add(cust)
    session.flush()
    return cust


def search_customers(
    session: Session,
    query: str,
    limit: int = 10,
) -> list[Customer]:
    """Case-insensitive substring search across name, phone, email, cedula, notes.

    Empty / whitespace query returns the most-recently-created customers
    (newest first) up to `limit` so the picker is never empty on first open.
    Uses ``or_`` with ``ilike`` patterns per the picker spec.
    """
    stmt = select(Customer).order_by(Customer.created_at.desc()).limit(limit)
    q = (query or "").strip()
    if q:
        like = f"%{q}%"
        stmt = (
            select(Customer)
            .where(
                or_(
                    Customer.name.ilike(like),
                    Customer.phone.ilike(like),
                    Customer.email.ilike(like),
                    Customer.cedula.ilike(like),
                    Customer.notes.ilike(like),
                )
            )
            .order_by(Customer.created_at.desc())
            .limit(limit)
        )
    return list(session.execute(stmt).scalars())


def find_customer_by_cedula(session: Session, cedula: str) -> Customer | None:
    return session.execute(
        select(Customer).where(Customer.cedula == cedula)
    ).scalar_one_or_none()


def get_customer(session: Session, customer_id: int) -> Customer | None:
    return session.get(Customer, customer_id)


def find_customer_by_phone(session: Session, phone: str) -> Customer | None:
    return session.execute(
        select(Customer).where(Customer.phone == phone)
    ).scalar_one_or_none()


def list_customers(
    session: Session,
    *,
    search: str | None = None,
    limit: int = 100,
) -> list[Customer]:
    """Return customers, newest first. Optional case-insensitive name search."""
    q = select(Customer).order_by(Customer.created_at.desc())
    if search:
        q = q.where(Customer.name.ilike(f"%{search}%"))
    return list(session.execute(q.limit(limit)).scalars())


# --- Loyalty helpers ---


def points_for_sale(total_gs: int, points_per_gs: float = POINTS_PER_GS) -> int:
    """Convert guaraní spent to loyalty points (rounded down)."""
    return int(total_gs * points_per_gs)


def award_points(session: Session, customer: Customer, total_gs: int) -> int:
    """Increment customer.loyalty_points; returns the points awarded."""
    pts = points_for_sale(total_gs)
    customer.loyalty_points += pts
    session.flush()
    return pts


def redeem_points(
    session: Session, customer: Customer, points_to_redeem: int
) -> tuple[int, int]:
    """Redeem points; returns (points_redeemed, discount_gs).

    1 point = 1000 Gs. (mirrors POINTS_PER_GS inverse).

    Raises ValueError if customer doesn't have enough points.
    """
    if points_to_redeem <= 0:
        raise ValueError("points_to_redeem must be > 0")
    if customer.loyalty_points < points_to_redeem:
        raise ValueError(
            f"Insufficient points: have {customer.loyalty_points}, want {points_to_redeem}"
        )
    discount = points_to_redeem * 1000
    customer.loyalty_points -= points_to_redeem
    session.flush()
    return points_to_redeem, discount


def tier_for_spend(lifetime_spend_gs: int) -> LoyaltyTier:
    """Map lifetime spend (Gs.) to a LoyaltyTier."""
    if lifetime_spend_gs >= TIER_THRESHOLDS[LoyaltyTier.PLATINUM]:
        return LoyaltyTier.PLATINUM
    if lifetime_spend_gs >= TIER_THRESHOLDS[LoyaltyTier.GOLD]:
        return LoyaltyTier.GOLD
    if lifetime_spend_gs >= TIER_THRESHOLDS[LoyaltyTier.SILVER]:
        return LoyaltyTier.SILVER
    return LoyaltyTier.BRONZE


def batch_customer_stats(
    session: Session, customers: list[Customer]
) -> dict[int, CustomerStats]:
    """Compute stats for multiple customers in a single query.

    Replaces N calls to customer_stats() — 2 queries per customer → 1 query total.
    """
    if not customers:
        return {}

    ids = [c.id for c in customers]
    rows = session.execute(
        select(
            Sale.customer_id,
            func.count(Sale.id).label("n_sales"),
            func.coalesce(func.sum(Sale.qty * Sale.unit_price_gs), 0).label("lifetime_spend_gs"),
            func.max(Sale.sold_at).label("last_sale_at"),
        )
        .where(Sale.customer_id.in_(ids), Sale.voided_at.is_(None))
        .group_by(Sale.customer_id)
    ).all()
    stats_by_cid = {
        r.customer_id: _raw_stats_to_customer_stats(session, r, customers)
        for r in rows
    }
    # Customers with zero sales won't appear in the aggregation — fill them in
    for c in customers:
        if c.id not in stats_by_cid:
            stats_by_cid[c.id] = CustomerStats(
                customer_id=c.id,
                name=c.name,
                phone=c.phone,
                email=c.email,
                loyalty_points=c.loyalty_points,
                lifetime_spend_gs=0,
                last_sale_at=None,
                n_sales=0,
                tier=LoyaltyTier.BRONZE,
            )
    return stats_by_cid


def _raw_stats_to_customer_stats(
    session: Session, row, customers: list[Customer]
) -> CustomerStats:
    """Convert an aggregated DB row to CustomerStats for one customer."""
    # Find the Customer object for this id
    customer = next((c for c in customers if c.id == row.customer_id), None)
    lifetime_spend = int(row.lifetime_spend_gs or 0)
    return CustomerStats(
        customer_id=row.customer_id,
        name=customer.name if customer else "",
        phone=customer.phone if customer else None,
        email=customer.email if customer else None,
        loyalty_points=customer.loyalty_points if customer else 0,
        lifetime_spend_gs=lifetime_spend,
        last_sale_at=row.last_sale_at,
        n_sales=row.n_sales or 0,
        tier=tier_for_spend(lifetime_spend),
    )


def customer_stats(session: Session, customer: Customer) -> CustomerStats:
    """Compute lifetime spend, n_sales, last_sale_at for one customer."""
    rows = session.execute(
        select(
            func.count(Sale.id).label("n_sales"),
            func.coalesce(func.sum(Sale.qty * Sale.unit_price_gs), 0).label("lifetime_spend_gs"),
            func.max(Sale.sold_at).label("last_sale_at"),
        )
        .where(Sale.customer_id == customer.id, Sale.voided_at.is_(None))
    ).one()
    lifetime_spend = int(rows.lifetime_spend_gs or 0)
    return CustomerStats(
        customer_id=customer.id,
        name=customer.name,
        phone=customer.phone,
        email=customer.email,
        loyalty_points=customer.loyalty_points,
        lifetime_spend_gs=lifetime_spend,
        last_sale_at=rows.last_sale_at,
        n_sales=rows.n_sales or 0,
        tier=tier_for_spend(lifetime_spend),
    )


def customer_purchase_history(
    session: Session, customer_id: int, limit: int = 50
) -> list[Sale]:
    """Return recent sales for one customer, newest first."""
    return list(
        session.execute(
            select(Sale)
            .where(Sale.customer_id == customer_id)
            .order_by(Sale.sold_at.desc())
            .limit(limit)
        ).scalars()
    )


__all__ = [
    "POINTS_PER_GS",
    "TIER_THRESHOLDS",
    "CustomerStats",
    "LoyaltyTier",
    "award_points",
    "batch_customer_stats",
    "customer_purchase_history",
    "customer_stats",
    "ensure_customer",
    "find_customer_by_phone",
    "get_customer",
    "list_customers",
    "points_for_sale",
    "redeem_points",
    "tier_for_spend",
]
