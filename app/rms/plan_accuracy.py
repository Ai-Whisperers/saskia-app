"""app/rms/plan_accuracy.py — BACKLOG #29 + #33: plan-vs-actual analytics.

Reads from:
  - ProductionCompletion (actual_qty baked per product per date)
  - plan_production() (what the forecast engine said to bake)
  - Sale.qty (real customer demand — actual sales, voided filtered out)

A "day row" is the join of:
  planned_qty  = sum(plan_production(d).qty_to_produce > 0) per product
  completed_qty= sum(ProductionCompletion.completed_qty) on date d
  sold_qty     = sum(Sale.qty) on date d, voided_at IS NULL

A "plan accuracy" metric per product per date:
  accuracy   = completed_qty / planned_qty if planned_qty > 0 else NULL
  under_baked = max(planned_qty - completed_qty, 0)
  over_baked  = max(completed_qty - planned_qty, 0)

A product with planned > 0 and accuracy < 0.7 was "under-baked" (ran out).
A product with completed > planned+2 and sold_qty < completed_qty was "over-baked"
(made too much, sold less — wasted capacity / cost).

This module is read-only — never writes. The DayView rendering on /produccion
already shows per-product progress; this module is the historical aggregator
for the dashboard.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.rms.config import ASUNCION_TZ
from app.rms.models_legacy import ProductionCompletion, Product, Sale


@dataclass(frozen=True)
class DailyAccuracyRow:
    """One (product, day) summary row."""
    product_id: int
    product_name: str
    for_date: date
    planned_qty: float
    completed_qty: float
    sold_qty: float

    @property
    def accuracy(self) -> float | None:
        """completed / planned; None when there was no plan (ad_hoc)."""
        if self.planned_qty <= 0:
            return None
        return round(self.completed_qty / self.planned_qty, 4)

    @property
    def under_baked(self) -> float:
        return max(self.planned_qty - self.completed_qty, 0.0)

    @property
    def over_baked(self) -> float:
        return max(self.completed_qty - self.planned_qty, 0.0)

    @property
    def demand_met(self) -> float | None:
        """sold_qty / completed_qty; None when completed was zero."""
        if self.completed_qty <= 0:
            return None
        return round(self.sold_qty / self.completed_qty, 4)


@dataclass
class ProductAccuracySummary:
    """Per-product aggregate over the period."""
    product_id: int
    product_name: str
    n_days_with_plan: int
    n_days_completed: int
    avg_accuracy: float | None  # mean of daily accuracies (planned > 0 days)
    under_baked_units: float
    over_baked_units: float
    total_planned: float
    total_completed: float
    total_sold: float

    @property
    def total_accuracy(self) -> float | None:
        if self.total_planned <= 0:
            return None
        return round(self.total_completed / self.total_planned, 4)


@dataclass
class AccuracyReport:
    """Full dashboard response — list-friendly + summary stats."""
    daily_rows: list[DailyAccuracyRow] = field(default_factory=list)
    product_summary: list[ProductAccuracySummary] = field(default_factory=list)
    n_days_in_period: int = 0
    n_days_with_completion: int = 0
    total_planned: float = 0.0
    total_completed: float = 0.0
    total_sold: float = 0.0
    avg_accuracy: float | None = None

    @property
    def under_baked_pct(self) -> float | None:
        """Share of planned units that were NOT completed."""
        if self.total_planned <= 0:
            return None
        return round(
            (self.total_planned - self.total_completed) / self.total_planned,
            4,
        )


def _daily_completions(
    session: Session,
    start_date: date,
    end_date: date,
) -> dict[tuple[int, date], float]:
    """{ (product_id, for_date): sum(completed_qty) } for dates in range."""
    rows = (
        session.query(
            ProductionCompletion.product_id,
            ProductionCompletion.for_date,
            func.coalesce(func.sum(ProductionCompletion.completed_qty), 0.0),
        )
        .filter(
            and_(
                ProductionCompletion.for_date >= start_date,
                ProductionCompletion.for_date <= end_date,
            )
        )
        .group_by(ProductionCompletion.product_id, ProductionCompletion.for_date)
        .all()
    )
    return {(pid, d): float(qty or 0.0) for pid, d, qty in rows}


def _daily_sales(
    session: Session,
    start_date: date,
    end_date: date,
) -> dict[tuple[int, date], float]:
    """{ (product_id, for_date): sum(Sale.qty) } for non-voided sales in range."""
    start_dt = datetime.combine(start_date, datetime.min.time()).replace(
        tzinfo=timezone.utc,
    )
    end_dt = datetime.combine(end_date, datetime.max.time()).replace(
        tzinfo=timezone.utc,
    )
    rows = (
        session.query(
            Sale.product_id,
            func.date(Sale.sold_at).label("d"),
            func.coalesce(func.sum(Sale.qty), 0.0),
        )
        .filter(
            and_(
                Sale.sold_at >= start_dt,
                Sale.sold_at <= end_dt,
                Sale.voided_at.is_(None),
            )
        )
        .group_by(Sale.product_id, func.date(Sale.sold_at))
        .all()
    )
    out: dict[tuple[int, date], float] = {}
    for pid, d, qty in rows:
        # SQLite date() returns ISO 'YYYY-MM-DD'; PG date_trunc may return date.
        d_str = str(d)
        try:
            d_obj = date.fromisoformat(d_str)
        except ValueError:
            continue
        out[(pid, d_obj)] = float(qty or 0.0)
    return out


def compute_plan_accuracy(
    session: Session,
    start_date: date,
    end_date: date,
    planned_qty_by_pid_day: dict[tuple[int, date], float],
) -> AccuracyReport:
    """Build the AccuracyReport from raw data.

    Args:
        session: SQLAlchemy session.
        start_date: inclusive start of range.
        end_date: inclusive end of range.
        planned_qty_by_pid_day: caller-supplied map
            { (product_id, for_date): qty_to_produce }. This avoids the
            cost of re-running plan_production() for every day in the period —
            the caller already has the plan context (the /produccion page
            computes it daily; for a dashboard, we run it in bulk).

    Returns:
        AccuracyReport with daily rows + per-product summaries.
    """
    completions = _daily_completions(session, start_date, end_date)
    sales = _daily_sales(session, start_date, end_date)

    # Collect every (pid, day) key from any of the three sources.
    all_keys = set(planned_qty_by_pid_day) | set(completions) | set(sales)
    if not all_keys:
        return AccuracyReport(n_days_in_period=(end_date - start_date).days + 1)

    # Resolve product names in one query (avoid N+1).
    pids = sorted({k[0] for k in all_keys})
    product_names = {
        p.id: p.name
        for p in session.query(Product).filter(Product.id.in_(pids)).all()
    }

    rows: list[DailyAccuracyRow] = []
    for pid, d in sorted(all_keys):
        rows.append(
            DailyAccuracyRow(
                product_id=pid,
                product_name=product_names.get(pid, f"#{pid}"),
                for_date=d,
                planned_qty=float(planned_qty_by_pid_day.get((pid, d), 0.0)),
                completed_qty=float(completions.get((pid, d), 0.0)),
                sold_qty=float(sales.get((pid, d), 0.0)),
            )
        )

    # Aggregate per product.
    by_pid: dict[int, list[DailyAccuracyRow]] = {}
    for r in rows:
        by_pid.setdefault(r.product_id, []).append(r)

    summaries: list[ProductAccuracySummary] = []
    for pid, drows in by_pid.items():
        planned_days = [r for r in drows if r.planned_qty > 0]
        accs = [r.accuracy for r in planned_days if r.accuracy is not None]
        summaries.append(
            ProductAccuracySummary(
                product_id=pid,
                product_name=product_names.get(pid, f"#{pid}"),
                n_days_with_plan=len(planned_days),
                n_days_completed=sum(1 for r in drows if r.completed_qty > 0),
                avg_accuracy=round(sum(accs) / len(accs), 4) if accs else None,
                under_baked_units=round(sum(r.under_baked for r in drows), 4),
                over_baked_units=round(sum(r.over_baked for r in drows), 4),
                total_planned=round(sum(r.planned_qty for r in drows), 4),
                total_completed=round(sum(r.completed_qty for r in drows), 4),
                total_sold=round(sum(r.sold_qty for r in drows), 4),
            )
        )
    summaries.sort(key=lambda s: -(s.under_baked_units + s.over_baked_units))

    n_days_with_completion = sum(
        1 for r in rows if r.completed_qty > 0
    )
    all_accs = [r.accuracy for r in rows if r.accuracy is not None]
    total_planned = round(sum(r.planned_qty for r in rows), 4)
    total_completed = round(sum(r.completed_qty for r in rows), 4)
    total_sold = round(sum(r.sold_qty for r in rows), 4)

    return AccuracyReport(
        daily_rows=rows,
        product_summary=summaries,
        n_days_in_period=(end_date - start_date).days + 1,
        n_days_with_completion=n_days_with_completion,
        total_planned=total_planned,
        total_completed=total_completed,
        total_sold=total_sold,
        avg_accuracy=round(sum(all_accs) / len(all_accs), 4) if all_accs else None,
    )


def date_range_presets() -> dict[str, tuple[date, date]]:
    """Return common date-range presets for the dashboard filter.

    Note: dates use Paraguay's local day boundaries, but the underlying
    queries normalize via SQL date() (UTC). For a bakery running same-day,
    the mismatch is at most 4h — acceptable for a 7/30/90 day view.
    """
    today = datetime.now(timezone.utc).date()
    return {
        "7d": (today - timedelta(days=6), today),
        "30d": (today - timedelta(days=29), today),
        "90d": (today - timedelta(days=89), today),
    }


__all__ = [
    "AccuracyReport",
    "DailyAccuracyRow",
    "ProductAccuracySummary",
    "compute_plan_accuracy",
    "date_range_presets",
]