"""app/rms/cierre.py — Phase 1.E Monthly P&L close (cierre mensual).

Computes the per-family + per-product P&L for a given month, broken down into:

  - ventas_gs        — total sales (sum of unit_price × qty, minus discounts)
  - iva_amount_gs    — total IVA from Factura sales (zero for Boleta Resimple)
  - costo_materiales — prime cost materials portion (recipe batch cost × sold qty)
  - mano_de_obra     — prime cost labor portion (informal; many rows will be 0)
  - overhead         — prime cost overhead portion
  - prime_cost_gs    — total of the three above
  - margen_neto_gs   — ventas_gs - prime_cost_gs
  - margen_pct       — margen_neto / ventas × 100

Returns a structured dict that the template renders into the monthly
close view. Per docs/plans/2026-09-22-ingredient-domain.md §D.

Note: this is operational margin, not accounting P&L. Tax (IVA débito /
crédito / IRP) is computed separately in /reportes/iva.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import Product, Sale


@dataclass
class MonthlyCloseRow:
    """One row of the monthly close — per product or aggregated per family."""

    label: str  # product name or family
    sku: str | None = None
    category: str | None = None  # family for product, family for aggregate
    ventas_gs: int = 0
    iva_ventas_gs: int = 0
    costo_materiales_gs: int = 0
    mano_de_obra_gs: int = 0
    overhead_gs: int = 0
    prime_cost_gs: int = 0
    margen_neto_gs: int = 0
    margen_pct: float = 0.0
    qty_sold: float = 0.0


@dataclass
class MonthlyClose:
    period_label: str  # "Septiembre 2026"
    start: date
    end: date
    rows: list[MonthlyCloseRow]
    # only real products (excludes family rollups) — use for totals math
    product_rows: list[MonthlyCloseRow] = field(default_factory=list)
    # Aggregate totals (sum of all rows)
    total_ventas_gs: int = 0
    total_iva_ventas_gs: int = 0
    total_prime_cost_gs: int = 0
    total_margen_neto_gs: int = 0
    total_margen_pct: float = 0.0
    # Sales count
    total_sales: int = 0
    # Top performer (highest margen)
    top_product: str | None = None


def _month_range(year: int, month: int) -> tuple[date, date]:
    """Return [first_day, last_day] for the given (year, month)."""
    first = date(year, month, 1)
    if month == 12:
        last = date(year, 12, 31)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    return first, last


def compute_monthly_close(session: Session, year: int, month: int) -> MonthlyClose:
    """Compute the full monthly P&L close for (year, month).

    Asunción timezone for period boundaries per AGENTS.md rule §4.
    """

    start_dt, end_dt = _get_month_range_dt(year, month)
    sales = _fetch_sales_in_period(session, start_dt, end_dt)
    by_product = _aggregate_sales_by_product(sales)
    rows = _build_product_rows(session, by_product)
    family_rows = _aggregate_by_family(rows)
    return _build_monthly_close_result(rows, family_rows, year, month)


def _get_month_range_dt(year: int, month: int) -> tuple:
    """Get the datetime range for a month in Asunción timezone.

    Extracted from compute_monthly_close to reduce complexity.
    """
    from app.rms.config import ASUNCION_TZ

    start, end = _month_range(year, month)
    start_dt = datetime.combine(start, datetime.min.time()).replace(tzinfo=ASUNCION_TZ)
    end_dt = datetime.combine(end, datetime.max.time()).replace(tzinfo=ASUNCION_TZ)
    return start_dt, end_dt


def _fetch_sales_in_period(session, start_dt, end_dt) -> list:
    """Fetch all non-voided sales in the period.

    Extracted from compute_monthly_close to reduce complexity.
    """
    return list(
        session.execute(
            select(Sale).where(
                Sale.sold_at >= start_dt,
                Sale.sold_at <= end_dt,
                Sale.voided_at.is_(None),
            )
        ).scalars().all()
    )


def _aggregate_sales_by_product(sales: list) -> dict[int, dict]:
    """Aggregate sales by product, computing gross and IVA totals.

    Extracted from compute_monthly_close to reduce complexity.
    """
    by_product: dict[int, dict] = {}
    for sale in sales:
        pid = sale.product_id
        if pid not in by_product:
            by_product[pid] = _new_product_aggregation()
        agg = by_product[pid]
        gross = round(sale.qty * sale.unit_price_gs) - (sale.discount_gs or 0)
        agg["qty"] += sale.qty
        agg["ventas_gs"] += gross
        agg["iva_ventas_gs"] += sale.iva_amount_gs or 0
    return by_product


def _new_product_aggregation() -> dict:
    """Create a new product aggregation dict.

    Extracted from _aggregate_sales_by_product to reduce complexity.
    """
    return {
        "qty": 0.0,
        "ventas_gs": 0,
        "iva_ventas_gs": 0,
        "costo_materiales_gs": 0,
        "mano_de_obra_gs": 0,
        "overhead_gs": 0,
    }


def _build_product_rows(session, by_product: dict) -> list[MonthlyCloseRow]:
    """Build MonthlyCloseRow for each product.

    Extracted from compute_monthly_close to reduce complexity.
    """
    from app.rms.prime_cost import compute_prime_cost

    rows: list[MonthlyCloseRow] = []
    for pid, agg in by_product.items():
        p = session.get(Product, pid)
        if p is None:
            continue
        pc = compute_prime_cost(session, pid)
        row = _build_single_product_row(p, agg, pc)
        rows.append(row)
    return rows


def _build_single_product_row(p, agg: dict, pc) -> MonthlyCloseRow:
    """Build a single MonthlyCloseRow for a product.

    Extracted from _build_product_rows to reduce complexity.
    """
    mat_total, lab_total, ovh_total, prime_total = _compute_product_costs(agg["qty"], pc)
    margen = agg["ventas_gs"] - prime_total
    margen_pct = (
        round(margen / agg["ventas_gs"] * 100, 1) if agg["ventas_gs"] > 0 else 0.0
    )
    return MonthlyCloseRow(
        label=p.name,
        sku=p.sku,
        category=p.recipe.family if p.recipe else None,
        ventas_gs=agg["ventas_gs"],
        iva_ventas_gs=agg["iva_ventas_gs"],
        costo_materiales_gs=mat_total,
        mano_de_obra_gs=lab_total,
        overhead_gs=ovh_total,
        prime_cost_gs=prime_total,
        margen_neto_gs=margen,
        margen_pct=margen_pct,
        qty_sold=agg["qty"],
    )


def _compute_product_costs(qty: float, pc) -> tuple:
    """Compute materials, labor, overhead, and prime cost totals.

    Extracted from _build_single_product_row to reduce complexity.
    """
    if pc.materials_cost_gs is None:
        return 0, 0, 0, 0
    mat = pc.materials_cost_gs
    mat_total = round(mat * qty)
    if pc.prime_cost_gs is not None:
        lab_total = round((pc.labor_cost_gs or 0) * qty)
        ovh_total = round((pc.overhead_cost_gs or 0) * qty)
        prime_total = mat_total + lab_total + ovh_total
    else:
        prime_total = mat_total
        lab_total = 0
        ovh_total = 0
    return mat_total, lab_total, ovh_total, prime_total


def _aggregate_by_family(rows: list[MonthlyCloseRow]) -> list[MonthlyCloseRow]:
    """Aggregate MonthlyCloseRows by family/category.

    Extracted from compute_monthly_close to reduce complexity.
    """
    by_family: dict[str, dict] = {}
    for r in rows:
        family = r.category or "sin familia"
        if family not in by_family:
            by_family[family] = _new_family_aggregation()
        _accumulate_family_aggregation(by_family[family], r)

    family_rows: list[MonthlyCloseRow] = []
    for family, agg in sorted(by_family.items()):
        family_rows.append(_build_family_row(family, agg))
    return family_rows


def _new_family_aggregation() -> dict:
    """Create a new family aggregation dict.

    Extracted from _aggregate_by_family to reduce complexity.
    """
    return {
        "ventas_gs": 0,
        "iva_ventas_gs": 0,
        "costo_materiales_gs": 0,
        "mano_de_obra_gs": 0,
        "overhead_gs": 0,
        "prime_cost_gs": 0,
        "margen_neto_gs": 0,
        "qty_sold": 0.0,
    }


def _accumulate_family_aggregation(agg: dict, r: MonthlyCloseRow) -> None:
    """Accumulate a row into a family aggregation.

    Extracted from _aggregate_by_family to reduce complexity.
    """
    agg["ventas_gs"] += r.ventas_gs
    agg["iva_ventas_gs"] += r.iva_ventas_gs
    agg["costo_materiales_gs"] += r.costo_materiales_gs
    agg["mano_de_obra_gs"] += r.mano_de_obra_gs
    agg["overhead_gs"] += r.overhead_gs
    agg["prime_cost_gs"] += r.prime_cost_gs
    agg["margen_neto_gs"] += r.margen_neto_gs
    agg["qty_sold"] += r.qty_sold


def _build_family_row(family: str, agg: dict) -> MonthlyCloseRow:
    """Build a MonthlyCloseRow for a family.

    Extracted from _aggregate_by_family to reduce complexity.
    """
    margen_pct = (
        round(agg["margen_neto_gs"] / agg["ventas_gs"] * 100, 1)
        if agg["ventas_gs"] > 0
        else 0.0
    )
    return MonthlyCloseRow(
        label=family,
        category=family,
        ventas_gs=agg["ventas_gs"],
        iva_ventas_gs=agg["iva_ventas_gs"],
        costo_materiales_gs=agg["costo_materiales_gs"],
        mano_de_obra_gs=agg["mano_de_obra_gs"],
        overhead_gs=agg["overhead_gs"],
        prime_cost_gs=agg["prime_cost_gs"],
        margen_neto_gs=agg["margen_neto_gs"],
        margen_pct=margen_pct,
        qty_sold=agg["qty_sold"],
    )


def _build_monthly_close_result(rows, family_rows, year: int, month: int) -> MonthlyClose:
    """Build the final MonthlyClose result.

    Extracted from compute_monthly_close to reduce complexity.
    """
    return MonthlyClose(year=year, month=month, rows=rows, family_rows=family_rows)


