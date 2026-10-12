"""tests/_lib/seed.py — Seed/test-data helpers.

Thin wrappers around the existing `tests.factories` module for the most
common test data setups. Use these instead of writing raw model
construction in your tests.

Usage:
    from tests._lib.seed import quick_ingredient, quick_product, quick_sale

    def test_x(session_factory):
        ing = quick_ingredient(session_factory(), name="harina", stock_qty=10.0)
        ...
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional


def quick_ingredient(
    session,
    name: str = "test_ingredient",
    *,
    stock_unit: str = "kg",
    stock_qty: float = 10.0,
    current_price_gs: int = 50_000,
    category: Optional[str] = None,
) -> object:
    """Insert a single Ingredient. Returns the model.

    Uniqueness is handled by the model's own constraint; pass a unique name
    or let `tests.factories.make_ingredient` handle it.
    """
    from tests.factories import make_ingredient

    return make_ingredient(
        session,
        name=name,
        stock_unit=stock_unit,
        stock_qty=stock_qty,
        current_price_gs=current_price_gs,
        category=category,
    )


def quick_product(
    session,
    name: str = "test_product",
    *,
    sale_price_gs: int = 100_000,
    category: Optional[str] = None,
    cost_gs: Optional[int] = None,
) -> object:
    """Insert a single Product. Returns the model."""
    from tests.factories import make_product

    return make_product(
        session,
        name=name,
        sale_price_gs=sale_price_gs,
        category=category,
        cost_gs=cost_gs,
    )


def quick_sale(
    session,
    *,
    items: Optional[list] = None,
    total_gs: int = 100_000,
    customer_name: Optional[str] = None,
    sold_at: Optional[datetime] = None,
) -> object:
    """Insert a Sale with line items. Returns the Sale model.

    Args:
        items: list of (product, qty) tuples. If None, creates a $1000 sale
               with no line items (use for testing sale-level logic only).
    """
    from tests.factories import make_sale

    return make_sale(
        session,
        items=items,
        total_gs=total_gs,
        customer_name=customer_name,
        sold_at=sold_at,
    )


def quick_supplier(session, name: str = "test_supplier", **kwargs) -> object:
    """Insert a Supplier."""
    from tests.factories import make_supplier

    return make_supplier(session, name=name, **kwargs)


def quick_customer(session, name: str = "test_customer", **kwargs) -> object:
    """Insert a Customer."""
    from tests.factories import make_customer

    return make_customer(session, name=name, **kwargs)


__all__ = [
    "quick_customer",
    "quick_ingredient",
    "quick_product",
    "quick_sale",
    "quick_supplier",
]
