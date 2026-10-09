"""app/rms/production.py — Daily production worksheet (E21).

Per docs/plans/2026-09-07-sazon-complete-epic-plan-v3.md E21.

Adds:
- ProductionPlan: auto-aggregated ingredient requirements for a day
- ProductionRow: per-product forecast (qty to produce)
- ProductionLine: per-ingredient aggregate (qty to use)
- forecast_sales(): uses last 14 days of sales + seasonal multiplier
- plan_production(): given a forecast + recipes, computes the
  ingredient shopping list
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.rms.models import (
    Ingredient,
    Product,
    Recipe,
    Sale,
)


@dataclass
class ProductionRow:
    """One product in the production plan."""

    product_id: int
    product_name: str
    recipe_id: int | None  # None when product has no recipe attached
    qty_to_produce: float
    forecast_source: str  # "rolling_14d_avg" | "seasonal_event" | "manual"
    confidence_pct: int = 50  # 0-100, see _forecast_confidence()
    # Fase 5 (2026-10-05): batch_count + reason replace the old
    # `production_scheduler.ProductionPlan` fields so /inicio can render
    # the "Plan de mañana" card without needing the deprecated module.
    # `batch_count` is ceil(qty_to_produce / recipe.yield_qty) for products
    # with a recipe, else 1. `reason` is the human-readable explanation
    # ("Vendés ~X/día; ..."); None for the day view (it shows forecast_source).
    batch_count: int = 1
    reason: str | None = None


@dataclass
class ProductionLine:
    """One ingredient needed across all products."""

    ingredient_id: int
    ingredient_name: str
    unit: str
    qty_required: float
    stock_on_hand: float
    qty_to_buy: float


@dataclass
class ProductionPlan:
    """Full day's production plan."""

    for_date: date
    rows: list[ProductionRow]
    lines: list[ProductionLine]
    total_ingredients_needed: int
    notes: list[str] = field(default_factory=list)


def _forecast_confidence(sale_count: int, days_span: int) -> int:
    """Return a 0-100 confidence score for a forecast based on data sample size.

    Heuristic (deterministic, no ML):
      - 0 sales  → 0% (no data)
      - 1 sale    → 25% (single data point, very noisy)
      - 2 sales   → 40%
      - 3-6 sales → 55-70%
      - 7-13 sales (1-2 weeks of daily data) → 70-80%
      - 14-29 sales (2-4 weeks of daily data) → 80-90%
      - 30+ sales (1+ month of daily data) → 90-95%

    The "confidence" tells the operator when to trust the auto-suggestion vs.
    when to override. The roadmap example: "mañana vas a necesitar ~120
    chipitas (confianza 78%)" — operator trusts it when confidence >= 70.
    """
    if sale_count == 0:
        return 0
    if sale_count == 1:
        return 25
    if sale_count == 2:
        return 40
    # Logarithmic curve from 3 sales (50%) upward
    base = 50 + min(sale_count - 3, 30) * 1.5  # +1.5% per extra sale, capped at +45%
    # Boost if we have data spread across many days (not all clustered)
    spread_bonus = min(days_span, 14)  # up to 14 days spread adds up to +14%
    return min(95, int(base + spread_bonus))


def _recipe_yield_qty(session: Session, product: Product) -> int:
    """Recipe yield_qty for the product (defaults to 10 when no recipe).

    Fase 5 (2026-10-05): ported from `production_scheduler._recipe_yield`
    so the /inicio "Plan de mañana" card can compute batch_count without
    depending on the deprecated module.
    """
    if product.recipe_id is None:
        return 10
    recipe = session.get(Recipe, product.recipe_id)
    if recipe is None or recipe.yield_qty is None:
        return 10
    return max(1, int(recipe.yield_qty or 10))


