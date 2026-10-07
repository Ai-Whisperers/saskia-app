"""app/rms/analytics.py — Operational analytics queries.

Per docs/plans/2026-09-07-sazon-complete-epic-plan-v3.md E8.

Pure query layer: takes a Session, returns dataclasses. No FastAPI
deps so the same functions can be used by reports, dashboards,
cron jobs, and tests without ceremony.

All currency in Paraguayan guaraní (Gs., integer). All quantities
in the same unit as stored on Ingredient (kg, l, g, ml, und).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.rms.models import Ingredient, Product, Recipe, RecipeLine, Sale, StockMovement
from app.rms.money import to_int_gs

# --- Public dataclasses ---


@dataclass
class StockTurnover:
    ingredient_id: int
    ingredient_name: str
    unit: str
    period_days: int
    consumed_qty: float  # negative qty_delta summed
    avg_stock: float  # midpoint of [current_stock, current_stock+consumed]
    turnover_ratio: float  # consumed / avg_stock; higher = faster-moving
    days_of_stock: int | None  # how many days until stockout (None if no consumption)


@dataclass
class DeadStockRow:
    ingredient_id: int
    ingredient_name: str
    unit: str
    stock_qty: float
    last_consumed_at: datetime | None
    days_since_consumed: int | None  # None if never consumed


@dataclass
class MarginErosionAlert:
    product_id: int
    product_name: str
    ingredient_name: str
    old_price_gs: int | None
    new_price_gs: int | None
    price_delta_pct: float | None
    old_margin_gs: int | None
    new_margin_gs: int | None
    margin_delta_pct: float | None


@dataclass
class DayOfWeekBucket:
    weekday: int  # 0=Mon, 6=Sun
    avg_sales_gs: float
    sale_count: int


@dataclass
class TopMarginProduct:
    product_id: int
    product_name: str
    margin_gs: int
    qty: float
    ventas_gs: int
    margin_pct: float  # 0-1


@dataclass
class IngredientConcentration:
    ingredient_id: int
    ingredient_name: str
    share_pct: float  # 0-1
    annual_cost_gs: int  # extrapolated from period usage * (365/period_days)


@dataclass
class RecipeComplexity:
    recipe_id: int
    recipe_name: str
    line_count: int
    cost_per_portion_gs: int
    prep_minutes: int | None
    cost_per_prep_minute_gs: float | None


@dataclass
class AuditIpPattern:
    """BACKLOG #30 (2026-10-02): IP pattern analytics for audit log."""
    ip: str
    count: int
    first_seen: datetime
    last_seen: datetime


@dataclass
class AuditTimePattern:
    """BACKLOG #30 (2026-10-02): time-of-day + day-of-week audit patterns."""
    hour: int  # 0..23
    day_of_week: int  # 0=Mon, 6=Sun
    count: int
    avg_hourly_actions: float


@dataclass
class AuditOperatorActivity:
    """BACKLOG #30 (2026-10-02): per-operator audit activity summary."""
    user_id: str
    name: str | None
    total_actions: int
    actions_per_day_avg: float
    most_common_action: str
    last_seen: datetime | None



# --- Public query functions ---


