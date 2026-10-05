"""app/rms/variants.py — Sprint 7 helpers for IngredientVariant and forecast horizon.

Helpers for the two new S7 decisions:

- Decision A1 — IngredientVariant rollups
  * ``rollup_ingredient_stock()`` — sum of variants in the Ingredient base unit
  * ``current_variant_price()`` — the preferred variant's price, fallback to
    parent Ingredient.purchase_price_gs (for backwards compatibility)

- Decision B — per-ingredient forecast horizon
  * ``forecast_horizon_days(ingredient)`` — returns the ingredient's explicit
    horizon, or the global default if unset
  * ``days_until_short()`` — "how many days until I reach reorder_point?"
    using a per-ingredient horizon
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.config import ASUNCION_TZ
from app.rms.models import Ingredient, IngredientVariant, StockMovement
from app.rms.money import to_decimal
from app.rms.units import Unit, can_convert, convert_qty

# Global default — overridable via env var. The audio reference for
# "how many days until I run out" used 14 days (current hardcoded value).
DEFAULT_FORECAST_HORIZON_DAYS = int(os.getenv("AIW_SASKIA_FORECAST_HORIZON", "14"))


# ---------------------------------------------------------------------------
# Variant rollups (Decision A1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VariantRollup:
    """Result of summing all variants of an Ingredient into the base unit."""

    ingredient_id: int
    base_qty: float  # total stock across all variants in base unit
    base_unit: str  # the Ingredient.unit
    variant_count: int
    preferred_price_gs: Optional[int]  # price from the preferred variant
    preferred_variant_id: Optional[int]
    # Per-variant breakdown, in display-friendly order. Keys:
    #   variant_id, package_size, package_unit, stock_qty (in variant unit),
    #   purchase_price_gs, supplier_id, preferred, label
    variants: list[dict]


def rollup_ingredient_stock(
    session: Session,
    ingredient_id: int,
) -> Optional[VariantRollup]:
    """Sum every variant's stock into the Ingredient's base unit.

    E.g. for harina (base unit = kg):
      variant 1 (package_size=1.0 kg, stock=3) → 3.0 kg
      variant 2 (package_size=0.25 kg, stock=12) → 3.0 kg
      variant 3 (package_size=5.0 kg, stock=1)  → 5.0 kg
      ⇒ total: 11.0 kg

    Cross-unit example (base unit = kg, variants in g):
      variant 1 (package_size=1000 g, stock=3)  → 3.0 kg
      variant 2 (package_size=250 g, stock=12)  → 3.0 kg
      ⇒ total: 6.0 kg

    The math is: ``total_in_base = stock_qty × size_in_base`` where
    ``size_in_base = convert_qty(package_size, package_unit, base_unit)``.

    Bug fix (2026-10-01, /inicio B1 follow-up): the previous code also
    converted ``stock_qty`` from ``package_unit`` to ``base_unit``
    before multiplying. That's wrong because ``stock_qty`` is a
    **count of packages**, not a quantity in package_unit. For
    same-unit variants the bug was invisible (kg×kg cancels), but
    for cross-unit (g + kg, ml + l) it produced wildly inflated
    numbers. See ``tests/test_rollup_cross_unit.py``.

    Returns None if the Ingredient doesn't exist. Returns a rollup with
    base_qty=0 if variants are missing.
    """
    ing = session.get(Ingredient, ingredient_id)
    if ing is None:
        return None
    variants = list(
        session.scalars(
            select(IngredientVariant)
            .where(IngredientVariant.ingredient_id == ingredient_id)
            .order_by(IngredientVariant.preferred.desc(), IngredientVariant.package_size)
        )
    )
    if not variants:
        # No variants — fall back to the legacy Ingredient.stock_qty column.
        return VariantRollup(
            ingredient_id=ingredient_id,
            base_qty=float(ing.stock_qty or 0.0),
            base_unit=ing.unit,
            variant_count=0,
            preferred_price_gs=ing.purchase_price_gs,
            preferred_variant_id=None,
            variants=[],
        )

    base_unit = Unit(ing.unit)
    total = to_decimal("0")
    breakdown = []
    preferred_price: Optional[int] = None
    preferred_id: Optional[int] = None

    for v in variants:
        # size_in_base = how many base units a single package contains.
        # E.g. package_size=1.0 kg, base=g → 1000.0 g per package.
        from_unit = Unit(v.package_unit)
        if can_convert(from_unit, base_unit):
            size_in_base = float(convert_qty(to_decimal(v.package_size), from_unit, base_unit))
            # Total contribution: stock_qty is a COUNT of packages, so
            # multiply by size_in_base to get the quantity in base units.
            # DO NOT convert stock_qty separately — that would treat the
            # count as if it were a quantity (the bug we just fixed).
            total_in_base = float(v.stock_qty) * size_in_base
        else:
            # Incompatible units (should never happen — UNIT constraint
            # enforces g/kg/ml/l/und). Be safe: fall back to no conversion,
            # and the per-variant total equals stock_qty × package_size
            # in the variant's own unit. This is the legacy behavior.
            total_in_base = float(v.stock_qty) * float(v.package_size)
            size_in_base = float(v.package_size)

        total += to_decimal(str(total_in_base))
        breakdown.append(
            {
                "variant_id": v.id,
                "package_size": v.package_size,
                "package_unit": v.package_unit,
                "stock_qty": v.stock_qty,
                "stock_in_base": total_in_base,  # each variant's contribution in base unit
                "size_in_base": size_in_base,  # how many base units per package
                "purchase_price_gs": v.purchase_price_gs,
                "supplier_id": v.supplier_id,
                "preferred": bool(v.preferred),
                "notes": v.notes,
            }
        )
        if v.preferred:
            preferred_price = v.purchase_price_gs
            preferred_id = v.id

    return VariantRollup(
        ingredient_id=ingredient_id,
        base_qty=float(total),
        base_unit=ing.unit,
        variant_count=len(variants),
        preferred_price_gs=preferred_price,
        preferred_variant_id=preferred_id,
        variants=breakdown,
    )


def current_variant_price(
    session: Session,
    ingredient_id: int,
) -> Optional[int]:
    """The preferred variant's price if any, else the parent Ingredient price.

    Used as the source-of-truth for "what does 'harina' cost today?" —
    backwards-compatible (returns Ingredient.purchase_price_gs when no
    variants exist).
    """
    v = session.scalars(
        select(IngredientVariant)
        .where(IngredientVariant.ingredient_id == ingredient_id)
        .where(IngredientVariant.preferred.is_(True))
        .limit(1)
    ).first()
    if v is not None:
        return v.purchase_price_gs
    ing = session.get(Ingredient, ingredient_id)
    return ing.purchase_price_gs if ing else None


# ---------------------------------------------------------------------------
# Forecast horizon (Decision B)
# ---------------------------------------------------------------------------


def forecast_horizon_days(
    ingredient: Ingredient,
    *,
    today: date | None = None,
    default: int | None = None,
) -> int:
    """The forecast horizon for this ingredient, in days.

    Resolution order:
      1. ingredient.forecast_horizon_days (if set)
      2. the ``default`` kwarg (if provided)
      3. DEFAULT_FORECAST_HORIZON_DAYS env var (default 14)

    Returns the resolved integer. The ``today`` argument is accepted for
    deterministic testing — it doesn't currently affect the horizon value
    but is reserved for future seasonal adjustments.
    """
    if ingredient.forecast_horizon_days:
        return int(ingredient.forecast_horizon_days)
    if default is not None:
        return int(default)
    return DEFAULT_FORECAST_HORIZON_DAYS


@dataclass(frozen=True)
class ForecastResult:
    """Result of "how many days until I'm short?" for one ingredient."""

    ingredient_id: int
    ingredient_name: str
    current_stock_base: float  # current stock in ingredient's base unit
    base_unit: str
    avg_daily_consumption: float  # from last N days of SaleStockMove
    days_remaining: Optional[float]  # None if consumption = 0
    horizon_days: int  # the horizon used (from forecast_horizon_days)
    forecast_qty: float  # predicted consumption over the horizon
    status: str  # "ok" | "watch" | "short" | "dead"


def _consumption_lookback_days(
    horizon_days: int,
    *,
    today: date | None = None,
) -> int:
    """How many days of past sales to look back to estimate consumption.

    Uses the same window as the horizon (a reasonable default), with a
    floor of 7 days so noise doesn't dominate for fresh ingredients.
    """
    return max(7, horizon_days)


def avg_daily_consumption(
    session: Session,
    ingredient_id: int,
    *,
    horizon_days: int,
    today: date | None = None,
) -> float:
    """Average daily consumption (in base unit) over the lookback window.

    Queries SaleStockMove (qty_delta is negative for stock decreases) joined
    to Sale for the date, takes the absolute qty_delta and averages per day
    in the window.
    """
    if today is None:
        today = datetime.now(ASUNCION_TZ).date()
    start = today - timedelta(days=_consumption_lookback_days(horizon_days, today=today))
    end = today

    # BACKLOG #1 (schema 92): replaced SaleStockMove + Sale join with
    # StockMovement (filtered to movement_type='sale' / reference_type='sale').
    # The recorded_at column on StockMovement is the sale timestamp.
    rows = session.execute(
        select(StockMovement.recorded_at, StockMovement.qty)
        .where(StockMovement.ingredient_id == ingredient_id)
        .where(StockMovement.movement_type == "sale")
        .where(StockMovement.recorded_at >= datetime.combine(start, datetime.min.time()))
        .where(StockMovement.recorded_at <= datetime.combine(end, datetime.max.time()))
    ).all()
    if not rows:
        return 0.0
    # qty is negative for consumption; absolute value
    total = float(sum(abs(float(q)) for _, q in rows))
    days = max(1, (end - start).days)
    return total / days


def days_until_short(
    session: Session,
    ingredient_id: int,
    *,
    today: date | None = None,
    default_horizon: int | None = None,
) -> Optional[ForecastResult]:
    """Compute the forecast result for an ingredient.

    Returns None if the ingredient doesn't exist. ``status`` rules:
      - "dead"   : avg_daily_consumption == 0
      - "short"  : days_remaining < horizon_days (you'll run out within horizon)
      - "watch"  : days_remaining < horizon_days * 2
      - "ok"     : otherwise

    The "short" + "watch" cutoffs use the *ingredient's own horizon* — so
    if the operator sets dulce_de_leche.forecast_horizon_days=21 and avg
    consumption eats through current stock in 18 days, status is "short"
    (she needs to reorder within the 21-day supplier window).
    """
    ing = session.get(Ingredient, ingredient_id)
    if ing is None:
        return None
    horizon = forecast_horizon_days(ing, today=today, default=default_horizon)
    avg = avg_daily_consumption(session, ingredient_id, horizon_days=horizon, today=today)
    rollup = rollup_ingredient_stock(session, ingredient_id)
    current = rollup.base_qty if rollup else float(ing.stock_qty or 0.0)

    if avg <= 0:
        # No consumption in the window → can't predict
        return ForecastResult(
            ingredient_id=ingredient_id,
            ingredient_name=ing.name,
            current_stock_base=current,
            base_unit=ing.unit,
            avg_daily_consumption=0.0,
            days_remaining=None,
            horizon_days=horizon,
            forecast_qty=0.0,
            status="dead",
        )

    days = current / avg
    forecast = avg * horizon
    if days < horizon:
        status = "short"
    elif days < horizon * 2:
        status = "watch"
    else:
        status = "ok"

    return ForecastResult(
        ingredient_id=ingredient_id,
        ingredient_name=ing.name,
        current_stock_base=current,
        base_unit=ing.unit,
        avg_daily_consumption=avg,
        days_remaining=days,
        horizon_days=horizon,
        forecast_qty=forecast,
        status=status,
    )


__all__ = [
    "DEFAULT_FORECAST_HORIZON_DAYS",
    "ForecastResult",
    "VariantRollup",
    "avg_daily_consumption",
    "current_variant_price",
    "days_until_short",
    "forecast_horizon_days",
    "rollup_ingredient_stock",
]
