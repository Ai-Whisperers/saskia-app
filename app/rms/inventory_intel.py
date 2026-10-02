"""app/rms/inventory_intel.py — days-of-stock, reorder points, dead stock, overstock.

Tells the operator:
- When to reorder (reorder_point)
- How many days of stock remain (days_of_stock)
- Which ingredients are dead stock (no consumption in N days)
- Which ingredients are overstocked (>3× monthly consumption in stock)
- Total capital tied up in inventory
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import Ingredient, StockMovement

# ---------------------------------------------------------------------------
# Dataclass results
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InventoryStatus:
    ingredient_id: int
    ingredient_name: str
    stock_qty: float
    avg_daily_consumption: float
    days_of_stock: float | None  # None if no consumption
    reorder_point: float
    lead_time_days: int
    needs_reorder: bool


@dataclass(frozen=True)
class DeadStock:
    ingredient_id: int
    ingredient_name: str
    stock_qty: float
    last_consumed_at: datetime | None
    days_since_consumed: int | None


@dataclass(frozen=True)
class Overstocked:
    ingredient_id: int
    ingredient_name: str
    stock_qty: float
    days_of_stock: float


# ---------------------------------------------------------------------------
# Consumption rate (from stock_movement where movement_type='sale', qty<0)
# ---------------------------------------------------------------------------

_CONSUMPTION_WINDOW_DAYS: Final[int] = 90  # last 90 days


def _avg_daily_consumption(session: Session, ingredient_id: int,
                           window_days: int = _CONSUMPTION_WINDOW_DAYS) -> float:
    """Average kg/day consumed in the last window.

    Returns 0.0 if no consumption.

    Reads from stock_movement (BACKLOG #1 consolidation — sale_stock_move
    was merged into stock_movement in this session, so the sale-driven
    stock-out lives there now with movement_type='sale' and qty<0). The
    recorded_at column lets us filter by date — no more "use all moves
    as approximation" workaround that the legacy SaleStockMove code
    had to use because SaleStockMove had no timestamp.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    rows = session.execute(
        select(StockMovement.qty)
        .where(
            StockMovement.ingredient_id == ingredient_id,
            StockMovement.movement_type == "sale",
            StockMovement.recorded_at >= cutoff,
        )
    ).all()
    total = sum(abs(float(r[0])) for r in rows if r[0] is not None and r[0] < 0)
    return total / window_days


# ---------------------------------------------------------------------------
# days_of_stock + reorder_point + status
# ---------------------------------------------------------------------------

def days_of_stock(stock_qty: float, avg_daily_consumption: float) -> float | None:
    """Days until stock runs out. None if consumption is 0."""
    if avg_daily_consumption <= 0:
        return None
    return stock_qty / avg_daily_consumption


def reorder_point(avg_daily_consumption: float, lead_time_days: int,
                  safety_pct: float = 0.2) -> float:
    """Minimum stock level that triggers a reorder.

    Formula: avg_daily × lead_time × (1 + safety_pct).
    """
    return avg_daily_consumption * lead_time_days * (1 + safety_pct)


def inventory_status(session: Session, ingredient: Ingredient,
                     safety_pct: float = 0.2) -> InventoryStatus:
    """Full inventory status for one ingredient."""
    lead_time = ingredient.lead_time_days or 3
    avg_daily = _avg_daily_consumption(session, ingredient.id)
    dos = days_of_stock(float(ingredient.stock_qty or 0), avg_daily)
    rp = reorder_point(avg_daily, lead_time, safety_pct)
    needs = float(ingredient.stock_qty or 0) <= rp
    return InventoryStatus(
        ingredient_id=ingredient.id,
        ingredient_name=ingredient.name,
        stock_qty=float(ingredient.stock_qty or 0),
        avg_daily_consumption=avg_daily,
        days_of_stock=dos,
        reorder_point=rp,
        lead_time_days=lead_time,
        needs_reorder=needs,
    )


