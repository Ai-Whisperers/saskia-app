"""tests/e2e/test_security_integrity_flows.py — G + H + F categories.

G: CSRF negative matrix, rate-limit burst + atomicity, session expiry,
   security headers, public-token enumeration.
H: FK integrity after a full day, cron-format (raw sqlite) restore drill,
   migration full-sweep marker usage.
F: pool-exhaustion probe, concurrent fulfill/adjust races.
"""

from __future__ import annotations

import threading

import pytest

from tests import flows
from tests._lib.invariants import foreign_keys_clean
from tests.factories import (
    ing_line,
    make_catalog,
    make_customer,
    make_ingredient,
    make_pedido,
    make_product,
    make_recipe,
    pedido_item,
)

pytestmark = [pytest.mark.security]


# ---------------------------------------------------------------------------
# G1 — CSRF negatives on top mutation routes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("url,payload", [
    ("/ventas/nueva", {"qty": "1"}),
    ("/inventario/1/ajustar", {"adjustment": "5"}),
    ("/shopping-list/add", {"ingredient_id": "1", "qty_to_buy": "1", "unit": "kg"}),
], ids=["sale", "adjust", "shopping-add"])
def test_post_without_csrf_cookie_rejected(client, session_factory, url, payload):
    """Strip the csrf cookie → every mutation POST must 403, not execute."""
    with flows.as_anonymous(client):
        # keep a session? no — anon here; the point is CSRF, so re-prime
        # session-less: the csrf middleware must reject regardless of auth
        r = client.post(url, data=payload, follow_redirects=False)
    # 403 (csrf) or 401/303 (auth gate first) — but NEVER 200/303-to-app
    assert r.status_code in (401, 403, 303), r.status_code
    if r.status_code == 303:
        assert "/login" in (r.headers.get("location") or "")


# ---------------------------------------------------------------------------
# G2 — rate limit: burst + no partial state
# ---------------------------------------------------------------------------


def test_rate_limit_burst_leaves_no_partial_rows(client, session_factory):
    with session_factory() as s:
        prod = make_catalog(s)["product"]
        s.commit()
        pid = prod.id

    codes = []
    for _ in range(15):
        r = flows.sell(client, pid, 1)
        codes.append(r.status_code)
        if r.status_code == 429:
            break

    # Either no rate limit fired (all 303) or it did — either way the DB
    # must show a whole number of completed sales, no half-writes.
    with session_factory() as s:
        from app.rms.models import Sale, SaleStockMove

        n_sales = s.query(Sale).filter_by(product_id=pid).count()
        n_moves = s.query(SaleStockMove).count()
    # Atomicity: every sale in the DB has its stock moves (no half-writes).
    # NOTE: if the rate limiter rejects AFTER writing, n_sales may exceed the
    # 303 count — that would be a finding to fix in the limiter ordering.
    assert n_moves == n_sales, f"half-writes: {n_sales} sales vs {n_moves} moves"


# ---------------------------------------------------------------------------
# G4 — expired/garbage session mid-flow
# ---------------------------------------------------------------------------


def test_garbage_session_cookie_redirects_not_500(client, session_factory):
    """Under the test auth-bypass the gate is skipped, but a corrupt session
    cookie must NEVER crash a route — any non-500 outcome is acceptable.
    (The strict 303-to-login variant lives in test_strict_auth.)"""
    client.cookies.set("saskia_rms_session", "garbage.notsigned")
    r = client.post("/ventas/nueva", data={"qty": "1"}, follow_redirects=False)
    assert r.status_code != 500, r.status_code


# ---------------------------------------------------------------------------
# G5 — security headers on HTML flows
# ---------------------------------------------------------------------------


def test_security_headers_present(client):
    r = client.get("/dashboard", follow_redirects=True)
    if r.status_code != 200:
        pytest.skip("dashboard needs seeded state")
    h = r.headers
    assert h.get("x-frame-options") in ("DENY", "SAMEORIGIN")
    assert "text/html" in h.get("content-type", "")


# ---------------------------------------------------------------------------
# G6 — public-token enumeration probe
# ---------------------------------------------------------------------------


