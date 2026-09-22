"""K1: /ventas must NOT raise TemplateRuntimeError.

The 2026-09-22 outage: GET /ventas returned 500 with `TemplateRuntimeError`
because the template referenced `s.customer_id` but `_decorated()` didn't
include it. Plus several other template-render issues surfaced from missing
context variables.

This test loads /ventas with three different DB states:
- Empty (no products, no sales)
- One product, no sales
- Many products + sales (the live case)

Each must return 200 with no TemplateRuntimeError.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text


def test_ventas_loads_with_empty_db(client, session_factory):
    """K1 #1: /ventas must render even with zero products + zero sales."""
    # DB is fresh — no products, no sales
    r = client.get("/ventas")
    assert r.status_code == 200, (
        f"/ventas on empty DB returned {r.status_code}: {r.text[:200]}"
    )


def test_ventas_loads_with_one_product_no_sales(client, session_factory):
    """K1 #2: /ventas must render with a product but no sales yet."""
    from app.rms.models import Product
    with session_factory() as s:
        p = Product(
            name="K1 Test Pan",
            portion_label="1 und",
            sale_price_gs=5000,
            is_available=True,
        )
        s.add(p)
        s.commit()

    r = client.get("/ventas")
    assert r.status_code == 200, (
        f"/ventas with 1 product returned {r.status_code}: {r.text[:200]}"
    )


def test_ventas_loads_with_many_products_and_sales(client, session_factory):
    """K1 #3: /ventas must render with the realistic live data shape.

    Mimics the live DB: many products, many sales, some voided.
    """
    from datetime import datetime, timedelta, timezone
    from app.rms.models import Product, Sale

    with session_factory() as s:
        for i in range(5):
            p = Product(
                name=f"K1 Product {i}",
                portion_label="1 und",
                sale_price_gs=5000 + i * 1000,
                is_available=True,
            )
            s.add(p)
        s.commit()

        with session_factory() as s2:
            products = s2.execute(text("SELECT id FROM product")).fetchall()
            for pid_row in products[:5]:
                pid = pid_row[0]
                for j in range(3):
                    sale = Sale(
                        product_id=pid,
                        qty=1,
                        unit_price_gs=5000,
                        sold_at=datetime.now(timezone.utc) - timedelta(days=j),
                    )
                    s2.add(sale)
                # One voided sale
                s2.add(Sale(
                    product_id=pid,
                    qty=1,
                    unit_price_gs=5000,
                    sold_at=datetime.now(timezone.utc),
                    voided_at=datetime.now(timezone.utc),
                ))
            s2.commit()

    r = client.get("/ventas")
    assert r.status_code == 200, (
        f"/ventas with realistic data returned {r.status_code}: {r.text[:200]}"
    )
    # Body should contain the ventas page title
    body = r.text
    assert "Ventas" in body or "ventas" in body


def test_ventas_loads_with_filter_query(client, session_factory):
    """K1 #4: /ventas must accept ?q=, ?product_id=, ?days= filters without 500."""
    from app.rms.models import Product
    with session_factory() as s:
        p = Product(
            name="K1 Filtered",
            portion_label="1 und",
            sale_price_gs=5000,
            is_available=True,
        )
        s.add(p)
        s.commit()

    # All three filter forms
    for params in ["", "?q=Test", "?product_id=1", "?days=7", "?days=30&product_id=1"]:
        r = client.get(f"/ventas{params}")
        assert r.status_code == 200, (
            f"/ventas{params} returned {r.status_code}: {r.text[:200]}"
        )