def inventory_status_all(session: Session,
                         safety_pct: float = 0.2) -> list[InventoryStatus]:
    """Status for every ingredient."""
    return [inventory_status(session, ing, safety_pct)
            for ing in session.scalars(select(Ingredient)).all()]


# ---------------------------------------------------------------------------
# Dead stock + overstocked
# ---------------------------------------------------------------------------

def dead_stock(session: Session, days_threshold: int = 30) -> list[DeadStock]:
    """Ingredients not consumed in the last N days.

    Heuristic: `last_consumed_at` column on Ingredient, OR fallback to
    "no SaleStockMove references".
    """
    out: list[DeadStock] = []
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days_threshold)

    for ing in session.scalars(select(Ingredient)).all():
        # Check ingredient.last_consumed_at first.
        last_at = ing.last_consumed_at
        if last_at is not None:
            # last_consumed_at is stored as naive-UTC string in some setups;
            # treat as datetime.
            if last_at < cutoff:
                days_since = (now - last_at).days
                out.append(DeadStock(
                    ingredient_id=ing.id,
                    ingredient_name=ing.name,
                    stock_qty=float(ing.stock_qty or 0),
                    last_consumed_at=last_at,
                    days_since_consumed=days_since,
                ))
            continue

        # Fallback: no stock_movement references AND no last_consumed_at set.
        move_count = session.execute(
            select(StockMovement.id).where(
                StockMovement.ingredient_id == ing.id,
            ).limit(1)
        ).first()
        if move_count is None and float(ing.stock_qty or 0) > 0:
            out.append(DeadStock(
                ingredient_id=ing.id,
                ingredient_name=ing.name,
                stock_qty=float(ing.stock_qty or 0),
                last_consumed_at=None,
                days_since_consumed=None,
            ))
    return out


def overstocked(session: Session, multiplier: float = 3.0,
                window_days: int = 30) -> list[Overstocked]:
    """Ingredients with stock > multiplier × expected 30-day consumption.

    "Expected 30-day consumption" = avg_daily × 30.
    """
    out: list[Overstocked] = []
    for ing in session.scalars(select(Ingredient)).all():
        avg_daily = _avg_daily_consumption(session, ing.id, window_days=window_days)
        expected_30d = avg_daily * window_days
        threshold = expected_30d * multiplier
        stock = float(ing.stock_qty or 0)
        if stock > threshold and stock > 0:
            dos = days_of_stock(stock, avg_daily) if avg_daily > 0 else float('inf')
            out.append(Overstocked(
                ingredient_id=ing.id,
                ingredient_name=ing.name,
                stock_qty=stock,
                days_of_stock=dos if dos != float('inf') else 9999.0,
            ))
    return out


# ---------------------------------------------------------------------------
# Capital tied up
# ---------------------------------------------------------------------------

def stock_value_gs(session: Session) -> int:
    """Total capital tied up in inventory at purchase price.

    Returns total in Gs. across all ingredients.
    """
    total = 0
    for ing in session.scalars(select(Ingredient)).all():
        stock = float(ing.stock_qty or 0)
        price = int(ing.purchase_price_gs or 0)
        total += int(stock * price)
    return total


# ---------------------------------------------------------------------------
# Low-stock alerts (for dashboard panel)
# ---------------------------------------------------------------------------

def low_stock_alerts(session: Session, top_n: int = 5) -> list[InventoryStatus]:
    """Top N ingredients most in need of reorder (sorted by days_of_stock ascending)."""
    statuses = inventory_status_all(session)
    # Filter to those needing reorder OR with finite days_of_stock.
    candidates = [s for s in statuses if s.needs_reorder
                  and s.days_of_stock is not None]
    candidates.sort(key=lambda s: s.days_of_stock or 0)
    return candidates[:top_n]


__all__ = [
    "DeadStock",
    "InventoryStatus",
    "Overstocked",
    "days_of_stock",
    "dead_stock",
    "inventory_status",
    "inventory_status_all",
    "low_stock_alerts",
    "overstocked",
    "reorder_point",
    "stock_value_gs",
]