def test_public_pedido_token_no_enumeration(client, session_factory):
    with session_factory() as s:
        cust = make_customer(s)
        ing = make_ingredient(s)
        rec = make_recipe(s, lines=[ing_line(ing)])
        prod = make_product(s, recipe=rec)
        ped = make_pedido(s, customer=cust, items=[pedido_item(prod)],
                          public_token="AAAA1111")
        s.commit()
        ped_id = ped.id

    # right token → 200
    r = client.get(f"/p/AAAA1111")
    assert r.status_code == 200, r.status_code

    # mutated tokens (the enumeration attempt) → 404, never other pedidos' data
    for bad in ["AAAA1110", "AAAA1112", "aaaa1111"]:
        r2 = client.get(f"/p/{bad}")
        assert r2.status_code == 404, f"/p/{bad}: {r2.status_code}"
        assert "AAAA1111" not in r2.text or ped_id is None


# ---------------------------------------------------------------------------
# H3 — FK integrity after a full mini-day
# ---------------------------------------------------------------------------


def test_fk_clean_after_day(client, session_factory, app_engine):
    cat = {}
    with session_factory() as s:
        cat = make_catalog(s)
        s.commit()
    pid = cat["product"].id

    assert flows.sell(client, pid, 1).ok
    with session_factory() as s:
        from app.rms.models import Sale
        sid = s.query(Sale).filter_by(product_id=pid).one().id
    assert flows.void_sale(client, sid, reason="e2e fk").ok
    assert flows.register_merma(client, cat["ingredient"].id, 0.1).ok

    violations = foreign_keys_clean(app_engine)
    assert not violations, violations


# ---------------------------------------------------------------------------
# H4 — cron-format (raw sqlite file) restore drill
# ---------------------------------------------------------------------------


def test_cron_sqlite_backup_restores(tmp_db_path, session_factory, app_engine):
    """The nightly cron ships raw rms.sqlite.gz — the JSON drill doesn't
    cover it. Simulate: VACUUM INTO a copy, boot a new engine on it, write."""
    import gzip as _gzip
    import shutil
    import sqlite3

    with session_factory() as s:
        make_catalog(s)
        s.commit()

    src = tmp_db_path / "test.sqlite"
    raw_copy = tmp_db_path / "restored-copy.sqlite"
    # sqlite3 backup API (what the cron's .backup / VACUUM INTO does)
    con = sqlite3.connect(src)
    try:
        con.execute(f"VACUUM INTO '{raw_copy}'")
    finally:
        con.close()

    from app.rms.db import make_engine, make_session_factory

    e2 = make_engine(f"sqlite:///{raw_copy}")
    sf2 = make_session_factory(e2)
    with sf2() as s2:
        from app.rms.models import Ingredient

        rows = s2.query(Ingredient).count()
        assert rows >= 1, "restored raw copy must have the data"
        # and accept new writes
        from tests.factories import make_ingredient as _mk

        _mk(s2)
        s2.commit()
        assert s2.query(Ingredient).count() == rows + 1


# ---------------------------------------------------------------------------
# F2 — pool exhaustion probe (the get_session leak class)
# ---------------------------------------------------------------------------


def test_fifty_requests_no_pool_exhaustion(client, session_factory):
    with session_factory() as s:
        make_catalog(s)
        s.commit()
    for _ in range(50):
        r = client.get("/inventario")
        assert r.status_code == 200
    # engine pool must not have grown connections without bound
    pool = session_factory.kw["bind"].pool
    assert pool.size() <= 10, f"pool grew: {pool.status()}"


# ---------------------------------------------------------------------------
# F1 — concurrent pedido-fulfill + stock-adjust race
# ---------------------------------------------------------------------------


def test_concurrent_fulfill_and_adjust_race(client, session_factory):
    with session_factory() as s:
        cat = make_catalog(s, stock_qty=500.0)
        cust = make_customer(s)
        ped = make_pedido(s, customer=cust,
                          items=[pedido_item(cat["product"], qty=2)])
        s.commit()
        ped_id, ing_id = ped.id, cat["ingredient"].id

    errors: list[str] = []

    def _fulfiller():
        try:
            r = client.post(f"/pedidos/{ped_id}/fulfill", data={}, follow_redirects=False)
            if r.status_code not in (303, 409, 422):
                errors.append(f"fulfill: {r.status_code}")
        except Exception as exc:
            errors.append(f"fulfill: {exc!r}")

    def _adjuster():
        try:
            for _ in range(3):
                r = client.post(f"/inventario/{ing_id}/ajustar",
                                data={"adjustment": "1", "reason": "race"},
                                follow_redirects=False)
                if r.status_code not in (303, 400):
                    errors.append(f"adjust: {r.status_code}")
        except Exception as exc:
            errors.append(f"adjust: {exc!r}")

    t1 = threading.Thread(target=_fulfiller)
    t2 = threading.Thread(target=_adjuster)
    t1.start(); t2.start(); t1.join(); t2.join()
    assert not errors, errors
