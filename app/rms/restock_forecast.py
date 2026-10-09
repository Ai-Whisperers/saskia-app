"""app/rms/restock_forecast.py — Poisson weekday restocking forecast (BACKLOG #5).

Upgrades the flat 30-day average in forecast.py with a per-weekday
Poisson rate model, without new dependencies (AGENTS.md rule 26 — no
numpy/scipy; closed-form Poisson MLE is λ̂ = Σcounts / Σexposure).

Model
-----
Daily consumption of an ingredient is modeled as Poisson(λ_w) where
w = weekday (Mon..Sun). λ̂_w = (total consumed on weekday w over the
window) / (number of weekday-w days in the window). Trend from the
prior window (same blend as forecast.py) scales λ forward.

95% interval for a future day: Wilson-style normal approximation
λ ± 1.96·√(λ/n_w) — exact enough at bakery volume, no scipy.

P95 stockout date: walk forward day by day accumulating the day's λ
(draws the *expected* path), find the day cumulative demand exceeds
current stock. The P95 variant uses λ + 1.645·σ accumulated, i.e. the
conservative path an operator should plan against.

Why weekday rates beat a flat average here: a bakery's Saturday sales
are routinely 2-3× Tuesday's. A flat λ says "12 days of stock left"
while the Saturday-heavy path actually runs out in 8 — the exact gap
this module closes.

Data sources
------------
- StockMovement(movement_type='sale') — ingredient-level daily series
  (SSOT since BACKLOG #1; sale_stock_move table was dropped in
  migration 092).
- ProductionDemandSnapshot — product-level daily demand snapshots
  filling since P40; used only to widen the exposure window when
  movement history is short (seeded installations).

No commits, no I/O beyond the passed session. Pure functions + one
session-reading aggregator, mirroring forecast.py's contract so
reorder.py can adopt it incrementally.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.rms.models import Ingredient, StockMovement

Z_95 = 1.959964  # two-sided 95% normal quantile
Z_95_ONE_SIDED = 1.644854  # one-sided 95% (P95 planning path)


@dataclass
class WeekdayRates:
    """Per-weekday Poisson rates in ingredient units/day."""

    # index 0 = Monday ... 6 = Sunday (date.weekday())
    lambdas: list[float] = field(default_factory=lambda: [0.0] * 7)
    exposures: list[float] = field(default_factory=lambda: [0.0] * 7)
    window_days: int = 56

    def rate(self, weekday: int) -> float:
        return self.lambdas[weekday % 7]

    def se(self, weekday: int) -> float:
        """Standard error of the weekday rate estimate."""
        n = self.exposures[weekday % 7]
        if n <= 0:
            return 0.0
        return math.sqrt(self.lambdas[weekday % 7] / n)

    def flat_equivalent(self) -> float:
        """Exposure-weighted mean rate — comparable to forecast.py's avg_daily."""
        total_exposure = sum(self.exposures)
        if total_exposure <= 0:
            return 0.0
        return (
            sum(lam * n for lam, n in zip(self.lambdas, self.exposures, strict=True))
            / total_exposure
        )


