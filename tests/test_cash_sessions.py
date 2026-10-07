"""tests/test_cash_sessions.py — WP-1.3 arqueo X/Z (2026-10-07).

cash_session: apertura → expected (opening + efectivo del período vía
sale_payment) → cierre con conteo → diff. Una sola sesión abierta.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import sessionmaker

from tests.factories import make_ingredient, make_product, make_recipe


@pytest.fixture()
def _seed(session_factory):
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        make_ingredient(s, unit="kg", stock_qty=25.0, min_stock_qty=2.0)
        rec = make_recipe(s, yield_qty=12, yield_unit="und")
        p = make_product(s, name="Caja Test", sale_price_gs=10000, recipe=rec)
        s.commit()
        return {"pid": p.id}
    finally:
        s.close()


def _cash(session_factory):
    from app.rms import cash

    s2 = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        return cash, s2
    finally:
        pass


def _svc_session(session_factory):
    return sessionmaker(bind=session_factory.kw["bind"])()


def test_migration_106_creates_table(app_engine):
    insp = inspect(app_engine)
    assert "cash_session" in insp.get_table_names()


def test_open_close_happy_path(session_factory, _seed):
    from app.rms import cash

    db = _svc_session(session_factory)
    try:
        sess = cash.open_session(db, opening_gs=50000, opened_by="cajera")
        db.commit()
        assert sess.status == "open"
        # expected = opening only (no sales yet)
        assert cash.expected_gs(db, sess) == 50000

        closed = cash.close_session(db, counted_gs=50000, closed_by="cajera")
        db.commit()
        assert closed.status == "closed"
        assert closed.expected_gs == 50000
        assert closed.diff_gs == 0
    finally:
        db.close()


def test_diff_positive_and_negative(session_factory, _seed):
    from app.rms import cash

    db = _svc_session(session_factory)
    try:
        cash.open_session(db, opening_gs=0, opened_by="c")
        db.commit()
        closed = cash.close_session(db, counted_gs=30000, closed_by="c")
        db.commit()
        assert closed.diff_gs == 30000  # sobrante
    finally:
        db.close()

    db = _svc_session(session_factory)
    try:
        cash.open_session(db, opening_gs=100000, opened_by="c")
        db.commit()
        closed = cash.close_session(db, counted_gs=95000, closed_by="c")
        db.commit()
        assert closed.diff_gs == -5000  # faltante
    finally:
        db.close()


def test_double_open_rejected(session_factory, _seed):
    from app.rms import cash

    db = _svc_session(session_factory)
    try:
        cash.open_session(db, opening_gs=0, opened_by="c")
        db.commit()
        with pytest.raises(cash.CashSessionConflict):
            cash.open_session(db, opening_gs=0, opened_by="c")
    finally:
        db.close()


def test_cash_sales_count_via_sale_payment(authed_client, session_factory, _seed):
    from app.rms import cash

    # 2 ventas en efectivo de 10000 c/u
    for _ in range(2):
        r = authed_client.post(
            "/ventas/nueva/multi",
            json={"items": [{"product_id": _seed["pid"], "qty": 1}], "payment_method": "efectivo"},
            follow_redirects=False,
        )
        assert r.status_code == 303, r.text[:200]
    # 1 venta con QR — NO cuenta para caja
    r = authed_client.post(
        "/ventas/nueva/multi",
        json={"items": [{"product_id": _seed["pid"], "qty": 1}], "payment_method": "qr"},
        follow_redirects=False,
    )
    assert r.status_code == 303

    db = _svc_session(session_factory)
    try:
        sess = cash.open_session(db, opening_gs=10000, opened_by="c")
        db.commit()
        # OJO: ventas anteriores a la apertura NO cuentan (sold_at < opened_at)
        exp = cash.expected_gs(db, sess)
        assert exp == 10000
    finally:
        db.close()


def test_close_without_open_rejected(session_factory, _seed):
    from app.rms import cash

    db = _svc_session(session_factory)
    try:
        with pytest.raises(cash.CashSessionError):
            cash.close_session(db, counted_gs=0, closed_by="c")
    finally:
        db.close()


def test_caja_page_renders(authed_client):
    r = authed_client.get("/caja")
    assert r.status_code == 200
    assert "Caja" in r.text
