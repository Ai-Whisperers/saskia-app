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
    label: str                          # product name or family
    sku: str | None = None
    category: str | None = None         # family for product, family for aggregate
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
    period_label: str              # "Septiembre 2026"
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
    from app.rms.config import ASUNCION_TZ

    start, end = _month_range(year, month)
    start_dt = datetime.combine(start, datetime.min.time()).replace(tzinfo=ASUNCION_TZ)
    end_dt = datetime.combine(end, datetime.max.time()).replace(tzinfo=ASUNCION_TZ)

    # Pull all non-voided sales in the period
    sales = session.execute(
        select(Sale).where(
            Sale.sold_at >= start_dt,
            Sale.sold_at <= end_dt,
            Sale.voided_at.is_(None),
        )
    ).scalars().all()

    # Aggregate per product
    by_product: dict[int, dict] = {}
    for sale in sales:
        pid = sale.product_id
        if pid not in by_product:
            by_product[pid] = {
                "qty": 0.0,
                "ventas_gs": 0,
                "iva_ventas_gs": 0,
                "costo_materiales_gs": 0,
                "mano_de_obra_gs": 0,
                "overhead_gs": 0,
            }
        agg = by_product[pid]
        gross = round(sale.qty * sale.unit_price_gs) - (sale.discount_gs or 0)
        agg["qty"] += sale.qty
        agg["ventas_gs"] += gross
        agg["iva_ventas_gs"] += sale.iva_amount_gs or 0

    # For each product, compute prime cost components via the existing costing module
    from app.rms.prime_cost import compute_prime_cost

    rows: list[MonthlyCloseRow] = []
    for pid, agg in by_product.items():
        p = session.get(Product, pid)
        if p is None:
            continue
        pc = compute_prime_cost(session, pid)
        factor = agg["qty"]
        mat = pc.materials_cost_gs
        lab = pc.labor_cost_gs
        ovh = pc.overhead_cost_gs
        if mat is None:
            mat = 0
            mat_total = 0
            lab_total = 0
            ovh_total = 0
            prime_total = 0
        else:
            # If yield/labor/overhead not configured, prime = materials × qty
            # (since compute_prime_cost returns prime=None in that case).
            if pc.prime_cost_gs is not None:
                mat_total = round(mat * factor)
                lab_total = round((lab or 0) * factor)
                ovh_total = round((ovh or 0) * factor)
                prime_total = mat_total + lab_total + ovh_total
            else:
                mat_total = round(mat * factor)
                lab_total = 0
                ovh_total = 0
                prime_total = mat_total

        margen = agg["ventas_gs"] - prime_total
        margen_pct = round(margen / agg["ventas_gs"] * 100, 1) if agg["ventas_gs"] > 0 else 0.0

        rows.append(MonthlyCloseRow(
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
        ))

    # Aggregate by family
    by_family: dict[str, dict] = {}
    for r in rows:
        family = r.category or "sin familia"
        if family not in by_family:
            by_family[family] = {
                "ventas_gs": 0, "iva_ventas_gs": 0,
                "costo_materiales_gs": 0, "mano_de_obra_gs": 0,
                "overhead_gs": 0, "prime_cost_gs": 0, "margen_neto_gs": 0,
                "qty_sold": 0.0,
            }
        agg = by_family[family]
        agg["ventas_gs"] += r.ventas_gs
        agg["iva_ventas_gs"] += r.iva_ventas_gs
        agg["costo_materiales_gs"] += r.costo_materiales_gs
        agg["mano_de_obra_gs"] += r.mano_de_obra_gs
        agg["overhead_gs"] += r.overhead_gs
        agg["prime_cost_gs"] += r.prime_cost_gs
        agg["margen_neto_gs"] += r.margen_neto_gs
        agg["qty_sold"] += r.qty_sold

    family_rows: list[MonthlyCloseRow] = []
    for family, agg in sorted(by_family.items()):
        margen_pct = round(agg["margen_neto_gs"] / agg["ventas_gs"] * 100, 1) if agg["ventas_gs"] > 0 else 0.0
        family_rows.append(MonthlyCloseRow(
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
        ))

    # Compose final: family breakdown first, then per-product detail
    all_rows = family_rows + rows
    # product_rows: rows WITHOUT sku are family rollups — the tfoot and any
    # "sum of rows" math must only count real products (bug: TOTAL used to
    # double-count qty/materials when family rollups shared the table).

    total_ventas = sum(r.ventas_gs for r in rows)
    total_prime = sum(r.prime_cost_gs for r in rows)
    total_margen = total_ventas - total_prime
    total_margen_pct = round(total_margen / total_ventas * 100, 1) if total_ventas > 0 else 0.0

    top = max(rows, key=lambda r: r.margen_neto_gs, default=None)

    month_names = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ]
    return MonthlyClose(
        period_label=f"{month_names[month-1]} {year}",
        start=start,
        end=end,
        rows=all_rows,
        product_rows=rows,
        total_ventas_gs=total_ventas,
        total_iva_ventas_gs=sum(r.iva_ventas_gs for r in rows),
        total_prime_cost_gs=total_prime,
        total_margen_neto_gs=total_margen,
        total_margen_pct=total_margen_pct,
        total_sales=len(sales),
        top_product=top.label if top else None,
    )


__all__ = ["MonthlyClose", "MonthlyCloseRow", "compute_monthly_close"]