def stock_turnover(session: Session, ingredient_id: int, days: int = 30) -> StockTurnover | None:
    """Return StockTurnover for one ingredient over the last `days` days.

    Returns None if the ingredient does not exist.
    """
    ing = session.get(Ingredient, ingredient_id)
    if ing is None:
        return None

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    # Sum qty over the period (negative values). Use StockMovement (the
    # unified ledger since BACKLOG #1 migration 090) instead of the
    # dropped SaleStockMove stub.
    consumed = (
        session.execute(
            select(func.coalesce(func.sum(StockMovement.qty), 0.0)).where(
                StockMovement.ingredient_id == ingredient_id,
                StockMovement.qty < 0,
                StockMovement.reference_type == "sale",
                StockMovement.recorded_at >= cutoff.replace(tzinfo=None),
            )
        ).scalar()
        or 0.0
    )
    consumed_abs = abs(float(consumed))

    current_stock = float(ing.stock_qty)
    avg_stock = max(current_stock, (current_stock + consumed_abs) / 2) or 0.01
    turnover = consumed_abs / avg_stock if avg_stock > 0 else 0.0
    days_of_stock: int | None = None
    if consumed_abs > 0:
        per_day = consumed_abs / days
        # TIER-4-PROPERTY-BUG (2026-10-01): the previous guard
        # `per_day > 0` let denormal floats (~1e-308) through, so the
        # next line divided by a denormal, producing `inf`, then
        # `int(inf)` raised OverflowError. Hypothesis caught this
        # with `consumed_qty = 1.11e-308, days=1`. Tighten the
        # guard with `math.isfinite + sane threshold` -- a real
        # kitchen has at least one gram/second consumption.
        if per_day > 1e-9 and math.isfinite(per_day):
            days_of_stock = int(current_stock / per_day)

    return StockTurnover(
        ingredient_id=ingredient_id,
        ingredient_name=ing.name,
        unit=ing.unit,
        period_days=days,
        consumed_qty=consumed_abs,
        avg_stock=avg_stock,
        turnover_ratio=turnover,
        days_of_stock=days_of_stock,
    )


def batch_stock_turnover(
    session: Session, ingredient_ids: list[int], days: int = 30
) -> dict[int, StockTurnover]:
    """Return StockTurnover for multiple ingredients in a single query.

    Replaces N separate stock_turnover() calls (1 query each) with a single
    batch query. Callers pass the list of ingredient IDs they need; this
    function handles the rest.
    """
    if not ingredient_ids:
        return {}

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Single query: get consumed qty for all ingredients at once. Use
    # StockMovement (the unified ledger since BACKLOG #1 migration 090)
    # instead of the dropped SaleStockMove stub.
    consumed_rows = dict(
        session.execute(
            select(StockMovement.ingredient_id, func.coalesce(func.sum(StockMovement.qty), 0.0))
            .where(
                StockMovement.ingredient_id.in_(ingredient_ids),
                StockMovement.qty < 0,
                StockMovement.reference_type == "sale",
                StockMovement.recorded_at >= cutoff.replace(tzinfo=None),
            )
            .group_by(StockMovement.ingredient_id)
        ).all()
    )

    # Single query: get all ingredient data at once
    ingredients = {
        ing.id: ing
        for ing in session.execute(select(Ingredient).where(Ingredient.id.in_(ingredient_ids)))
        .scalars()
        .all()
    }

    result = {}
    for ingredient_id in ingredient_ids:
        ing = ingredients.get(ingredient_id)
        if ing is None:
            continue
        consumed_abs = abs(float(consumed_rows.get(ingredient_id, 0.0)))
        current_stock = float(ing.stock_qty)
        avg_stock = max(current_stock, (current_stock + consumed_abs) / 2) or 0.01
        turnover = consumed_abs / avg_stock if avg_stock > 0 else 0.0
        days_of_stock: int | None = None
        if consumed_abs > 0:
            per_day = consumed_abs / days
            # TIER-4-PROPERTY-BUG (2026-10-01): same fix as in
            # stock_turnover() above -- `per_day > 0` lets denormals
            # through, leading to int(inf) OverflowError on the next
            # line. Tighten with math.isfinite + sane threshold.
            if per_day > 1e-9 and math.isfinite(per_day):
                days_of_stock = int(current_stock / per_day)
        result[ingredient_id] = StockTurnover(
            ingredient_id=ingredient_id,
            ingredient_name=ing.name,
            unit=ing.unit,
            period_days=days,
            consumed_qty=consumed_abs,
            avg_stock=avg_stock,
            turnover_ratio=turnover,
            days_of_stock=days_of_stock,
        )
    return result


def all_stock_turnover(session: Session, days: int = 30) -> list[StockTurnover]:
    """Return StockTurnover for every ingredient that had consumption in the period."""
    ingredient_ids = session.execute(select(Ingredient.id)).scalars().all()
    return [st for iid in ingredient_ids if (st := stock_turnover(session, iid, days)) is not None]


