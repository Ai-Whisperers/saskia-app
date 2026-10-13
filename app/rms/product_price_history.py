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


# ─── margin_drift_all helpers (S3 batch-5 split, CC 22 → 6) ────────────────
#
# Orchestrator pattern: thin coordinator (`margin_drift_all`, CC 6) +
# single-purpose _helpers. No behavior change — every branch from the
# pre-split implementation is preserved character-for-character.
# Public signature `margin_drift_all(session, days, min_sales)` is
# unchanged so callers (app/routers/insights_stock.py) and the
# 7-scenario test matrix in tests/test_d_grade_helpers_batch5.py
# pass without modification.
#
# NOTE: `min_sales` is declared but NOT honored in the body (would
# need `GROUP BY ... HAVING count(*) >= min_sales`). The 7-scenario
# test `multi_product_window` documents this as the existing
# behavior; wiring it through is queued as a separate change.


def _sale_window_bounds(session: Session, days: int) -> list[tuple[int, datetime, datetime]]:
    """Per-product (product_id, first_at, last_at) for the sale window.

    Excludes voided sales. Returns [] when no non-voided sales fall
    inside the `days`-day window — caller short-circuits.
    """
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
    return [(r[0], r[1], r[2]) for r in rows]


def _last_sale_price_at_or_before(session: Session, product_id: int, at: datetime) -> int | None:
    """Last non-voided sale price for `product_id` at-or-before `at`.

    Returns None when no qualifying sale exists (the caller skips the
    product rather than building a partial row).
    """
    return session.execute(
        select(Sale.unit_price_gs)
        .where(Sale.product_id == product_id, Sale.voided_at.is_(None))
        .where(Sale.sold_at <= at)
        .order_by(Sale.sold_at.desc())
        .limit(1)
    ).scalar()


def _current_cost_for(margins: dict, product_id: int) -> int | None:
    """Extract the int Gs. recipe cost from a margin entry.

    Returns None when:
      - the product has no margin entry (e.g. no recipe), OR
      - the entry's `batch_cost_gs` is None (the cost could not be
        computed; the margin fields will fall through to None).
    """
    entry = margins.get(product_id)
    if entry is None:
        return None
    if entry[0].batch_cost_gs is None:
        return None
    return int(entry[0].batch_cost_gs)


def _safe_pct_change(new: int, old: int) -> float | None:
    """`(new - old) / old` for the price/margin-change fields.

    Returns None when `old <= 0` (matches the prior guard
    `if int(first_sale) > 0` / `if int(first_margin) > 0`).
    """
    if old <= 0:
        return None
    return (new - old) / old


def _build_margin_drift(
    product_id: int,
    product_name: str,
    first_sale: int,
    last_sale: int,
    current_cost: int | None,
) -> MarginDrift:
    """Build a `MarginDrift` row from the per-product numbers.

    Pure function over ints — no DB, no Session. Every None branch
    matches the pre-split behavior (P-26 / no-recipe edge).
    """
    price_change_gs = last_sale - first_sale
    price_change_pct = _safe_pct_change(last_sale, first_sale)
    if current_cost is None:
        first_margin_gs: int | None = None
        last_margin_gs: int | None = None
        margin_change_gs: int | None = None
        margin_change_pct: float | None = None
    else:
        first_margin_gs = first_sale - current_cost
        last_margin_gs = last_sale - current_cost
        margin_change_gs = last_margin_gs - first_margin_gs
        margin_change_pct = _safe_pct_change(last_margin_gs, first_margin_gs)
    return MarginDrift(
        product_id=product_id,
        product_name=product_name,
        first_price_gs=first_sale,
        last_price_gs=last_sale,
        price_change_gs=price_change_gs,
        price_change_pct=price_change_pct,
        first_margin_gs=first_margin_gs,
        last_margin_gs=last_margin_gs,
        margin_change_gs=margin_change_gs,
        margin_change_pct=margin_change_pct,
    )


def _resolve_drift_row(
    session: Session,
    margins: dict,
    product_id: int,
    first_at: datetime,
    last_at: datetime,
) -> MarginDrift | None:
    """Build one `MarginDrift` row, or return None when incomplete.

    Returns None when any of:
      - the Product row is missing,
      - the first-window sale price is missing,
      - the last-window sale price is missing.

    On a non-None return, every field on the dataclass is populated
    (the no-recipe branch is handled inside `_build_margin_drift`).
    """
    prod = session.get(Product, product_id)
    if prod is None:
        return None
    first_sale = _last_sale_price_at_or_before(session, product_id, first_at)
    last_sale = _last_sale_price_at_or_before(session, product_id, last_at)
    if first_sale is None or last_sale is None:
        return None
    return _build_margin_drift(
        product_id=product_id,
        product_name=prod.name,
        first_sale=int(first_sale),
        last_sale=int(last_sale),
        current_cost=_current_cost_for(margins, product_id),
    )


def _existing_products(session: Session, product_ids: list[int]) -> list[Product]:
    """`Product` rows for `product_ids`, skipping any that no longer exist.

    Preserves the order of `product_ids` so the cost-margin dict is
    stable for the orchestrator's downstream lookup.
    """
    return [p for p in (session.get(Product, pid) for pid in product_ids) if p is not None]


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

    Note: `min_sales` is currently declared but NOT honored in the body —
    see test_d_grade_helpers_batch5.py::multi_product_window for the
    locked-as-is behavior. Wiring it through `GROUP BY ... HAVING
    count(*) >= min_sales` is a separate queued change.
    """
    from app.rms.profitability.cost import batch_products_cost_margin

    bounds = _sale_window_bounds(session, days)
    if not bounds:
        return []

    product_ids = [pid for pid, _first, _last in bounds]
    margins = batch_products_cost_margin(session, _existing_products(session, product_ids))

    out: list[MarginDrift] = []
    for product_id, first_at, last_at in bounds:
        row = _resolve_drift_row(session, margins, product_id, first_at, last_at)
        if row is not None:
            out.append(row)
    # interesting first: biggest margin erosion / growth
    out.sort(key=lambda d: d.margin_change_gs if d.margin_change_gs is not None else 0)
    return out
