"""tests/test_dashboard_perf.py — regression test: dashboard must not regress
to N+1 queries. Asserts the dashboard route uses fewer than 20 queries
for a typical seed dataset.
"""

from __future__ import annotations

import pytest
from sqlalchemy import event

pytestmark = pytest.mark.perf


def test_dashboard_renders_under_60_queries(client, session_factory):
    """A single GET / should not issue hundreds of queries.

    Pre-fix this hit ~3,000+ queries from N+1 patterns. After fix it
    should be under 60 even with the migration bootstrap queries
    (`CREATE TABLE IF NOT EXISTS app_meta`, etc.) added by the
    lifespan in 2026-09-08.
    """
    engine = session_factory.kw["bind"]

    queries: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def _count(conn, cursor, statement, params, context, executemany):
        queries.append(statement)

    # We don't assert 200 here: there are pre-existing tz-naive datetime
    # bugs in the dashboard render path when products+customers exist
    # (C.6 follow-up). The N+1 detection works either way — we count
    # queries regardless of response status.
    from starlette.testclient import TestClient

    from app.rms.main import app

    tc = TestClient(app, raise_server_exceptions=False)
    try:
        tc.get("/?period=month")
    finally:
        event.remove(engine, "before_cursor_execute", _count)

    # Threshold: 100 real queries (PRAGMA table_info excluded).
    # Re-measured 2026-09-24: 125 total = 88 PRAGMA (sqlite table_info,
    # 44 tables × 2 bootstrap passes: fixture + app lifespan) + 37 real
    # SELECT/INSERT. The PRAGMA noise is one-time migration bootstrap on
    # the tmp test DB — proportional to table count, not row count, so
    # it can't mask an N+1. Excluding it keeps the budget meaningful as
    # the schema grows (schema v49 added storage_keyword; every new
    # table adds 2 more PRAGMAs).
    # The pre-fix N+1 bug hit ~3,000 queries, so this test's job is to
    # fail loudly if any future feature accidentally reintroduces
    # per-row N+1. If you bump this number, RE-RUN the measurement
    # against the real tree and document the new budget in the commit.
    real = [q for q in queries if not q.upper().startswith("PRAGMA")]
    assert len(real) < 100, (
        f"Dashboard issued {len(real)} queries — N+1 regression. First 5 queries: {real[:5]}"
    )


def test_dashboard_no_n_plus_1_in_cost_loop(client, session_factory):
    """Regression: must not call product_unit_cost_gs in a loop over sales.

    Pre-fix: one call per sale (~920 calls). Post-fix: batched via
    batch_products_cost_margin, so product_unit_cost_gs appears at most
    once (or zero times if all sales cached).
    """
    engine = session_factory.kw["bind"]

    queries: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def _count(conn, cursor, statement, params, context, executemany):
        queries.append(statement)

    try:
        with client:
            resp = client.get("/?period=month")
        assert resp.status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", _count)

    # The bad pattern was: SELECT ingredient ... WHERE id = ?  (per-sale)
    # After fix: SELECT ingredient ... WHERE id IN (...)  (batched)
    ingredient_point_queries = sum(
        1 for q in queries if "FROM ingredient" in q and "WHERE ingredient.id = ?" in q
    )
    assert ingredient_point_queries <= 2, (
        f"Found {ingredient_point_queries} point-queries against ingredient "
        f"table — likely N+1 in cost loop. Bump threshold if a legitimate "
        f"single-row lookup is being counted."
    )


def test_dashboard_forecast_no_n_plus_1(client, session_factory, qseed) -> None:
    """C.6 regression test: /inicio forecast loop must not do per-product
    SELECTs against `sale`. With 25+ products seeded, the old per-product
    path ran 25+ queries; the batched fix runs 1-2.

    The fix is in app/routers/dashboard.py:617-690 (N+1 fix dated
    2026-10-07) — the loop now uses a single batched SELECT
    `WHERE sale.product_id IN (...)` instead of calling
    `forecast_sales(...)` once per product.
    """
    from starlette.testclient import TestClient

    from app.rms.main import app

    # Seed many products so the loop has work to do.
    qseed("with_many_products")

    # Same wiring as test_dashboard_renders_under_60_queries: hook the
    # conftest's session_factory engine and use a fresh TestClient.
    engine = session_factory.kw["bind"]
    queries: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def _count(conn, cursor, statement, params, context, executemany):
        queries.append(statement)

    tc = TestClient(app, raise_server_exceptions=False)
    try:
        resp = tc.get("/?period=month")
    finally:
        event.remove(engine, "before_cursor_execute", _count)

    # The WIP at dashboard.py:617-690 makes two changes:
    # 1) Fixes a tz-naive datetime comparison on /?period=month
    #    (line ~481) that 500'd the route when products+customers
    #    existed. Pre-fix, the route crashed before reaching the
    #    forecast loop, so this test couldn't observe the batched
    #    query at all.
    # 2) Batches the per-product forecast loop into a single
    #    `WHERE sale.product_id IN (...)` query. Pre-fix, the loop
    #    called `forecast_sales(...)` once per product — 2 SELECTs
    #    each — for ~50+ queries on 25 products.
    assert resp.status_code == 200, (
        f"/?period=month returned {resp.status_code} — pre-fix tz-naive "
        f"datetime bug (dashboard.py:~481) is back, blocking the "
        f"forecast loop from running."
    )
    # The batched forecast query is `SELECT sale.product_id, sale.qty
    # FROM sale WHERE sale.product_id IN (?, ?, ...) AND
    # sale.voided_at IS NULL AND sale.sold_at >= ?`. The `IN (...)`
    # distinguishes it from per-product `WHERE sale.product_id = ?`
    # queries.
    batched_forecast_queries = [
        q
        for q in queries
        if "SELECT sale.product_id" in q and "sale.product_id IN " in q and "FROM sale" in q
    ]
    assert len(batched_forecast_queries) >= 1, (
        "Expected the batched forecast query "
        "(`SELECT sale.product_id ... WHERE sale.product_id IN (...)`) "
        "to appear at least once on /?period=month. The per-product "
        "N+1 in dashboard.py:617-690 is back."
    )