def dead_stock(session: Session, threshold_days: int = 30) -> list[DeadStockRow]:
    """Return ingredients not consumed in the last `threshold_days` days.

    Uses StockMovement (the unified ledger since BACKLOG #1 migration 090)
    instead of the dropped SaleStockMove stub.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=threshold_days)
    # Find ingredient ids that HAVE had consumption since cutoff
    active_ids = set(
        session.execute(
            select(StockMovement.ingredient_id)
            .where(
                StockMovement.recorded_at >= cutoff.replace(tzinfo=None),
                StockMovement.qty < 0,
                StockMovement.reference_type == "sale",
            )
            .distinct()
        )
        .scalars()
        .all()
    )

    rows: list[DeadStockRow] = []
    for ing in session.execute(select(Ingredient)).scalars():
        # Use last_consumed_at if populated; otherwise fall back to stock_move scan
        if ing.last_consumed_at is not None:
            last = ing.last_consumed_at
            days_since: int | None = (datetime.now(timezone.utc) - last).days
        else:
            last_move = session.execute(
                select(func.max(StockMovement.recorded_at)).where(
                    StockMovement.ingredient_id == ing.id,
                    StockMovement.reference_type == "sale",
                )
            ).scalar()
            if last_move is None:
                days_since = None
                last = None
            else:
                last = last_move
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                days_since = (datetime.now(timezone.utc) - last).days

        if ing.id not in active_ids:
            rows.append(
                DeadStockRow(
                    ingredient_id=ing.id,
                    ingredient_name=ing.name,
                    unit=ing.unit,
                    stock_qty=float(ing.stock_qty),
                    last_consumed_at=last,
                    days_since_consumed=days_since,
                )
            )
    return rows


def margin_erosion_alerts(session: Session, threshold_pct: float = 5.0) -> list[MarginErosionAlert]:
    """Return products whose margin dropped > threshold_pct due to ingredient price changes.

    Heuristic: compare the current ingredient purchase_price_gs against
    `purchase_price_updated_at` - 1 week (a reasonable proxy for "old price").
    If the difference exceeds `threshold_pct` and there's a recipe involved,
    surface it.
    """
    alerts: list[MarginErosionAlert] = []
    # For now: report ingredients whose purchase_price_gs was updated in the last 7 days.
    one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent_ingredients = (
        session.execute(
            select(Ingredient).where(
                Ingredient.purchase_price_updated_at >= one_week_ago.replace(tzinfo=None),
                Ingredient.purchase_price_gs.is_not(None),
            )
        )
        .scalars()
        .all()
    )

    for ing in recent_ingredients:
        # Find products that use this ingredient
        products = (
            session.execute(
                select(Product)
                .join(Recipe, Recipe.id == Product.recipe_id)
                .join(RecipeLine, RecipeLine.recipe_id == Recipe.id)
                .where(RecipeLine.line_kind == "ingredient", RecipeLine.line_ref_id == ing.id)
                .distinct()
            )
            .scalars()
            .all()
        )

        new_price = ing.purchase_price_gs or 0
        # We don't have a stored "old price" so estimate: if min_stock_qty > 0
        # then ~10% lower; otherwise leave as None.
        old_price = int(new_price * 0.9) if new_price > 0 else None
        delta_pct = (
            ((new_price - old_price) / old_price * 100) if old_price and old_price > 0 else 0.0
        )

        if abs(delta_pct) < threshold_pct:
            continue

        for product in products:
            # Estimate margin impact
            cost_change_per_unit = (new_price - (old_price or new_price)) * 0.01
            new_margin = product.sale_price_gs - int(cost_change_per_unit)
            old_margin = product.sale_price_gs
            margin_delta_pct = (
                ((new_margin - old_margin) / old_margin * 100) if old_margin > 0 else 0.0
            )

            alerts.append(
                MarginErosionAlert(
                    product_id=product.id,
                    product_name=product.name,
                    ingredient_name=ing.name,
                    old_price_gs=old_price,
                    new_price_gs=new_price,
                    price_delta_pct=delta_pct,
                    old_margin_gs=old_margin,
                    new_margin_gs=new_margin,
                    margin_delta_pct=margin_delta_pct,
                )
            )
    return alerts


def day_of_week_heatmap(session: Session, days: int = 90) -> list[DayOfWeekBucket]:
    """Return average daily sales total per weekday over the last `days` days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    sales = session.execute(
        select(Sale.sold_at, Sale.qty, Sale.unit_price_gs).where(
            Sale.sold_at >= cutoff.replace(tzinfo=None),
            Sale.voided_at.is_(None),
        )
    ).all()

    buckets: dict[int, list[int]] = {i: [] for i in range(7)}
    for sold_at, qty, unit_price in sales:
        wd = sold_at.weekday()
        total = to_int_gs(Decimal(str(qty)) * Decimal(str(unit_price)))
        buckets[wd].append(total)

    out: list[DayOfWeekBucket] = []
    for wd in range(7):
        totals = buckets[wd]
        avg = sum(totals) / len(totals) if totals else 0.0
        out.append(
            DayOfWeekBucket(
                weekday=wd,
                avg_sales_gs=avg,
                sale_count=len(totals),
            )
        )
    return out


