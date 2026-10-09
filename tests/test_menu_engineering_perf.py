"""tests/test_menu_engineering_perf.py — regression test for classify_products N+1."""

from __future__ import annotations

from sqlalchemy import event


def test_classify_products_uses_batch_load(client, session_factory):
    """classify_products must not N+1 over products.

    Pre-fix: _product_volume queries `sale` once per product (~20 queries
    for 20 products), plus _product_margin calls batch_products_cost_margin
    per product (~20 batch calls × 3-4 queries each = ~80 queries).

    Post-fix: 2 queries (current sales window + prior window) regardless
    of product count.
    """
    from datetime import datetime, timedelta, timezone

    from app.rms.models import Ingredient, Product, Sale

    # Seed enough products + sales to actually trigger N+1
    with session_factory() as s:
        for i in range(10):
            ing = Ingredient(name=f"ing_{i}", unit="g", stock_qty=1000, purchase_price_gs=100)
            s.add(ing)
            s.flush()
            p = Product(name=f"prod_{i}", sale_price_gs=1000, recipe_id=None)
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
        from app.rms.menu_engineering import classify_products

        with session_factory() as s:
            classify_products(s)
    finally:
        event.remove(engine, "before_cursor_execute", _count)

    # The bad pattern was: SELECT sale.qty FROM sale WHERE sale.product_id = ?
    # After fix: no per-product point queries — use IN clause or aggregation.
    per_product_point_queries = sum(
        1 for q in queries if "FROM sale" in q and "sale.product_id = ?" in q
    )
    assert per_product_point_queries == 0, (
        f"Found {per_product_point_queries} per-product point queries against "
        f"sale table — N+1 in classify_products."
    )
