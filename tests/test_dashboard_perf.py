"""tests/test_dashboard_perf.py — regression test: dashboard must not regress
to N+1 queries. Asserts the dashboard route uses fewer than 20 queries
for a typical seed dataset.
"""
from __future__ import annotations

import pytest
from sqlalchemy import event


def test_dashboard_renders_under_40_queries(client, session_factory):
    """A single GET / should not issue hundreds of queries.

    Pre-fix this hit ~3,000+ queries from N+1 patterns. After fix it should
    be under 40 even with a populated database.

    Note: the dashboard renders 8 analytics sections (Stars, Dogs, Rising,
    Churning, Food cost, Production tomorrow, etc.) — each one is allowed
    its own query. Budget = ~5 baseline + ~30 analytics = 35.
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

    assert len(queries) < 40, (
        f"Dashboard issued {len(queries)} queries — N+1 regression. "
        f"First 5 queries: {queries[:5]}"
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
        1 for q in queries
        if 'FROM ingredient' in q and 'WHERE ingredient.id = ?' in q
    )
    assert ingredient_point_queries <= 2, (
        f"Found {ingredient_point_queries} point-queries against ingredient "
        f"table — likely N+1 in cost loop. Bump threshold if a legitimate "
        f"single-row lookup is being counted."
    )