def top_margin_products(
    session: Session, days: int = 30, limit: int = 10
) -> list[TopMarginProduct]:
    """Return products ranked by total margin Gs. over the last `days` days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = session.execute(
        select(
            Sale.product_id,
            func.coalesce(func.sum(Sale.qty * Sale.unit_price_gs), 0).label("ventas"),
            func.coalesce(func.sum(Sale.qty), 0.0).label("qty"),
        )
        .where(Sale.sold_at >= cutoff.replace(tzinfo=None), Sale.voided_at.is_(None))
        .group_by(Sale.product_id)
    ).all()

    out: list[TopMarginProduct] = []
    for product_id, ventas, qty in rows:
        product = session.get(Product, product_id)
        if product is None:
            continue
        # Cost per unit: walk recipe (if any). For v1 we use sale_price_gs * 0.4 as a
        # rough proxy if we can't resolve the recipe cost. Real costing lives in
        # app/rms/costing.py; this is an analytics-level estimate.
        cost_per_unit = _quick_cost_estimate(session, product)
        if cost_per_unit is None:
            cost_per_unit = int(product.sale_price_gs * Decimal("0.4"))
        margin_gs = to_int_gs(
            Decimal(str(qty)) * (Decimal(str(product.sale_price_gs)) - Decimal(str(cost_per_unit)))
        )
        margin_pct = (
            (product.sale_price_gs - cost_per_unit) / product.sale_price_gs
            if product.sale_price_gs > 0
            else 0.0
        )
        out.append(
            TopMarginProduct(
                product_id=product_id,
                product_name=product.name,
                margin_gs=margin_gs,
                qty=float(qty),
                ventas_gs=int(ventas),
                margin_pct=float(margin_pct),
            )
        )
    out.sort(key=lambda x: x.margin_gs, reverse=True)
    return out[:limit]


def _quick_cost_estimate(session: Session, product: Product) -> int | None:
    """Cheap cost estimate per unit. Returns None if recipe not resolvable.

    Note: recipe_line.qty is Numeric(12,4) — Python returns Decimal here.
    We coerce all values to Decimal so the division doesn't raise
    TypeError (Decimal / float is undefined in Python).
    """
    from decimal import Decimal as _D

    if product.recipe_id is None:
        return None
    recipe = session.get(Recipe, product.recipe_id)
    if recipe is None or recipe.yield_qty is None or recipe.yield_qty <= 0:
        return None
    batch_cost = _D(0)
    for line in recipe.lines:
        if line.line_kind != "ingredient":
            continue
        ing = session.get(Ingredient, line.line_ref_id)
        if ing is None or ing.purchase_price_gs is None:
            return None
        # BACKLOG #13 (2026-10-02): prefer the moving-average cost when
        # available — it reflects supplier price drift over the batch's
        # lifetime. Falls back to purchase_price_gs when avg is NULL
        # (fresh installs, backfilled rows where the migration ran but
        # no waste event has fired yet, or legacy data from before v89).
        price_unit = ing.avg_cost_gs if ing.avg_cost_gs is not None else ing.purchase_price_gs
        batch_cost += line.qty * _D(price_unit)
    return int(batch_cost / _D(recipe.yield_qty))


def ingredient_concentration(session: Session, days: int = 90) -> list[IngredientConcentration]:
    """Return top ingredients by cost share over the last `days` days.

    Shares sum to 1.0 across all ingredients. Annual cost is extrapolated
    from the period consumption * (365 / days).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    # Use StockMovement (unified ledger since BACKLOG #1 migration 090)
    # instead of the dropped SaleStockMove stub. StockMovement.qty is
    # already signed (negative for sales), so we negate to get the
    # positive "consumed" amount for cost calculations.
    rows = session.execute(
        select(
            StockMovement.ingredient_id,
            func.coalesce(func.sum(-StockMovement.qty), 0.0).label("consumed"),
        )
        .where(
            StockMovement.reference_type == "sale",
            StockMovement.recorded_at >= cutoff.replace(tzinfo=None),
        )
        .group_by(StockMovement.ingredient_id)
    ).all()

    costs: list[tuple[int, str, int]] = []
    for ing_id, consumed in rows:
        ing = session.get(Ingredient, ing_id)
        if ing is None or ing.purchase_price_gs is None:
            continue
        cost = float(consumed) * ing.purchase_price_gs
        costs.append((ing_id, ing.name, int(cost)))

    total = sum(c for _, _, c in costs) or 1
    out: list[IngredientConcentration] = []
    for ing_id, name, cost in sorted(costs, key=lambda r: r[2], reverse=True):
        annual = int(cost * 365 / days)
        share = cost / total
        out.append(
            IngredientConcentration(
                ingredient_id=ing_id,
                ingredient_name=name,
                share_pct=share,
                annual_cost_gs=annual,
            )
        )
    return out


