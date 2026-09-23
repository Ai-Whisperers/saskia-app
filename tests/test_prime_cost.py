"""tests/test_prime_cost.py — Phase 1.D Prime Cost calculation."""
from __future__ import annotations

import pytest
from decimal import Decimal

from app.rms.prime_cost import compute_prime_cost, PrimeCostBreakdown, _round_half_up
from app.rms.models import ComplianceInfo, Product, Recipe, RecipeLine, Ingredient


@pytest.fixture
def setup_product_with_recipe(session_factory):
    """Seed: a flour ingredient @ Gs 5000/kg + a recipe yielding 10 muffins + a product @ Gs 30000."""
    Session = session_factory

    def _setup(*, ingredients=None, yield_qty=10, labor_minutes=None,
               yield_pct=None, labor_rate=25000, overhead_pct=15, sale_price=30000,
               recipe_name="Test Recipe", product_name="Test Muffin"):
        # Ensure compliance info exists with test rates
        with Session() as s:
            ci = s.get(ComplianceInfo, 1)
            ci.labor_cost_per_hour_gs = labor_rate
            ci.overhead_multiplier_pct = overhead_pct
            s.commit()

        with Session() as s:
            # Create ingredient(s)
            ing_ids = []
            for ing_def in (ingredients or [{"name": "harina", "price": 5000, "qty": 0.5}]):
                ing = Ingredient(
                    name=ing_def["name"],
                    unit="kg",
                    stock_qty=10.0,
                    purchase_price_gs=ing_def["price"],
                )
                s.add(ing); s.commit(); s.refresh(ing)
                ing_ids.append((ing.id, ing_def["qty"]))

            # Create recipe
            r = Recipe(
                name=recipe_name,
                yield_qty=yield_qty,
                yield_unit="und",
                yield_percentage=yield_pct,
                direct_labor_minutes=labor_minutes,
            )
            s.add(r); s.commit(); s.refresh(r)

            for ing_id, qty in ing_ids:
                rl = RecipeLine(
                    recipe_id=r.id,
                    line_kind="ingredient",
                    line_ref_id=ing_id,
                    qty=qty,
                    line_unit="kg",
                )
                s.add(rl)
            s.commit()

            # Create product
            p = Product(
                name=product_name,
                sale_price_gs=sale_price,
                portion_label="1 und",
                recipe_id=r.id,
            )
            s.add(p); s.commit(); s.refresh(p)
            return p.id

    return _setup


class TestRoundHalfUp:
    def test_round_half_up_basic(self):
        assert _round_half_up(Decimal("10.5")) == 11
        assert _round_half_up(Decimal("10.4")) == 10
        assert _round_half_up(Decimal("10.6")) == 11
        assert _round_half_up(Decimal("0.5")) == 1

    def test_round_half_up_negative(self):
        # ROUND_HALF_UP rounds away from zero for negative
        assert _round_half_up(Decimal("-10.5")) == -11


class TestPrimeCostBasic:
    def test_product_without_recipe_returns_none_materials(self, session_factory):
        """No recipe → no materials cost, no prime cost."""
        Session = session_factory
        with Session() as s:
            p = Product(name="Manual item", sale_price_gs=5000, portion_label="1 und")
            s.add(p); s.commit(); s.refresh(p)
            pc = compute_prime_cost(s, p.id)
        assert pc.materials_cost_gs is None
        assert pc.prime_cost_gs is None
        assert any("sin receta" in n for n in pc.notes)

    def test_product_without_price_returns_none_sale(self, session_factory):
        Session = session_factory
        with Session() as s:
            p = Product(name="Free sample", sale_price_gs=0, portion_label="1 und")
            s.add(p); s.commit(); s.refresh(p)
            pc = compute_prime_cost(s, p.id)
        assert pc.sale_price_gs == 0  # Stored, not None
        assert pc.gross_margin_pct is None  # Can't compute pct when sale is 0


class TestPrimeCostWithRecipe:
    def test_simple_recipe_prime_cost(self, session_factory, setup_product_with_recipe):
        """harina 0.5kg × Gs 5000/kg = Gs 2500 materials.
        No yield, no labor, no overhead → prime = 2500."""
        pid = setup_product_with_recipe(ingredients=[
            {"name": "harina", "price": 5000, "qty": 0.5}
        ])
        with session_factory() as s:
            pc = compute_prime_cost(s, pid)
        assert pc.materials_cost_gs == 2500
        # No yield, no labor → prime cost is None (yield_corrected is None)
        assert pc.yield_corrected_cost_gs is None
        assert pc.prime_cost_gs is None
        assert any("tiempo" in n.lower() for n in pc.notes)

    def test_recipe_with_labor_minutes(self, session_factory, setup_product_with_recipe):
        """60 min labor × Gs 25000/h = Gs 25000 labor."""
        pid = setup_product_with_recipe(
            ingredients=[{"name": "harina", "price": 5000, "qty": 0.5}],
            labor_minutes=60,
        )
        with session_factory() as s:
            pc = compute_prime_cost(s, pid)
        assert pc.labor_cost_gs == 25000
        # 60min × 25000/h = 25000, but yield_corrected is None so prime is None
        assert pc.prime_cost_gs is None


