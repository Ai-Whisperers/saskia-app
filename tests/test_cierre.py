"""tests/test_cierre.py — Phase 1.E Monthly P&L close (cierre mensual)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.rms.cierre import _month_range, compute_monthly_close
from app.rms.models import Ingredient, Product, Recipe, RecipeLine, Sale


class TestMonthRange:
    def test_january(self):
        s, e = _month_range(2026, 1)
        assert s == __import__('datetime').date(2026, 1, 1)
        assert e == __import__('datetime').date(2026, 1, 31)

    def test_february_non_leap(self):
        _s, e = _month_range(2025, 2)
        assert e == __import__('datetime').date(2025, 2, 28)

    def test_february_leap(self):
        _s, e = _month_range(2024, 2)
        assert e == __import__('datetime').date(2024, 2, 29)

    def test_december(self):
        s, e = _month_range(2026, 12)
        assert s == __import__('datetime').date(2026, 12, 1)
        assert e == __import__('datetime').date(2026, 12, 31)


@pytest.fixture
def seed_month_data(session_factory):
    """Seed: 1 product + 1 recipe + 5 sales in Sept 2026 + 1 voided sale."""
# allow-hardcoded-dates: cierre day-of-month / month-end / leap-year edge cases
    Session = session_factory

    def _seed():
        with Session() as s:
            ing = Ingredient(name="harina", unit="kg", stock_qty=10.0, purchase_price_gs=5000)
            s.add(ing)
            s.commit()
            s.refresh(ing)

            r = Recipe(name="Muffin test", yield_qty=10, yield_unit="und", family="pastelería")
            s.add(r)
            s.commit()
            s.refresh(r)

            rl = RecipeLine(recipe_id=r.id, line_kind="ingredient", line_ref_id=ing.id, qty=0.5, line_unit="kg")
            s.add(rl)
            s.commit()

            p = Product(name="Muffin test", sale_price_gs=25000, portion_label="1 und",
                        recipe_id=r.id, iva_rate="10")
            s.add(p)
            s.commit()
            s.refresh(p)

            # 5 sales in Sept 2026
            for d in (5, 10, 15, 20, 25):
                sale = Sale(
                    product_id=p.id,
                    qty=2.0,
                    unit_price_gs=25000,
                    sold_at=datetime(2026, 9, d, 12, 0, tzinfo=timezone.utc),
                    invoice_type="boleta_resimple",
                    invoice_number=d,
                    iva_amount_gs=0,
                    iva_base_gs=0,
                )
                s.add(sale)

            # 1 voided sale (should NOT be counted)
            voided = Sale(
                product_id=p.id,
                qty=1.0,
                unit_price_gs=25000,
                sold_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc),
                voided_at=datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc),
            )
            s.add(voided)

            # 1 sale in Oct (different month, should NOT be counted)
            oct_sale = Sale(
                product_id=p.id,
                qty=1.0,
                unit_price_gs=25000,
                sold_at=datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc),
            )
            s.add(oct_sale)

            s.commit()
        return "ok"

    return _seed


class TestCierreEmpty:
    def test_no_sales_returns_zero_close(self, session_factory):
        with session_factory() as s:
            close = compute_monthly_close(s, 2026, 9)
        assert close.total_sales == 0
        assert close.total_ventas_gs == 0
        assert close.total_prime_cost_gs == 0
        assert close.total_margen_pct == 0.0
        assert close.top_product is None
        assert close.rows == []
        assert close.period_label == "Septiembre 2026"


class TestCierreBasic:
    def test_counts_only_in_period_sales(self, session_factory, seed_month_data):
        seed_month_data()
        with session_factory() as s:
            close = compute_monthly_close(s, 2026, 9)
        # 5 sales counted (oct excluded, voided excluded)
        assert close.total_sales == 5

    def test_total_ventas(self, session_factory, seed_month_data):
        seed_month_data()
        with session_factory() as s:
            close = compute_monthly_close(s, 2026, 9)
        # 5 sales × 2 qty × 25000 = 250000
        assert close.total_ventas_gs == 250000

    def test_total_iva_zero_for_boleta_resimple(self, session_factory, seed_month_data):
        """Boletas Resimple don't itemize IVA — total should be 0."""
        seed_month_data()
        with session_factory() as s:
            close = compute_monthly_close(s, 2026, 9)
        assert close.total_iva_ventas_gs == 0

    def test_prime_cost_includes_materials(self, session_factory, seed_month_data):
        seed_month_data()
        with session_factory() as s:
            close = compute_monthly_close(s, 2026, 9)
        # Materials per portion: 0.5kg × 5000 = 2500. Sold 5 × 2 = 10 portions.
        # Prime cost per portion = materials (no yield/labor/overhead configured).
        # Total materials = 2500 × 10 = 25000
        assert close.total_prime_cost_gs == 25000

    def test_margen_neto(self, session_factory, seed_month_data):
        seed_month_data()
        with session_factory() as s:
            close = compute_monthly_close(s, 2026, 9)
        # 250000 - 25000 = 225000
        assert close.total_margen_neto_gs == 225000

    def test_margen_pct(self, session_factory, seed_month_data):
        seed_month_data()
        with session_factory() as s:
            close = compute_monthly_close(s, 2026, 9)
        # 225000 / 250000 = 90%
        assert close.total_margen_pct == 90.0


class TestCierreStructure:
    def test_rows_contain_family_and_product_aggregates(self, session_factory, seed_month_data):
        seed_month_data()
        with session_factory() as s:
            close = compute_monthly_close(s, 2026, 9)
        # Should have at least one family aggregate + one product row
        labels = [r.label for r in close.rows]
        assert "pastelería" in labels
        assert "Muffin test" in labels

    def test_top_product_is_highest_margin(self, session_factory, seed_month_data):
        seed_month_data()
        with session_factory() as s:
            close = compute_monthly_close(s, 2026, 9)
        # Only one product, it should be the top
        assert close.top_product == "Muffin test"

    def test_different_month_returns_empty(self, session_factory, seed_month_data):
        seed_month_data()
        with session_factory() as s:
            close = compute_monthly_close(s, 2027, 1)  # No sales in Jan 2027
        assert close.total_sales == 0


class TestCierreFactura:
    """Factura sales include IVA in the breakdown."""

    def test_factura_includes_iva(self, session_factory):
        Session = session_factory
        with Session() as s:
            p = Product(name="Producto con IVA", sale_price_gs=25000, portion_label="1 und", iva_rate="10")
            s.add(p)
            s.commit()
            s.refresh(p)
            sale = Sale(
                product_id=p.id,
                qty=1.0,
                unit_price_gs=25000,
                sold_at=datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc),
                invoice_type="factura",
                iva_rate="10",
                iva_base_gs=22727,
                iva_amount_gs=2273,
            )
            s.add(sale)
            s.commit()

        with Session() as s:
            close = compute_monthly_close(s, 2026, 9)
        assert close.total_iva_ventas_gs == 2273
        assert close.total_ventas_gs == 25000