def recipe_complexity(session: Session) -> list[RecipeComplexity]:
    """Return one RecipeComplexity per recipe."""
    out: list[RecipeComplexity] = []
    for recipe in session.execute(select(Recipe)).scalars():
        line_count = len(recipe.lines)
        cost_per_portion = _quick_cost_estimate(
            session,
            Product(
                name=recipe.name,
                sale_price_gs=0,
                recipe_id=recipe.id,
            ),
        )
        if cost_per_portion is None:
            cost_per_portion = 0
        prep_minutes = recipe.prep_minutes
        cost_per_prep_min: float | None = None
        if prep_minutes and prep_minutes > 0 and cost_per_portion > 0:
            cost_per_prep_min = cost_per_portion / prep_minutes
        out.append(
            RecipeComplexity(
                recipe_id=recipe.id,
                recipe_name=recipe.name,
                line_count=line_count,
                cost_per_portion_gs=cost_per_portion,
                prep_minutes=prep_minutes,
                cost_per_prep_minute_gs=cost_per_prep_min,
            )
        )
    return out



def audit_ip_patterns(session: Session, *, days: int = 30) -> list[AuditIpPattern]:
    """BACKLOG #30 (2026-10-02): IP pattern analytics for audit log.

    Returns most frequent client IPs with activity count and date range.
    Helps identify suspicious IP patterns or untrusted locations.
    """
    from app.rms.config import ASUNCION_TZ
    from app.rms.models_legacy import AuditLog

    cutoff = datetime.now(ASUNCION_TZ) - timedelta(days=days)

    stmt = (
        select(
            AuditLog.ip,
            func.count(AuditLog.id).label("count"),
            func.min(AuditLog.occurred_at).label("first_seen"),
            func.max(AuditLog.occurred_at).label("last_seen")
        )
        .where(AuditLog.ip.isnot(None))
        .where(AuditLog.occurred_at >= cutoff)
        .group_by(AuditLog.ip)
        .order_by(func.count(AuditLog.id).desc())
        .limit(10)
    )

    rows = session.execute(stmt).fetchall()

    return [
        AuditIpPattern(
            ip=row.ip,
            count=row.count,
            first_seen=row.first_seen,
            last_seen=row.last_seen,
        )
        for row in rows
    ]



