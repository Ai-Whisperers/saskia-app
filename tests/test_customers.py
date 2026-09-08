"""tests/test_customers.py — verify app/rms/customers.py (E13).

Per docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md E13.

Covers:
- ensure_customer by phone is idempotent
- ensure_customer without phone creates new rows
- find_customer_by_phone finds existing
- list_customers with search filter
- points_for_sale: 25k Gs. = 25 points
- award_points increments
- redeem_points: 10 points -> 10k Gs. discount
- redeem_points raises on insufficient balance
- tier_for_spend: 0=bronze, 100k=silver, 500k=gold, 1M=platinum
- customer_stats computes lifetime spend from sales
- customer_purchase_history returns recent sales
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.rms.customers import (
    LoyaltyTier,
    award_points,
    customer_purchase_history,
    customer_stats,
    ensure_customer,
    find_customer_by_phone,
    list_customers,
    points_for_sale,
    redeem_points,
    tier_for_spend,
)
from app.rms.models import Customer, Product, Sale


def test_ensure_customer_by_phone_is_idempotent(session_factory):
    """ensure_customer with same phone returns same row."""
    s = session_factory()
    try:
        c1 = ensure_customer(s, "María", phone="+595981123456")
        s.commit()
        c2 = ensure_customer(s, "María", phone="+595981123456")
        s.commit()
        assert c1.id == c2.id
        # Only one row
        all_cust = list(s.query(Customer).all())
        assert len(all_cust) == 1
    finally:
        s.close()


def test_ensure_customer_without_phone_creates_each_time(session_factory):
    """Without a phone, ensure_customer treats each as a new person."""
    s = session_factory()
    try:
        c1 = ensure_customer(s, "Anónimo 1")
        c2 = ensure_customer(s, "Anónimo 2")
        s.commit()
        assert c1.id != c2.id
    finally:
        s.close()


def test_ensure_customer_updates_existing_with_new_fields(session_factory):
    """If we re-call with new name/email/notes, update them."""
    s = session_factory()
    try:
        c1 = ensure_customer(s, "M", phone="+595981000000")
        s.commit()
        c2 = ensure_customer(s, "María", phone="+595981000000", email="m@x.com", notes="VIP")
        s.commit()
        assert c1.id == c2.id
        assert c2.name == "María"
        assert c2.email == "m@x.com"
        assert c2.notes == "VIP"
    finally:
        s.close()


def test_find_customer_by_phone(session_factory):
    s = session_factory()
    try:
        ensure_customer(s, "A", phone="+595981000001")
        ensure_customer(s, "B", phone="+595981000002")
        s.commit()
        a = find_customer_by_phone(s, "+595981000001")
        assert a is not None
        assert a.name == "A"
        b = find_customer_by_phone(s, "+595981000002")
        assert b.name == "B"
        missing = find_customer_by_phone(s, "+595981999999")
        assert missing is None
    finally:
        s.close()


def test_list_customers_with_search_filter(session_factory):
    s = session_factory()
    try:
        ensure_customer(s, "María González", phone="+595981000003")
        ensure_customer(s, "Pedro Pérez", phone="+595981000004")
        ensure_customer(s, "María López", phone="+595981000005")
        s.commit()
        results = list_customers(s, search="María")
        names = sorted([c.name for c in results])
        assert names == ["María González", "María López"]
    finally:
        s.close()


def test_points_for_sale():
    """25k Gs. = 25 points (1 point per 1000 Gs.)."""
    assert points_for_sale(25_000) == 25
    assert points_for_sale(1_000) == 1
    assert points_for_sale(999) == 0  # rounded down
    assert points_for_sale(0) == 0


def test_award_points_increments(session_factory):
    s = session_factory()
    try:
        cust = ensure_customer(s, "Test", phone="+595981000010")
        s.commit()
        assert cust.loyalty_points == 0
        pts = award_points(s, cust, 25_000)
        s.commit()
        assert pts == 25
        assert cust.loyalty_points == 25
        award_points(s, cust, 100_000)
        s.commit()
        assert cust.loyalty_points == 125
    finally:
        s.close()


def test_redeem_points_returns_discount(session_factory):
    """10 points -> 10k Gs. discount."""
    s = session_factory()
    try:
        cust = ensure_customer(s, "Test", phone="+595981000011")
        award_points(s, cust, 25_000)
        s.commit()
        assert cust.loyalty_points == 25
        redeemed, discount = redeem_points(s, cust, 10)
        s.commit()
        assert redeemed == 10
        assert discount == 10_000
        assert cust.loyalty_points == 15
    finally:
        s.close()


def test_redeem_points_raises_on_insufficient(session_factory):
    s = session_factory()
    try:
        cust = ensure_customer(s, "Broke", phone="+595981000012")
        s.commit()
        with pytest.raises(ValueError, match="Insufficient points"):
            redeem_points(s, cust, 10)
    finally:
        s.close()


def test_redeem_points_raises_on_zero_or_negative(session_factory):
    s = session_factory()
    try:
        cust = ensure_customer(s, "T", phone="+595981000013")
        award_points(s, cust, 25_000)
        s.commit()
        with pytest.raises(ValueError, match="must be > 0"):
            redeem_points(s, cust, 0)
        with pytest.raises(ValueError, match="must be > 0"):
            redeem_points(s, cust, -5)
    finally:
        s.close()


def test_tier_for_spend():
    """Tier thresholds: 0=bronze, 100k=silver, 500k=gold, 1M=platinum."""
    assert tier_for_spend(0) == LoyaltyTier.BRONZE
    assert tier_for_spend(50_000) == LoyaltyTier.BRONZE
    assert tier_for_spend(99_999) == LoyaltyTier.BRONZE
    assert tier_for_spend(100_000) == LoyaltyTier.SILVER
    assert tier_for_spend(250_000) == LoyaltyTier.SILVER
    assert tier_for_spend(499_999) == LoyaltyTier.SILVER
    assert tier_for_spend(500_000) == LoyaltyTier.GOLD
    assert tier_for_spend(750_000) == LoyaltyTier.GOLD
    assert tier_for_spend(999_999) == LoyaltyTier.GOLD
    assert tier_for_spend(1_000_000) == LoyaltyTier.PLATINUM
    assert tier_for_spend(10_000_000) == LoyaltyTier.PLATINUM


def test_customer_stats_lifetime_spend(session_factory):
    """customer_stats computes lifetime spend from sales."""
    s = session_factory()
    try:
        prod = Product(name="Muffin", sale_price_gs=2500)
        s.add(prod)
        s.flush()
        cust = ensure_customer(s, "Test", phone="+595981000020")
        s.commit()
        # Three sales: 1, 2, 4 muffins = 17_500 Gs.
        s.add_all([
            Sale(customer_id=cust.id, product_id=prod.id, qty=1.0, unit_price_gs=2500,
                 sold_at=datetime.now(timezone.utc) - timedelta(days=10)),
            Sale(customer_id=cust.id, product_id=prod.id, qty=2.0, unit_price_gs=2500,
                 sold_at=datetime.now(timezone.utc) - timedelta(days=5)),
            Sale(customer_id=cust.id, product_id=prod.id, qty=4.0, unit_price_gs=2500,
                 sold_at=datetime.now(timezone.utc) - timedelta(days=1)),
        ])
        s.commit()
        stats = customer_stats(s, cust)
        assert stats.lifetime_spend_gs == 17_500
        assert stats.n_sales == 3
        assert stats.tier == LoyaltyTier.BRONZE  # 17_500 < 100k
        assert stats.last_sale_at is not None
    finally:
        s.close()


def test_customer_stats_excludes_voided(session_factory):
    """Voided sales are excluded from lifetime spend."""
    s = session_factory()
    try:
        prod = Product(name="Muffin", sale_price_gs=2500)
        s.add(prod)
        s.flush()
        cust = ensure_customer(s, "T", phone="+595981000021")
        s.commit()
        s.add_all([
            Sale(customer_id=cust.id, product_id=prod.id, qty=1.0, unit_price_gs=2500,
                 sold_at=datetime.now(timezone.utc)),
            Sale(customer_id=cust.id, product_id=prod.id, qty=10.0, unit_price_gs=2500,
                 sold_at=datetime.now(timezone.utc), voided_at=datetime.now(timezone.utc)),
        ])
        s.commit()
        stats = customer_stats(s, cust)
        assert stats.lifetime_spend_gs == 2500  # voided excluded
        assert stats.n_sales == 1
    finally:
        s.close()


def test_customer_purchase_history(session_factory):
    s = session_factory()
    try:
        prod = Product(name="Muffin", sale_price_gs=2500)
        s.add(prod)
        s.flush()
        cust = ensure_customer(s, "T", phone="+595981000022")
        s.commit()
        for i in range(5):
            s.add(Sale(
                customer_id=cust.id,
                product_id=prod.id,
                qty=1.0,
                unit_price_gs=2500,
                sold_at=datetime.now(timezone.utc) - timedelta(days=i),
            ))
        s.commit()
        history = customer_purchase_history(s, cust.id, limit=3)
        assert len(history) == 3
        # Newest first
        assert history[0].sold_at > history[-1].sold_at
    finally:
        s.close()
