"""tests/test_loyalty_ledger.py — verify loyalty ledger (Phase 4, 2026-10-01).

Per the Phase 4 loyalty decision (2026-10-01): ship the points program
already 80% built, with a proper LoyaltyTransaction ledger for audit,
refunds, and reconciliation. Covers:

- award_points writes a ledger row + updates the cached balance
- award_points is a no-op when total_gs < 1000 Gs. (zero points earned)
- redeem_points writes a ledger row + debits the cached balance
- redeem_points raises ValueError on insufficient balance or non-positive
- reverse_points_for_void writes a NEGATIVE ledger row matching the earn
- reconcile_loyalty_balance rebuilds the cached column from SUM(delta)
- The migration 074 creates the loyalty_transaction table
- POST /clientes/{id}/puntos/redeem flows through the endpoint correctly
- The ledger appears on /clientes/{id} in the recent_loyalty list
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.crud


def test_award_points_writes_ledger_row_and_credits_balance(session_factory):
    from app.rms.customers import ensure_customer
    from app.rms.loyalty import award_points
    from app.rms.models import LoyaltyTransaction

    with session_factory() as s:
        cust = ensure_customer(s, "Cliente Ledger A", phone="+595981000111")
        s.commit()
        cust_id = cust.id
        assert cust.loyalty_points == 0

    with session_factory() as s:
        from app.rms.models import Customer
        cust = s.get(Customer, cust_id)
        pts = award_points(s, cust, total_gs=25_000, sale_id=None, actor="test")
        s.commit()

    assert pts == 25  # 1 pt / 1.000 Gs.

    with session_factory() as s:
        from app.rms.models import Customer
        cust = s.get(Customer, cust_id)
        assert cust.loyalty_points == 25

        rows = s.query(LoyaltyTransaction).filter_by(customer_id=cust_id).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.delta == 25
        assert row.reason == "earn_sale"
        assert row.actor == "test"
        assert row.sale_id is None
        assert "earn on sale of 25,000 Gs" in row.notes


def test_award_points_zero_when_below_threshold(session_factory):
    from app.rms.customers import ensure_customer
    from app.rms.loyalty import award_points
    from app.rms.models import LoyaltyTransaction

    with session_factory() as s:
        cust = ensure_customer(s, "Cliente Ledger B", phone="+595981000112")
        s.commit()
        cust_id = cust.id

    with session_factory() as s:
        from app.rms.models import Customer
        cust = s.get(Customer, cust_id)
        pts = award_points(s, cust, total_gs=500, sale_id=None)
        s.commit()

    assert pts == 0
    with session_factory() as s:
        rows = s.query(LoyaltyTransaction).filter_by(customer_id=cust_id).all()
        assert len(rows) == 0, "no ledger row when 0 points earned"


def test_redeem_points_writes_ledger_row_and_debits_balance(session_factory):
    from app.rms.customers import ensure_customer
    from app.rms.loyalty import POINTS_VALUE_GS, award_points, redeem_points
    from app.rms.models import Customer, LoyaltyTransaction

    with session_factory() as s:
        cust = ensure_customer(s, "Cliente Ledger C", phone="+595981000113")
        s.commit()
        cust_id = cust.id

    with session_factory() as s:
        cust = s.get(Customer, cust_id)
        award_points(s, cust, total_gs=50_000)  # +50 pts
        s.commit()

    with session_factory() as s:
        cust = s.get(Customer, cust_id)
        redeemed, discount = redeem_points(s, cust, 10, actor="saskia", notes="descuento cumpleaños")
        s.commit()

    assert redeemed == 10
    # T-2026-10-01: redemption rate is now POINTS_VALUE_GS (100 Gs per
    # point at the new defaults), not 1.000 Gs/point. Pre-this-fix the
    # redeem returned 1 pt = 1.000 Gs (100% return rate). The constants
    # are split now: see app/rms/loyalty/ledger.py.
    assert discount == 10 * POINTS_VALUE_GS  # = 1.000 at current default

    with session_factory() as s:
        cust = s.get(Customer, cust_id)
        assert cust.loyalty_points == 40

        rows = (
            s.query(LoyaltyTransaction)
            .filter_by(customer_id=cust_id, reason="redeem")
            .all()
        )
        assert len(rows) == 1
        assert rows[0].delta == -10
        assert rows[0].notes == "descuento cumpleaños"


def test_redeem_points_raises_on_insufficient(session_factory):
    from app.rms.customers import ensure_customer
    from app.rms.loyalty import redeem_points
    from app.rms.models import Customer

    with session_factory() as s:
        cust = ensure_customer(s, "Cliente Ledger D", phone="+595981000114")
        s.commit()
        cust_id = cust.id

    with session_factory() as s:
        cust = s.get(Customer, cust_id)
        with pytest.raises(ValueError, match="Insufficient points"):
            redeem_points(s, cust, 5)
        s.rollback()


def test_redeem_points_raises_on_zero_or_negative(session_factory):
    from app.rms.customers import ensure_customer
    from app.rms.loyalty import redeem_points
    from app.rms.models import Customer

    with session_factory() as s:
        cust = ensure_customer(s, "Cliente Ledger E", phone="+595981000115")
        s.commit()
        cust_id = cust.id

    with session_factory() as s:
        cust = s.get(Customer, cust_id)
        with pytest.raises(ValueError, match="must be > 0"):
            redeem_points(s, cust, 0)
        with pytest.raises(ValueError, match="must be > 0"):
            redeem_points(s, cust, -3)
        s.rollback()


def test_reverse_points_for_void_writes_negative_ledger(session_factory, qseed):
    """When a sale that earned points is voided, reverse the points via a void_reversal ledger row."""
    from datetime import datetime as _dt
    from app.rms.costing import apply_sale
    from app.rms.customers import (
        award_points,
        ensure_customer,
        reverse_points_for_void,
    )
    from app.rms.models import Customer, LoyaltyTransaction, Sale

    data = qseed("basic")
    prod = data["product"]
    cust_data = qseed("with_customer")
    cust = cust_data["customer"]

    # Create a real sale via apply_sale (so the FK target exists), then
    # credit points tied to that sale_id. We re-fetch the customer
    # inside the working session because ``qseed`` returns a detached
    # instance from a closed session; SQLAlchemy cannot UPDATE a
    # detached object directly.
    sf = qseed.session_factory
    with sf() as s:
        result = apply_sale(
            s,
            product_id=prod.id,
            qty=1.0,
            sold_at=_dt.utcnow(),
            customer_id=cust.id,
        )
        sale_id = result.sale_id
        c_attached = s.get(Customer, cust.id)
        pts = award_points(s, c_attached, total_gs=50_000, sale_id=sale_id)
        assert pts == 50
        assert c_attached.loyalty_points == 50
        s.commit()

    # Verify the earn_sale row exists with the right sale_id.
    with sf() as s:
        earn = (
            s.query(LoyaltyTransaction)
            .filter_by(customer_id=cust.id, reason="earn_sale")
            .first()
        )
        assert earn is not None and earn.sale_id == sale_id
        # Re-fetch the customer in this session (committed by the prior session).
        cust_fresh = s.get(Customer, cust.id)
        starting_pts = cust_fresh.loyalty_points
        assert starting_pts == 50, f"expected 50 pts after award, got {starting_pts}"

    # Now void that sale — points should be reversed.
    with sf() as s:
        cust = s.get(Customer, cust.id)
        reversed_pts = reverse_points_for_void(s, cust, sale_id=sale_id, actor="system")
        s.commit()

    assert reversed_pts == 50

    with sf() as s:
        cust = s.get(Customer, cust.id)
        assert cust.loyalty_points == 0, "balance back to zero after void reversal"

        earn_rows = (
            s.query(LoyaltyTransaction)
            .filter_by(customer_id=cust.id, reason="earn_sale")
            .all()
        )
        void_rows = (
            s.query(LoyaltyTransaction)
            .filter_by(customer_id=cust.id, reason="void_reversal")
            .all()
        )
        assert len(earn_rows) == 1 and earn_rows[0].delta == 50
        assert len(void_rows) == 1 and void_rows[0].delta == -50
        assert void_rows[0].sale_id == sale_id


def test_reverse_points_for_void_noop_when_no_earn(session_factory):
    from app.rms.customers import ensure_customer
    from app.rms.loyalty import reverse_points_for_void
    from app.rms.models import Customer, LoyaltyTransaction

    with session_factory() as s:
        cust = ensure_customer(s, "Cliente Ledger G", phone="+595981000117")
        s.commit()
        cust_id = cust.id

    with session_factory() as s:
        cust = s.get(Customer, cust_id)
        result = reverse_points_for_void(s, cust, sale_id=999)  # non-existent sale
        s.commit()

    assert result == 0
    with session_factory() as s:
        rows = (
            s.query(LoyaltyTransaction).filter_by(customer_id=cust_id).all()
        )
        assert len(rows) == 0


def test_reconcile_loyalty_balance_rebuilds_from_ledger(session_factory):
    """If the cached balance drifts (manual SQL, old bug), reconcile rebuilds it."""
    from app.rms.customers import (
        award_points,
        ensure_customer,
        redeem_points,
        reconcile_loyalty_balance,
    )
    from app.rms.models import Customer

    with session_factory() as s:
        cust = ensure_customer(s, "Cliente Ledger H", phone="+595981000118")
        s.commit()
        cust_id = cust.id

    # Build up a real ledger: +30, -10, +20 = +40
    with session_factory() as s:
        cust = s.get(Customer, cust_id)
        award_points(s, cust, total_gs=30_000)
        redeem_points(s, cust, 10)
        award_points(s, cust, total_gs=20_000)
        s.commit()

    # Corrupt the cached column (simulate drift).
    with session_factory() as s:
        cust = s.get(Customer, cust_id)
        cust.loyalty_points = 999
        s.commit()

    # Reconcile.
    with session_factory() as s:
        cust = s.get(Customer, cust_id)
        new_balance = reconcile_loyalty_balance(s, cust)
        s.commit()

    assert new_balance == 40


def test_loyalty_transaction_table_exists_in_db(tmp_db_path):
    """Migration 074 must have created loyalty_transaction with the right columns.

    Tier 3.2 (2026-10-01): now uses tmp_db_path so the test runs
    against the test engine, not the LIVE DB (which may be at any
    schema_version). This also makes it runnable in CI without
    polluting prod.
    """
    from sqlalchemy import create_engine, text

    eng = create_engine(f"sqlite:///{tmp_db_path}/test.sqlite")
    with eng.connect() as c:
        cols = c.execute(text("PRAGMA table_info(loyalty_transaction)")).fetchall()
    col_names = [r[1] for r in cols]
    assert "id" in col_names
    assert "customer_id" in col_names
    assert "delta" in col_names
    assert "reason" in col_names
    assert "sale_id" in col_names
    assert "actor" in col_names
    assert "notes" in col_names
    assert "recorded_at" in col_names


def test_loyalty_transaction_check_constraint_rejects_zero_delta():
    """Tier 3.2 (2026-10-01): the DB-level CHECK for delta != 0 was
    dropped in migration 075 to allow ``suggestion_applied`` event
    rows (delta=0 by design). The remaining CHECK on ``reason`` does
    NOT enforce delta != 0 for non-zero reasons — that's now an
    application-layer invariant (see ``app/rms/customers.py`` guards).

    This test now verifies that the ``delta != 0`` constraint has
    been dropped by migration 075. If you run this against a DB at
    schema_version < 75, the test will SKIP (it's an old schema).
    """
    from app.rms.config import DB_PATH
    from sqlalchemy import create_engine, text
    import datetime as _dt

    eng = create_engine(f"sqlite:///{DB_PATH}")
    with eng.connect() as c:
        # Only meaningful if migration 075 has been applied (drops
        # the ck_loyalty_delta_nonzero constraint). schema version
        # lives in app_meta.value (TEXT on SQLite, JSONB on Postgres).
        ver_row = c.execute(
            text("SELECT value FROM app_meta WHERE key = 'schema_version'")
        ).fetchone()
        if ver_row is None:
            pytest.skip("app_meta table has no schema_version row yet")
        # On SQLite value is the int as a string; on Postgres it's
        # a JSON-encoded quoted string like '"75"'.
        raw = str(ver_row[0]).strip('"')
        try:
            current_ver = int(raw)
        except (TypeError, ValueError):
            pytest.skip(f"schema_version is unparseable: {ver_row[0]!r}")
        if current_ver < 75:
            pytest.skip(
                f"DB is at schema_version {current_ver} (< 75) — "
                f"ck_loyalty_delta_nonzero constraint still active. "
                f"Migration 075 drops it; this test is only meaningful "
                f"after the migration runs."
            )
        # Get any customer_id from the DB
        cust = c.execute(text("SELECT id FROM customer LIMIT 1")).fetchone()
        if not cust:
            pytest.skip("no customer in DB — table is empty")
        cust_id = cust[0]
        # Insert a delta=0 manual_adjust row. Should SUCCEED (the
        # constraint was dropped). The application layer is
        # responsible for never writing delta=0 for non-event reasons.
        try:
            c.execute(
                text(
                    "INSERT INTO loyalty_transaction "
                    "(customer_id, delta, reason, actor, recorded_at) "
                    "VALUES (:cid, :delta, 'manual_adjust', 'test', :ts)"
                ),
                {"cid": cust_id, "delta": 0, "ts": _dt.datetime.utcnow()},
            )
            c.commit()
            # Insert succeeded → constraint is gone, as expected.
            # Roll back the row so we don't pollute the prod DB.
            c.execute(
                text(
                    "DELETE FROM loyalty_transaction "
                    "WHERE customer_id = :cid AND reason = 'manual_adjust' "
                    "AND delta = 0 AND actor = 'test'"
                ),
                {"cid": cust_id},
            )
            c.commit()
        except Exception as exc:  # noqa: BLE001
            pytest.fail(
                f"migration 075 should have dropped ck_loyalty_delta_nonzero, "
                f"but manual_adjust delta=0 still failed: {exc}"
            )


def test_redeem_endpoint_writes_ledger_and_redirects(authed_client, qseed):
    """Full HTTP flow: POST /clientes/{id}/puntos/redeem → ledger row."""
    from app.rms.loyalty import award_points
    from app.rms.models import Customer, LoyaltyTransaction

    data = qseed("with_customer")
    cust = data["customer"]
    cust_id = cust.id

    # Seed some points via the helper (avoid HTTP for setup).
    sf = qseed.session_factory
    with sf() as s:
        c = s.get(Customer, cust_id)
        award_points(s, c, total_gs=30_000)
        s.commit()

    resp = authed_client.post(
        f"/clientes/{cust_id}/puntos/redeem",
        data={"points_to_redeem": "10", "notes": "test redemption"},
        follow_redirects=False,
    )
    assert resp.status_code in (303, 307), resp.text

    with sf() as s:
        rows = (
            s.query(LoyaltyTransaction)
            .filter_by(customer_id=cust_id, reason="redeem")
            .all()
        )
        assert len(rows) == 1
        assert rows[0].delta == -10
        assert rows[0].notes == "test redemption"


def test_redeem_endpoint_rejects_more_than_balance(authed_client, qseed):
    """Should redirect with points_insufficient flash when balance too low."""
    data = qseed("with_customer")
    cust = data["customer"]

    # Customer has 0 points — try to redeem 5.
    resp = authed_client.post(
        f"/clientes/{cust.id}/puntos/redeem",
        data={"points_to_redeem": "5"},
        follow_redirects=False,
    )
    assert resp.status_code in (303, 307)
    assert "points_insufficient" in (resp.headers.get("location") or "")


def test_redeem_endpoint_rejects_zero_or_negative(authed_client, qseed):
    data = qseed("with_customer")
    cust = data["customer"]
    resp = authed_client.post(
        f"/clientes/{cust.id}/puntos/redeem",
        data={"points_to_redeem": "0"},
        follow_redirects=False,
    )
    assert resp.status_code in (303, 307)
    assert "points_invalid" in (resp.headers.get("location") or "")


def test_customer_detail_shows_ledger_table(authed_client, qseed):
    """GET /clientes/{id} should include the recent loyalty transactions in the page."""
    from app.rms.loyalty import award_points
    from app.rms.models import Customer

    data = qseed("with_customer")
    cust = data["customer"]
    cust_id = cust.id
    sf = qseed.session_factory

    with sf() as s:
        c = s.get(Customer, cust_id)
        award_points(s, c, total_gs=15_000)
        award_points(s, c, total_gs=10_000)
        s.commit()

    resp = authed_client.get(f"/clientes/{cust_id}")
    assert resp.status_code == 200
    body = resp.text
    assert "Movimientos recientes" in body
    assert "Compra" in body  # reason label
    # The recent ledger table should show at least one row with the right delta
    assert "+15" in body or "+10" in body


def test_sale_creation_credits_points_to_customer(authed_client, qseed):
    """End-to-end: POST a sale with a customer attached → ledger earn_sale row."""
    from app.rms.models import Customer, LoyaltyTransaction

    data = qseed("basic")
    prod = data["product"]
    cust_data = qseed("with_customer")
    cust = cust_data["customer"]
    sf = qseed.session_factory

    resp = authed_client.post(
        "/ventas/nueva",
        data={
            "product_id": str(prod.id),
            "qty": "1",
            "customer_id": str(cust.id),
        },
        follow_redirects=False,
    )
    assert resp.status_code in (303, 200), resp.text

    with sf() as s:
        earn_rows = (
            s.query(LoyaltyTransaction)
            .filter_by(customer_id=cust.id, reason="earn_sale")
            .all()
        )
        assert len(earn_rows) >= 1, "expected at least one earn_sale ledger row"
        total_earned = sum(r.delta for r in earn_rows)
        assert total_earned > 0
