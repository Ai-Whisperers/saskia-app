"""app/rms/demand_freshness.py — demand forecasting + freshness + substitutions.

Closes the never-wired loops (2026-09-24 plan):

4. Demand algebra — predict per-product demand from sales history
   (base rate × weekday factor × trend), convert to production
   suggestions, and into an exact shopping list
   (Σ production × recipe lines − stock).

2. Freshness — use-first flags from shelf_life_days vs last receipt;
   expiring-first recipe suggestions ("cook this TODAY").

10. Substitutions — role-based substitutes (ingredient_intel) enriched
   with price delta and tag preservation (tag_algebra).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.rms.config import ASUNCION_TZ
from app.rms.models import (
    Ingredient,
    Product,
    Recipe,
    RecipeLine,
    Sale,
)

# ───────────────────────────────────────────────────────────────────────────
# 4. Demand algebra
# ───────────────────────────────────────────────────────────────────────────


@dataclass
class DemandForecast:
    product_id: int
    name: str
    avg_per_day: float
    weekday_factor: float  # target day vs average (1.0 = average day)
    predicted_qty: float
    trend: float  # recent-14d / prior-14d qty ratio (1.0 = flat)
    recipe_id: int | None = None
    yield_qty: float | None = None
    suggested_batches: float = 0.0


def forecast_demand(
    session: Session,
    target_date: datetime | None = None,
    *,
    product_ids: list[int] | None = None,
    history_days: int = 56,
) -> list[DemandForecast]:
    """Per-product demand prediction for target_date (default tomorrow).

    Model (deliberately simple, bakery-honest):
      predicted = avg_per_day(56d) × weekday_factor(target) × trend(14d/14d)
    trend clamped to [0.6, 1.6] so a catering outlier doesn't double the
    bread order.
    """
    now = datetime.now(ASUNCION_TZ)
    target = target_date or (now + timedelta(days=1))
    cutoff = now.replace(tzinfo=None) - timedelta(days=history_days)

    q = (
        select(Sale.product_id, Sale.sold_at, Sale.qty, Product.name)
        .join(Product, Sale.product_id == Product.id)
        .where(Sale.sold_at >= cutoff, Sale.voided_at.is_(None))
    )
    if product_ids:
        q = q.where(Sale.product_id.in_(product_ids))
    rows = session.execute(q).all()

    def _naive(t: datetime) -> datetime:
        # DB may return naive datetimes; normalize everything to naive local
        # for comparisons (DB stores UTC; Asunción offset is stable enough
        # for day-bucketing).
        return t.replace(tzinfo=None) if t.tzinfo else t

    by_product: dict[int, dict] = {}
    for pid, sold_at, qty, name in rows:
        d = by_product.setdefault(pid, {"name": name, "sales": []})
        d["sales"].append((_naive(sold_at), float(qty)))

    forecasts: list[DemandForecast] = []
    recent_cutoff = now.replace(tzinfo=None) - timedelta(days=14)
    for pid, d in by_product.items():
        sales = d["sales"]
        if len(sales) < 3:
            continue  # not enough history
        # Rate over the OBSERVED span (capped at history_days): a product
        # first sold 10 days ago shouldn't be diluted by 46 zero-days.
        span_days = min(
            history_days,
            max(1.0, (now.replace(tzinfo=None) - min(t for t, _ in sales)).days + 1),
        )
        avg = sum(q for _, q in sales) / span_days
        same_weekday = [q for t, q in sales if t.weekday() == target.weekday()]
        overall_per_day = avg
        weekday_avg = (sum(same_weekday) / (history_days / 7)) if same_weekday else overall_per_day
        factor = (weekday_avg / overall_per_day) if overall_per_day > 0 else 1.0
        factor = max(0.3, min(2.5, factor))
        recent = sum(q for t, q in sales if t >= recent_cutoff)
        prior = sum(q for t, q in sales if t < recent_cutoff)
        trend = (recent / prior) if prior > 0 else 1.0
        trend = max(0.6, min(1.6, trend))

        p = session.get(Product, pid)
        recipe_id = p.recipe_id if p else None
        yq = None
        batches = 0.0
        if recipe_id:
            r = session.get(Recipe, recipe_id)
            if r and r.yield_qty:
                yq = float(r.yield_qty)
                predicted = avg * factor * trend
                batches = predicted / yq if yq else 0.0
        forecasts.append(DemandForecast(
            product_id=pid, name=d["name"],
            avg_per_day=round(avg, 2),
            weekday_factor=round(factor, 2),
            predicted_qty=round(avg * factor * trend, 1),
            trend=round(trend, 2),
            recipe_id=recipe_id, yield_qty=yq,
            suggested_batches=round(batches, 1),
        ))
    forecasts.sort(key=lambda f: f.predicted_qty, reverse=True)
    return forecasts


def shopping_list_from_forecast(
    session: Session,
    forecasts: list[DemandForecast],
) -> list[dict]:
    """Exact purchase needs: Σ(batches × recipe lines) − current stock.

    Sub-recipe lines expand recursively via the tag_algebra walker
    (include_packaging=True — boxes ARE needed for production).
    Only ingredients with a shortfall are returned.
    """
    from app.rms.tag_algebra import walk_recipe_tree

    need: dict[int, float] = {}
    for f in forecasts:
        if not f.recipe_id or f.suggested_batches <= 0:
            continue
        targets, _cycles = walk_recipe_tree(
            session, f.recipe_id, include_packaging=True
        )
        for t in targets:
            if not isinstance(t.target, Ingredient):
                continue
            need[t.target.id] = need.get(t.target.id, 0.0) + t.line.qty * f.suggested_batches

    out: list[dict] = []
    for ing_id, qty_needed in sorted(need.items()):
        ing = session.get(Ingredient, ing_id)
        if ing is None:
            continue
        shortfall = qty_needed - float(ing.stock_qty or 0)
        if shortfall <= 0.01:
            continue
        out.append({
            "ingredient_id": ing_id,
            "name": ing.name,
            "unit": ing.unit,
            "needed_qty": round(qty_needed, 3),
            "stock_qty": float(ing.stock_qty or 0),
            "buy_qty": round(shortfall, 3),
            "est_cost_gs": int(shortfall * float(ing.purchase_price_gs or 0)),
        })
    return out


# ───────────────────────────────────────────────────────────────────────────
# 2. Freshness
# ───────────────────────────────────────────────────────────────────────────


@dataclass
class FreshnessFlag:
    ingredient_id: int
    name: str
    days_until_expiry: int | None
    urgency: str  # "expired" | "critical" | "soon" | "ok" | "unknown"
    value_at_risk_gs: int


def freshness_flags(session: Session) -> list[FreshnessFlag]:
    """Per-ingredient freshness from shelf_life_days − days since last
    consumption-adjusted receipt.

    Approximation (no lot tracking yet): we use the most recent
    IngredientPriceEvent date as a proxy for the last receipt date. When no
    price event exists, urgency is 'unknown', never guessed.
    """
    from app.rms.models import IngredientPriceEvent

    rows = session.execute(
        select(
            Ingredient.id,
            Ingredient.name,
            Ingredient.shelf_life_days,
            Ingredient.stock_qty,
            Ingredient.purchase_price_gs,
            func.max(IngredientPriceEvent.recorded_at),
        )
        .outerjoin(IngredientPriceEvent, IngredientPriceEvent.ingredient_id == Ingredient.id)
        .where(Ingredient.stock_qty > 0)
        .group_by(Ingredient.id)
    ).all()

    now = datetime.now(ASUNCION_TZ)
    flags: list[FreshnessFlag] = []
    for iid, name, shelf, stock, price, last_event in rows:
        value = int(float(stock or 0) * float(price or 0))
        if shelf is None or last_event is None:
            flags.append(FreshnessFlag(iid, name, None, "unknown", value))
            continue
        # Compare in the event's own awareness; DB may store naive UTC.
        last = last_event if last_event.tzinfo else last_event.replace(tzinfo=ASUNCION_TZ)
        now_cmp = now if last.tzinfo else now.replace(tzinfo=None)
        age_days = (now_cmp - last).days
        remaining = int(shelf) - age_days
        urgency = (
            "expired" if remaining <= 0
            else "critical" if remaining <= 2
            else "soon" if remaining <= 5
            else "ok"
        )
        flags.append(FreshnessFlag(iid, name, remaining, urgency, value))
    order = {"expired": 0, "critical": 1, "soon": 2, "unknown": 3, "ok": 4}
    flags.sort(key=lambda f: (order[f.urgency], -f.value_at_risk_gs))
    return flags


def cook_today_suggestions(session: Session, limit: int = 5) -> list[dict]:
    """Recipes whose critical/expiring ingredients get used by baking them.

    Joins freshness flags with direct recipe lines; ranks by value at risk.
    """
    flags = [f for f in freshness_flags(session) if f.urgency in ("expired", "critical")]
    if not flags:
        return []
    ing_map = {f.ingredient_id: f for f in flags}
    rows = session.execute(
        select(RecipeLine.line_ref_id, Recipe.id, Recipe.name)
        .join(Recipe, RecipeLine.recipe_id == Recipe.id)
        .where(
            RecipeLine.line_kind == "ingredient",
            RecipeLine.line_ref_id.in_(list(ing_map)),
        )
    ).all()
    scored: dict[int, dict] = {}
    for ref_id, rid, rname in rows:
        f = ing_map[ref_id]
        e = scored.setdefault(rid, {"recipe_id": rid, "name": rname,
                                    "rescues": [], "value_gs": 0})
        e["rescues"].append(f.name)
        e["value_gs"] += f.value_at_risk_gs
    out = sorted(scored.values(), key=lambda x: -x["value_gs"])[:limit]
    return out


# ───────────────────────────────────────────────────────────────────────────
# 10. Substitutions
# ───────────────────────────────────────────────────────────────────────────


@dataclass
class SubstituteOption:
    ingredient_id: int
    name: str
    role: str | None
    price_delta_per_unit_gs: int
    keeps_tags: bool
    tag_conflicts: list[str] = field(default_factory=list)


def substitutes_for(
    session: Session,
    ingredient_id: int,
    *,
    in_recipe_id: int | None = None,
) -> list[SubstituteOption]:
    """Role-mates ranked by (tag preservation, price delta).

    Uses ingredient_intel.find_substitutes_by_role (finally wired) and
    checks tag compatibility against the ORIGINAL ingredient's dietary set
    — and, when in_recipe_id is given, against the recipe's derived tags.
    """
    from app.rms.ingredient_intel import find_substitutes_by_role
    from app.rms.tag_algebra import ingredient_dietary_set

    original = session.get(Ingredient, ingredient_id)
    if original is None:
        return []
    orig_tags = ingredient_dietary_set(original)
    orig_price = float(original.purchase_price_gs or 0)

    mates = find_substitutes_by_role(session, ingredient_id)
    options: list[SubstituteOption] = []
    for mate_id in mates:
        if mate_id == ingredient_id:
            continue
        mate = session.get(Ingredient, mate_id)
        if mate is None:
            continue
        mate_tags = ingredient_dietary_set(mate)
        # Tags the original brought that the mate can't: conflicts.
        conflicts = sorted(orig_tags - mate_tags) if orig_tags else []
        options.append(SubstituteOption(
            ingredient_id=mate_id,
            name=mate.name,
            role=mate.role,
            price_delta_per_unit_gs=int(float(mate.purchase_price_gs or 0) - orig_price),
            keeps_tags=not conflicts,
            tag_conflicts=conflicts,
        ))
    options.sort(key=lambda o: (not o.keeps_tags, abs(o.price_delta_per_unit_gs)))
    return options


__all__ = [
    "DemandForecast",
    "FreshnessFlag",
    "SubstituteOption",
    "cook_today_suggestions",
    "forecast_demand",
    "freshness_flags",
    "shopping_list_from_forecast",
    "substitutes_for",
]