def audit_time_patterns(session: Session, *, days: int = 30) -> list[AuditTimePattern]:
    """BACKLOG #30 (2026-10-02): Time pattern analytics for audit log.

    Returns hourly and day-of-week activity patterns.
    Helps identify anomalous activity times or automated access.
    """
    from app.rms.config import ASUNCION_TZ
    from app.rms.models_legacy import AuditLog

    cutoff = datetime.now(ASUNCION_TZ) - timedelta(days=days)

    # Hourly patterns (weekday + hour)
    stmt = (
        select(
            extract('dow', AuditLog.occurred_at).label("day_of_week"),
            extract('hour', AuditLog.occurred_at).label("hour"),
            func.count(AuditLog.id).label("count")
        )
        .where(AuditLog.occurred_at >= cutoff)
        .group_by(extract('dow', AuditLog.occurred_at), extract('hour', AuditLog.occurred_at))
        .order_by(extract('dow', AuditLog.occurred_at), extract('hour', AuditLog.occurred_at))
    )

    hourly_rows = session.execute(stmt).fetchall()

    # Calculate avg hourly actions per pattern for normalization
    total_actions = sum(row.count for row in hourly_rows)
    total_hourly_buckets = len(hourly_rows)
    avg_hourly = total_actions / max(total_hourly_buckets, 1)

    return [
        AuditTimePattern(
            hour=row.hour,
            day_of_week=row.day_of_week,
            count=row.count,
            avg_hourly_actions=row.count / avg_hourly,
        )
        for row in hourly_rows
    ]



def audit_operator_patterns(session: Session, *, days: int = 30) -> list[AuditOperatorActivity]:
    """BACKLOG #30 (2026-10-02): Operator activity analytics for audit log.

    Returns user activity sorted by volume, frequency, and recency.
    Highlights dormant users or unusually active accounts.
    """
    from datetime import datetime, timedelta

    from app.rms.config import ASUNCION_TZ
    from app.rms.models_legacy import AuditLog

    cutoff = datetime.now(ASUNCION_TZ) - timedelta(days=days)

    # Get user activity totals and most common action
    # SQLite doesn't support mode(), so do it manually
    stmt = (
        select(
            AuditLog.user_id,
            func.count(AuditLog.id).label("total_actions"),
            func.max(AuditLog.occurred_at).label("last_seen")
        )
        .where(AuditLog.user_id.isnot(None))
        .where(AuditLog.occurred_at >= cutoff)
        .group_by(AuditLog.user_id)
        .order_by(func.count(AuditLog.id).desc())
        .limit(10)
    )

    rows = session.execute(stmt).fetchall()

    # Find most common action for each user (manual mode calculation)
    user_actions = {}
    action_stmt = (
        select(
            AuditLog.user_id,
            AuditLog.action,
            func.count(AuditLog.id).label("action_count")
        )
        .where(AuditLog.user_id.isnot(None))
        .where(AuditLog.occurred_at >= cutoff)
        .group_by(AuditLog.user_id, AuditLog.action)
        .order_by(AuditLog.user_id, func.count(AuditLog.id).desc())
    )

    action_rows = session.execute(action_stmt).fetchall()
    for row in action_rows:
        if row.user_id not in user_actions:
            user_actions[row.user_id] = row.action
        # Keep the first (most frequent) action per user

    # Get user names from a realistic lookup (in real app would use user service)
    user_names = {}
    for row in rows:
        # Simple naming convention: if UUID-like, truncate; if int, use as-is
        user_id = row.user_id
        if len(user_id) > 12:  # UUID-like
            user_names[user_id] = f"user@{user_id[:8]}"
        else:
            user_names[user_id] = user_id

    days_active = days
    return [
        AuditOperatorActivity(
            user_id=row.user_id,
            name=user_names.get(row.user_id),
            total_actions=row.total_actions,
            actions_per_day_avg=row.total_actions / max(days_active, 1),
            most_common_action=user_actions.get(row.user_id, "unknown"),
            last_seen=row.last_seen,
        )
        for row in rows
    ]




