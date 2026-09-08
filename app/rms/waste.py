"""app/rms/waste.py — Merma (waste) tracking (E22).

Per docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md E22.

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

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.rms.models import Ingredient, WasteLog


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

    n_events: int
    total_qty: float
    total_cost_gs: int
    by_reason: dict[str, int]  # reason -> cost_gs
    by_ingredient: list[tuple[int, str, int]]  # (id, name, cost_gs)


# --- CRUD ---


def record_waste(
    session: Session,
    *,
    ingredient_id: int,
    qty: float,
    reason: WasteReason,
    recorded_by: str | None = None,
    notes: str | None = None,
) -> WasteLog:
    """Log a waste event. Decrements stock + records cost-at-time.

    Cost is denormalized at insert time so historical waste reports
    remain stable even if purchase prices change.
    """
    ing = session.get(Ingredient, ingredient_id)
    if ing is None:
        raise ValueError(f"Ingredient {ingredient_id} not found")
    cost_gs = (
        int(round(qty * ing.purchase_price_gs))
        if ing.purchase_price_gs is not None
        else 0
    )
    log = WasteLog(
        ingredient_id=ingredient_id,
        qty=qty,
        reason=reason.value,
        cost_gs=cost_gs,
        recorded_at=datetime.now(timezone.utc),
        recorded_by=recorded_by,
        notes=notes,
    )
    session.add(log)
    # Decrement stock
    ing.stock_qty = max(0.0, ing.stock_qty - qty)
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
    qty_sum = session.execute(
        select(func.sum(WasteLog.qty)).where(
            WasteLog.recorded_at >= start_date, WasteLog.recorded_at <= end_date
        )
    ).scalar() or 0.0

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


__all__ = [
    "WasteReason",
    "WasteImpact",
    "record_waste",
    "list_waste",
    "waste_impact",
    "waste_as_pct_of_revenue",
]
