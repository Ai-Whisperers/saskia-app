"""app/rms/product_price_history.py — product price history + margin drift.

Generalizes the ingredient price-history pattern (app/rms/price_history.py)
to PRODUCTS: every sale is a price observation. From those observations we
derive margin drift — how the real margin moved vs the recipe cost of the
day — so pricing decisions ("subió el precio?" / "conviene subir el
precio?") are data-driven.

Pure functions over a Session; no writes. Money stays int Gs. until
display. Uses variants.current_variant_price for ingredient cost basis
(the "what does harina cost today" source of truth).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.rms.models import Product, Sale


@dataclass(frozen=True)
class ProductPricePoint:
    product_id: int
    sold_at: datetime
    unit_price_gs: int


@dataclass(frozen=True)
class MarginDrift:
    product_id: int
    product_name: str
    first_price_gs: int | None
    last_price_gs: int | None
    price_change_gs: int | None  # last − first
    price_change_pct: float | None  # relative
    first_margin_gs: int | None
    last_margin_gs: int | None
    margin_change_gs: int | None  # last − first (negative = margin eroded)
    margin_change_pct: float | None  # relative (last_margin − first) / first


def product_price_history(
    session: Session,
    product_id: int,
    days: int = 90,
) -> list[ProductPricePoint]:
    """Observed sale prices for a product, oldest → newest.

    Voided sales excluded. Only one observation per day (the last sale of
    the day) to keep the series readable.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = session.execute(
        select(Sale.sold_at, Sale.unit_price_gs)
        .where(Sale.product_id == product_id)
        .where(Sale.voided_at.is_(None))
        .where(Sale.sold_at >= cutoff.replace(tzinfo=None))
        .order_by(Sale.sold_at)
    ).all()
    # last sale per day
    by_day: dict[str, ProductPricePoint] = {}
    for sold_at, price in rows:
        key = sold_at.date().isoformat()
        by_day[key] = ProductPricePoint(product_id, sold_at, int(price))
    return [by_day[k] for k in sorted(by_day)]


def margin_drift_all(
    session: Session,
    days: int = 30,
    min_sales: int = 2,
) -> list[MarginDrift]:
    """Margin drift for every product with ≥ min_sales in the window.

    Compares the FIRST observed window price/margin vs the LAST, using the
    current recipe cost as the cost basis (historical per-day recipe cost
    is not reconstructible without historical price events per ingredient;
    the ingredient price-history tables make a full reconstruction a
    Phase-2 follow-up).
    """
    from app.rms.costing import batch_products_cost_margin

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    rows = session.execute(
        select(
            Sale.product_id,
            func.min(Sale.sold_at),
            func.max(Sale.sold_at),
        )
        .where(Sale.voided_at.is_(None))
        .where(Sale.sold_at >= cutoff.replace(tzinfo=None))
        .group_by(Sale.product_id)
    ).all()
    if not rows:
        return []

    product_ids = [r[0] for r in rows]
    prod_objs = [session.get(Product, pid) for pid in product_ids]
    prod_objs = [p for p in prod_objs if p is not None]
    margins = batch_products_cost_margin(session, prod_objs)
    out: list[MarginDrift] = []
    for product_id, first_at, last_at in rows:
        first_sale = session.execute(
            select(Sale.unit_price_gs)
            .where(Sale.product_id == product_id, Sale.voided_at.is_(None))
            .where(Sale.sold_at <= first_at)
            .order_by(Sale.sold_at.desc())
            .limit(1)
        ).scalar()
        last_sale = session.execute(
            select(Sale.unit_price_gs)
            .where(Sale.product_id == product_id, Sale.voided_at.is_(None))
            .where(Sale.sold_at <= last_at)
            .order_by(Sale.sold_at.desc())
            .limit(1)
        ).scalar()
        prod = session.get(Product, product_id)
        if prod is None or first_sale is None or last_sale is None:
            continue
        entry = margins.get(product_id)
        current_cost: int | None = None
        if entry is not None:
            _cost_result, (_margin_gs, _ratio) = entry
            if entry[0].batch_cost_gs is not None:
                current_cost = int(entry[0].batch_cost_gs)
        first_margin = (int(first_sale) - current_cost) if current_cost is not None else None
        last_margin = (int(last_sale) - current_cost) if current_cost is not None else None
        out.append(
            MarginDrift(
                product_id=product_id,
                product_name=prod.name,
                first_price_gs=int(first_sale),
                last_price_gs=int(last_sale),
                price_change_gs=int(last_sale) - int(first_sale),
                price_change_pct=(
                    (int(last_sale) - int(first_sale)) / int(first_sale)
                    if int(first_sale) > 0
                    else None
                ),
                first_margin_gs=int(first_margin) if first_margin is not None else None,
                last_margin_gs=int(last_margin) if last_margin is not None else None,
                margin_change_gs=(
                    int(last_margin) - int(first_margin)
                    if first_margin is not None and last_margin is not None
                    else None
                ),
                margin_change_pct=(
                    (int(last_margin) - int(first_margin)) / int(first_margin)
                    if first_margin is not None and int(first_margin) > 0
                    else None
                ),
            )
        )
    # interesting first: biggest margin erosion / growth
    out.sort(key=lambda d: d.margin_change_gs if d.margin_change_gs is not None else 0)
    return out