__all__ = [
    "AuditIpPattern",
    "AuditOperatorActivity",
    "AuditTimePattern",
    "DayOfWeekBucket",
    "DeadStockRow",
    "IngredientConcentration",
    "MarginErosionAlert",
    "RecipeComplexity",
    "StockTurnover",
    "TopMarginProduct",
    "all_stock_turnover",
    "audit_ip_patterns",
    "audit_operator_patterns",
    "audit_time_patterns",
    "day_of_week_heatmap",
    "dead_stock",
    "ingredient_concentration",
    "margin_erosion_alerts",
    "recipe_complexity",
    "stock_turnover",
    "top_margin_products",
]


# --- Consumption forecast (BACKLOG #32 — predictive restocking foundation) ---


@dataclass
class ConsumptionForecast:
    ingredient_id: int
    name: str
    current_stock_qty: float
    avg_daily_consumption: float
    days_until_stockout: int
    horizon_days: int
    safety_stock_factor: float
    predicted_consumption: float
    recommended_reorder_qty: float
    is_predicted_to_stockout: bool


def consumption_forecast(
    session: Session,
    *,
    ingredient_id: int | None = None,
    lookback_days: int = 30,
    horizon_days: int = 7,
    safety_factor: float = 1.5,
) -> list[ConsumptionForecast]:
    """Deterministic baseline forecast: avg daily consumption x horizon x safety.

    Consumption = StockMovement rows with movement_type='sale' and qty<0
    within the lookback window, summed as -qty. Only ingredients with at
    least one such movement get a forecast row (no data -> empty list).
    Sorted by days_until_stockout ascending (most urgent first).
    """
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=lookback_days)

    q = (
        select(
            StockMovement.ingredient_id,
            func.coalesce(func.sum(-StockMovement.qty), 0.0).label("total_consumed"),
        )
        .where(StockMovement.movement_type == "sale")
        .where(StockMovement.qty < 0)
        .where(StockMovement.recorded_at >= window_start)
        .where(StockMovement.recorded_at <= now)
        .group_by(StockMovement.ingredient_id)
    )
    if ingredient_id is not None:
        q = q.where(StockMovement.ingredient_id == ingredient_id)

    rows = session.execute(q).all()
    if not rows:
        return []

    forecasts: list[ConsumptionForecast] = []
    for ing_id, total_consumed in rows:
        ing = session.get(Ingredient, ing_id)
        if ing is None:
            continue
        avg_daily = float(total_consumed) / float(lookback_days)
        stock = float(ing.stock_qty or 0.0)
        days_until = int(stock / avg_daily) if avg_daily > 0 else 999999
        predicted = avg_daily * float(horizon_days) * float(safety_factor)
        recommended = max(0.0, predicted - stock)
        forecasts.append(
            ConsumptionForecast(
                ingredient_id=int(ing_id),
                name=ing.name,
                current_stock_qty=stock,
                avg_daily_consumption=avg_daily,
                days_until_stockout=days_until,
                horizon_days=int(horizon_days),
                safety_stock_factor=float(safety_factor),
                predicted_consumption=predicted,
                recommended_reorder_qty=recommended,
                is_predicted_to_stockout=days_until < int(horizon_days),
            )
        )

    forecasts.sort(key=lambda f: f.days_until_stockout)
    return forecasts


# --- Probabilistic (Poisson) forecast — BACKLOG #29 ---


@dataclass
class ProbabilisticForecast:
    """Poisson-shaped uncertainty around the deterministic baseline."""

    ingredient_id: int
    name: str
    avg_daily_consumption: float
    expected_horizon_consumption: float
    p_zero_consumption: float
    p_any_consumption: float
    p_stockout_within_horizon: float
    safety_stock_95pct: float


