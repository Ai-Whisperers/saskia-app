"""app/rms/accounting.py — Paraguay accounting/IVA reports (E17).

Per docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md E17.

Paraguay tax basics (10% IVA on most goods including prepared foods):
- If prices are gross (IVA included in sale_price_gs):
  base = gross / 1.10
  iva = gross - base
- If prices are net (IVA excluded):
  base = gross
  iva = gross * 0.10

This module supports both modes via the `tax_mode` setting
("included" | "excluded"), defaulting to "included" since
bakeries typically quote prices tax-inclusive in PY.

Reports produced:
- monthly_iva_breakdown: per-month IVA base + IVA amount + total
- libro_ventas: chronological sale listing with computed IVA
- top_customers_by_month: customers by month-spend
- product_margin_summary: per-product margin in a window
- daily_summary: revenue + iva + cost + margin for one day
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.rms.models import Customer, Ingredient, Product, Sale, SaleStockMove

# --- Tax config ---


# Paraguay IVA: 10% on most food items.
PARAGUAY_IVA_RATE = 0.10
IVA_DIVISOR = 1 + PARAGUAY_IVA_RATE  # 1.10


@dataclass
class IVACalc:
    """Result of IVA extraction from a gross amount."""

    gross_gs: int
    base_gs: int  # monto sin IVA
    iva_gs: int  # IVA component


def extract_iva(gross_gs: int, *, tax_mode: str = "included") -> IVACalc:
    """Split a sale amount into base + IVA.

    tax_mode="included" (default): sale prices already include IVA.
        base = gross / 1.10
        iva = gross - base
    tax_mode="excluded": sale prices are net of IVA.
        base = gross
        iva = gross * 0.10
    """
    if tax_mode == "included":
        base = gross_gs / IVA_DIVISOR
        iva = gross_gs - base
    elif tax_mode == "excluded":
        base = float(gross_gs)
        iva = gross_gs * PARAGUAY_IVA_RATE
    else:
        raise ValueError(f"Unknown tax_mode: {tax_mode!r}")
    return IVACalc(
        gross_gs=int(round(gross_gs)),
        base_gs=int(round(base)),
        iva_gs=int(round(iva)),
    )


# --- Reports ---


@dataclass
class MonthlyIVA:
    """Per-month summary for the IVA report."""

    year: int
    month: int
    n_sales: int
    total_gross_gs: int
    total_base_gs: int
    total_iva_gs: int


def monthly_iva_breakdown(
    session: Session,
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    tax_mode: str = "included",
) -> list[MonthlyIVA]:
    """Per-month IVA report. If dates are None, last 12 months."""
    if end_date is None:
        end_date = datetime.now(timezone.utc)
    if start_date is None:
        start_date = end_date - timedelta(days=365)

    sales = list(
        session.execute(
            select(Sale)
            .where(
                Sale.sold_at >= start_date,
                Sale.sold_at <= end_date,
                Sale.voided_at.is_(None),
            )
            .order_by(Sale.sold_at)
        ).scalars()
    )

    # Aggregate per (year, month)
    buckets: dict[tuple[int, int], list[Sale]] = {}
    for s in sales:
        # Sale.sold_at is UTC-naive; treat as UTC.
        key = (s.sold_at.year, s.sold_at.month)
        buckets.setdefault(key, []).append(s)

    out: list[MonthlyIVA] = []
    for (year, month), month_sales in sorted(buckets.items()):
        gross = sum(int(round(s.qty * s.unit_price_gs)) for s in month_sales)
        iva = extract_iva(gross, tax_mode=tax_mode)
        out.append(
            MonthlyIVA(
                year=year,
                month=month,
                n_sales=len(month_sales),
                total_gross_gs=iva.gross_gs,
                total_base_gs=iva.base_gs,
                total_iva_gs=iva.iva_gs,
            )
        )
    return out


@dataclass
class LibroVentasRow:
    """One row of the Libro de Ventas (chronological)."""

    sale_id: int
    sold_at: datetime
    customer_name: str | None
    product_name: str
    qty: float
    unit_price_gs: int
    total_gross_gs: int
    base_gs: int
    iva_gs: int


def libro_ventas(
    session: Session,
    *,
    start_date: datetime,
    end_date: datetime,
    tax_mode: str = "included",
    limit: int = 10_000,
) -> list[LibroVentasRow]:
    """Chronological Libro de Ventas (sales ledger).

    Each row has gross + base + IVA extracted per sale.
    """
    rows = session.execute(
        select(Sale)
        .where(
            Sale.sold_at >= start_date,
            Sale.sold_at <= end_date,
            Sale.voided_at.is_(None),
        )
        .order_by(Sale.sold_at)
        .limit(limit)
    ).scalars().all()

    # Resolve customer + product names (one query each)
    cust_ids = {r.customer_id for r in rows if r.customer_id}
    prod_ids = {r.product_id for r in rows}
    custs = {
        c.id: c.name
        for c in session.execute(select(Customer).where(Customer.id.in_(cust_ids))).scalars()
        if cust_ids
    } if cust_ids else {}
    prods = {
        p.id: p.name
        for p in session.execute(select(Product).where(Product.id.in_(prod_ids))).scalars()
    }

    out: list[LibroVentasRow] = []
    for r in rows:
        gross = int(round(r.qty * r.unit_price_gs))
        iva = extract_iva(gross, tax_mode=tax_mode)
        out.append(
            LibroVentasRow(
                sale_id=r.id,
                sold_at=r.sold_at,
                customer_name=custs.get(r.customer_id) if r.customer_id else None,
                product_name=prods.get(r.product_id, f"#{r.product_id}"),
                qty=r.qty,
                unit_price_gs=r.unit_price_gs,
                total_gross_gs=iva.gross_gs,
                base_gs=iva.base_gs,
                iva_gs=iva.iva_gs,
            )
        )
    return out


@dataclass
class DailySummary:
    """One day's revenue/IVA/cost/margin."""

    date: datetime
    n_sales: int
    revenue_gross_gs: int
    revenue_base_gs: int
    iva_gs: int
    cogs_gs: int  # Cost of goods sold (recipe cost x qty)
    margin_gs: int


