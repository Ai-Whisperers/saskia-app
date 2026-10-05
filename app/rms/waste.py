"""app/rms/waste.py — Merma (waste) tracking (E22).

Per docs/plans/2026-09-07-sazon-complete-epic-plan-v3.md E22.

Adds:
- WasteLog model: ingredient, qty, reason, cost_gs (denormalized at
  insert time so historical cost changes don't retro-affect),
  notes, recorded_at, recorded_by
- WasteReason enum: vencida (expired), quemada (burned),
  derrame (spilled), robo (stolen), danio_despacho (delivery
  damage), receta_incompleta (recipe incomplete), otra (other)
- Pure-Python helpers for CRUD + reporting
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum

from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.rms.models import Ingredient, Recipe, StockMovement, WasteLog
from app.rms.money import to_int_gs
from app.rms.units import Unit, can_convert, convert_qty


class WasteReason(str, Enum):
    """Reason for the waste event."""

    VENCIDA = "vencida"
    QUEMADA = "quemada"
    DERRAME = "derrame"
    ROBO = "robo"
    DANIO_DESPACHO = "danio_despacho"
    RECETA_INCOMPLETA = "receta_incompleta"
    OTRA = "otra"


@dataclass
class WasteImpact:
    """Summary of waste cost in a period."""

    n_events: int = 0
    total_qty: float = 0.0
    total_cost_gs: int = 0
    by_reason: dict[str, int] = field(default_factory=dict)
    by_ingredient: list[tuple[int, str, int]] = field(default_factory=list)


# --- CRUD ---


def record_waste(
    session: Session,
    *,
    ingredient_id: int,
    qty: float,
    reason: WasteReason,
    recorded_by: str | None = None,
    notes: str | None = None,
    qty_unit: str | None = None,
) -> WasteLog:
    """Log a waste event. Decrements stock + records cost-at-time.

    Cost is denormalized at insert time so historical waste reports
    remain stable even if purchase prices change.

    MER-01: qty_unit lets the operator enter 200 g of harina instead of
    0.2 kg (or 50 ml of leche instead of 0.05 l). Cross-family conversion
    (g→l, kg→und) is forbidden — see app.rms.units.Unit.coerce.
    """
    ing = session.get(Ingredient, ingredient_id)
    if ing is None:
        raise ValueError(f"Ingredient {ingredient_id} not found")
    # MER-01: normalize the input unit to the ingredient's stock unit.
    # The form's "Cantidad" + "Unidad" pair is converted to kg/l/und BEFORE
    # stock decrement so 50 g of harina truly deducts 0.05 kg.
    qty_in_stock_unit = qty
    if qty_unit and ing.unit and qty_unit != ing.unit:
        from_unit = Unit.coerce(qty_unit)
        to_unit = Unit.coerce(ing.unit)
        if not can_convert(from_unit, to_unit):
            raise HTTPException(
                status_code=400,
                detail=f"No se puede convertir {qty_unit} a {ing.unit} (familia distinta)",
            )
        qty_in_stock_unit = float(convert_qty(qty, from_unit, to_unit))
    cost_gs = (
        to_int_gs(Decimal(str(qty_in_stock_unit)) * Decimal(str(ing.purchase_price_gs)))
        if ing.purchase_price_gs is not None
        else 0
    )
    log = WasteLog(
        ingredient_id=ingredient_id,
        qty=qty_in_stock_unit,
        reason=reason.value,
        cost_gs=cost_gs,
        recorded_at=datetime.now(timezone.utc),
        recorded_by=recorded_by,
        notes=notes,
    )
    session.add(log)
    # Decrement stock
    old_stock = ing.stock_qty
    new_stock = max(0.0, old_stock - qty_in_stock_unit)
    ing.stock_qty = new_stock
    # BACKLOG #13 (2026-10-02): keep ingredient.avg_cost_gs in sync with
    # the waste event using the moving-average formula:
    #   new_avg = ((old_avg * old_stock) - waste_cost) / new_stock
    # where waste_cost is the cost at the time the waste happened
    # (already denormalized in `cost_gs`). Falls back to NULL when
    # new_stock is zero (no basis to compute an average).
    old_avg = ing.avg_cost_gs
    if new_stock > 0:
        if old_avg is not None and old_stock > 0:
            numerator = (old_avg * old_stock) - cost_gs
            # Defensive: numerator shouldn't go negative (waste can't
            # cost more than the stock on hand), but if it does, clamp.
            numerator = max(0, numerator)
            ing.avg_cost_gs = round(numerator / new_stock)
        elif ing.purchase_price_gs is not None:
            # No prior avg — initialize from purchase price.
            ing.avg_cost_gs = ing.purchase_price_gs
        # else: leave as None — analytics falls back to purchase_price_gs
    else:
        # Stock fully depleted by this waste — no basis for an average.
        ing.avg_cost_gs = None
    # StockMovement audit record (negative qty = stock out)
    movement = StockMovement(
        ingredient_id=ingredient_id,
        movement_type="merma",
        qty=-qty_in_stock_unit,
        reason=f"Merma: {reason.value}",
        reference_id=log.id,
        reference_type="waste_log",
        recorded_at=datetime.now(timezone.utc),
        created_by=recorded_by,
    )
    session.add(movement)
    session.flush()
    return log


def list_waste(
    session: Session,
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    reason: WasteReason | None = None,
    ingredient_id: int | None = None,
    limit: int = 100,
) -> list[WasteLog]:
    """Return recent waste events with optional filters."""
    q = select(WasteLog).order_by(WasteLog.recorded_at.desc())
    if start_date:
        q = q.where(WasteLog.recorded_at >= start_date)
    if end_date:
        q = q.where(WasteLog.recorded_at <= end_date)
    if reason is not None:
        q = q.where(WasteLog.reason == reason.value)
    if ingredient_id is not None:
        q = q.where(WasteLog.ingredient_id == ingredient_id)
    return list(session.execute(q.limit(limit)).scalars())


def waste_impact(
    session: Session,
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> WasteImpact:
    """Aggregate waste cost in a period."""
    if start_date is None:
        start_date = datetime.now(timezone.utc) - timedelta(days=30)
    if end_date is None:
        end_date = datetime.now(timezone.utc)

    # Aggregate by reason
    reason_q = (
        select(WasteLog.reason, func.sum(WasteLog.cost_gs), func.count(WasteLog.id))
        .where(WasteLog.recorded_at >= start_date, WasteLog.recorded_at <= end_date)
        .group_by(WasteLog.reason)
    )
    by_reason: dict[str, int] = {}
    n_events = 0
    for reason_str, cost_sum, count in session.execute(reason_q).all():
        by_reason[reason_str] = int(cost_sum or 0)
        n_events += int(count or 0)

    # Aggregate by ingredient
    ing_q = (
        select(
            WasteLog.ingredient_id,
            Ingredient.name,
            func.sum(WasteLog.cost_gs),
        )
        .join(Ingredient, WasteLog.ingredient_id == Ingredient.id)
        .where(WasteLog.recorded_at >= start_date, WasteLog.recorded_at <= end_date)
        .group_by(WasteLog.ingredient_id, Ingredient.name)
        .order_by(func.sum(WasteLog.cost_gs).desc())
    )
    by_ingredient: list[tuple[int, str, int]] = []
    total_cost = 0
    for ing_id, name, cost_sum in session.execute(ing_q).all():
        c = int(cost_sum or 0)
        by_ingredient.append((int(ing_id), str(name), c))
        total_cost += c

    # Total qty
    qty_sum = (
        session.execute(
            select(func.sum(WasteLog.qty)).where(
                WasteLog.recorded_at >= start_date, WasteLog.recorded_at <= end_date
            )
        ).scalar()
        or 0.0
    )

    return WasteImpact(
        n_events=n_events,
        total_qty=float(qty_sum),
        total_cost_gs=total_cost,
        by_reason=by_reason,
        by_ingredient=by_ingredient,
    )


def waste_as_pct_of_revenue(
    session: Session,
    *,
    start_date: datetime,
    end_date: datetime,
    revenue_gs: int,
) -> float:
    """Waste cost as % of revenue (e.g. 2.5 = 2.5%).

    Industry benchmark: < 5% is healthy for bakeries.
    """
    impact = waste_impact(session, start_date=start_date, end_date=end_date)
    if revenue_gs <= 0:
        return 0.0
    return (impact.total_cost_gs / revenue_gs) * 100


@dataclass
class RecipeWasteResult:
    """Result of record_recipe_waste(). One WasteLog row per ingredient."""

    recipe_id: int
    recipe_name: str
    batch_qty: float
    cost_gs: int
    waste_logs: list[WasteLog] = field(default_factory=list)


def record_recipe_waste(
    session: Session,
    *,
    recipe_id: int,
    batch_qty: float,
    reason: WasteReason,
    recorded_by: str | None = None,
    notes: str | None = None,
) -> RecipeWasteResult:
    """Log a whole-batch waste event for a recipe (the operator review T6).

    A whole-batch waste ("se quemó la masa") reduces stock of every
    ingredient in the recipe proportionally. Implemented by walking the
    recipe tree (same path costing.apply_sale uses) and creating one
    WasteLog row per ingredient, with the recipe's yield_qty as the
    denominator. Sub-recipes recurse, so a top-level recipe waste that
    references a sub-recipe also wastes the sub-recipe's ingredients.

    Cost is computed per-ingredient at insert time using the ingredient's
    current purchase_price_gs (same denormalization policy as record_waste).

    Raises ValueError if the recipe has no yield_qty or doesn't exist.
    Atomic: all waste logs + stock decrements land in one session commit.
    """
    if batch_qty <= 0:
        raise ValueError("batch_qty debe ser mayor a 0")

    recipe = session.get(Recipe, recipe_id)
    if recipe is None:
        raise ValueError(f"Recipe {recipe_id} not found")
    if recipe.yield_qty is None or recipe.yield_qty <= 0:
        raise ValueError(
            f"Receta '{recipe.name}' sin rendimiento. Cargá el rendimiento antes de registrar merma."
        )

    # Lazy import to avoid circular: costing imports waste transitively in some paths.
    from app.rms.costing import _compute_stock_moves

    # The recipe walker expects (sale_qty) in "output units" (e.g. muffins).
    # batch_qty is the multiplier on yield — e.g. 2.0 means "2 batches".
    sale_qty = float(recipe.yield_qty) * batch_qty
    moves = _compute_stock_moves(session, recipe, sale_qty, set())

    logs: list[WasteLog] = []
    total_cost = 0
    now = datetime.now(timezone.utc)

    for _affected_recipe_id, ingredient_id, qty_delta in moves:
        qty = abs(qty_delta)
        if qty <= 0:
            continue
        ing = session.get(Ingredient, ingredient_id)
        if ing is None:
            continue
        cost_gs = (
            to_int_gs(Decimal(str(qty)) * Decimal(str(ing.purchase_price_gs)))
            if ing.purchase_price_gs is not None
            else 0
        )
        log = WasteLog(
            ingredient_id=ingredient_id,
            qty=qty,
            reason=reason.value,
            cost_gs=cost_gs,
            recorded_at=now,
            recorded_by=recorded_by,
            notes=notes,
        )
        session.add(log)
        ing.stock_qty = max(0.0, (ing.stock_qty or 0) - qty)
        logs.append(log)
        total_cost += cost_gs
        # StockMovement audit record (negative qty = stock out)
        movement = StockMovement(
            ingredient_id=ingredient_id,
            movement_type="merma",
            qty=-qty,
            reason=f"Merma receta '{recipe.name}': {reason.value}",
            reference_id=log.id,
            reference_type="waste_log",
            recorded_at=now,
            created_by=recorded_by,
        )
        session.add(movement)

    session.flush()
    return RecipeWasteResult(
        recipe_id=recipe.id,
        recipe_name=recipe.name,
        batch_qty=batch_qty,
        cost_gs=total_cost,
        waste_logs=logs,
    )


__all__ = [
    "RecipeWasteResult",
    "WasteImpact",
    "WasteReason",
    "list_waste",
    "record_recipe_waste",
    "record_waste",
    "waste_as_pct_of_revenue",
    "waste_impact",
]


@dataclass
class WasteIngredientTrend:
    """BACKLOG #34: one ingredient's waste cost + its purchase-price trend.

    Operators want to know: "I'm wasting Harina, but is the price
    rising too?" If yes, the waste is becoming MORE expensive and
    should be prioritized. If price is also falling, the waste is
    becoming less of a concern (relative to other ingredients).

    `trend_pct` is the percentage change in average price between the
    recent half of `days` and the prior half:
        trend_pct = (avg_recent - avg_prior) / avg_prior * 100

    NULL when there's no price history in either window (you can't
    compute a trend from a single point). A `null` trend is NOT the
    same as a 0% trend.
    """

    ingredient_id: int = 0
    ingredient_name: str = ""
    cost_gs: int = 0  # total waste cost in the window
    qty: float = 0.0  # total wasted qty
    avg_price_recent_gs: int | None = None  # avg price in recent half
    avg_price_prior_gs: int | None = None  # avg price in prior half
    trend_pct: float | None = None  # (recent - prior) / prior * 100


def waste_impact_with_trends(
    session: Session,
    *,
    days: int = 60,
    now: datetime | None = None,
) -> list[WasteIngredientTrend]:
    """BACKLOG #34: per-ingredient waste cost + purchase-price trend.

    Splits the price-history window into two halves:
      - recent half:  [now - days/2, now]
      - prior half:   [now - days,    now - days/2)

    Computes the average price in each half per ingredient, then the
    percentage change. The waste cost comes from WasteLog in the FULL
    `days` window (we're measuring the cost of the trend, not the
    trend itself).

    Returns one row per ingredient that has waste events in the
    window — sorted by cost desc so the most expensive waste surfaces.

    `trend_pct` semantics:
      - positive  → price is rising → waste is becoming more expensive
      - negative  → price is falling → waste is becoming cheaper
      - None      → no price events in either half (insufficient data)

    The function does NOT call `waste_impact()` — it would re-aggregate
    the same waste rows. We share the by_ingredient aggregation here.
    """
    from app.rms.models import IngredientPriceEvent

    if now is None:
        now = datetime.now(timezone.utc)
    if days < 60:
        # Need at least 60 days to make a meaningful recent/prior split.
        days = 60
    half_days = days // 2
    window_start = now - timedelta(days=days)
    mid = now - timedelta(days=half_days)

    # Aggregate waste cost + qty per ingredient in the FULL window.
    waste_q = (
        select(
            WasteLog.ingredient_id,
            Ingredient.name,
            func.sum(WasteLog.cost_gs).label("cost"),
            func.sum(WasteLog.qty).label("qty"),
        )
        .join(Ingredient, WasteLog.ingredient_id == Ingredient.id)
        .where(
            WasteLog.recorded_at >= window_start,
            WasteLog.recorded_at <= now,
        )
        .group_by(WasteLog.ingredient_id, Ingredient.name)
        .order_by(func.sum(WasteLog.cost_gs).desc())
    )
    waste_rows = session.execute(waste_q).all()
    if not waste_rows:
        return []

    ing_ids = [r[0] for r in waste_rows]

    # Aggregate price history per ingredient per half-window in ONE query.
    # CASE WHEN splits each event into recent/prior based on its
    # recorded_at. We SUM the prices, COUNT distinct events (so a flurry
    # of identical restock rows at the same price doesn't dominate).
    price_q = (
        select(
            IngredientPriceEvent.ingredient_id,
            func.coalesce(
                func.sum(
                    case(
                        (
                            IngredientPriceEvent.recorded_at >= mid,
                            IngredientPriceEvent.price_gs,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("recent_sum"),
            func.coalesce(
                func.count(
                    case(
                        (
                            IngredientPriceEvent.recorded_at >= mid,
                            IngredientPriceEvent.id,
                        ),
                        else_=None,
                    )
                ),
                0,
            ).label("recent_count"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            IngredientPriceEvent.recorded_at < mid,
                            IngredientPriceEvent.price_gs,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("prior_sum"),
            func.coalesce(
                func.count(
                    case(
                        (
                            IngredientPriceEvent.recorded_at < mid,
                            IngredientPriceEvent.id,
                        ),
                        else_=None,
                    )
                ),
                0,
            ).label("prior_count"),
        )
        .where(
            IngredientPriceEvent.ingredient_id.in_(ing_ids),
            IngredientPriceEvent.recorded_at >= window_start,
            IngredientPriceEvent.recorded_at <= now,
        )
        .group_by(IngredientPriceEvent.ingredient_id)
    )
    price_by_pid: dict[int, dict[str, int]] = {}
    for pid, recent_sum, recent_count, prior_sum, prior_count in (
        session.execute(price_q).all()
    ):
        price_by_pid[int(pid)] = {
            "recent_sum": int(recent_sum or 0),
            "recent_count": int(recent_count or 0),
            "prior_sum": int(prior_sum or 0),
            "prior_count": int(prior_count or 0),
        }

    out: list[WasteIngredientTrend] = []
    for ing_id, name, cost, qty in waste_rows:
        avg_recent = avg_prior = None
        trend_pct: float | None = None
        agg = price_by_pid.get(int(ing_id))
        if agg:
            if agg["recent_count"] > 0:
                avg_recent = int(agg["recent_sum"] / agg["recent_count"])
            if agg["prior_count"] > 0:
                avg_prior = int(agg["prior_sum"] / agg["prior_count"])
            if avg_prior is not None and avg_prior > 0 and avg_recent is not None:
                trend_pct = round(
                    (avg_recent - avg_prior) / avg_prior * 100.0, 2
                )
        out.append(
            WasteIngredientTrend(
                ingredient_id=int(ing_id),
                ingredient_name=str(name),
                cost_gs=int(cost or 0),
                qty=float(qty or 0.0),
                avg_price_recent_gs=avg_recent,
                avg_price_prior_gs=avg_prior,
                trend_pct=trend_pct,
            )
        )
    return out


_AMPLIFIED_TREND_PCT = 5.0


def amplified_waste_ingredients(
    rows: list[WasteIngredientTrend],
    *,
    trend_threshold_pct: float = _AMPLIFIED_TREND_PCT,
) -> list[WasteIngredientTrend]:
    """Filter `waste_impact_with_trends()` output to ingredients where the
    purchase price is rising AND the waste cost is significant.

    "Amplified waste" = waste on an ingredient whose price is going up.
    Reducing that waste yields a bigger bottom-line win than reducing
    waste on a falling-price ingredient.

    Args:
        rows: output of `waste_impact_with_trends()`
        trend_threshold_pct: only flag rows where trend_pct >= threshold
            (default 5.0% — see _AMPLIFIED_TREND_PCT).

    Returns the same dataclass rows in the same order (cost desc),
    filtered to the amplified subset.
    """
    return [
        r for r in rows
        if r.trend_pct is not None and r.trend_pct >= trend_threshold_pct
    ]
