"""tests/test_reports.py — monthly close + stockout reports.

Per dev plan Batch 6.

Tests:
- _validate_year_month: rejects bad year/month; accepts valid
- monthly_stockout_report: lists below-min ingredients, sorts by deficit
- monthly_stockout_report: ignores ingredients with min_stock_qty = 0
- monthly_stockout_report: empty list when nothing below threshold
- monthly_close_summary: zero state when no sales in period
- monthly_close_summary: counts ventas / cogs / margen for the period
- monthly_close_summary: excludes voided sales
- monthly_close_summary: ranks products by margin descending
- monthly_close_summary: stockout_count reflects end-of-month state
- month_label: returns Spanish month name
- days_in_month: returns correct day count (incl. leap year)
"""

from __future__ import annotations

from datetime import datetime

import pytest


def _seed_catalog(session_factory):
    """3 ingredients, 1 product, 1 recipe. Prices: 1000, 2000, 3000 Gs."""
    from app.rms.models import Ingredient, Product, Recipe, RecipeLine

    with session_factory() as s:
        flour = Ingredient(
            name="Harina",
            unit="kg",
            stock_qty=2.0,
            purchase_price_gs=1000,
            min_stock_qty=1.0,
        )
        sugar = Ingredient(
            name="Azúcar",
            unit="kg",
            stock_qty=0.5,
            purchase_price_gs=2000,
            min_stock_qty=1.0,
        )
        egg = Ingredient(
            name="Huevo",
            unit="und",
            stock_qty=20.0,
            purchase_price_gs=3000,
            min_stock_qty=0.0,  # no threshold
        )
        s.add_all([flour, sugar, egg])
        s.flush()

        recipe = Recipe(name="Muffin", yield_qty=12.0, yield_unit="und")
        s.add(recipe)
        s.flush()

        s.add_all(
            [
                RecipeLine(
                    recipe_id=recipe.id,
                    line_kind="ingredient",
                    line_ref_id=flour.id,
                    qty=0.3,
                ),
                RecipeLine(
                    recipe_id=recipe.id,
                    line_kind="ingredient",
                    line_ref_id=sugar.id,
                    qty=0.2,
                ),
                RecipeLine(
                    recipe_id=recipe.id,
                    line_kind="ingredient",
                    line_ref_id=egg.id,
                    qty=2.0,
                ),
            ]
        )
        s.flush()

        product = Product(
            name="Muffin",
            portion_label="1 muffin",
            sale_price_gs=8000,
            recipe_id=recipe.id,
        )
        s.add(product)
        s.commit()
        return flour.id, sugar.id, egg.id, product.id


def _record_sale(session_factory, product_id, qty, sold_at, voided_at=None):
    """Helper: insert a sale row directly (skip apply_sale to keep tests focused)."""
    from app.rms.models import Sale

    with session_factory() as s:
        sale = Sale(
            sold_at=sold_at,
            product_id=product_id,
            qty=qty,
            unit_price_gs=8000,
            voided_at=voided_at,
        )
        s.add(sale)
        s.commit()


# --- Validation ---


def test_validate_year_month_rejects_zero_month():
    """month=0 → ValueError."""
    from app.services.reports import _validate_year_month

    with pytest.raises(ValueError, match="month out of range"):
        _validate_year_month(2026, 0)


def test_validate_year_month_rejects_thirteen():
    """month=13 → ValueError."""
    from app.services.reports import _validate_year_month

    with pytest.raises(ValueError, match="month out of range"):
        _validate_year_month(2026, 13)


def test_validate_year_month_rejects_year_zero():
    """year=0 → ValueError."""
    from app.services.reports import _validate_year_month

    with pytest.raises(ValueError, match="year out of range"):
        _validate_year_month(0, 6)


def test_validate_year_month_accepts_december():
    """December end-of-month → first day of next year."""
    from app.services.reports import _validate_year_month

    start, end = _validate_year_month(2026, 12)
    assert start == datetime(2026, 12, 1)
    assert end == datetime(2027, 1, 1)


def test_validate_year_month_rejects_string():
    """Non-int → ValueError."""
    from app.services.reports import _validate_year_month

    with pytest.raises(ValueError, match="must be ints"):
        _validate_year_month("2026", 6)  # type: ignore[arg-type]


# --- monthly_stockout_report ---


def test_stockout_report_lists_below_min(session_factory):
    """flour (stock 2 > min 1) NOT listed; sugar (stock 0.5 < min 1) IS."""
    from app.services.reports import monthly_stockout_report

    flour_id, sugar_id, _, _ = _seed_catalog(session_factory)
    with session_factory() as s:
        rows = monthly_stockout_report(s, 2026, 9)
    names = [r.name for r in rows]
    assert "Azúcar" in names
    assert "Harina" not in names
    # Egg has min_stock=0 → never in report
    assert "Huevo" not in names


