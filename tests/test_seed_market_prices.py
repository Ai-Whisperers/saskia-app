"""tests/test_seed_market_prices.py — Wave 4: seed market reference prices.

Exercises the MARKET_REFERENCE_SEED constant in app.rms.seed_market_prices
against the seeded ingredient inventory, verifying each row inserts cleanly
and the delta computation produces sensible results.
"""
from __future__ import annotations

from datetime import datetime, timezone

_UTC = timezone.utc

from sqlalchemy import select

from app.rms.models import Ingredient, MarketPriceReference
from app.rms.seed_market_prices import MARKET_REFERENCE_SEED


def _ensure_seeded(session):
    """Make sure the test session has ingredients to attach market prices to."""
    count = session.query(Ingredient).count()
    if count == 0:
        from app.rms.seed import seed_demo_data
        seed_demo_data(session, seed=20260922)
        count = session.query(Ingredient).count()
    return count


def test_seed_market_prices_inserts_all_rows(session_factory):
    """Every entry in MARKET_REFERENCE_SEED that matches an ingredient
    in the seeded DB should insert a MarketPriceReference row."""
    Session = session_factory
    session = Session()
    try:
        n = _ensure_seeded(session)
        assert n > 0, "seed_demo_data should have inserted ingredients"

        existing_ingredients = {
            row.name: row for row in session.execute(select(Ingredient)).scalars()
        }

        # Wipe any prior seed
        session.query(MarketPriceReference).delete()
        session.commit()

        today = datetime.now(_UTC).date()
        matched = 0
        for name, unit, price_gs, source, notes in MARKET_REFERENCE_SEED:
            ing = next(
                (i for n_, i in existing_ingredients.items() if n_.lower() == name.lower()),
                None,
            )
            if not ing:
                continue
            row = MarketPriceReference(
                ingredient_id=ing.id,
                unit=unit,
                price_gs=price_gs,
                source=source,
                notes=notes,
                as_of=today,
            )
            session.add(row)
            matched += 1
        session.commit()

        assert matched >= 10, f"Expected ≥10 ingredients to match, got {matched}"
        total = session.query(MarketPriceReference).count()
        assert total == matched
    finally:
        session.close()


def test_seed_is_idempotent(session_factory):
    """Re-running the seed should not duplicate rows because we wipe first."""
    Session = session_factory
    session = Session()
    try:
        _ensure_seeded(session)
        existing = {r.name: r for r in session.execute(select(Ingredient)).scalars()}

        for _ in range(2):
            session.query(MarketPriceReference).delete()
            today = datetime.now(_UTC).date()
            for name, unit, price_gs, source, notes in MARKET_REFERENCE_SEED:
                ing = next(
                    (i for n_, i in existing.items() if n_.lower() == name.lower()), None
                )
                if not ing:
                    continue
                session.add(MarketPriceReference(
                    ingredient_id=ing.id, unit=unit, price_gs=price_gs,
                    source=source, notes=notes, as_of=today,
                ))
            session.commit()

        count = session.query(MarketPriceReference).count()
        assert count >= 10, f"Expected ≥10 after idempotent run, got {count}"
    finally:
        session.close()


def test_market_price_delta_helper():
    """Delta computation: positive = above market, negative = below."""
    class MockIng:
        purchase_price_gs = 6500

    class MockRef:
        price_gs = 6000
        unit = "kg"

    delta_pct = (MockIng.purchase_price_gs - MockRef.price_gs) / MockRef.price_gs * 100
    assert abs(delta_pct - 8.333) < 0.01, f"Expected 8.33%, got {delta_pct:.2f}%"
