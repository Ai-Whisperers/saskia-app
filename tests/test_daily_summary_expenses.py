"""tests/test_daily_summary_expenses.py — verify daily_summary surfaces the
expenses placeholder as a documented gap, not silent zero.

Phase 3C ticket #66 (per SASKIA_ARCHITECTURE_REFACTOR_PLAN_2026-09-24.md):
`accounting.py:daily_summary` returns expenses_gs=0 with a TODO comment
because the Expense model doesn't exist yet. Operators see the daily
summary in the dashboard and trust the zero — but it's a placeholder,
not a real number.

Fix: rename to expenses_placeholder_gs so callers + dashboards can
distinguish "we don't track expenses yet" from "expenses = 0".
"""

# allow-hardcoded-dates: daily rollups over a specific date range
from __future__ import annotations

from datetime import datetime, timezone


def _seed_sale(session_factory):
    """One sale on a known day so daily_summary has something to compute."""
    from app.rms.models import Ingredient, Product, Recipe, RecipeLine, Sale

    with session_factory() as s:
        ing = Ingredient(name="TestFlour", unit="kg", stock_qty=10.0, purchase_price_gs=5000)
        s.add(ing)
        s.flush()
        recipe = Recipe(name="TestMuffin", yield_qty=12.0, yield_unit="und")
        s.add(recipe)
        s.flush()
        s.add(RecipeLine(recipe_id=recipe.id, line_kind="ingredient", line_ref_id=ing.id, qty=0.3))
        s.flush()
        product = Product(
            name="TestMuffin",
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
                sold_at=datetime(2026, 9, 15, 14, 0, tzinfo=timezone.utc),
                invoice_type="boleta_resimple",
            )
        )
        s.commit()


def test_daily_summary_has_expenses_placeholder_field(session_factory):
    """DailySummary MUST have an expenses_placeholder_gs field.

    This is a renaming test: the field name makes it clear the value is
    a placeholder, not a real number.
    """
    from app.rms.accounting import DailySummary

    # Field exists
    assert hasattr(DailySummary, "expenses_placeholder_gs"), (
        "DailySummary should expose expenses_placeholder_gs (renamed from "
        "expenses_gs) to make the placeholder nature explicit"
    )


def test_daily_summary_returns_placeholder_zero(session_factory):
    """daily_summary() returns DailySummary with expenses_placeholder_gs=0."""
    from app.rms.accounting import daily_summary

    _seed_sale(session_factory)
    day = datetime(2026, 9, 15, tzinfo=timezone.utc)

    with session_factory() as s:
        summary = daily_summary(s, day=day)

    assert summary.expenses_placeholder_gs == 0
    # Also verify the original name is removed (renaming is the whole point)
    assert not hasattr(summary, "expenses_gs")