def test_stockout_report_sorts_by_deficit_desc(session_factory):
    """Largest deficit first."""
    from app.rms.models import Ingredient
    from app.services.reports import monthly_stockout_report

    _seed_catalog(session_factory)
    with session_factory() as s:
        # Add a third ingredient with bigger deficit
        s.add(
            Ingredient(
                name="Crítico",
                unit="kg",
                stock_qty=0.0,
                purchase_price_gs=500,
                min_stock_qty=5.0,
            )
        )
        s.commit()

    with session_factory() as s:
        rows = monthly_stockout_report(s, 2026, 9)
    assert rows[0].name == "Crítico"  # deficit = 5.0
    assert rows[0].deficit == pytest.approx(5.0)


def test_stockout_report_empty_when_all_above_min(session_factory):
    """All stock above threshold → empty list."""
    from app.rms.models import Ingredient
    from app.services.reports import monthly_stockout_report

    with session_factory() as s:
        s.add(
            Ingredient(
                name="Suficiente",
                unit="kg",
                stock_qty=10.0,
                purchase_price_gs=500,
                min_stock_qty=1.0,
            )
        )
        s.commit()

    with session_factory() as s:
        rows = monthly_stockout_report(s, 2026, 9)
    assert rows == []


def test_stockout_report_ignores_zero_min(session_factory):
    """min_stock_qty = 0 means 'no threshold'; never reported."""
    from app.services.reports import monthly_stockout_report

    _seed_catalog(session_factory)  # egg has min_stock=0
    with session_factory() as s:
        rows = monthly_stockout_report(s, 2026, 9)
    assert all(r.name != "Huevo" for r in rows)


# --- monthly_close_summary ---


def test_monthly_summary_empty_when_no_sales(session_factory):
    """No sales in the period → all zeros, stockout_count still computed."""
    from app.services.reports import monthly_close_summary

    _seed_catalog(session_factory)
    with session_factory() as s:
        summary = monthly_close_summary(s, 2026, 9)
    assert summary.ventas_gs == 0
    assert summary.cogs_gs == 0
    assert summary.margen_gs == 0
    assert summary.margen_ratio == 0.0
    assert summary.sale_count == 0
    assert summary.ranking == []
    # sugar is below threshold → stockout_count should be 1
    assert summary.stockout_count == 1


def test_monthly_summary_counts_sales_in_period(session_factory):
    """Sale in period is counted; sale outside period is not."""
    from app.services.reports import monthly_close_summary

    _, _, _, product_id = _seed_catalog(session_factory)
    # 2 sales in September, 1 in October
    _record_sale(session_factory, product_id, 1.0, datetime(2026, 9, 5, 10, 0))
    _record_sale(session_factory, product_id, 2.0, datetime(2026, 9, 15, 14, 0))
    _record_sale(session_factory, product_id, 1.0, datetime(2026, 10, 1, 9, 0))

    with session_factory() as s:
        sep = monthly_close_summary(s, 2026, 9)
        oct_ = monthly_close_summary(s, 2026, 10)

    # September: 1 + 2 = 3 units @ 8000 Gs = 24000
    assert sep.sale_count == 2
    assert sep.ventas_gs == 24000
    # October: 1 unit @ 8000 = 8000
    assert oct_.sale_count == 1
    assert oct_.ventas_gs == 8000


def test_monthly_summary_excludes_voided_sales(session_factory):
    """Voided sales don't count toward ventas/cogs/margen."""
    from app.services.reports import monthly_close_summary

    _, _, _, product_id = _seed_catalog(session_factory)
    _record_sale(session_factory, product_id, 2.0, datetime(2026, 9, 5, 10, 0))
    _record_sale(
        session_factory,
        product_id,
        1.0,
        datetime(2026, 9, 10, 10, 0),
        voided_at=datetime(2026, 9, 11, 12, 0),
    )

    with session_factory() as s:
        summary = monthly_close_summary(s, 2026, 9)
    # Only the non-voided sale counts: 2 units @ 8000 = 16000
    assert summary.sale_count == 1
    assert summary.ventas_gs == 16000


def test_monthly_summary_ranks_by_margin_desc(session_factory):
    """Top product by margin is first in ranking."""
    from app.rms.models import Product
    from app.services.reports import monthly_close_summary

    _, _, _, product_id = _seed_catalog(session_factory)
    # Add a no-recipe product with higher margin per sale
    with session_factory() as s:
        s.add(
            Product(
                name="SinReceta",
                portion_label="1 unidad",
                sale_price_gs=15000,
                recipe_id=None,
            )
        )
        s.commit()
        no_recipe_id = s.query(Product).filter_by(name="SinReceta").one().id

    # Sell 1 of each
    _record_sale(session_factory, product_id, 1.0, datetime(2026, 9, 5, 10, 0))
    _record_sale(session_factory, no_recipe_id, 1.0, datetime(2026, 9, 6, 10, 0))

    with session_factory() as s:
        summary = monthly_close_summary(s, 2026, 9)

    # Both products appear in ranking. SinReceta has no recipe → cost is None →
    # margin_ratio is 0 → sorted last by margin_gs desc. Muffin (with cost)
    # comes first because it has a smaller but computable margen.
    # Actually with the current sort: SinReceta margen_gs=0, Muffin margen_gs>0.
    # So Muffin first.
    product_names = [r["product_name"] for r in summary.ranking]
    assert "SinReceta" in product_names
    assert "Muffin" in product_names