def daily_summary(
    session: Session,
    day: datetime,
    *,
    tax_mode: str = "included",
) -> DailySummary:
    """Compute one day's summary."""
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    sales = list(
        session.execute(
            select(Sale)
            .where(
                Sale.sold_at >= start,
                Sale.sold_at < end,
                Sale.voided_at.is_(None),
            )
        ).scalars()
    )

    revenue_gross = sum(int(round(s.qty * s.unit_price_gs)) for s in sales)
    iva = extract_iva(revenue_gross, tax_mode=tax_mode)

    # COGS via SaleStockMove (qty_delta is negative on sales).
    # We sum abs(qty_delta) * ingredient.purchase_price_gs at query time.
    # Note: SaleStockMove has no created_at column, so we filter via sale FK.
    # The join: SaleStockMove -> Sale -> filtered by date.
    cogs = session.execute(
        select(func.coalesce(func.sum(func.abs(SaleStockMove.qty_delta) * Ingredient.purchase_price_gs), 0))
        .select_from(SaleStockMove)
        .join(Sale, Sale.id == SaleStockMove.sale_id)
        .join(Ingredient, Ingredient.id == SaleStockMove.ingredient_id)
        .where(
            Sale.sold_at >= start,
            Sale.sold_at < end,
            Sale.voided_at.is_(None),
        )
    ).scalar() or 0

    return DailySummary(
        date=start,
        n_sales=len(sales),
        revenue_gross_gs=iva.gross_gs,
        revenue_base_gs=iva.base_gs,
        iva_gs=iva.iva_gs,
        cogs_gs=int(cogs),
        margin_gs=iva.gross_gs - int(cogs),
    )


@dataclass
class ProductMarginRow:
    """Per-product margin summary."""

    product_id: int
    product_name: str
    n_sold: int
    revenue_gs: int
    estimated_cost_gs: int
    margin_gs: int
    margin_pct: float  # 0-100


def product_margin_summary(
    session: Session,
    *,
    start_date: datetime,
    end_date: datetime,
) -> list[ProductMarginRow]:
    """Per-product margin in a window.

    Cost is approximated via SaleStockMove (which records per-sale
    cost at the time). For products with no stock moves, cost=0.
    """
    sales = list(
        session.execute(
            select(Sale)
            .where(
                Sale.sold_at >= start_date,
                Sale.sold_at <= end_date,
                Sale.voided_at.is_(None),
            )
        ).scalars()
    )

    # Aggregate per product
    buckets: dict[int, list[Sale]] = {}
    for s in sales:
        buckets.setdefault(s.product_id, []).append(s)

    # Aggregate per product via SaleStockMove (which carries the
    # ingredient-level cost; recipe-level aggregation is done by joining
    # on Sale.product_id via the Sale relation).
    # Approach: for each (product_id, ingredient_id), compute cost =
    # abs(qty_delta) * ingredient.purchase_price_gs, then sum per product.
    cost_rows = session.execute(
        select(
            Sale.product_id,
            func.coalesce(
                func.sum(func.abs(SaleStockMove.qty_delta) * Ingredient.purchase_price_gs),
                0,
            ),
        )
        .join(SaleStockMove, SaleStockMove.sale_id == Sale.id)
        .join(Ingredient, Ingredient.id == SaleStockMove.ingredient_id)
        .where(
            Sale.sold_at >= start_date,
            Sale.sold_at <= end_date,
            Sale.voided_at.is_(None),
            Ingredient.purchase_price_gs.is_not(None),
        )
        .group_by(Sale.product_id)
    ).all()
    cost_by_prod: dict[int, int] = {int(r[0]): int(r[1] or 0) for r in cost_rows}

    # Lookup product names for the result rows
    prod_ids = list(buckets.keys())
    prods = {
        p.id: p
        for p in session.execute(select(Product).where(Product.id.in_(prod_ids))).scalars()
    }

    out: list[ProductMarginRow] = []
    for prod_id, sales_list in buckets.items():
        prod = prods.get(prod_id)
        if prod is None:
            continue
        revenue = sum(int(round(s.qty * s.unit_price_gs)) for s in sales_list)
        cost = cost_by_prod.get(prod_id, 0)
        margin = revenue - cost
        margin_pct = (margin / revenue * 100) if revenue > 0 else 0.0
        out.append(
            ProductMarginRow(
                product_id=prod_id,
                product_name=prod.name,
                n_sold=len(sales_list),
                revenue_gs=revenue,
                estimated_cost_gs=cost,
                margin_gs=margin,
                margin_pct=margin_pct,
            )
        )
    return out


__all__ = [
    "PARAGUAY_IVA_RATE",
    "IVA_DIVISOR",
    "IVACalc",
    "MonthlyIVA",
    "LibroVentasRow",
    "DailySummary",
    "ProductMarginRow",
    "extract_iva",
    "monthly_iva_breakdown",
    "libro_ventas",
    "daily_summary",
    "product_margin_summary",
]
