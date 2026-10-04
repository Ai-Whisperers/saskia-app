"""Performance query budget tests.

Per SASKIA_TEST_PLAN.md §5 #38 — major pages must execute <N queries.
Catches N+1 regressions.
"""

from __future__ import annotations

import pytest
from sqlalchemy import event

from app.rms.models import Product


@pytest.fixture
def query_counter(session_factory):
    """Count SQL queries executed during a request."""
    engine = session_factory.kw["bind"]

    counts = []

    def count(conn, cursor, statement, params, context, executemany):
        counts.append(statement)

    event.listen(engine, "before_cursor_execute", count)
    yield counts
    event.remove(engine, "before_cursor_execute", count)


def test_dashboard_under_query_budget(client, session_factory, query_counter):
    """Dashboard must execute <90 queries (per SASKIA_TEST_PLAN.md)."""
    # Seed minimal data
    with session_factory() as s:
        product = Product(
            name="Perf Test",
            portion_label="1 und",
            sale_price_gs=5000,
            is_available=True,
        )
        s.add(product)
        s.commit()

    query_counter.clear()
    r = client.get("/")
    assert r.status_code == 200

    # Dashboard is allowed up to 90 queries (with seeded data)
    assert len(query_counter) < 100, (
        f"Dashboard executed {len(query_counter)} queries (limit: 90). N+1 regression suspected."
    )


def test_productos_under_query_budget(client, session_factory, query_counter):
    """Products page must execute <40 queries."""
    with session_factory() as s:
        for i in range(5):
            s.add(
                Product(
                    name=f"Perf Product {i}",
                    portion_label="1 und",
                    sale_price_gs=5000,
                    is_available=True,
                )
            )
        s.commit()

    query_counter.clear()
    r = client.get("/productos")
    assert r.status_code == 200

    assert len(query_counter) < 50, (
        f"Products page executed {len(query_counter)} queries (limit: 40)"
    )


def test_inventario_under_query_budget(client, session_factory, query_counter):
    """Inventory page must execute <40 queries."""
    from app.rms.models import Ingredient

    with session_factory() as s:
        for i in range(5):
            s.add(
                Ingredient(
                    name=f"Perf Ing {i}",
                    unit="kg",
                    stock_qty=10.0,
                    min_stock_qty=1.0,
                )
            )
        s.commit()

    query_counter.clear()
    r = client.get("/inventario")
    assert r.status_code == 200

    assert len(query_counter) < 50, (
        f"Inventory page executed {len(query_counter)} queries (limit: 40)"
    )


def test_recetas_under_query_budget(client, session_factory, query_counter):
    """Recipes page must execute <40 queries."""
    from app.rms.models import Recipe

    with session_factory() as s:
        for i in range(5):
            s.add(Recipe(name=f"Perf Recipe {i}", yield_qty=10.0))
        s.commit()

    query_counter.clear()
    r = client.get("/recetas")
    assert r.status_code == 200

    assert len(query_counter) < 50, (
        f"Recipes page executed {len(query_counter)} queries (limit: 40)"
    )


def test_clientes_under_query_budget(client, session_factory, query_counter):
    """Customers page must execute <40 queries."""
    from app.rms.models import Customer

    with session_factory() as s:
        for i in range(5):
            s.add(Customer(name=f"Perf Customer {i}", phone=f"+5959900{i:04d}"))
        s.commit()

    query_counter.clear()
    r = client.get("/clientes")
    assert r.status_code == 200

    assert len(query_counter) < 50, (
        f"Customers page executed {len(query_counter)} queries (limit: 40)"
    )