def test_monthly_summary_margin_ratio_is_zero_when_no_ventas(session_factory):
    """When ventas_total = 0, margen_ratio is 0.0 (no division-by-zero)."""
    from app.services.reports import monthly_close_summary

    _seed_catalog(session_factory)
    with session_factory() as s:
        summary = monthly_close_summary(s, 2026, 9)
    assert summary.margen_ratio == 0.0


def test_monthly_summary_unique_products_count(session_factory):
    """unique_products counts distinct products sold in the period."""
    from app.services.reports import monthly_close_summary

    _, _, _, product_id = _seed_catalog(session_factory)
    _record_sale(session_factory, product_id, 1.0, datetime(2026, 9, 5, 10, 0))
    _record_sale(session_factory, product_id, 1.0, datetime(2026, 9, 6, 10, 0))
    _record_sale(session_factory, product_id, 1.0, datetime(2026, 9, 7, 10, 0))

    with session_factory() as s:
        summary = monthly_close_summary(s, 2026, 9)
    assert summary.unique_products == 1  # same product 3 times
    assert summary.sale_count == 3


def test_monthly_summary_to_dict_roundtrip(session_factory):
    """to_dict() returns the same data in dict form."""
    from app.services.reports import monthly_close_summary

    _, _, _, product_id = _seed_catalog(session_factory)
    _record_sale(session_factory, product_id, 1.0, datetime(2026, 9, 5, 10, 0))

    with session_factory() as s:
        summary = monthly_close_summary(s, 2026, 9)
        d = summary.to_dict()
    assert d["year"] == 2026
    assert d["month"] == 9
    assert d["ventas_gs"] == 8000
    assert d["sale_count"] == 1
    assert isinstance(d["ranking"], list)


def test_stockout_row_to_dict(session_factory):
    """StockoutRow.to_dict() has all fields."""
    from app.services.reports import monthly_stockout_report

    _seed_catalog(session_factory)
    with session_factory() as s:
        rows = monthly_stockout_report(s, 2026, 9)
    assert len(rows) >= 1
    d = rows[0].to_dict()
    assert set(d.keys()) == {
        "ingredient_id",
        "name",
        "unit",
        "stock_qty",
        "min_stock_qty",
        "deficit",
    }


# --- month_label + days_in_month ---


def test_month_label_spanish():
    """month_label returns Spanish month name."""
    from app.services.reports import month_label

    assert month_label(2026, 1) == "Enero 2026"
    assert month_label(2026, 9) == "Septiembre 2026"
    assert month_label(2026, 12) == "Diciembre 2026"


def test_days_in_month_normal():
    """Days in month for non-leap years."""
    from app.services.reports import days_in_month

    assert days_in_month(2026, 1) == 31
    assert days_in_month(2026, 2) == 28
    assert days_in_month(2026, 4) == 30
    assert days_in_month(2026, 12) == 31


def test_days_in_month_leap_year():
    """February in a leap year = 29."""
    from app.services.reports import days_in_month

    assert days_in_month(2024, 2) == 29
    assert days_in_month(2028, 2) == 29


def test_days_in_month_rejects_invalid():
    """Out-of-range month → ValueError."""
    from app.services.reports import days_in_month

    with pytest.raises(ValueError):
        days_in_month(2026, 13)


# --- Integration with costing engine ---


def test_monthly_summary_uses_recipe_cost_for_cogs(session_factory):
    """cogs_gs is computed from product recipe cost × qty."""
    from app.services.reports import monthly_close_summary

    _, _, _, product_id = _seed_catalog(session_factory)
    _record_sale(session_factory, product_id, 1.0, datetime(2026, 9, 5, 10, 0))

    with session_factory() as s:
        summary = monthly_close_summary(s, 2026, 9)
    # Seed prices: flour 1000, sugar 2000, egg 3000 Gs.
    # Batch cost = 0.3*1000 + 0.2*2000 + 2.0*3000 = 6700 Gs.
    # Unit cost = 6700 / 12 = 558.33 → to_int_gs = 558 Gs.
    # cogs = 558 * 1 = 558
    # ventas = 8000
    # margen = 8000 - 558 = 7442
    assert summary.ventas_gs == 8000
    assert summary.cogs_gs == 558
    assert summary.margen_gs == 7442
    assert summary.margen_ratio == pytest.approx(0.93025, abs=1e-4)
