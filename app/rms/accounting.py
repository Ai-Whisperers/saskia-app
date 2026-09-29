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
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.rms.models import Customer, Ingredient, Product, Sale, SaleStockMove
from app.rms.money import to_int_gs

# --- Tax config ---


# Paraguay IVA: 10% on most food items.
PARAGUAY_IVA_RATE = Decimal("0.10")
IVA_DIVISOR = Decimal("1.10")  # gross / 1.10 = net


def sales_in_window(
    session: Session,
    start: datetime,
    end: datetime,
    *,
    include_voided: bool = False,
    end_inclusive: bool = True,
) -> list[Sale]:
    """Return non-voided sales with sold_at in [start, end] (inclusive by default).

    Centralized helper for the 9 copies of this query in the report
    functions below. If we ever need to honor tz or change the void
    semantics, this is the only place to edit.

    Args:
        session: SQLAlchemy session.
        start: Window start (always inclusive).
        end: Window end (inclusive or exclusive per `end_inclusive`).
        include_voided: If False (default), voided sales are excluded.
        end_inclusive: True (default) → sold_at <= end. False → sold_at < end.

    Returns:
        list[Sale] ordered by sold_at ascending.
    """
    stmt = select(Sale).where(Sale.sold_at >= start)
    if end_inclusive:
        stmt = stmt.where(Sale.sold_at <= end)
    else:
        stmt = stmt.where(Sale.sold_at < end)
    if not include_voided:
        stmt = stmt.where(Sale.voided_at.is_(None))
    stmt = stmt.order_by(Sale.sold_at)
    return list(session.execute(stmt).scalars())


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
        gross = Decimal(gross_gs)
        base = gross / IVA_DIVISOR
        iva = gross - base
    elif tax_mode == "excluded":
        gross = Decimal(gross_gs)
        base = gross
        iva = gross * PARAGUAY_IVA_RATE
    else:
        raise ValueError(f"Unknown tax_mode: {tax_mode!r}")
    return IVACalc(
        gross_gs=int(gross),
        base_gs=int(base),
        iva_gs=int(iva),
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

    sales = sales_in_window(session, start=start_date, end=end_date)

    # Aggregate per (year, month)
    buckets: dict[tuple[int, int], list[Sale]] = {}
    for s in sales:
        # Sale.sold_at is UTC-naive; treat as UTC.
        key = (s.sold_at.year, s.sold_at.month)
        buckets.setdefault(key, []).append(s)

    out: list[MonthlyIVA] = []
    for (year, month), month_sales in sorted(buckets.items()):
        gross = sum(to_int_gs(Decimal(str(s.qty)) * Decimal(str(s.unit_price_gs))) for s in month_sales)
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
    """One row of the Libro de Ventas (chronological). Phase 1.B adds
    the fiscal invoice fields required for the SET/DNIT Form 211."""

    sale_id: int
    sold_at: datetime
    customer_name: str | None
    product_name: str
    qty: float
    unit_price_gs: int
    total_gross_gs: int
    base_gs: int
    iva_gs: int
    # Phase 1.B — fiscal invoice metadata (Phase 1.B)
    invoice_type: str = ""
    invoice_number: int | None = None
    invoice_customer_ruc: str | None = None
    invoice_customer_name: str | None = None


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
    rows = sales_in_window(session, start=start_date, end=end_date)[:limit]

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
        # AGENTS.md money rule: never use float precision for money.
        gross = to_int_gs(Decimal(str(r.qty)) * Decimal(str(r.unit_price_gs)))
        iva = extract_iva(gross, tax_mode=tax_mode)
        # Phase 1.B — prefer the snapshotted IVA fields when present (Factura)
        # over the computed-from-gross extraction (Boleta Resimple path).
        snap_base = getattr(r, "iva_base_gs", None) or 0
        snap_iva = getattr(r, "iva_amount_gs", None) or 0
        if snap_base > 0 or snap_iva > 0:
            base_out = snap_base
            iva_out = snap_iva
        else:
            base_out = iva.base_gs
            iva_out = iva.iva_gs

        out.append(
            LibroVentasRow(
                sale_id=r.id,
                sold_at=r.sold_at,
                customer_name=custs.get(r.customer_id) if r.customer_id else None,
                product_name=prods.get(r.product_id, f"#{r.product_id}"),
                qty=r.qty,
                unit_price_gs=r.unit_price_gs,
                total_gross_gs=iva.gross_gs,
                base_gs=base_out,
                iva_gs=iva_out,
                invoice_type=getattr(r, "invoice_type", "") or "",
                invoice_number=getattr(r, "invoice_number", None),
                invoice_customer_ruc=getattr(r, "invoice_customer_ruc", None),
                invoice_customer_name=getattr(r, "invoice_customer_name", None),
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
    # Renamed from `expenses_gs` to make the placeholder explicit.
    # Until the Expense model ships, this is always 0 and operators
    # reading the dashboard should not mistake it for a real number.
    expenses_placeholder_gs: int = 0  # TODO(phase-3c): wire Expense model


def daily_summary(
    session: Session,
    day: datetime,
    *,
    tax_mode: str = "included",
) -> DailySummary:
    """Compute one day's summary."""
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    sales = sales_in_window(session, start=start, end=end, end_inclusive=False)

    revenue_gross = sum(to_int_gs(Decimal(str(s.qty)) * Decimal(str(s.unit_price_gs))) for s in sales)
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
        expenses_placeholder_gs=0,  # TODO: wire Expense model when added
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
    sales = sales_in_window(session, start=start_date, end=end_date)

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
        revenue = sum(to_int_gs(Decimal(str(s.qty)) * Decimal(str(s.unit_price_gs))) for s in sales_list)
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


def cross_period_comparison(
    session: Session,
    period1_start: datetime,
    period1_end: datetime,
    period2_start: datetime,
    period2_end: datetime,
) -> dict:
    """Compare sales between two periods (this month vs last month)."""
    def _period_summary(s_start, s_end):
        sales = sales_in_window(
            session, start=s_start, end=s_end, end_inclusive=False
        )
        revenue = sum(to_int_gs(Decimal(str(s.qty)) * Decimal(str(s.unit_price_gs))) for s in sales)
        iva = extract_iva(revenue)
        cogs = session.execute(
            select(func.coalesce(func.sum(func.abs(SaleStockMove.qty_delta) * Ingredient.purchase_price_gs), 0))
            .select_from(SaleStockMove)
            .join(Sale, Sale.id == SaleStockMove.sale_id)
            .join(Ingredient, Ingredient.id == SaleStockMove.ingredient_id)
            .where(Sale.sold_at >= s_start, Sale.sold_at < s_end, Sale.voided_at.is_(None))
        ).scalar() or 0
        return {
            "n_sales": len(sales),
            "revenue_gs": iva.gross_gs,
            "iva_gs": iva.iva_gs,
            "cogs_gs": int(cogs),
            "margin_gs": iva.gross_gs - int(cogs),
        }

    p1 = _period_summary(period1_start, period1_end)
    p2 = _period_summary(period2_start, period2_end)

    def _diff(current, prior):
        if prior == 0:
            return None
        return ((current - prior) / prior) * 100

    return {
        "period1": {**p1, "start": period1_start, "end": period1_end},
        "period2": {**p2, "start": period2_start, "end": period2_end},
        "revenue_change_pct": _diff(p1["revenue_gs"], p2["revenue_gs"]),
        "sales_count_change_pct": _diff(p1["n_sales"], p2["n_sales"]),
        "margin_change_pct": _diff(p1["margin_gs"], p2["margin_gs"]),
    }


def top_products_report(
    session: Session,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    limit: int = 20,
) -> list[dict]:
    """Top products by revenue in a date range."""
    if end_date is None:
        end_date = datetime.now(timezone.utc)
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    sales = sales_in_window(session, start=start_date, end=end_date)

    by_product: dict[int, dict] = {}
    for s in sales:
        d = by_product.setdefault(s.product_id, {"product_id": s.product_id, "n_sold": 0, "revenue_gs": 0})
        d["n_sold"] += 1
        d["revenue_gs"] += to_int_gs(Decimal(str(s.qty)) * Decimal(str(s.unit_price_gs)))

    prod_ids = list(by_product.keys())
    prods = {p.id: p for p in session.execute(select(Product).where(Product.id.in_(prod_ids))).scalars()}
    rows = []
    for pid, d in by_product.items():
        prod = prods.get(pid)
        rows.append({
            "product_id": pid,
            "product_name": prod.name if prod else f"#{pid}",
            "n_sold": d["n_sold"],
            "revenue_gs": d["revenue_gs"],
        })
    rows.sort(key=lambda r: r["revenue_gs"], reverse=True)
    return rows[:limit]


def average_order_value(
    session: Session,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> float:
    """Average order value (revenue per sale)."""
    if end_date is None:
        end_date = datetime.now(timezone.utc)
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    sales = sales_in_window(session, start=start_date, end=end_date)
    if not sales:
        return 0.0
    total = sum(to_int_gs(Decimal(str(s.qty)) * Decimal(str(s.unit_price_gs))) for s in sales)
    return total / len(sales)


def sales_by_payment_method(
    session: Session,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> dict[str, dict]:
    """Breakdown of sales by payment method."""
    if end_date is None:
        end_date = datetime.now(timezone.utc)
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    rows = session.execute(
        select(
            Sale.payment_method,
            func.count(Sale.id).label("n_sales"),
            func.sum(Sale.qty * Sale.unit_price_gs).label("total_gs"),
        )
        .where(
            Sale.sold_at >= start_date,
            Sale.sold_at <= end_date,
            Sale.voided_at.is_(None),
        )
        .group_by(Sale.payment_method)
    ).all()

    result = {}
    for payment_method, n_sales, total_gs in rows:
        key = payment_method or "SIN METODO"
        result[key] = {
            "n_sales": n_sales,
            "total_gs": int(total_gs or 0),
        }
    return result


__all__ = [
    "IVA_DIVISOR",
    "PARAGUAY_IVA_RATE",
    "DailySummary",
    "IVACalc",
    "LibroVentasRow",
    "MonthlyIVA",
    "ProductMarginRow",
    "average_order_value",
    "cross_period_comparison",
    "daily_summary",
    "extract_iva",
    "libro_ventas",
    "monthly_iva_breakdown",
    "product_margin_summary",
    "sales_by_payment_method",
    "top_products_report",
]
