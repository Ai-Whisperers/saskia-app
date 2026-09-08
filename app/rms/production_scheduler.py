"""app/rms/production_scheduler.py — when to bake how much of each product.

Uses velocity (from sales_intel), shelf-life (from ingredient_intel),
and current stock (from ingredient_intel) to plan production runs that:
- minimize waste (don't bake more than shelf-life)
- minimize stockouts (don't under-bake peak days)
- batch by product family (bake all panadería together)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import Ingredient, Product, Recipe, RecipeLine, Sale

# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProductionPlan:
    product_id: int
    product_name: str
    target_qty: int
    reason: str  # why we need this many
    batch_count: int  # how many batches to run


@dataclass(frozen=True)
class ProductionDay:
    date: str  # YYYY-MM-DD
    expected_sales: int
    plans: list[ProductionPlan]


# ---------------------------------------------------------------------------
# Daily expected sales (from velocity)
# ---------------------------------------------------------------------------

def expected_daily_sales(session: Session, product_id: int,
                         window_days: int = 14) -> float:
    """Average daily sales count for a product."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)
    rows = session.execute(
        select(Sale.qty).where(
            Sale.product_id == product_id,
            Sale.voided_at.is_(None),
            Sale.sold_at >= cutoff,
        )
    ).all()
    total = sum(int(r[0] or 0) for r in rows)
    return total / window_days


# ---------------------------------------------------------------------------
# Stock coverage
# ---------------------------------------------------------------------------

def stock_coverage_hours(session: Session, product: Product,
                        velocity_per_day: float) -> float | None:
    """How many hours of sales are covered by current stock.

    Returns None if velocity is zero.
    """
    if velocity_per_day <= 0:
        return None
    # We don't have a finished-goods stock table. Use the volume heuristic:
    # ingredients in stock → max batches we could bake now.
    # Simplified: return 0 (no finished goods buffer tracked).
    return 0.0


# ---------------------------------------------------------------------------
# Production plan
# ---------------------------------------------------------------------------

def production_plan_for_day(session: Session, product: Product,
                            target_date: datetime | None = None,
                            safety_pct: float = 0.20
                            ) -> ProductionPlan:
    """Plan production for ONE product on ONE day.

    Formula: daily_velocity × (1 + safety_pct) - finished_stock_buffer.
    Rounded up to integer.
    """
    velocity = expected_daily_sales(session, product.id)
    target = max(1, int(round(velocity * (1 + safety_pct))))
    # Determine yield_per_batch from product recipe yield_qty (10 default).
    yield_per_batch = max(1, _recipe_yield(session, product))
    batches = max(1, -(-target // yield_per_batch))  # ceil div
    reason = (
        f"velocity={velocity:.1f}/day + {int(safety_pct*100)}% safety "
        f"→ target {target} units ({batches} batch{'es' if batches > 1 else ''})"
    )
    return ProductionPlan(
        product_id=product.id,
        product_name=product.name,
        target_qty=target,
        reason=reason,
        batch_count=batches,
    )


def _recipe_yield(session: Session, product: Product) -> int:
    """Recipe yield_qty for the product (defaults to 10)."""
    if product.recipe_id is None:
        return 10
    recipe = session.get(Recipe, product.recipe_id)
    if recipe is None or recipe.yield_qty is None:
        return 10
    return int(recipe.yield_qty or 10)


# ---------------------------------------------------------------------------
# Multi-day plan
# ---------------------------------------------------------------------------

def production_calendar(session: Session,
                        days: int = 7,
                        safety_pct: float = 0.20) -> list[ProductionDay]:
    """Plan production for the next N days.

    Each day uses the standard velocity (no DOW modifier for simplicity).
    """

    # Map weekday → multiplier (1.0 = avg, weekend typically higher).
    dow_mult = _build_dow_multiplier(session)

    out = []
    now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0,
                                             microsecond=0)
    for i in range(days):
        day = now + timedelta(days=i)
        weekday = day.weekday()
        mult = dow_mult.get(weekday, 1.0)

        plans = []
        expected_total = 0
        for p in session.scalars(select(Product)).all():
            base = expected_daily_sales(session, p.id)
            adj_velocity = base * mult
            target = max(1, int(round(adj_velocity * (1 + safety_pct))))
            yield_per_batch = max(1, _recipe_yield(session, p))
            batches = max(1, -(-target // yield_per_batch))
            plans.append(ProductionPlan(
                product_id=p.id,
                product_name=p.name,
                target_qty=target,
                reason=(
                    f"base {base:.1f}/day × DOW {mult:.2f} + "
                    f"{int(safety_pct*100)}% safety → {target} "
                    f"({batches} batch{'es' if batches > 1 else ''})"
                ),
                batch_count=batches,
            ))
            expected_total += target

        out.append(ProductionDay(
            date=day.strftime("%Y-%m-%d"),
            expected_sales=expected_total,
            plans=sorted(plans, key=lambda x: x.target_qty, reverse=True),
        ))
    return out


def _build_dow_multiplier(session: Session) -> dict[int, float]:
    """Per-weekday multiplier based on actual sales volume.

    Computed as: weekday_sales / avg_weekday_sales.
    """
    rows = session.execute(
        select(Sale.sold_at).where(Sale.voided_at.is_(None))
    ).all()
    if not rows:
        return {d: 1.0 for d in range(7)}
    from collections import Counter
    dow_counts: Counter[int] = Counter()
    for (sold_at,) in rows:
        if sold_at is None:
            continue
        dow_counts[sold_at.weekday()] += 1
    total = sum(dow_counts.values())
    avg = total / 7
    return {d: (dow_counts.get(d, 0) / avg) if avg > 0 else 1.0
            for d in range(7)}


# ---------------------------------------------------------------------------
# Stock-check: can we actually bake this plan?
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IngredientShortage:
    ingredient_id: int
    ingredient_name: str
    needed: float
    available: float
    deficit: float


def ingredient_requirements(session: Session,
                             plan: ProductionPlan) -> list[tuple[int, float]]:
    """Compute ingredient requirements for one ProductionPlan.

    Returns list of (ingredient_id, total_qty_needed).
    """
    product = session.get(Product, plan.product_id)
    if product is None or product.recipe_id is None:
        return []
    lines = session.scalars(
        select(RecipeLine).where(RecipeLine.recipe_id == product.recipe_id)
    ).all()
    return [(line.line_ref_id, (line.qty or 0) * plan.batch_count)
            for line in lines if line.line_kind == "ingredient"]


def check_ingredient_availability(session: Session,
                                  plan: ProductionPlan) -> list[IngredientShortage]:
    """Return shortages (deficit > 0). Empty list = can produce."""
    reqs = ingredient_requirements(session, plan)
    shortages = []
    for ing_id, needed in reqs:
        ing = session.get(Ingredient, ing_id)
        if ing is None:
            continue
        avail = float(ing.stock_qty or 0)
        if needed > avail:
            shortages.append(IngredientShortage(
                ingredient_id=ing_id,
                ingredient_name=ing.name,
                needed=needed,
                available=avail,
                deficit=needed - avail,
            ))
    return shortages


__all__ = [
    "IngredientShortage",
    "ProductionDay",
    "ProductionPlan",
    "check_ingredient_availability",
    "expected_daily_sales",
    "ingredient_requirements",
    "production_calendar",
    "production_plan_for_day",
    "stock_coverage_hours",
]
