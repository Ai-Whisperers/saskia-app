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

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.rms.models import Customer, Sale


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


def customer_stats(session: Session, customer: Customer) -> CustomerStats:
    """Compute lifetime spend, n_sales, last_sale_at for one customer."""
    sales = list(
        session.execute(
            select(Sale.sold_at, Sale.qty, Sale.unit_price_gs)
            .where(Sale.customer_id == customer.id, Sale.voided_at.is_(None))
            .order_by(Sale.sold_at.desc())
        ).all()
    )
    n_sales = len(sales)
    lifetime_spend = sum(
        int(round(s.qty * s.unit_price_gs)) for s in sales
    )
    last_sale_at = sales[0].sold_at if sales else None
    return CustomerStats(
        customer_id=customer.id,
        name=customer.name,
        phone=customer.phone,
        email=customer.email,
        loyalty_points=customer.loyalty_points,
        lifetime_spend_gs=lifetime_spend,
        last_sale_at=last_sale_at,
        n_sales=n_sales,
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
    "LoyaltyTier",
    "TIER_THRESHOLDS",
    "POINTS_PER_GS",
    "CustomerStats",
    "ensure_customer",
    "get_customer",
    "find_customer_by_phone",
    "list_customers",
    "points_for_sale",
    "award_points",
    "redeem_points",
    "tier_for_spend",
    "customer_stats",
    "customer_purchase_history",
]