def poisson_weekday_rates(
    session: Session,
    ingredient_id: int,
    *,
    window_days: int = 56,
    now: datetime | None = None,
) -> WeekdayRates:
    """Estimate per-weekday Poisson consumption rates from stock_movement.

    Uses the last ``window_days`` days of movement_type='sale' rows.
    Two 28-day windows minimum is ideal; fewer weekday occurrences just
    widen the interval (the SE handles it honestly).
    """
    now = now or datetime.now(timezone.utc)
    # Midnight-aligned cutoff: a sale any time on the window's first day
    # counts (an exact-now cutoff drops it by seconds and biases one
    # weekday's λ low by 1/N).
    cutoff = datetime.combine(
        (now - timedelta(days=window_days)).date(),
        datetime.min.time(),
        tzinfo=now.tzinfo,
    )

    rows = session.execute(
        select(
            func.strftime("%w", StockMovement.recorded_at),
            func.sum(-StockMovement.qty),
        )
        .where(StockMovement.ingredient_id == ingredient_id)
        .where(StockMovement.movement_type == "sale")
        .where(StockMovement.recorded_at >= cutoff)
        .group_by(func.strftime("%w", StockMovement.recorded_at))
    ).all()

    # SQLite %w: 0=Sunday..6=Saturday → date.weekday(): 0=Mon..6=Sun
    # (%w + 6) % 7 converts: Sun 0→6, Mon 1→0, ... Sat 6→5.
    consumed_by_dow = {(int(dow) + 6) % 7: float(qty or 0.0) for dow, qty in rows}

    # Exposure: count of each weekday in the window (including days with
    # zero sales — absence of movement rows IS zero consumption, kitchen
    # closed days aside; the operator's min_stock covers closed days).
    counts_by_dow: dict[int, int] = {}
    start = (now - timedelta(days=window_days)).date()
    for i in range(window_days):
        wd = (start + timedelta(days=i)).weekday()
        counts_by_dow[wd] = counts_by_dow.get(wd, 0) + 1

    lambdas: list[float] = []
    exposures: list[float] = []
    for wd in range(7):
        n = float(counts_by_dow.get(wd, 0))
        exposures.append(n)
        lambdas.append(consumed_by_dow.get(wd, 0.0) / n if n > 0 else 0.0)

    return WeekdayRates(lambdas=lambdas, exposures=exposures, window_days=window_days)


@dataclass
class RestockForecast:
    ingredient_id: int
    name: str
    current_stock_qty: float
    lambda_flat: float  # exposure-weighted daily rate
    p50_stockout_date: date | None  # expected path
    p95_stockout_date: date | None  # conservative path (plan against this)
    days_to_p95_stockout: float | None
    recommended_restock_qty: float  # covers 14 days ahead on the P95 path
    restock_cost_gs_estimate: int | None
    weekday_peak_rate: float
    weekday_trough_rate: float
    weekend_uplift_pct: float  # (avg Sat+Sun / avg Mon-Thu - 1) * 100
    confidence: str  # 'high' | 'medium' | 'low' — by total exposure


def forecast_restock(
    session: Session,
    ingredient_id: int,
    *,
    window_days: int = 56,
    horizon_days: int = 60,
    cover_days: int = 14,
    now: datetime | None = None,
) -> RestockForecast:
    """Poisson weekday forecast for one ingredient (restock planning)."""
    ing = session.get(Ingredient, ingredient_id)
    if ing is None:
        raise ValueError(f"Ingredient {ingredient_id} not found")

    now = now or datetime.now(timezone.utc)
    rates = poisson_weekday_rates(session, ingredient_id, window_days=window_days, now=now)
    stock = ing.stock_qty or 0.0
    today = now.date()

    p50_date, p95_date = _compute_stockout_dates(rates, stock, today, horizon_days)
    days_to_p95 = (p95_date - today).days if p95_date is not None else None
    recommended, _p95_daily_avg = _compute_recommended_restock(
        rates, ing, stock, cover_days
    )
    cost_estimate = _compute_cost_estimate(ing, recommended)
    uplift = _compute_weekend_uplift(rates)
    confidence = _compute_confidence(session, ingredient_id, window_days, now)

    return RestockForecast(
        ingredient_id=ing.id,
        name=ing.name,
        current_stock_qty=stock,
        lambda_flat=rates.flat_equivalent(),
        p50_stockout_date=p50_date,
        p95_stockout_date=p95_date,
        days_to_p95_stockout=days_to_p95,
        recommended_restock_qty=recommended,
        restock_cost_gs_estimate=cost_estimate,
        weekday_peak_rate=max(rates.lambdas) if rates.lambdas else 0.0,
        weekday_trough_rate=min(rates.lambdas) if rates.lambdas else 0.0,
        weekend_uplift_pct=uplift,
        confidence=confidence,
    )