class TestPrimeCostWithYieldCorrection:
    def test_yield_85pct_corrects_materials_upward(self, session_factory, setup_product_with_recipe):
        """0.5kg × Gs 5000 = Gs 2500 materials.
        yield_pct=0.85 → corrected = 2500 / 0.85 = 2941.176 → rounds to 2941.
        Overhead 15% × 2500 = 375.
        No labor.
        Prime = 2941 + 375 = 3316."""
        pid = setup_product_with_recipe(
            ingredients=[{"name": "harina", "price": 5000, "qty": 0.5}],
            yield_pct=0.85,
        )
        with session_factory() as s:
            pc = compute_prime_cost(s, pid)
        assert pc.materials_cost_gs == 2500
        assert pc.yield_corrected_cost_gs == 2941
        assert pc.overhead_cost_gs == 375
        assert pc.labor_cost_gs is None
        assert pc.prime_cost_gs == 2941 + 375  # = 3316

    def test_full_prime_cost(self, session_factory, setup_product_with_recipe):
        """All four components: materials + yield + labor + overhead."""
        pid = setup_product_with_recipe(
            ingredients=[{"name": "harina", "price": 5000, "qty": 0.5}],
            yield_pct=0.85,
            labor_minutes=30,
            labor_rate=24000,
            overhead_pct=15,
            sale_price=30000,
        )
        with session_factory() as s:
            pc = compute_prime_cost(s, pid)
        # Materials = 2500
        assert pc.materials_cost_gs == 2500
        # Yield-corrected = 2500 / 0.85 = 2941
        assert pc.yield_corrected_cost_gs == 2941
        # Labor = 30 × 24000 / 60 = 12000
        assert pc.labor_cost_gs == 12000
        # Overhead = 2500 × 0.15 = 375
        assert pc.overhead_cost_gs == 375
        # Prime = 2941 + 12000 + 375 = 15316
        assert pc.prime_cost_gs == 15316
        # Sale = 30000, margin = 30000 - 15316 = 14684
        assert pc.gross_margin_gs == 14684
        # margin_pct = 14684/30000 * 100 = 48.9%
        assert pc.gross_margin_pct == 48.9
        # prime_cost_pct = 15316/30000 * 100 = 51.1%
        assert pc.prime_cost_pct_of_sale == 51.1


class TestPrimeCostEdgeCases:
    def test_invalid_yield_percentage_falls_back_to_no_correction(self, session_factory, setup_product_with_recipe):
        """yield_pct > 1.0 is invalid; should fall back to no correction."""
        pid = setup_product_with_recipe(
            ingredients=[{"name": "harina", "price": 5000, "qty": 0.5}],
            yield_pct=1.5,  # Invalid
        )
        with session_factory() as s:
            pc = compute_prime_cost(s, pid)
        assert pc.yield_corrected_cost_gs is None
        assert any("inválido" in n for n in pc.notes)

    def test_zero_yield_percentage_falls_back_to_no_correction(self, session_factory, setup_product_with_recipe):
        pid = setup_product_with_recipe(
            ingredients=[{"name": "harina", "price": 5000, "qty": 0.5}],
            yield_pct=0.0,  # Invalid
        )
        with session_factory() as s:
            pc = compute_prime_cost(s, pid)
        assert pc.yield_corrected_cost_gs is None

    def test_missing_ingredient_price_marks_note(self, session_factory):
        """When an ingredient has no price, materials is None and we get a note."""
        Session = session_factory
        with Session() as s:
            ing = Ingredient(name="mystery", unit="kg", stock_qty=5.0, purchase_price_gs=None)
            s.add(ing); s.commit(); s.refresh(ing)
            r = Recipe(name="R", yield_qty=10, yield_unit="und")
            s.add(r); s.commit(); s.refresh(r)
            rl = RecipeLine(recipe_id=r.id, line_kind="ingredient", line_ref_id=ing.id, qty=1.0)
            s.add(rl)
            p = Product(name="P", sale_price_gs=5000, portion_label="1 und", recipe_id=r.id)
            s.add(p); s.commit(); s.refresh(p)
            pc = compute_prime_cost(s, p.id)
        assert pc.materials_cost_gs is None
        assert any("Faltan precios" in n for n in pc.notes)

    def test_nonexistent_product_returns_notes(self, session_factory):
        with session_factory() as s:
            pc = compute_prime_cost(s, 99999)
        assert pc.materials_cost_gs is None
        assert any("no existe" in n for n in pc.notes)


class TestProfitabilityMath:
    def test_gross_margin_pct_calculation(self, session_factory, setup_product_with_recipe):
        """Verify the gross margin percentage math."""
        # prime = 15000, sale = 30000 → margin = 15000, margin_pct = 50%
        pid = setup_product_with_recipe(
            ingredients=[{"name": "harina", "price": 5000, "qty": 0.5}],
            yield_pct=1.0,  # No correction
            labor_minutes=0,
            overhead_pct=0,
            sale_price=30000,
        )
        with session_factory() as s:
            pc = compute_prime_cost(s, pid)
        # Materials = 2500, no yield, no labor, no overhead → prime = 2500
        assert pc.prime_cost_gs == 2500
        assert pc.gross_margin_gs == 27500  # 30000 - 2500
        assert pc.gross_margin_pct == 91.7  # 27500/30000 * 100
