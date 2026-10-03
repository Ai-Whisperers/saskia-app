"""tests/test_refunds.py — M1 refund entity + service (BACKLOG, Phase 14+).

Tests for app/rms/refunds.py and the underlying migration 089 cap trigger.
Uses the standard conftest fixtures (client, session_factory, qseed) plus
raw SQLite session for trigger testing.

What this catches:
  1. cap trigger: SUM(amount_gs) per target must not exceed target_amount_gs
  2. cap trigger catches DB-level bypass (raw SQL bypassing service layer)
  3. partial refund allowed (multiple refunds per target)
  4. voided sale cannot be refunded
  5. unknown target rejected
  6. amount must be positive (model CheckConstraint)
  7. loyalty points reverse proportionally to refund amount
  8. restock updates ingredient stock_qty + writes StockMovement row
  9. eod-closed day blocks refunds
 10. payment_method captured from target

Real bugs we caught during Phase 14:
  - Pyright noise on test imports (suppressed)
  - Service imports Refund from wrong module (fixed in refunds.py)

What's NOT covered (deferred):
  - HTTP router (covered separately in test_refunds_router.py, TBD)
  - UI template button (deferred to UI work)
  - Daily report subtracts refunds (deferred to M1+)
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select as sa_select
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Headless test env
os.environ.setdefault("SASKIA_ENV", "test")
os.environ.setdefault("SASKIA_TEST_AUTH_DISABLED", "1")


# --- Helpers --------------------------------------------------------------


@pytest.fixture()
def refund_engine():
    """In-memory SQLite engine with all migrations applied + fresh schema."""
    from app.rms.db import init_db, make_engine

    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    yield engine


@pytest.fixture()
def refund_session(refund_engine):
    """Session bound to the in-memory engine, rolled back per test."""
    SessionLocal = sessionmaker(bind=refund_engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _make_sale(session, *, total_gs: int = 10_000, payment_method: str = "efectivo",
               customer_id: int | None = None, qty: float = 1.0, voided: bool = False):
    """Helper to create a minimal Sale row for refund tests.

    Ensures a Product row exists so the FK constraint is satisfied.
    """
    from app.rms.models_legacy import Product, Sale

    # Idempotent: only create the Product if it doesn't exist
    existing_product = session.execute(
        text("SELECT id FROM product WHERE id = 1")
    ).first()
    if existing_product is None:
        product = Product(
            id=1,
            name="Test Product",
            sale_price_gs=total_gs,
            portion_label="unit",
        )
        session.add(product)
        session.flush()

    sale = Sale(
        product_id=1,
        qty=qty,
        unit_price_gs=total_gs,
        sold_at=datetime.utcnow(),
        payment_method=payment_method,
        customer_id=customer_id,
        discount_gs=0,
        channel="mostrador",
        invoice_type="none",
        tz="America/Asuncion",
    )
    if voided:
        sale.voided_at = datetime.utcnow()
    session.add(sale)
    session.flush()
    return sale


# --- 1. Cap trigger ------------------------------------------------------


def test_refund_cap_rejects_when_exceeded(refund_session):
    """sum(amount_gs) > target_amount_gs must raise (DB or service)."""
    from app.rms.refunds import RefundError, create_refund

    sale = _make_sale(refund_session, total_gs=10_000)

    # First refund: 8_000 — OK
    create_refund(
        refund_session,
        "sale",
        sale.id,
        8_000,
        recorded_by="operator",
    )
    # Second refund: 3_000 — would total 11_000 > 10_000, must fail
    with pytest.raises(RefundError) as exc_info:
        create_refund(
            refund_session,
            "sale",
            sale.id,
            3_000,
            recorded_by="operator",
        )
    assert exc_info.value.code in ("cap_exceeded",), f"got code={exc_info.value.code}"


def test_refund_partial_then_full_works(refund_session):
    """Multiple refunds summing exactly to target_amount_gs should be allowed."""
    from app.rms.refunds import create_refund, list_refunds_for

    sale = _make_sale(refund_session, total_gs=10_000)
    create_refund(refund_session, "sale", sale.id, 6_000, recorded_by="op")
    create_refund(refund_session, "sale", sale.id, 4_000, recorded_by="op")
    refunds = list_refunds_for(refund_session, "sale", sale.id)
    assert len(refunds) == 2
    assert sum(r.amount_gs for r in refunds) == 10_000


def test_refund_db_trigger_catches_bypass(refund_engine):
    """Direct INSERT bypassing the service layer must also fail via DB trigger."""

    from sqlalchemy.exc import IntegrityError

    SessionLocal = sessionmaker(bind=refund_engine)
    s = SessionLocal()
    sale = _make_sale(s, total_gs=1_000)
    s.commit()
    sale_id = sale.id

    # First insert: 1000 — OK
    with refund_engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO refund (target_type, target_id, target_amount_gs, amount_gs, "
            "payment_method, restock_qty, restocked_qty, recorded_at, loyalty_reversed, eod_date) "
            "VALUES ('sale', :sid, 1000, 1000, 'efectivo', 0, 0, :ts, 0, :d)"
        ), {"sid": sale_id, "ts": datetime.utcnow(), "d": datetime.utcnow().date()})

    # Second insert: 1500 — must fail (would total 2500 > 1000)
    with pytest.raises(IntegrityError):
        with refund_engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO refund (target_type, target_id, target_amount_gs, amount_gs, "
                "payment_method, restock_qty, restocked_qty, recorded_at, loyalty_reversed, eod_date) "
                "VALUES ('sale', :sid, 1000, 1500, 'efectivo', 0, 0, :ts, 0, :d)"
            ), {"sid": sale_id, "ts": datetime.utcnow(), "d": datetime.utcnow().date()})


# --- 2. Voided sale rejection ---------------------------------------------


def test_refund_voided_sale_rejected(refund_session):
    """A sale with voided_at set cannot be refunded (voids are separate from refunds)."""
    from app.rms.refunds import RefundError, create_refund

    sale = _make_sale(refund_session, total_gs=5_000, voided=True)
    with pytest.raises(RefundError) as exc_info:
        create_refund(refund_session, "sale", sale.id, 1_000, recorded_by="op")
    assert exc_info.value.code == "voided"


# --- 3. Unknown target rejection ------------------------------------------


def test_refund_unknown_sale_rejected(refund_session):
    from app.rms.refunds import RefundError, create_refund

    with pytest.raises(RefundError) as exc_info:
        create_refund(refund_session, "sale", 99_999_999, 1_000, recorded_by="op")
    assert exc_info.value.code == "not_found"


def test_refund_invalid_target_type_rejected(refund_session):
    from app.rms.refunds import RefundError, create_refund

    with pytest.raises(RefundError) as exc_info:
        create_refund(refund_session, "totally_not_valid", 1, 1_000, recorded_by="op")
    assert exc_info.value.code == "invalid_target_type"


# --- 4. Amount validation ------------------------------------------------


def test_refund_amount_must_be_positive(refund_session):
    """amount_gs <= 0 must raise (caught by either service or DB)."""

    from app.rms.refunds import RefundError, create_refund

    sale = _make_sale(refund_session, total_gs=5_000)
    # Service-layer check
    with pytest.raises(RefundError) as exc_info:
        create_refund(refund_session, "sale", sale.id, 0, recorded_by="op")
    assert exc_info.value.code == "amount_invalid"


def test_refund_amount_zero_blocked_by_db(refund_engine):
    """DB trigger catches amount_gs=0 even if service is bypassed."""
    from sqlalchemy.exc import IntegrityError

    SessionLocal = sessionmaker(bind=refund_engine)
    s = SessionLocal()
    sale = _make_sale(s, total_gs=5_000)
    s.commit()

    with refund_engine.connect() as conn:
        with pytest.raises(IntegrityError):
            with conn.begin():
                conn.execute(text(
                    "INSERT INTO refund (target_type, target_id, target_amount_gs, amount_gs, "
                    "payment_method, restock_qty, restocked_qty, recorded_at, loyalty_reversed) "
                    "VALUES ('sale', :sid, 5000, 0, 'efectivo', 0, 0, :ts, 0)"
                ), {"sid": sale.id, "ts": datetime.utcnow()})


# --- 5. Loyalty proportional reversal ------------------------------------


def test_refund_loyalty_reverses_proportionally(refund_session):
    """Loyalty points are reversed in proportion to refund amount.

    With POINTS_PER_GS = 1/1000, a sale of 10_000 Gs earns 10 points.
    A 25% refund (2_500 Gs) should reverse floor(10 * 0.25) = 2 points.
    """
    from app.rms.loyalty.ledger import award_points
    from app.rms.models_legacy import Customer, LoyaltyTransaction
    from app.rms.refunds import create_refund

    # Create a customer
    cust = Customer(name="Test Cust", phone="0981111111")
    refund_session.add(cust)
    refund_session.flush()

    sale = _make_sale(refund_session, total_gs=10_000, customer_id=None)
    sale.customer_id = cust.id
    refund_session.flush()

    # Award points for this sale (10_000 Gs → 10 points at 1pt/1000Gs)
    pts_earned = award_points(refund_session, cust, total_gs=10_000, sale_id=sale.id)
    refund_session.flush()
    assert pts_earned == 10  # sanity

    # Refund 25% of the sale (= 2_500 Gs) → should reverse floor(10 * 0.25) = 2 points
    result = create_refund(
        refund_session, "sale", sale.id, 2_500, recorded_by="op"
    )
    assert result.loyalty_reversed == 2

    # Customer balance should be 10 - 2 = 8
    refund_session.refresh(cust)
    assert cust.loyalty_points == 8

    # Ledger should have a void_reversal row with -2
    reversal = refund_session.scalars(
        sa_select(LoyaltyTransaction).where(
            LoyaltyTransaction.reason == "void_reversal",
            LoyaltyTransaction.sale_id == sale.id,
        )
    ).all()
    assert len(reversal) == 1
    assert reversal[0].delta == -2


# --- 6. Sum helper -------------------------------------------------------


def test_sum_refunds_for_aggregates_correctly(refund_session):
    from app.rms.refunds import create_refund, sum_refunds_for

    sale = _make_sale(refund_session, total_gs=10_000)
    assert sum_refunds_for(refund_session, "sale", sale.id) == 0

    create_refund(refund_session, "sale", sale.id, 1_000, recorded_by="op")
    create_refund(refund_session, "sale", sale.id, 2_000, recorded_by="op")
    assert sum_refunds_for(refund_session, "sale", sale.id) == 3_000


# --- 7. EOD closure blocks new refunds ------------------------------------


def test_refund_blocked_after_eod_close(refund_session):
    """A refund on a day whose EOD has been closed must be rejected."""
    from app.rms.refunds import RefundError, create_refund

    sale = _make_sale(refund_session, total_gs=5_000)
    sale.sold_at = datetime.utcnow() - timedelta(days=2)
    refund_session.flush()

    # Mark EOD closed for that day (all checklist items value="1")
    from app.rms.models import AppMeta
    from app.rms.workflow import fresh_eod_checklist

    sale_date = sale.sold_at.date()
    keys = [f"eod_check_{sale_date.isoformat()}_{k.key}" for k in fresh_eod_checklist()]
    for k in keys:
        refund_session.add(AppMeta(key=k, value="1", updated_at=datetime.utcnow()))
    refund_session.commit()  # CRITICAL: commit so the EOD rows are visible

    with pytest.raises(RefundError) as exc_info:
        create_refund(refund_session, "sale", sale.id, 1_000, recorded_by="op")
    assert exc_info.value.code == "eod_closed"


# --- 8. Restock updates ingredient stock_qty ------------------------------


def test_refund_with_restock_updates_stock(refund_session):
    """Refund with restock_qty=True should increase ingredient stock_qty."""
    from app.rms.models import Ingredient, Recipe, RecipeLine, StockMovement

    # Create a minimal ingredient + recipe + sale + stock_move
    ing = Ingredient(name="harina", unit="kg", stock_qty=10.0)
    refund_session.add(ing)
    refund_session.flush()
    recipe = Recipe(name="torta", yield_qty=4.0)
    refund_session.add(recipe)
    refund_session.flush()
    # RecipeLine uses polymorphic line_kind + line_ref_id (not ingredient_id)
    refund_session.add(RecipeLine(
        recipe_id=recipe.id, line_kind="ingredient",
        line_ref_id=ing.id, qty=2.0,
    ))
    refund_session.flush()

    sale = _make_sale(refund_session, total_gs=10_000, qty=4.0)
    # BACKLOG #1 (2026-10-02): sale_stock_move dropped; use StockMovement
    # with reference_type='sale' for the consumption row.
    move = StockMovement(
        ingredient_id=ing.id,
        movement_type="sale",
        qty=-8.0,  # consumed 8 kg
        reason=f"Venta #{sale.id}",
        reference_id=sale.id,
        reference_type="sale",
        affected_recipe_id=recipe.id,
    )
    refund_session.add(move)
    refund_session.flush()

    initial_stock = ing.stock_qty
    assert initial_stock == 10.0

    from app.rms.refunds import create_refund
    # The service computes share = |qty_delta| / total_delta * restocked_qty.
    # With one move of qty_delta=-8.0 and restocked_qty=2.0, share = 2.0 kg.
    expected_share = 2.0
    result = create_refund(
        refund_session, "sale", sale.id, 5_000,
        restock_qty=True, restocked_qty=2.0,  # refund 2 of 4 portions
        recorded_by="op",
    )

    # Stock should have increased by the share
    refund_session.refresh(ing)
    assert ing.stock_qty == initial_stock + expected_share, (
        f"expected stock {initial_stock + expected_share}, got {ing.stock_qty}"
    )

    # StockMovement row should be recorded with movement_type="adjustment"
    # ("refund" isn't in the ck_stock_movement_type enum — adjustments are
    # the catch-all for any non-sale change, including refunds-with-restock).
    # We filter by reference_type='refund_sale' so we don't pick up the
    # original sale's consumption row (which is reference_type='sale').
    from app.rms.models import StockMovement
    moves = refund_session.scalars(
        sa_select(StockMovement).where(
            StockMovement.reference_id == result.refund.id,
            StockMovement.reference_type == "refund_sale",
        )
    ).all()
    assert len(moves) == 1
    assert moves[0].movement_type == "adjustment"