def _compute_stockout_dates(
    rates, stock: float, today, horizon_days: int
) -> tuple:
    """Walk both P50 and P95 paths forward to find stockout dates.

    Walk the two paths forward (on a LOCAL copy — the reported
    current_stock_qty must stay the pre-walk value).
    Extracted from forecast_restock to reduce complexity.
    """
    remaining = stock
    p50_date: date | None = None
    p95_date: date | None = None
    cumulative_p95 = 0.0
    for i in range(horizon_days):
        wd = (today + timedelta(days=i)).weekday()
        lam = rates.rate(wd)
        se = rates.se(wd)
        # Expected path
        if p50_date is None and remaining > 0 and lam > 0:
            remaining -= lam
            if remaining <= 0:
                p50_date = today + timedelta(days=i)
        # P95 path (per-day upper bound)
        day_p95 = lam + Z_95_ONE_SIDED * se
        cumulative_p95 += day_p95
        if p95_date is None and stock > 0 and cumulative_p95 >= stock:
            p95_date = today + timedelta(days=i)
    return p50_date, p95_date


def _compute_recommended_restock(
    rates, ing, stock: float, cover_days: int
) -> tuple:
    """Compute recommended restock quantity based on P95 path.

    Recommended qty: cover `cover_days` ahead on the P95 path, keep the
    2x-min floor from forecast.py (operators already understand it).
    Extracted from forecast_restock to reduce complexity.
    """
    p95_week_total = sum(rates.rate(wd) + Z_95_ONE_SIDED * rates.se(wd) for wd in range(7))
    p95_daily_avg = p95_week_total / 7.0
    target = max(
        (ing.min_stock_qty or 0) * 2,
        p95_daily_avg * cover_days,
    )
    if p95_week_total > 0:
        recommended = max(0.0, target - stock)
    else:
        recommended = max(0.0, (ing.min_stock_qty or 0) * 2 - stock)
    return recommended, p95_daily_avg


def _compute_cost_estimate(ing, recommended: float) -> int | None:
    """Compute cost estimate at the ingredient's catalog price (per-unit, Gs).

    Extracted from forecast_restock to reduce complexity.
    """
    unit_price = ing.purchase_price_gs
    if not unit_price:
        return None
    return round(recommended * unit_price)


def _compute_weekend_uplift(rates) -> float:
    """Compute weekend uplift signal (Sat/Sun vs Mon-Thu).

    Extracted from forecast_restock to reduce complexity.
    """
    weekday_avg = sum(rates.rate(wd) for wd in range(4)) / 4.0 if rates.exposures[0] else 0.0
    weekend_avg = (rates.rate(5) + rates.rate(6)) / 2.0
    if weekday_avg <= 0:
        return 0.0
    return (weekend_avg / weekday_avg - 1.0) * 100.0


def _compute_confidence(
    session, ingredient_id: int, window_days: int, now
) -> str:
    """Compute confidence based on observed movement days.

    Confidence keys on OBSERVED movement days (days with sale rows in
    the window), not raw exposure — a 56-day window with 3 sale days is
    sparse data, not high confidence.
    Extracted from forecast_restock to reduce complexity.
    """
    obs_cutoff = datetime.combine(
        (now - timedelta(days=window_days)).date(),
        datetime.min.time(),
        tzinfo=now.tzinfo,
    )
    observed_days = (
        session.scalar(
            select(func.count(func.distinct(func.date(StockMovement.recorded_at))))
            .where(StockMovement.ingredient_id == ingredient_id)
            .where(StockMovement.movement_type == "sale")
            .where(StockMovement.recorded_at >= obs_cutoff)
        )
        or 0
    )
    if observed_days >= 28:
        return "high"
    if observed_days >= 10:
        return "medium"
    return "low"


def forecast_restock_batch(
    session: Session,
    ingredient_ids: list[int],
    *,
    window_days: int = 56,
    only_at_risk: bool = True,
    p95_days_threshold: int = 14,
) -> dict[int, RestockForecast]:
    """Batch wrapper for the reorder page.

    only_at_risk=True filters to ingredients whose P95 stockout lands
    within ``p95_days_threshold`` days (the actionable set).
    """
    out: dict[int, RestockForecast] = {}
    for ing_id in ingredient_ids:
        fc = forecast_restock(session, ing_id, window_days=window_days)
        if only_at_risk:
            if fc.days_to_p95_stockout is None:
                continue
            if fc.days_to_p95_stockout > p95_days_threshold:
                continue
        out[ing_id] = fc
    return out
