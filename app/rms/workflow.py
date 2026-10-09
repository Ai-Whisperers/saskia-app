"""app/rms/workflow.py — Operator workflow helpers (E12).

Per docs/plans/2026-09-07-sazon-complete-epic-plan-v3.md E12.

Adds:
- EndOfDayChecklist: 10-item structured daily close (cash count,
  ingredient reorder check, sales sync, etc.)
- DailySummary: revenue + cogs + top products + warnings + low stock
- SeasonalCalendar: holiday/event awareness that hints at product
  demand changes (Navidad, Día de la Madre, Año Nuevo, etc.)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.rms.models import Ingredient, Product, Sale
from app.rms.money import to_int_gs

# --- EOD Checklist ---


class EODItemStatus(str, Enum):
    """Status of an EOD checklist item."""

    PENDING = "pending"
    DONE = "done"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


@dataclass
class EODChecklistItem:
    """One item in the daily close checklist."""

    key: str
    label: str
    status: EODItemStatus = EODItemStatus.PENDING
    notes: str | None = None


# Standard EOD checklist (10 items).
EOD_CHECKLIST_TEMPLATE: list[EODChecklistItem] = [
    EODChecklistItem("cash_count", "Conteo de caja (efectivo + SIPAP)"),
    EODChecklistItem("sales_reconciled", "Ventas del día conciliadas"),
    EODChecklistItem("low_stock_reviewed", "Stock bajo revisado"),
    EODChecklistItem("ingredients_reordered", "Pedido a proveedor (si aplica)"),
    EODChecklistItem("waste_logged", "Merma registrada (si aplica)"),
    EODChecklistItem("tomorrow_prep", "Plan de producción para mañana"),
    EODChecklistItem("cash_deposit", "Depósito bancario realizado"),
    EODChecklistItem("equipment_cleaned", "Equipo y mesada limpios"),
    EODChecklistItem("receipts_archived", "Recibos físicos archivados"),
    EODChecklistItem("notes_for_tomorrow", "Notas para el turno siguiente"),
]


def fresh_eod_checklist() -> list[EODChecklistItem]:
    """Return a fresh checklist with PENDING status on every item."""
    return [
        EODChecklistItem(
            key=item.key,
            label=item.label,
            status=EODItemStatus.PENDING,
        )
        for item in EOD_CHECKLIST_TEMPLATE
    ]


def eod_progress(items: list[EODChecklistItem]) -> dict:
    """Compute progress: total, done, pending, blocked, skipped, pct."""
    total = len(items)
    counts: dict[EODItemStatus, int] = {s: 0 for s in EODItemStatus}
    for item in items:
        counts[item.status] += 1
    return {
        "total": total,
        "done": counts[EODItemStatus.DONE],
        "pending": counts[EODItemStatus.PENDING],
        "blocked": counts[EODItemStatus.BLOCKED],
        "skipped": counts[EODItemStatus.SKIPPED],
        "pct": round((counts[EODItemStatus.DONE] + counts[EODItemStatus.SKIPPED]) / total * 100, 1)
        if total > 0
        else 0.0,
    }


# --- Daily summary ---


@dataclass
class DailyProductRow:
    """One row of the daily summary (per product)."""

    product_id: int
    product_name: str
    qty_sold: float
    revenue_gs: int


@dataclass
class DailySummaryFull:
    """End-of-day summary."""

    date: datetime
    n_sales: int
    n_voided: int
    revenue_gs: int
    cogs_gs: int
    margin_gs: int
    margin_pct: float
    top_products: list[DailyProductRow]
    low_stock_ingredients: list[str]  # ingredient names below min
    warnings: list[str]


def _get_daily_sales(session: Session, start: datetime, end: datetime) -> tuple[list, list, list]:
    """Fetch sales for a day, split into valid and voided."""
    sales = list(
        session.execute(select(Sale).where(Sale.sold_at >= start, Sale.sold_at < end)).scalars()
    )
    valid = [s for s in sales if s.voided_at is None]
    voided = [s for s in sales if s.voided_at is not None]
    return sales, valid, voided


def _compute_daily_revenue(valid: list) -> int:
    """Compute total revenue from valid sales."""
    return sum(to_int_gs(Decimal(str(s.qty)) * Decimal(str(s.unit_price_gs))) for s in valid)


def _compute_daily_cogs(session: Session, start: datetime, end: datetime) -> int:
    """Compute COGS for a day using StockMovement + Ingredient.purchase_price_gs.

    T-2026-10-04: BACKLOG #1 (migration 092) dropped the sale_stock_move
    table. Use StockMovement with movement_type='sale' as the
    authoritative source.
    """
    from app.rms.models import StockMovement

    cogs = (
        session.execute(
            select(
                func.coalesce(
                    func.sum(func.abs(StockMovement.qty) * Ingredient.purchase_price_gs),
                    0,
                )
            )
            .select_from(StockMovement)
            .join(Sale, Sale.id == StockMovement.reference_id)
            .join(Ingredient, Ingredient.id == StockMovement.ingredient_id)
            .where(
                StockMovement.movement_type == "sale",
                StockMovement.reference_type == "sale",
                Sale.sold_at >= start,
                Sale.sold_at < end,
                Sale.voided_at.is_(None),
            )
        ).scalar()
        or 0
    )
    return int(cogs)


def _get_top_products(session: Session, valid: list) -> list:
    """Get top 10 products by revenue."""
    buckets: dict[int, dict] = {}
    for s in valid:
        b = buckets.setdefault(s.product_id, {"qty": 0.0, "rev": 0})
        b["qty"] += s.qty
        b["rev"] += to_int_gs(Decimal(str(s.qty)) * Decimal(str(s.unit_price_gs)))
    prod_ids = list(buckets.keys())
    prods_by_id = {}
    if prod_ids:
        prods_by_id = {
            p.id: p
            for p in session.execute(select(Product).where(Product.id.in_(prod_ids))).scalars()
        }
    return sorted(
        [
            DailyProductRow(
                product_id=pid,
                product_name=prods_by_id.get(pid, Product(name=f"#{pid}")).name,
                qty_sold=b["qty"],
                revenue_gs=b["rev"],
            )
            for pid, b in buckets.items()
        ],
        key=lambda r: -r.revenue_gs,
    )[:10]


def _get_low_stock_ingredients(session: Session) -> list:
    """Get ingredients below minimum stock."""
    return list(
        session.execute(
            select(Ingredient).where(
                Ingredient.min_stock_qty > 0,
                Ingredient.stock_qty < Ingredient.min_stock_qty,
            )
        ).scalars()
    )


def _generate_warnings(
    sales: list, valid: list, voided: list, revenue: int, margin_pct: float, low_stock: list
) -> list[str]:
    """Generate warning messages for the daily summary."""
    warnings: list[str] = []
    if len(voided) > len(valid) * 0.1 and len(valid) > 0:
        warnings.append(
            f"Alto ratio de anulaciones: {len(voided)}/{len(sales)} ({len(voided) / len(sales) * 100:.0f}%)"
        )
    if margin_pct < 30 and revenue > 0:
        warnings.append(f"Margen bajo: {margin_pct:.1f}% (objetivo >= 30%)")
    if low_stock:
        warnings.append(f"{len(low_stock)} ingredientes bajo mínimo")
    if revenue == 0:
        warnings.append("Sin ventas registradas hoy")
    return warnings


def daily_summary_full(
    session: Session,
    day: datetime,
) -> DailySummaryFull:
    """Generate a comprehensive daily summary."""
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    sales, valid, voided = _get_daily_sales(session, start, end)
    revenue = _compute_daily_revenue(valid)
    cogs = _compute_daily_cogs(session, start, end)

    margin = revenue - cogs
    margin_pct = (margin / revenue * 100) if revenue > 0 else 0.0

    top_products = _get_top_products(session, valid)
    low_stock = _get_low_stock_ingredients(session)
    warnings = _generate_warnings(sales, valid, voided, revenue, margin_pct, low_stock)

    return DailySummaryFull(
        date=start,
        n_sales=len(valid),
        n_voided=len(voided),
        revenue_gs=revenue,
        cogs_gs=int(cogs),
        margin_gs=margin,
        margin_pct=margin_pct,
        top_products=top_products,
        low_stock_ingredients=[i.name for i in low_stock],
        warnings=warnings,
    )


# --- Seasonal calendar (E19 prep) ---


@dataclass
class SeasonalEvent:
    """A Paraguay-relevant seasonal event."""

    name: str
    start: date
    end: date
    hint: str
    multiplier: float  # demand multiplier vs. baseline


# Fixed-date + relative events. Multiplier is illustrative.
SEASONAL_CALENDAR_2026: list[SeasonalEvent] = [
    SeasonalEvent(
        "Año Nuevo",
        date(2026, 1, 1),
        date(2026, 1, 2),
        "Desayunos familiares y brunch. +30% demanda de muffins/tostados.",
        1.3,
    ),
    SeasonalEvent(
        "Día de los Enamorados",
        date(2026, 2, 14),
        date(2026, 2, 14),
        "Regalos comestibles. +40% chocolates y tortas pequeñas.",
        1.4,
    ),
    SeasonalEvent(
        "Día de la Mujer",
        date(2026, 3, 1),
        date(2026, 3, 8),
        "Regalos corporativos. +25% tortas y cupcakes premium.",
        1.25,
    ),
    SeasonalEvent(
        "Día del Padre",
        date(2026, 3, 15),
        date(2026, 3, 15),
        "Mismo patrón que Día de la Madre.",
        1.2,
    ),
    SeasonalEvent(
        "Pascuas",
        date(2026, 4, 1),
        date(2026, 4, 15),
        "Huevos de Pascua + roscas. +50% repostería fina.",
        1.5,
    ),
    SeasonalEvent(
        "Día de la Madre (PY)",
        date(2026, 5, 15),
        date(2026, 5, 15),
        "Mismo día. Pico de tortas + cupcakes decorados.",
        2.0,
    ),
    SeasonalEvent(
        "Día del Niño",
        date(2026, 7, 16),
        date(2026, 7, 16),
        "Cupcakes y galletas decoradas. +30%.",
        1.3,
    ),
    SeasonalEvent(
        "Día de la Independencia",
        date(2026, 8, 14),
        date(2026, 8, 15),
        "Patrios: chipa, sopa paraguaya. +80% volumen.",
        1.8,
    ),
    SeasonalEvent(
        "Halloween",
        date(2026, 10, 31),
        date(2026, 10, 31),
        "Decoraciones temáticas. +20%.",
        1.2,
    ),
    SeasonalEvent(
        "Día de Todos los Santos",
        date(2026, 11, 1),
        date(2026, 11, 1),
        "Dulces tradicionales. +15%.",
        1.15,
    ),
    SeasonalEvent(
        "Navidad",
        date(2026, 12, 15),
        date(2026, 12, 31),
        "Pico anual. +200% volumen; pan dulce, roscas, tortas.",
        3.0,
    ),
]


def active_events(day: date) -> list[SeasonalEvent]:
    """Return seasonal events active on a given day."""
    return [ev for ev in SEASONAL_CALENDAR_2026 if ev.start <= day <= ev.end]


def upcoming_events(day: date, *, days_ahead: int = 14) -> list[SeasonalEvent]:
    """Return events starting in the next N days."""
    horizon = day + timedelta(days=days_ahead)
    return [ev for ev in SEASONAL_CALENDAR_2026 if day < ev.start <= horizon]


def demand_multiplier(day: date) -> float:
    """Aggregate demand multiplier for a given day (max of active events)."""
    events = active_events(day)
    if not events:
        return 1.0
    return max(e.multiplier for e in events)


__all__ = [
    "EOD_CHECKLIST_TEMPLATE",
    "SEASONAL_CALENDAR_2026",
    "DailyProductRow",
    "DailySummaryFull",
    "EODChecklistItem",
    "EODItemStatus",
    "SeasonalEvent",
    "active_events",
    "daily_summary_full",
    "demand_multiplier",
    "eod_progress",
    "fresh_eod_checklist",
    "upcoming_events",
]
