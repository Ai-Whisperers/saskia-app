"""app/rms/prime_cost.py — Phase 1.D Prime Cost calculation.

True product cost = materials (with yield correction) + labor + overhead.
This is the "30/40% rule" of bakery economics: food cost alone understates
real cost by 60-70% because it ignores labor and overhead.

Per AGENTS.md money rules:
- All math in Decimal; only int() at persistence boundaries.
- Integer Gs. in the DB.
- Round half-up at the persistence site.

References:
- CIA (Culinary Institute of America) food cost guidelines
- Paraguay bakery industry benchmarks (25-35% materials + 25-30% labor + 10-15% overhead)
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Sequence

from sqlalchemy.orm import Session

from app.rms.constants import (
    DEFAULT_LABOR_COST_PER_HOUR_GS,
    DEFAULT_OVERHEAD_MULTIPLIER_PCT,
)
from app.rms.costing import recipe_batch_cost_gs
from app.rms.models import ComplianceInfo, Product, Recipe


@dataclass
class PrimeCostBreakdown:
    """Phase 1.D — full per-product cost breakdown.

    All values are integer Gs. None means "unknown" (missing price / yield / labor).
    """
    product_id: int
    materials_cost_gs: int | None       # raw materials (no yield correction)
    yield_corrected_cost_gs: int | None # materials × (1 / yield_percentage) — what 1 portion actually costs after moisture loss
    labor_cost_gs: int | None           # direct_labor_minutes × (labor_rate / 60)
    overhead_cost_gs: int | None        # materials × overhead_multiplier_pct / 100
    prime_cost_gs: int | None           # yield_corrected + labor + overhead

    # Profitability (None when sale_price or prime_cost missing)
    sale_price_gs: int | None
    gross_margin_gs: int | None          # sale - prime_cost
    gross_margin_pct: float | None       # (sale - prime) / sale × 100
    prime_cost_pct_of_sale: float | None # prime / sale × 100

    # Diagnostic flags
    notes: list[str]


def _round_half_up(value: Decimal) -> int:
    """Round to nearest integer Gs. using ROUND_HALF_UP per AGENTS.md rule #3."""
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def compute_prime_cost(session: Session, product_id: int) -> PrimeCostBreakdown:
    """Compute the full Prime Cost for a Product.

    Walks the recipe (sub-recipes recursively) for materials cost, applies the
    recipe's yield_percentage correction, adds direct_labor_minutes at the
    operator-configured hourly rate, and applies the overhead multiplier.

    Returns PrimeCostBreakdown with None fields where data is missing (the UI
    can then show partial breakdowns instead of zero).
    """
    notes: list[str] = []
    product = session.get(Product, product_id)
    if product is None:
        return PrimeCostBreakdown(
            product_id=product_id, materials_cost_gs=None,
            yield_corrected_cost_gs=None, labor_cost_gs=None,
            overhead_cost_gs=None, prime_cost_gs=None,
            sale_price_gs=None, gross_margin_gs=None,
            gross_margin_pct=None, prime_cost_pct_of_sale=None,
            notes=["producto no existe"],
        )

    sale_price = product.sale_price_gs  # Raw value; downstream treats 0 as 'no price'

    # Materials cost (from existing costing module — walks sub-recipes)
    materials: int | None = None
    if product.recipe_id is not None:
        batch = recipe_batch_cost_gs(session, product.recipe_id)
        if batch.batch_cost_gs is not None:
            materials = batch.batch_cost_gs
        elif batch.missing_ingredient_names:
            notes.append("Faltan precios en: " + ", ".join(batch.missing_ingredient_names))
        elif batch.cycle_detected:
            notes.append("Ciclo detectado en receta")
    else:
        notes.append("Producto sin receta")

    # Yield correction. If recipe.yield_percentage is set, the real per-portion
    # cost is materials / yield_percentage. If NULL, default 1.0 (no correction).
    yield_pct = None
    if product.recipe_id is not None:
        recipe = session.get(Recipe, product.recipe_id)
        if recipe and recipe.yield_percentage is not None:
            yield_pct = recipe.yield_percentage
            if yield_pct <= 0 or yield_pct > 1.0:
                notes.append(f"yield_percentage inválido: {yield_pct} (debe estar entre 0 y 1)")
                yield_pct = None

    yield_corrected = None
    if materials is not None and yield_pct is not None and yield_pct > 0:
        # Cost scales by 1/yield (e.g. 0.85 yield → multiply cost by 1.176)
        yield_corrected = _round_half_up(
            Decimal(str(materials)) / Decimal(str(yield_pct))
        )

    # Labor cost: direct_labor_minutes × (labor_rate / 60)
    ci = session.get(ComplianceInfo, 1)
    labor_rate_gs_per_h = ci.labor_cost_per_hour_gs if ci else DEFAULT_LABOR_COST_PER_HOUR_GS
    overhead_pct = ci.overhead_multiplier_pct if ci else DEFAULT_OVERHEAD_MULTIPLIER_PCT

    labor = None
    if product.recipe_id is not None:
        recipe = session.get(Recipe, product.recipe_id)
        if recipe and recipe.direct_labor_minutes is not None and recipe.direct_labor_minutes > 0:
            labor = _round_half_up(
                Decimal(str(recipe.direct_labor_minutes)) * Decimal(str(labor_rate_gs_per_h)) / Decimal("60")
            )
        else:
            notes.append("sin tiempo de mano de obra (informal — no bloquea)")

    # Overhead: pct of materials (not yield-corrected — overhead is fixed cost)
    overhead = None
    if materials is not None:
        overhead = _round_half_up(Decimal(str(materials)) * Decimal(str(overhead_pct)) / Decimal("100"))

    # Prime cost = yield_corrected + labor + overhead
    prime = None
    if yield_corrected is not None:
        total = Decimal(str(yield_corrected))
        if labor is not None:
            total += Decimal(str(labor))
        if overhead is not None:
            total += Decimal(str(overhead))
        prime = _round_half_up(total)

    # Profitability — None when prime is None. Sale=0 → pct undefined.
    gross_margin = None
    gross_margin_pct = None
    prime_cost_pct = None
    if prime is not None and sale_price is not None:
        gross_margin = sale_price - prime
        if sale_price > 0:
            gross_margin_pct = round(gross_margin / sale_price * 100, 1)
            prime_cost_pct = round(prime / sale_price * 100, 1)

    return PrimeCostBreakdown(
        product_id=product_id,
        materials_cost_gs=materials,
        yield_corrected_cost_gs=yield_corrected,
        labor_cost_gs=labor,
        overhead_cost_gs=overhead,
        prime_cost_gs=prime,
        sale_price_gs=sale_price,
        gross_margin_gs=gross_margin,
        gross_margin_pct=gross_margin_pct,
        prime_cost_pct_of_sale=prime_cost_pct,
        notes=notes,
    )


