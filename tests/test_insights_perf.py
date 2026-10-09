"""tests/test_insights_perf.py — regression test for insights + sales_intel N+1."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import event


def test_build_insights_no_n_plus_1(client, session_factory):
    """build_insights must not N+1 over products.

    Pre-fix: for p in products: production_plan_for_day(session, p) was one
    query per product (~20 queries for 20 products). Post-fix:
    batch_production_plans() does it in 2 queries.
    """
    from app.rms.insights import build_insights
    from app.rms.models import Ingredient, Product, Sale

    # Seed enough products to actually trigger N+1
    with session_factory() as s:
        for i in range(10):
            ing = Ingredient(name=f"ins_ing_{i}", unit="g", stock_qty=1000, purchase_price_gs=100)
            s.add(ing)
            s.flush()
            p = Product(name=f"ins_prod_{i}", sale_price_gs=1000, recipe_id=None)
            s.add(p)
            s.flush()
            for j in range(3):
                s.add(
                    Sale(
                        product_id=p.id,
                        qty=1,
                        unit_price_gs=1000,
                        sold_at=datetime.now(timezone.utc) - timedelta(days=j),
                    )
                )
        s.commit()

    engine = session_factory.kw["bind"]
    queries: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def _count(conn, cursor, statement, params, context, executemany):
        queries.append(statement)

    try:
        with session_factory() as s:
            build_insights(s)
    finally:
        event.remove(engine, "before_cursor_execute", _count)

    # The bad pattern was: SELECT sale.qty FROM sale WHERE sale.product_id = ?
    # Post-fix: a single SELECT ... WHERE sale.product_id IN (?,?,...)
    per_product_point_queries = sum(
        1 for q in queries if "FROM sale" in q and "sale.product_id = ?" in q
    )
    assert per_product_point_queries == 0, (
        f"Found {per_product_point_queries} per-product point queries — "
        f"N+1 in build_insights (production_plan_for_day loop)."
    )


def test_rising_churning_uses_batch_load(client, session_factory):
    """rising_products + churning_products must not N+1 over products.

    Pre-fix: for p in products: _trend_for_product(...) was 3 queries each.
    Post-fix: 2 queries total (current + prior window).
    """
    from app.rms.models import Product, Sale
    from app.rms.sales_intel import churning_products, rising_products

    # Seed 10 products with sales in current and prior windows
    with session_factory() as s:
        now = datetime.now(timezone.utc)
        for i in range(10):
            p = Product(name=f"trend_prod_{i}", sale_price_gs=1000, recipe_id=None)
            s.add(p)
            s.flush()
            for j in range(28):
                # Recent window (last 14 days): increasing qty
                if j < 14:
                    qty = 5 + (14 - j)  # newer = less volume
                else:
                    qty = 1 + (28 - j)  # prior window: decreasing
                s.add(
                    Sale(
                        product_id=p.id,
                        qty=qty,
                        unit_price_gs=1000,
                        sold_at=now - timedelta(days=j),
                    )
                )
        s.commit()

    engine = session_factory.kw["bind"]
    queries: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def _count(conn, cursor, statement, params, context, executemany):
        queries.append(statement)

    try:
        with session_factory() as s:
            rising_products(s)
            churning_products(s)
    finally:
        event.remove(engine, "before_cursor_execute", _count)

    # The bad pattern was 2 queries per product (current + prior).
    # Post-fix: 2 total queries regardless of product count.
    sale_window_queries = sum(
        1
        for q in queries
        if "FROM sale" in q and "sold_at >=" in q and "sale.voided_at IS NULL" in q
    )
    assert sale_window_queries <= 4, (
        f"Found {sale_window_queries} sale-window queries — should be at most "
        f"4 (2 per function × 2 functions), likely N+1 over products."
    )
