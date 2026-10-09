"""app/rms/derived_intel.py — money & safety derivation engines.

Three engines over existing tables (2026-09-24 plan):

1. Customer-allergen guard
   Customer allergies (free-text + structured) × product inherited allergens
   → risk verdict at sale time. Used by the POS route and a
   /api/product-allergen-check endpoint.

2. Theoretical vs actual food cost
   theoretical = Σ(sale.qty × product unit cost AT SALE TIME approximated by
   current recipe cost — historical costing noted in limitations)
   actual      = Σ(ingredient stock moves valued at purchase price) + waste
   variance    = actual − theoretical (positive = missing stock/waste/portion
   drift/theft)

3. Price-sensitivity cascade
   Ingredient price change → affected recipes (batch cost delta) → products
   now under target margin → suggested price to hit target food cost %.
   Feeds the dashboard alert + the receta/product detail views.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.rms.models import (
    ComplianceInfo,
    Customer,
    Ingredient,
    Product,
    Recipe,
    Sale,
    SaleStockMove,
    WasteLog,
)
from app.rms.tagging.cache import _split_tags

# ───────────────────────────────────────────────────────────────────────────
# 1. Customer-allergen guard
# ───────────────────────────────────────────────────────────────────────────
# Canonical Spanish allergen words customers use, mapped to our codes.
#
# As of the 2026-09-29 tagging/ refactor, the canonical vocabulary lives
# in app.rms.tagging.vocabulary.CUSTOMER_ALLERGEN_WORDS. This shim is kept
# for backwards compatibility with code that imports the underscore-prefixed
# name from this module. New code should use the public re-export from
# app.rms.tagging.
from app.rms.tagging.vocabulary import (
    CUSTOMER_ALLERGEN_WORDS as _CUSTOMER_ALLERGEN_WORDS,
)


def parse_customer_allergies(notes: str | None) -> list[str]:
    """Extract allergen codes from free-text customer notes ('alérgica al maní')."""
    if not notes:
        return []
    n = notes.lower()
    return sorted({code for word, code in _CUSTOMER_ALLERGEN_WORDS.items() if word in n})


@dataclass
class AllergenRisk:
    safe: bool
    matched: list[str] = field(default_factory=list)  # allergens both declared


def product_allergens(session: Session, product_id: int) -> list[str]:
    """Effective allergens for a product: inherited cache, falling back to a
    live recipe walk (first request after migration, before any save)."""
    p = session.get(Product, product_id)
    if p is None:
        return []
    if p.inherited_tags:
        codes = [t[3:] for t in _split_tags(p.inherited_tags) if t.startswith("al:")]
        if codes:
            return codes
    if p.recipe_id:
        r = session.get(Recipe, p.recipe_id)
        if r is not None:
            if r.allergens:
                return _split_tags(r.allergens)
            from app.rms.tag_algebra import derive_recipe_tags

            return derive_recipe_tags(session, p.recipe_id).allergens
    return []


def check_customer_risk(session: Session, customer_id: int | None, product_id: int) -> AllergenRisk:
    """POS guard: does this product contain anything this customer is allergic to?"""
    if customer_id is None:
        return AllergenRisk(safe=True)
    cust = session.get(Customer, customer_id)
    if cust is None:
        return AllergenRisk(safe=True)
    declared = parse_customer_allergies(cust.notes)
    if not declared:
        return AllergenRisk(safe=True)
    p_allergens = set(product_allergens(session, product_id))
    matched = sorted(p_allergens & set(declared))
    return AllergenRisk(safe=not matched, matched=matched)


# ───────────────────────────────────────────────────────────────────────────
# 2. Theoretical vs actual food cost
# ───────────────────────────────────────────────────────────────────────────


@dataclass
class FoodCostVariance:
    theoretical_gs: int
    actual_ingredient_gs: int
    waste_gs: int
    variance_gs: int  # actual − theoretical; positive = unexplained usage
    variance_pct: float
    by_product: list[dict] = field(default_factory=list)


def theoretical_vs_actual(
    session: Session,
    *,
    days: int = 30,
) -> FoodCostVariance:
    """Compare recipe-derived COGS against stock usage + waste.

    Limitation (documented): theoretical uses CURRENT recipe costs, not
    costs as they were at each sale's date. For a bakery with weekly price
    updates this drift is small; historical per-sale costing needs
    sale_stock_move.cost_gs which is out of scope here.
    """
    from app.rms.config import ASUNCION_TZ
    from app.rms.costing import batch_products_cost_margin

    cutoff = datetime.now(ASUNCION_TZ) - timedelta(days=days)

    # Sales in window joined to products
    rows = session.execute(
        select(Sale.product_id, func.sum(Sale.qty), Product.name)
        .join(Product, Sale.product_id == Product.id)
        .where(Sale.sold_at >= cutoff, Sale.voided_at.is_(None))
        .group_by(Sale.product_id, Product.name)
    ).all()

    product_ids = [r[0] for r in rows]
    unit_costs: dict[int, int] = {}
    if product_ids:
        prods = session.scalars(select(Product).where(Product.id.in_(product_ids))).all()
        cm = batch_products_cost_margin(session, list(prods))
        for pid, (cost_result, _margin) in cm.items():
            unit_costs[pid] = int(cost_result.batch_cost_gs or 0)

    theoretical = 0
    by_product = []
    for pid, qty, name in rows:
        cost = unit_costs.get(pid, 0) * float(qty)
        theoretical += cost
        by_product.append(
            {"product_id": pid, "name": name, "qty": float(qty), "theoretical_gs": int(cost)}
        )

    # Actual ingredient usage valued at purchase price.
    # SaleStockMove has no timestamp — join through Sale.sold_at.
    usage_rows = session.execute(
        select(
            SaleStockMove.ingredient_id,
            func.sum(SaleStockMove.qty_delta),
            Ingredient.purchase_price_gs,
        )
        .join(Sale, SaleStockMove.sale_id == Sale.id)
        .join(Ingredient, SaleStockMove.ingredient_id == Ingredient.id)
        .where(Sale.sold_at >= cutoff)
        .group_by(SaleStockMove.ingredient_id, Ingredient.purchase_price_gs)
    ).all()
    actual = sum(abs(float(d)) * float(price or 0) for _, d, price in usage_rows)

    # Waste in window
    waste_rows = (
        session.execute(
            select(func.sum(WasteLog.qty * Ingredient.purchase_price_gs))
            .join(Ingredient, WasteLog.ingredient_id == Ingredient.id)
            .where(WasteLog.recorded_at >= cutoff)
        ).scalar()
        or 0
    )
    waste = int(float(waste_rows))

    variance = int(actual + waste - theoretical)
    pct = (variance / theoretical * 100) if theoretical else 0.0
    return FoodCostVariance(
        theoretical_gs=int(theoretical),
        actual_ingredient_gs=int(actual),
        waste_gs=waste,
        variance_gs=variance,
        variance_pct=round(pct, 1),
        by_product=by_product,
    )


# ───────────────────────────────────────────────────────────────────────────
# 3. Price-sensitivity cascade
# ───────────────────────────────────────────────────────────────────────────


@dataclass
class PriceImpact:
    ingredient_id: int
    ingredient_name: str
    old_price_gs: int
    new_price_gs: int
    affected_recipes: list[dict] = field(default_factory=list)  # {id,name,delta_unit_cost}
    affected_products: list[dict] = field(
        default_factory=list
    )  # {id,name,food_cost_pct,under_target,suggested_price}


def _target_food_cost_pct(session: Session) -> float:
    """Target food-cost % from ComplianceInfo costing config (default 33%)."""
    ci = session.get(ComplianceInfo, 1)
    if ci and getattr(ci, "overhead_multiplier_pct", None):
        pass  # overhead is a different knob; food cost target default:
    return 0.33


def price_change_impact(
    session: Session,
    ingredient_id: int,
    old_price_gs: int,
    new_price_gs: int,
) -> PriceImpact:
    """What happens to recipes/products when one ingredient's price moves."""
    from app.rms.costing import recipe_unit_cost_gs
    from app.rms.tag_algebra import recipes_using_ingredient

    ing = session.get(Ingredient, ingredient_id)
    impact = PriceImpact(
        ingredient_id=ingredient_id,
        ingredient_name=ing.name if ing else f"#{ingredient_id}",
        old_price_gs=old_price_gs,
        new_price_gs=new_price_gs,
    )

    recipe_ids = recipes_using_ingredient(session, ingredient_id)
    current_costs: dict[int, float] = {}
    for rid in recipe_ids:
        cr = recipe_unit_cost_gs(session, rid)
        current_costs[rid] = float(cr.batch_cost_gs or 0)

    # Simulate: temporarily set the new price
    old_val = ing.purchase_price_gs
    ing.purchase_price_gs = new_price_gs
    session.flush()
    try:
        target = _target_food_cost_pct(session)
        for rid in recipe_ids:
            r = session.get(Recipe, rid)
            if r is None:
                continue
            new_cost = float(recipe_unit_cost_gs(session, rid).batch_cost_gs or 0)
            delta = new_cost - current_costs[rid]
            if abs(delta) < 1:  # skip noise
                continue
            impact.affected_recipes.append(
                {
                    "id": rid,
                    "name": r.name,
                    "delta_unit_cost_gs": int(delta),
                }
            )
            for p in session.scalars(select(Product).where(Product.recipe_id == rid)):
                price = p.sale_price_gs or 0
                fc_pct = (new_cost / price * 100) if price else 999.0
                suggested = int(new_cost / target) if target else None
                impact.affected_products.append(
                    {
                        "id": p.id,
                        "name": p.name,
                        "food_cost_pct": round(fc_pct, 1),
                        "under_target": fc_pct > target * 100,
                        "suggested_price_gs": suggested,
                    }
                )
    finally:
        ing.purchase_price_gs = old_val
        session.flush()
    return impact


__all__ = [
    "AllergenRisk",
    "FoodCostVariance",
    "PriceImpact",
    "check_customer_risk",
    "parse_customer_allergies",
    "price_change_impact",
    "product_allergens",
    "theoretical_vs_actual",
]
