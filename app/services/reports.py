"""app/services/reports.py — monthly close + stockout reports.

Per dev plan §9 Task 8 + v2 §8 (Reports).

Two public functions:

- `monthly_stockout_report(session, year, month) -> list[dict]`
    Returns rows for ingredients that ended the month below their
    `min_stock_qty` threshold. Useful for "what do I need to buy?"

- `monthly_close_summary(session, year, month) -> dict`
    Returns the same metrics the dashboard computes (ventas_gs, cogs_gs,
    margen_gs, margen_ratio, ranking) but for a calendar month. Designed
    for printing/exporting at month-end.

Both functions operate on a SQLAlchemy session and read-only query the DB.
They do NOT mutate state.

Edge cases:
- month=1..12; year=4-digit int. Out-of-range → ValueError.
- No sales in the period → all money fields 0, ranking empty, margin ratio 0.
- Voided sales (voided_at IS NOT NULL) are excluded from ventas / margen
  / ranking — they didn't actually count.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.costing import product_unit_cost_gs
from app.rms.models import Ingredient, Sale

# --- Validation helpers ---


def _validate_year_month(year: int, month: int) -> tuple[datetime, datetime]:
    """Validate year/month are in range. Return (start_dt, end_dt_exclusive).

    end_dt_exclusive is the first day of the next month at 00:00 — used for
    half-open interval queries.
    """
    if not isinstance(year, int) or not isinstance(month, int):
        raise ValueError(
            f"year/month must be ints, got {type(year).__name__}/{type(month).__name__}"
        )
    if not (1 <= year <= 9999):
        raise ValueError(f"year out of range: {year}")
    if not (1 <= month <= 12):
        raise ValueError(f"month out of range: {month}")
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)
    return start, end


# --- Result dataclasses ---


@dataclass
class StockoutRow:
    """One ingredient below its min_stock threshold at end of month."""

    ingredient_id: int
    name: str
    unit: str
    stock_qty: float
    min_stock_qty: float
    deficit: float  # positive = missing this much

    def to_dict(self) -> dict:
        return {
            "ingredient_id": self.ingredient_id,
            "name": self.name,
            "unit": self.unit,
            "stock_qty": self.stock_qty,
            "min_stock_qty": self.min_stock_qty,
            "deficit": self.deficit,
        }


@dataclass
class MonthlySummary:
    """Month-end financial summary. Mirrors the dashboard metrics."""

    year: int
    month: int
    ventas_gs: int = 0
    cogs_gs: int = 0
    margen_gs: int = 0
    margen_ratio: float = 0.0
    sale_count: int = 0
    unique_products: int = 0
    ranking: list[dict] = field(default_factory=list)  # top products by margin
    stockout_count: int = 0  # ingredients below min_stock at end of month

    def to_dict(self) -> dict:
        return {
            "year": self.year,
            "month": self.month,
            "ventas_gs": self.ventas_gs,
            "cogs_gs": self.cogs_gs,
            "margen_gs": self.margen_gs,
            "margen_ratio": self.margen_ratio,
            "sale_count": self.sale_count,
            "unique_products": self.unique_products,
            "ranking": list(self.ranking),
            "stockout_count": self.stockout_count,
        }


# --- Reports ---


def monthly_stockout_report(session: Session, year: int, month: int) -> list[StockoutRow]:
    """Return ingredients below min_stock_qty at end of month.

    The "end of month" snapshot is the current stock (we don't track
    historical stock levels, so we report what's there now). The report
    is most useful shortly after month-end.

    Only ingredients with min_stock_qty > 0 are considered (others have
    no threshold set).
    """
    _validate_year_month(year, month)
    rows: list[StockoutRow] = []
    for ing in session.scalars(select(Ingredient).where(Ingredient.min_stock_qty > 0)).all():
        if ing.stock_qty < ing.min_stock_qty:
            rows.append(
                StockoutRow(
                    ingredient_id=ing.id,
                    name=ing.name,
                    unit=ing.unit,
                    stock_qty=ing.stock_qty,
                    min_stock_qty=ing.min_stock_qty,
                    deficit=ing.min_stock_qty - ing.stock_qty,
                )
            )
    # Sort by largest deficit first (most urgent)
    rows.sort(key=lambda r: r.deficit, reverse=True)
    return rows


def monthly_close_summary(session: Session, year: int, month: int) -> MonthlySummary:
    """Compute month-end financial summary.

    Voided sales are excluded. Cost of goods sold is computed using the
    product's recipe_unit_cost at sale-time (which we approximate with the
    current recipe cost — Fase 1 has no recipe-history).
    """
    start, end = _validate_year_month(year, month)

    # Sales in the period (exclude voided)
    sales_in_period = session.scalars(
        select(Sale).where(
            Sale.sold_at >= start,
            Sale.sold_at < end,
            Sale.voided_at.is_(None),
        )
    ).all()

    summary = MonthlySummary(year=year, month=month)
    summary.sale_count = len(sales_in_period)
    if not sales_in_period:
        summary.stockout_count = len(monthly_stockout_report(session, year, month))
        return summary

    # Aggregate by product
    by_product: dict[int, dict] = {}
    ventas_total = 0
    cogs_total = 0
    for s in sales_in_period:
        ventas_total += int(round(s.qty * s.unit_price_gs))
        # Cost: product recipe cost × qty
        cost = product_unit_cost_gs(session, s.product_id)
        if cost.batch_cost_gs is not None:
            cogs_total += int(round(s.qty * cost.batch_cost_gs))

        d = by_product.setdefault(
            s.product_id,
            {
                "product_id": s.product_id,
                "product_name": s.product.name if s.product else "(deleted)",
                "qty": 0.0,
                "ventas_gs": 0,
                "cogs_gs": 0,
                "margen_gs": 0,
            },
        )
        d["qty"] += s.qty
        d["ventas_gs"] += int(round(s.qty * s.unit_price_gs))
        if cost.batch_cost_gs is not None:
            d["cogs_gs"] += int(round(s.qty * cost.batch_cost_gs))
            d["margen_gs"] = d["ventas_gs"] - d["cogs_gs"]

    summary.ventas_gs = ventas_total
    summary.cogs_gs = cogs_total
    summary.margen_gs = ventas_total - cogs_total
    if ventas_total > 0:
        summary.margen_ratio = summary.margen_gs / ventas_total
    summary.unique_products = len(by_product)

    # Ranking: top 10 by margen_gs desc
    ranking = sorted(by_product.values(), key=lambda r: r["margen_gs"], reverse=True)
    for r in ranking:
        if r["ventas_gs"] > 0:
            r["margen_ratio"] = r["margen_gs"] / r["ventas_gs"]
        else:
            r["margen_ratio"] = 0.0
    summary.ranking = ranking[:10]

    summary.stockout_count = len(monthly_stockout_report(session, year, month))
    return summary


# --- Convenience: human-readable month label ---


def month_label(year: int, month: int) -> str:
    """Return 'Septiembre 2026' style label (Spanish, since the app is es-PY)."""
    meses = [
        "Enero",
        "Febrero",
        "Marzo",
        "Abril",
        "Mayo",
        "Junio",
        "Julio",
        "Agosto",
        "Septiembre",
        "Octubre",
        "Noviembre",
        "Diciembre",
    ]
    return f"{meses[month - 1]} {year}"


def days_in_month(year: int, month: int) -> int:
    """Number of days in the given month. Useful for UI hints."""
    _validate_year_month(year, month)
    return monthrange(year, month)[1]


__all__ = [
    "StockoutRow",
    "MonthlySummary",
    "monthly_stockout_report",
    "monthly_close_summary",
    "month_label",
    "days_in_month",
]