def _compute_batch_count(session: Session, product: Product, qty: float) -> int:
    """How many batches to run to make `qty` units.

    Uses recipe.yield_qty as the per-batch size. Products without a
    recipe get 1 batch (we can't compute further without the recipe).
    """
    if qty <= 0:
        return 0
    yield_per_batch = _recipe_yield_qty(session, product)
    # ceil(qty / yield_per_batch) but integer math: -(-x // y)
    return max(1, -(-int(qty) // yield_per_batch))


def _build_plan_reason(
    product: Product,
    qty: float,
    source: str,
    session: Session,
    days_history: int,
) -> str | None:
    """Human-readable explanation of why this many units (Spanish).

    Used by /inicio "Plan de mañana" card. Returns None for the day view
    because the day view shows the structured `forecast_source` instead.
    For non-auto sources (manual/override/template), the reason is a
    short label. For auto forecasts, includes the velocity.
    """
    if source in ("manual", "override"):
        return "Ajuste manual del operador"
    if source == "template":
        return "Plantilla semanal"
    if source == "seasonal_event":
        return "Evento del calendario"
    if qty <= 0:
        return None
    # Auto forecast: include the underlying velocity.
    batch_count = _compute_batch_count(session, product, qty)
    avg_per_day = qty / max(days_history, 1)
    return (
        f"Vendés ~{avg_per_day:.1f}/día → hacer {int(qty)} u. "
        f"({batch_count} tanda{'s' if batch_count > 1 else ''})"
    )


def forecast_sales(
    session: Session,
    *,
    product_id: int,
    days_history: int = 14,
    target_weekday: int | None = None,
) -> float:
    """Forecast sales for tomorrow based on the last N days.

    Returns the daily average qty (handles zero-sales gracefully).

    When ``target_weekday`` is set (0=Mon ... 6=Sun), aggregates ONLY
    the historical sales on that weekday within the window — making the
    forecast day-of-week-aware. E.g. with ``target_weekday=2``
    (Wednesday) and ``days_history=84`` (12 weeks), it averages the
    last 12 Wednesdays' sales for this product, ignoring all other
    days. This is the B2 forecast mode powering /produccion/manana
    and the /inicio headline. (Decision 2026-10-01: 12-week lookback,
    DOW-only aggregation, fallback to all-DOW avg when < 4 DOW weeks
    exist.)

    When ``target_weekday`` is None, returns the flat daily average
    (legacy behavior, kept for any caller that wants it).
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days_history)
    base_q = (
        session.execute(
            select(func.sum(Sale.qty)).where(
                Sale.product_id == product_id,
                Sale.sold_at >= start,
                Sale.sold_at <= end,
                Sale.voided_at.is_(None),
            )
        ).scalar()
        or 0.0
    )

    if target_weekday is None:
        # Legacy flat average.
        return float(base_q) / days_history

    # DOW-only aggregation. We aggregate by DOW via SQL (GROUP BY the
    # Asunción-local weekday) so this is one query, not N.
    from app.rms.config import ASUNCION_TZ

    rows = session.execute(
        select(Sale.sold_at, Sale.qty).where(
            Sale.product_id == product_id,
            Sale.sold_at >= start,
            Sale.sold_at <= end,
            Sale.voided_at.is_(None),
        )
    ).all()

    by_dow_qty: dict[int, float] = {}
    by_dow_count: dict[int, int] = {}
    for sold_at, qty in rows:
        wd = sold_at.astimezone(ASUNCION_TZ).weekday()
        by_dow_qty[wd] = by_dow_qty.get(wd, 0.0) + float(qty)
        by_dow_count[wd] = by_dow_count.get(wd, 0) + 1

    target_qty = by_dow_qty.get(target_weekday, 0.0)
    target_days = by_dow_count.get(target_weekday, 0)

    # Fallback (decision 2026-10-01): if < 4 historical weeks on this DOW,
    # use the all-DOW average over the full window so we always show
    # something. The confidence calc downstream will reflect the weak
    # signal via low sale_count.
    if target_days < 4:
        return float(base_q) / max(days_history, 1)
    return target_qty / target_days


def _forecast_sample_stats(
    session: Session, *, product_id: int, days_history: int
) -> tuple[int, int]:
    """Return (sale_count, days_span) for the confidence calculation.

    sale_count = number of distinct sales of this product in the window.
    days_span = number of distinct calendar days (Asunción local) with
                at least one sale. A product sold 5 times all on Saturday
                has sale_count=5 but days_span=1 — the forecast is less
                trustworthy than one sold 5 times across 5 days.
    """
    from app.rms.config import ASUNCION_TZ

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days_history)
    rows = session.execute(
        select(Sale.sold_at).where(
            Sale.product_id == product_id,
            Sale.sold_at >= start,
            Sale.sold_at <= end,
            Sale.voided_at.is_(None),
        )
    ).all()
    if not rows:
        return 0, 0
    days = {(r[0].astimezone(ASUNCION_TZ).date().isoformat()) for r in rows}
    return len(rows), len(days)


def plan_production(
    session: Session,
    *,
    for_date: date | None = None,
    days_history: int = 14,
    seasonal_multiplier: float | None = None,
    manual_forecast: dict[int, float] | None = None,
    use_dow_forecast: bool = False,
) -> ProductionPlan:
    """Generate the full production plan for a given date.

    Inputs:
      - for_date: which day to plan for (default: tomorrow)
      - days_history: look-back window for forecasting
      - seasonal_multiplier: applied to forecast (uses calendar if None)
      - manual_forecast: {product_id: qty} overrides (operator override)
      - use_dow_forecast: when True, restrict auto-forecast to historical
        rows on ``for_date.weekday()`` only (B2 day-of-week-aware
        forecast, 2026-10-01). Default False preserves legacy flat avg.

    Output: ProductionPlan with rows + ingredient lines.
    """
    if for_date is None:
        for_date = (datetime.now(timezone.utc) + timedelta(days=1)).date()

    # Auto-apply seasonal multiplier from the calendar if not provided
    if seasonal_multiplier is None:
        from app.rms.workflow import demand_multiplier

        seasonal_multiplier = demand_multiplier(for_date)

    notes: list[str] = []
    if seasonal_multiplier > 1.0:
        notes.append(f"Multiplicador estacional: {seasonal_multiplier:.1f}x")

    # 1. Build per-product forecast
    products = list(session.execute(select(Product)).scalars())
    rows: list[ProductionRow] = []
    product_forecasts: dict[int, float] = {}

    # PRO-01: precedence is (a) explicit override for this date, (b) weekly
    # template for this weekday, (c) auto-forecast from sales. Each step
    # only fills in products not already covered by an earlier source.
    overrides_for_date: dict[int, float] = {}
    if for_date is not None:
        overrides_for_date = get_overrides_for_date(session, for_date)
    template_for_weekday: dict[int, float] = {}
    if for_date is not None:
        weekday = for_date.weekday()
        full_template = get_weekly_template(session)
        template_for_weekday = full_template.get(weekday, {})

    for prod in products:
        # (a) per-date override (highest priority)
        if manual_forecast and prod.id in manual_forecast:
            qty = float(manual_forecast[prod.id])
            source = "manual"
        elif prod.id in overrides_for_date:
            qty = float(overrides_for_date[prod.id])
            source = "override"
        # (b) weekly template (mid priority)
        elif prod.id in template_for_weekday:
            qty = float(template_for_weekday[prod.id])
            source = "template"
        # (c) auto-forecast from sales (fallback). PRO-11: productos ocultos
        # (is_available=False) nunca reciben auto-sugerencia — la operadora
        # puede forzarlos igual con override/template/manual.
        else:
            if not prod.is_available:
                qty = 0.0
                source = "oculto"
            else:
                # B2 DOW-aware: when use_dow_forecast=True, restrict to
                # historical rows matching for_date.weekday() (Mon=0..Sun=6).
                # Falls back to flat average inside forecast_sales() when
                # there are < 4 DOW weeks of history for this product.
                base = forecast_sales(
                    session,
                    product_id=prod.id,
                    days_history=days_history,
                    target_weekday=for_date.weekday() if use_dow_forecast else None,
                )
                qty = base * seasonal_multiplier
                source = "rolling_14d_avg"
        # PRO-02: a bakery cannot bake 0.1 of a muffin. Round the suggested
        # forecast UP to a whole piece. Manual overrides and template rows are
        # kept as-typed (operator-entered); only auto-suggestions are rounded.
        if source not in ("manual", "override", "template") and qty > 0:
            qty = math.ceil(qty)
        if qty > 0:
            # Compute confidence for auto-forecasts (skip for explicit overrides
            # — operator-typed values get 100% by definition).
            if source in ("manual", "override", "template"):
                confidence = 100
            else:
                sale_count, days_span = _forecast_sample_stats(
                    session, product_id=prod.id, days_history=days_history
                )
                confidence = _forecast_confidence(sale_count, days_span)
            rows.append(
                ProductionRow(
                    product_id=prod.id,
                    product_name=prod.name,
                    recipe_id=prod.recipe_id,
                    qty_to_produce=qty,
                    forecast_source=source,
                    confidence_pct=confidence,
                    # Fase 5: batch_count + reason for the /inicio "Plan de mañana"
                    # card (replaces the deprecated production_scheduler).
                    # batch_count = ceil(qty / recipe.yield_qty); 1 if no recipe.
                    batch_count=_compute_batch_count(session, prod, qty),
                    reason=_build_plan_reason(prod, qty, source, session, days_history),
                )
            )
            product_forecasts[prod.id] = qty

    # 2. For each product, expand its recipe lines into ingredient requirements
    ingredient_requirements: dict[int, dict] = {}  # ing_id -> {qty, unit}
    for prod_id, qty_to_produce in product_forecasts.items():
        prod = session.get(Product, prod_id)
        if prod is None or prod.recipe_id is None:
            continue
        recipe = session.get(Recipe, prod.recipe_id)
        if recipe is None or recipe.yield_qty is None or recipe.yield_qty <= 0:
            continue  # no yield -> can't scale batches (guarded upstream too)
        batches = qty_to_produce / recipe.yield_qty  # portions -> batches
        # Sprint shopping-list: use explode_recipe() so SUB-RECIPES are
        # included. The old loop read only direct `line_kind == "ingredient"`
        # lines — a Carrot Cake with cream-cheese glaze never showed the
        # glaze's ingredients in the day's needs. explode_recipe() scales
        # sub-recipes by (line_qty / sub.yield_qty), normalizes units and
        # sums duplicates; scale = batches (this product's batch multiplier).
        from app.rms.recipes_consolidated import explode_recipe

        for cl in explode_recipe(session, prod.recipe_id, scale=batches):
            if cl.error:
                # Unconvertible line (density missing / missing ingredient):
                # surface it as a plan note instead of silently dropping it.
                notes.append(f"{cl.name}: {cl.error}")
                continue
            if cl.ingredient_id is None:
                continue
            entry = ingredient_requirements.setdefault(
                cl.ingredient_id,
                {"qty": 0.0, "unit": cl.unit, "name": cl.name},
            )
            entry["qty"] += cl.qty

    # 3. Add stock-on-hand + qty_to_buy
    lines: list[ProductionLine] = []
    for ing_id, info in ingredient_requirements.items():
        ing = session.get(Ingredient, ing_id)
        stock = ing.stock_qty if ing else 0.0
        buy = max(0.0, info["qty"] - stock)
        lines.append(
            ProductionLine(
                ingredient_id=ing_id,
                ingredient_name=info["name"],
                unit=info["unit"],
                qty_required=info["qty"],
                stock_on_hand=stock,
                qty_to_buy=buy,
            )
        )
    # Sort by qty_required desc (most-needed at top)
    lines.sort(key=lambda ln: -ln.qty_required)

    return ProductionPlan(
        for_date=for_date,
        rows=rows,
        lines=lines,
        total_ingredients_needed=len(lines),
        notes=notes,
    )


# --- PRO-01: Weekly repeating template + per-date overrides ---

from app.rms.models import ProductionPlanOverride, ProductionPlanTemplate


def get_weekly_template(session: Session) -> dict[int, dict[int, float]]:
    """Return {weekday: {product_id: qty}} from production_plan_template.

    Used to fill the production plan when an explicit override doesn't exist
    for that date. Empty dict if the operator hasn't set a template yet
    (auto-forecast takes over).
    """
    rows = session.query(ProductionPlanTemplate).all()
    template: dict[int, dict[int, float]] = {wd: {} for wd in range(7)}
    for r in rows:
        if r.weekday in template:
            template[r.weekday][r.product_id] = r.qty
    return template


def get_overrides_for_date(session: Session, for_date: date) -> dict[int, float]:
    """Return {product_id: qty} from production_plan_override for a specific date.

    Overrides are date-scoped (not weekday-scoped): changing one Thursday does
    NOT affect other Thursdays.
    """
    rows = (
        session.query(ProductionPlanOverride)
        .filter(ProductionPlanOverride.for_date == for_date)
        .all()
    )
    return {r.product_id: r.qty for r in rows}


def upsert_template_row(
    session: Session,
    weekday: int,
    product_id: int,
    qty: float,
    updated_by: str | None = None,
    notes: str | None = None,
) -> ProductionPlanTemplate:
    """Insert or update the (weekday, product) row in the weekly template.

    Upserts in place via the unique constraint on (weekday, product_id).
    """
    if not (0 <= weekday <= 6):
        raise ValueError(f"weekday must be 0..6 (Mon..Sun); got {weekday}")
    if qty < 0:
        raise ValueError(f"qty must be ≥ 0; got {qty}")
    row = (
        session.query(ProductionPlanTemplate)
        .filter(
            ProductionPlanTemplate.weekday == weekday,
            ProductionPlanTemplate.product_id == product_id,
        )
        .one_or_none()
    )
    if row is None:
        row = ProductionPlanTemplate(
            weekday=weekday,
            product_id=product_id,
            qty=qty,
            notes=notes,
            updated_at=datetime.now(timezone.utc),
            updated_by=updated_by,
        )
        session.add(row)
    else:
        row.qty = qty
        row.notes = notes
        row.updated_at = datetime.now(timezone.utc)
        row.updated_by = updated_by
    session.flush()
    return row


def upsert_override(
    session: Session,
    product_id: int,
    for_date: date,
    qty: float,
    updated_by: str | None = None,
    notes: str | None = None,
) -> ProductionPlanOverride:
    """Insert or update the per-date override for (product, date)."""
    if qty < 0:
        raise ValueError(f"qty must be ≥ 0; got {qty}")
    row = (
        session.query(ProductionPlanOverride)
        .filter(
            ProductionPlanOverride.product_id == product_id,
            ProductionPlanOverride.for_date == for_date,
        )
        .one_or_none()
    )
    if row is None:
        row = ProductionPlanOverride(
            product_id=product_id,
            for_date=for_date,
            qty=qty,
            notes=notes,
            updated_at=datetime.now(timezone.utc),
            updated_by=updated_by,
        )
        session.add(row)
    else:
        row.qty = qty
        row.notes = notes
        row.updated_at = datetime.now(timezone.utc)
        row.updated_by = updated_by
    session.flush()
    return row


__all__ = [
    "ProductionLine",
    "ProductionPlan",
    "ProductionRow",
    "forecast_sales",
    "get_overrides_for_date",
    "get_weekly_template",
    "plan_production",
    "upsert_override",
    "upsert_template_row",
]
