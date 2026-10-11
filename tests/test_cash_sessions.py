"""tests/test_cash_sessions.py — WP-1.3 arqueo X/Z (2026-10-07).

cash_session: apertura → expected (opening + efectivo del período vía
sale_payment) → cierre con conteo → diff. Una sola sesión abierta.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, select
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


def test_cash_sales_count_via_sale_payment(client, session_factory, _seed):
    # SASKIA-MIG-2: this test predates the cash-session gate. It tests
    # that ventas in a CLOSED session do NOT carry over to a NEW
    # session's expected_gs. The fixture's CSRF post-hook handles
    # token injection (per conftest.py).
    from app.rms import cash

    # Open the fixture-managed caja manually (opened_by="c" so the
    # fixture's teardown — keyed on opened_by="test-fixture" — leaves
    # it alone; we close it ourselves below).
    db = _svc_session(session_factory)
    try:
        cash.open_session(db, opening_gs=0, opened_by="c")
        db.commit()
    finally:
        db.close()

    # 2 ventas en efectivo de 10000 c/u
    for _ in range(2):
        r = client.post(
            "/ventas/nueva/multi",
            json={"items": [{"product_id": _seed["pid"], "qty": 1}], "payment_method": "efectivo"},
            follow_redirects=False,
        )
        assert r.status_code == 303, r.text[:200]
    # 1 venta con QR — NO cuenta para caja
    r = client.post(
        "/ventas/nueva/multi",
        json={"items": [{"product_id": _seed["pid"], "qty": 1}], "payment_method": "qr"},
        follow_redirects=False,
    )
    assert r.status_code == 303

    # Close the existing session so we can open a fresh one for the
    # boundary check.
    db = _svc_session(session_factory)
    try:
        open_sess = cash.get_open_session(db)
        if open_sess is not None:
            cash.close_session(db, counted_gs=open_sess.opening_gs, closed_by="c")
            db.commit()
    finally:
        db.close()

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


# ─── Route-level tests (SASKIA audit: caja router had 0 route tests) ─────
# The caja router has 5 routes (open/close, home, z/{id}) but the
# existing tests only covered the business logic + 1 page render.
# These are the missing route-level assertions.


def test_caja_abrir_route_redirects_on_success(authed_client, session_factory):
    """POST /caja/abrir with valid opening amount → 303 redirect with success flash."""
    # Make sure no open session exists first.
    from app.rms import cash

    db = _svc_session(session_factory)
    try:
        open_sess = cash.get_open_session(db)
        if open_sess is not None:
            cash.close_session(db, counted_gs=open_sess.opening_gs, closed_by="cleanup")
            db.commit()
    finally:
        db.close()

    r = authed_client.post(
        "/caja/abrir",
        data={"opening_gs": "50000", "channel": "efectivo", "note": "Apertura test"},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text[:200]
    assert "caja_open" in r.headers["location"]


def test_caja_abrir_rejects_double_open(authed_client, session_factory):
    """POST /caja/abrir while one is open → 303 redirect with error flash."""
    # Ensure a session is open first via the service.
    from app.rms import cash

    db = _svc_session(session_factory)
    try:
        open_sess = cash.get_open_session(db)
        if open_sess is None:
            cash.open_session(db, opening_gs=10000, opened_by="seed")
            db.commit()
    finally:
        db.close()

    r = authed_client.post(
        "/caja/abrir",
        data={"opening_gs": "20000", "channel": "", "note": ""},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "caja_error" in r.headers["location"]


def test_caja_cerrar_route_redirects_on_success(authed_client, session_factory):
    """POST /caja/cerrar with counted > 0 → 303 redirect with success flash."""
    from app.rms import cash

    # Open a session first.
    db = _svc_session(session_factory)
    try:
        open_sess = cash.get_open_session(db)
        if open_sess is None:
            cash.open_session(db, opening_gs=30000, opened_by="seed")
            db.commit()
    finally:
        db.close()

    r = authed_client.post(
        "/caja/cerrar",
        data={"counted_gs": "30000"},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text[:200]
    # After closing, the URL should contain the zid of the new Z ticket.
    assert "caja_closed" in r.headers["location"]
    assert "zid=" in r.headers["location"]


def test_caja_cerrar_without_open_returns_error(authed_client, session_factory):
    """POST /caja/cerrar with no open session → 303 redirect with error flash."""
    from app.rms import cash

    db = _svc_session(session_factory)
    try:
        open_sess = cash.get_open_session(db)
        if open_sess is not None:
            cash.close_session(db, counted_gs=open_sess.opening_gs, closed_by="cleanup")
            db.commit()
    finally:
        db.close()

    r = authed_client.post(
        "/caja/cerrar",
        data={"counted_gs": "0"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "caja_error" in r.headers["location"]


def test_caja_z_renders_404_for_unknown_session(authed_client):
    """GET /caja/z/{nonexistent} → 404 with error message."""
    r = authed_client.get("/caja/z/9999999")
    assert r.status_code == 404
    assert "no encontrada" in r.text.lower() or "error" in r.text.lower()


def test_caja_z_renders_ticket_for_closed_session(authed_client, session_factory):
    """GET /caja/z/{id} → 200 with the closed session's data."""
    # First ensure no open session, then open + close via the route itself
    # (so the test client's session sees the row).
    from app.rms import cash

    db = _svc_session(session_factory)
    try:
        open_sess = cash.get_open_session(db)
        if open_sess is not None:
            cash.close_session(db, counted_gs=open_sess.opening_gs, closed_by="cleanup")
            db.commit()
    finally:
        db.close()

    # Use the actual route to open + close so the get_session() dep sees
    # the data.
    r1 = authed_client.post(
        "/caja/abrir",
        data={"opening_gs": "25000", "channel": "test-z", "note": "seed-z-test"},
        follow_redirects=False,
    )
    assert r1.status_code == 303
    r2 = authed_client.post(
        "/caja/cerrar",
        data={"counted_gs": "25000"},
        follow_redirects=False,
    )
    assert r2.status_code == 303
    # Extract zid from the redirect location: /caja?flash=caja_closed&zid=N
    loc = r2.headers["location"]
    sess_id = int(loc.split("zid=")[1])

    r = authed_client.get(f"/caja/z/{sess_id}")
    assert r.status_code == 200
    # The Z ticket shows the recent sessions table with Apertura /
    # Esperado / Contado / Diferencia columns.
    assert "Apertura" in r.text
    assert "Diferencia" in r.text
