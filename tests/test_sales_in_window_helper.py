"""tests/test_sales_in_window_helper.py — extract a shared helper for
the 9 copies of 'non-voided sales in [start, end]' query in accounting.py.

Per SASKIA_ARCHITECTURE_REFACTOR_PLAN_2026-09-24.md ticket #26 (C-1):
the same window+voided filter is repeated 9 times across accounting.py.
If we ever need to honor tz or change the void semantics, we have to
edit 9 functions. Centralize into one helper.
"""
# allow-hardcoded-dates: window helper tests use fixed date ranges

from __future__ import annotations

from datetime import datetime, timezone


def _seed_sale(session_factory, sold_at, voided=False, name_suffix=""):
    from app.rms.models import Ingredient, Product, Recipe, RecipeLine, Sale

    with session_factory() as s:
        ing = Ingredient(
            name=f"TestFlour{name_suffix}", unit="kg", stock_qty=10.0, purchase_price_gs=5000
        )
        s.add(ing)
        s.flush()
        recipe = Recipe(name=f"TestMuffin{name_suffix}", yield_qty=12.0, yield_unit="und")
        s.add(recipe)
        s.flush()
        s.add(RecipeLine(recipe_id=recipe.id, line_kind="ingredient", line_ref_id=ing.id, qty=0.3))
        s.flush()
        product = Product(
            name=f"TestMuffin{name_suffix}",
            portion_label="1 muffin",
            recipe_id=recipe.id,
            sale_price_gs=10000,
            iva_rate="10",
        )
        s.add(product)
        s.flush()
        s.add(
            Sale(
                product_id=product.id,
                qty=1.0,
                unit_price_gs=10000,
                sold_at=sold_at,
                invoice_type="boleta_resimple",
                voided_at=(sold_at if voided else None),
            )
        )
        s.commit()


def test_sales_in_window_returns_matching_sales(session_factory):
    """sales_in_window returns sales with sold_at in [start, end]."""
    from app.rms.accounting import sales_in_window

    _seed_sale(session_factory, datetime(2026, 9, 15, 14, 0, tzinfo=timezone.utc))

    with session_factory() as s:
        sales = sales_in_window(
            s,
            start=datetime(2026, 9, 1, tzinfo=timezone.utc),
            end=datetime(2026, 9, 30, tzinfo=timezone.utc),
        )

    assert len(sales) == 1
    assert sales[0].qty == 1.0


def test_sales_in_window_excludes_voided_sales(session_factory):
    """Voided sales are NOT returned."""
    from app.rms.accounting import sales_in_window

    _seed_sale(session_factory, datetime(2026, 9, 15, 14, 0, tzinfo=timezone.utc), voided=True)

    with session_factory() as s:
        sales = sales_in_window(
            s,
            start=datetime(2026, 9, 1, tzinfo=timezone.utc),
            end=datetime(2026, 9, 30, tzinfo=timezone.utc),
        )

    assert sales == []


def test_sales_in_window_excludes_out_of_window(session_factory):
    """Sales before start or after end are NOT returned."""
    from app.rms.accounting import sales_in_window

    # Inside window
    _seed_sale(session_factory, datetime(2026, 9, 15, 14, 0, tzinfo=timezone.utc), name_suffix="_a")
    # Before window
    _seed_sale(session_factory, datetime(2026, 8, 30, 14, 0, tzinfo=timezone.utc), name_suffix="_b")
    # After window
    _seed_sale(session_factory, datetime(2026, 10, 5, 14, 0, tzinfo=timezone.utc), name_suffix="_c")

    with session_factory() as s:
        sales = sales_in_window(
            s,
            start=datetime(2026, 9, 1, tzinfo=timezone.utc),
            end=datetime(2026, 9, 30, tzinfo=timezone.utc),
        )

    assert len(sales) == 1
    assert sales[0].sold_at.day == 15


def test_sales_in_window_orders_by_sold_at_asc(session_factory):
    """Default order is by sold_at ascending for chronological reports."""
    from app.rms.accounting import sales_in_window

    # Seed out of order
    _seed_sale(session_factory, datetime(2026, 9, 18, 14, 0, tzinfo=timezone.utc), name_suffix="_1")
    _seed_sale(session_factory, datetime(2026, 9, 15, 14, 0, tzinfo=timezone.utc), name_suffix="_2")
    _seed_sale(session_factory, datetime(2026, 9, 20, 14, 0, tzinfo=timezone.utc), name_suffix="_3")

    with session_factory() as s:
        sales = sales_in_window(
            s,
            start=datetime(2026, 9, 1, tzinfo=timezone.utc),
            end=datetime(2026, 9, 30, tzinfo=timezone.utc),
        )

    days = [s_.sold_at.day for s_ in sales]
    assert days == [15, 18, 20], f"expected sorted ascending, got {days}"


def test_sales_in_window_end_inclusive_false_excludes_boundary(session_factory):
    """end_inclusive=False uses sold_at < end (daily_summary style)."""
    from app.rms.accounting import sales_in_window

    # Sale exactly at end-of-window
    _seed_sale(
        session_factory, datetime(2026, 9, 15, 23, 59, 59, tzinfo=timezone.utc), name_suffix="_z"
    )
    # Sale 1 second after end
    _seed_sale(
        session_factory, datetime(2026, 9, 16, 0, 0, 0, tzinfo=timezone.utc), name_suffix="_y"
    )

    end_of_day = datetime(2026, 9, 16, 0, 0, 0, tzinfo=timezone.utc)

    with session_factory() as s:
        # Exclusive end: sale at 23:59:59 is IN, sale at 00:00:00 is OUT
        sales = sales_in_window(
            s,
            start=datetime(2026, 9, 15, 0, 0, 0, tzinfo=timezone.utc),
            end=end_of_day,
            end_inclusive=False,
        )
    assert len(sales) == 1
    assert sales[0].sold_at.hour == 23