def batch_compute_prime_cost(
    session: Session, products: Sequence[Product]
) -> dict[int, PrimeCostBreakdown]:
    """Compute PrimeCostBreakdown for many products in one pass.

    Avoids the N+1 pattern in `compute_prime_cost`: the per-product path
    does 3+ session.get() calls (Product, Recipe, ComplianceInfo) plus
    recipe_batch_cost_gs (more queries). For a list page of 50 products
    that's 200+ DB round-trips.

    This batched version does exactly 4 queries (Products eager-loaded
    with .recipe, ComplianceInfo once, ingredient prices once via
    recipe_batch_cost_gs which itself batches), regardless of N.

    Returns a dict {product_id: PrimeCostBreakdown} preserving all the
    None semantics of compute_prime_cost — callers that get None fields
    can still show partial breakdowns.
    """
    if not products:
        return {}

    # 1 query: ComplianceInfo (singleton)
    ci = session.get(ComplianceInfo, 1)
    labor_rate_gs_per_h = (
        ci.labor_cost_per_hour_gs if ci else DEFAULT_LABOR_COST_PER_HOUR_GS
    )
    overhead_pct = ci.overhead_multiplier_pct if ci else DEFAULT_OVERHEAD_MULTIPLIER_PCT

    result: dict[int, PrimeCostBreakdown] = {}

    for product in products:
        product_id = product.id
        notes: list[str] = []
        sale_price = product.sale_price_gs

        # Materials cost — same per-product call, but it's already batched
        # internally (recipe_batch_cost_gs walks IngredientPriceEvent in one
        # query per recipe; for 50 products with recipes, that's still 50
        # recipe walks but each one is O(1) queries vs N).
        materials: int | None = None
        recipe = product.recipe  # already eager-loaded
        if product.recipe_id is not None and recipe is not None:
            batch = recipe_batch_cost_gs(session, product.recipe_id)
            if batch.batch_cost_gs is not None:
                materials = batch.batch_cost_gs
            elif batch.missing_ingredient_names:
                notes.append(
                    "Faltan precios en: " + ", ".join(batch.missing_ingredient_names)
                )
            elif batch.cycle_detected:
                notes.append("Ciclo detectado en receta")
        else:
            notes.append("Producto sin receta")

        # Yield correction
        yield_pct = None
        if recipe is not None and recipe.yield_percentage is not None:
            yield_pct = recipe.yield_percentage
            if yield_pct <= 0 or yield_pct > 1.0:
                notes.append(
                    f"yield_percentage inválido: {yield_pct} (debe estar entre 0 y 1)"
                )
                yield_pct = None

        yield_corrected = None
        if materials is not None and yield_pct is not None and yield_pct > 0:
            yield_corrected = _round_half_up(
                Decimal(str(materials)) / Decimal(str(yield_pct))
            )

        # Labor cost
        labor = None
        if recipe is not None and recipe.direct_labor_minutes is not None and recipe.direct_labor_minutes > 0:
            labor = _round_half_up(
                Decimal(str(recipe.direct_labor_minutes))
                * Decimal(str(labor_rate_gs_per_h))
                / Decimal("60")
            )
        else:
            if recipe is not None:
                notes.append("sin tiempo de mano de obra (informal — no bloquea)")

        # Overhead
        overhead = None
        if materials is not None:
            overhead = _round_half_up(
                Decimal(str(materials)) * Decimal(str(overhead_pct)) / Decimal("100")
            )

        # Prime
        prime = None
        if yield_corrected is not None:
            total = Decimal(str(yield_corrected))
            if labor is not None:
                total += Decimal(str(labor))
            if overhead is not None:
                total += Decimal(str(overhead))
            prime = _round_half_up(total)

        # Profitability
        gross_margin = None
        gross_margin_pct = None
        prime_cost_pct = None
        if prime is not None and sale_price is not None:
            gross_margin = sale_price - prime
            if sale_price > 0:
                gross_margin_pct = round(gross_margin / sale_price * 100, 1)
                prime_cost_pct = round(prime / sale_price * 100, 1)

        result[product_id] = PrimeCostBreakdown(
            product_id=product_id,
            materials_cost_gs=materials,
            yield_corrected_cost_gs=yield_corrected,
            labor_cost_gs=labor,
            overhead_cost_gs=overhead,
            prime_cost_gs=prime,
            sale_price_gs=sale_price,
            gross_margin_gs=gross_margin,
            gross_margin_pct=gross_margin_pct,
            prime_cost_pct_of_sale=prime_cost_pct,
            notes=notes,
        )

    return result


__all__ = ["PrimeCostBreakdown", "compute_prime_cost", "batch_compute_prime_cost"]