def probabilistic_consumption_forecast(
    session: Session,
    *,
    ingredient_id: int | None = None,
    lookback_days: int = 30,
    horizon_days: int = 7,
) -> list[ProbabilisticForecast]:
    """Rule-based Poisson approximation (BACKLOG #29).

    Uses avg_daily_consumption as rate λ; expected horizon consumption
    μ = λ × horizon. p_zero = e^-μ, p_stockout = P(X > stock | Poisson(μ)),
    95th-percentile safety stock via normal approx μ + 1.645·√μ.
    Sorted most-urgent (highest stockout probability) first.
    """
    baseline = consumption_forecast(
        session,
        ingredient_id=ingredient_id,
        lookback_days=lookback_days,
        horizon_days=horizon_days,
    )
    out: list[ProbabilisticForecast] = []
    for b in baseline:
        mu = max(b.avg_daily_consumption * float(horizon_days), 0.0)
        p_zero = math.exp(-mu) if mu > 0 else 1.0
        stock = max(int(math.floor(b.current_stock_qty)), 0)
        cdf = 0.0
        term = math.exp(-mu)
        for k in range(stock + 1):
            cdf += term
            term *= mu / (k + 1)
        p_stockout = max(0.0, min(1.0, 1.0 - cdf))
        out.append(
            ProbabilisticForecast(
                ingredient_id=b.ingredient_id,
                name=b.name,
                avg_daily_consumption=b.avg_daily_consumption,
                expected_horizon_consumption=mu,
                p_zero_consumption=p_zero,
                p_any_consumption=1.0 - p_zero,
                p_stockout_within_horizon=p_stockout,
                safety_stock_95pct=mu + 1.645 * math.sqrt(mu) if mu > 0 else 0.0,
            )
        )
    out.sort(key=lambda f: f.p_stockout_within_horizon, reverse=True)
    return out


# --- Day×hour sales heatmap (Tier-4 #22 follow-up) ---


@dataclass
class DayHourCell:
    """One (weekday, hour) bucket in operator-local time (Asuncion)."""

    weekday: int  # 0=Monday .. 6=Sunday
    hour: int  # 0-23, America/Asuncion wall clock
    sales_gs: float = 0.0
    n_sales: int = 0


@dataclass
class DayHourHeatmap:
    days: int
    cells: list
    max_sales_gs: float
    total_sales_gs: float
    total_n_sales: int


def day_hour_heatmap(session: Session, days: int = 7) -> DayHourHeatmap:
    """Sales bucketed by weekday×hour in Asuncion local time.

    Net revenue per cell = unit_price × qty − discount_gs (Tier-4 #22:
    post-discount, so operators see real revenue). Voided sales excluded.
    Every (weekday, hour) cell is materialized — even empty ones — so
    templates can iterate without sparse-key logic.
    """
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo

    from sqlalchemy import text as _text

    days = max(1, min(int(days), 365))
    tz = ZoneInfo("America/Asuncion")
    window_start = datetime.now(timezone.utc) - timedelta(days=days)

    rows = session.execute(
        _text(
            """
            SELECT sold_at, unit_price_gs, qty, discount_gs
            FROM sale
            WHERE voided_at IS NULL AND sold_at >= :start
            """
        ),
        {"start": window_start},
    ).all()

    cells = [DayHourCell(weekday=wd, hour=h) for wd in range(7) for h in range(24)]
    total_gs = 0.0
    total_n = 0
    for sold_at, unit_price, qty, discount in rows:
        if sold_at is None:
            continue
        if isinstance(sold_at, str):
            try:
                sold_at = datetime.fromisoformat(sold_at.replace("Z", "+00:00"))
            except ValueError:
                continue
        # SQLite may hand back naive datetimes (mixed-type guard).
        if sold_at.tzinfo is None:
            sold_at = sold_at.replace(tzinfo=timezone.utc)
        local = sold_at.astimezone(tz)
        net = (unit_price or 0) * (qty or 0) - (discount or 0)
        cell = cells[local.weekday() * 24 + local.hour]
        cell.sales_gs += net
        cell.n_sales += 1
        total_gs += net
        total_n += 1

    return DayHourHeatmap(
        days=days,
        cells=cells,
        max_sales_gs=max((c.sales_gs for c in cells), default=0.0),
        total_sales_gs=total_gs,
        total_n_sales=total_n,
    )
