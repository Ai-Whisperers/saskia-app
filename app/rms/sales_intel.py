"""app/rms/sales_intel.py — time patterns, product affinity, churn/rising.

Answers:
- When are my peak hours / days / months?
- What products are bought together (market basket)?
- Which products are declining (churn) or trending up?
"""

from __future__ import annotations

import itertools
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Final

from sqlalchemy import Integer, func, select
from sqlalchemy.orm import Session

from app.rms.models import Product, Sale

# ---------------------------------------------------------------------------
# Time-pattern functions
# ---------------------------------------------------------------------------


def sales_by_hour(session: Session) -> dict[int, int]:
    """Count of sales per hour 0-23."""
    rows = session.execute(select(Sale.sold_at).where(Sale.voided_at.is_(None))).all()
    counts: Counter[int] = Counter()
    for (sold_at,) in rows:
        if sold_at is None:
            continue
        counts[sold_at.hour] += 1
    return {h: counts.get(h, 0) for h in range(24)}


def sales_by_day_of_week(session: Session) -> dict[int, int]:
    """Count of sales per weekday (0=Mon, 6=Sun)."""
    rows = session.execute(select(Sale.sold_at).where(Sale.voided_at.is_(None))).all()
    counts: Counter[int] = Counter()
    for (sold_at,) in rows:
        if sold_at is None:
            continue
        counts[sold_at.weekday()] += 1
    return {d: counts.get(d, 0) for d in range(7)}


def sales_heatmap(session: Session, since_days: int = 90) -> list[list[int]]:
    """Day-of-week × hour grid of sale counts for the last `since_days`.

    Output shape: `grid[weekday][hour] = count`, weekday 0..6 (Mon..Sun),
    hour 0..23. Local-time bucketing so operators see Asunción hours.

    BACKLOG #36 (2026-10-02): original `/reportes/ventas-hora` was a
    bar chart by hour only. This adds the day-of-week dimension so
    operators can spot "Friday 18-21h is the busy slot" patterns.

    No-data case: returns a 7×24 grid of zeros (so the template can
    render an empty heatmap without special-casing).
    """
    from app.rms.config import ASUNCION_TZ

    cutoff = datetime.now(ASUNCION_TZ) - timedelta(days=since_days)
    # `cutoff` is tz-aware (ASUNCION_TZ); Sale.sold_at is UTC tz-aware.
    # Comparing tz-aware to tz-naive raises; convert if needed.
    rows = session.execute(
        select(Sale.sold_at).where(
            Sale.voided_at.is_(None),
            Sale.sold_at >= cutoff,
        )
    ).all()

    grid: list[list[int]] = [[0 for _ in range(24)] for _ in range(7)]
    for (sold_at,) in rows:
        if sold_at is None:
            continue
        local_dt = sold_at.astimezone(ASUNCION_TZ) if sold_at.tzinfo else sold_at
        grid[local_dt.weekday()][local_dt.hour] += 1
    return grid


# Internal alias so tests can patch the in-progress helper without
# conflicting with any future public name.
_sales_heatmap = sales_heatmap


def sales_by_month(session: Session) -> dict[str, int]:
    """Count of sales per YYYY-MM."""
    rows = session.execute(select(Sale.sold_at).where(Sale.voided_at.is_(None))).all()
    counts: Counter[str] = Counter()
    for (sold_at,) in rows:
        if sold_at is None:
            continue
        key = sold_at.strftime("%Y-%m")
        counts[key] += 1
    return dict(sorted(counts.items()))


def peak_hour(session: Session) -> int:
    """Hour with highest sales count. -1 if no sales."""
    by_hour = sales_by_hour(session)
    if not by_hour or max(by_hour.values()) == 0:
        return -1
    return max(by_hour.items(), key=lambda kv: kv[1])[0]


def peak_day_of_week(session: Session) -> int:
    """Weekday with highest sales count. -1 if no sales."""
    by_dow = sales_by_day_of_week(session)
    if not by_dow or max(by_dow.values()) == 0:
        return -1
    return max(by_dow.items(), key=lambda kv: kv[1])[0]


# ---------------------------------------------------------------------------
# Product affinity (market basket)
# ---------------------------------------------------------------------------

_BASKET_WINDOW_HOURS: Final[int] = 2  # sales within 2 hours = same basket


def product_affinity(session: Session, min_cooccurrence: int = 2) -> dict[tuple[int, int], int]:
    """Co-occurrence count of (product_a, product_b) pairs in same basket.

    A "basket" is sales of multiple products within _BASKET_WINDOW_HOURS
    (or sales from the same customer if customer_id is set).

    Returns dict with (smaller_id, larger_id) → count, only pairs with
    count >= min_cooccurrence.
    """
    sales = _fetch_all_sales(session)
    baskets = _group_sales_into_baskets(sales)
    pair_counts = _count_pair_cooccurrences(baskets)
    return _filter_by_min_cooccurrence(pair_counts, min_cooccurrence)


def _fetch_all_sales(session) -> list:
    """Fetch all non-voided sales ordered by time.

    Extracted from product_affinity to reduce complexity.
    """
    return list(
        session.execute(
            select(Sale.sold_at, Sale.product_id, Sale.customer_id)
            .where(Sale.voided_at.is_(None))
            .order_by(Sale.sold_at)
        ).all()
    )


def _group_sales_into_baskets(sales: list) -> list[set[int]]:
    """Group sales into baskets based on time window.

    Extracted from product_affinity to reduce complexity.
    """
    baskets: list[set[int]] = []
    current_basket: list[tuple[datetime, int]] = []
    for sold_at, product_id, _customer_id in sales:
        if _should_start_new_basket(current_basket, sold_at):
            baskets.append(_flush_basket(current_basket))
            current_basket = []
        current_basket.append((sold_at, product_id))
    if current_basket:
        baskets.append(_flush_basket(current_basket))
    return baskets


def _should_start_new_basket(current_basket: list, sold_at: datetime) -> bool:
    """Determine if a new basket should be started based on time window.

    Extracted from _group_sales_into_baskets to reduce complexity.
    """
    if not current_basket:
        return False
    prev_time, _ = current_basket[-1]
    return (sold_at - prev_time) > timedelta(hours=_BASKET_WINDOW_HOURS)


def _flush_basket(basket: list[tuple[datetime, int]]) -> set[int]:
    """Convert a basket list to a set of product IDs.

    Extracted from _group_sales_into_baskets to reduce complexity.
    """
    return {pid for _, pid in basket}


def _count_pair_cooccurrences(baskets: list[set[int]]) -> Counter:
    """Count co-occurrences of product pairs in each basket.

    Extracted from product_affinity to reduce complexity.
    """
    pair_counts: Counter[tuple[int, int]] = Counter()
    for basket in baskets:
        products = sorted(basket)
        for i in range(len(products)):
            for j in range(i + 1, len(products)):
                pair_counts[(products[i], products[j])] += 1
    return pair_counts


def _filter_by_min_cooccurrence(pair_counts: Counter, min_cooccurrence: int) -> dict:
    """Filter pair counts to only include those meeting minimum threshold.

    Extracted from product_affinity to reduce complexity.
    """
    return {pair: count for pair, count in pair_counts.items() if count >= min_cooccurrence}


def top_pairs(session: Session, n: int = 10) -> list[dict]:
    """Top N product pairs by co-occurrence."""
    pairs = product_affinity(session, min_cooccurrence=1)
    top = sorted(pairs.items(), key=lambda kv: kv[1], reverse=True)[:n]

    out = []
    for (a, b), count in top:
        prod_a = session.get(Product, a)
        prod_b = session.get(Product, b)
        out.append(
            {
                "product_a_id": a,
                "product_a_name": prod_a.name if prod_a else None,
                "product_b_id": b,
                "product_b_name": prod_b.name if prod_b else None,
                "count": count,
            }
        )
    return out


# ---------------------------------------------------------------------------
# Churn + rising products
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TrendResult:
    product_id: int
    product_name: str
    recent_sales: int
    prior_sales: int
    change_pct: float | None  # None if prior = 0
    direction: str  # "rising" | "stable" | "churning" | "new"


def _sales_count(session: Session, product_id: int, start: datetime, end: datetime) -> int:
    """Count sales for product in [start, end)."""
    rows = session.execute(
        select(Sale.qty).where(
            Sale.product_id == product_id,
            Sale.voided_at.is_(None),
            Sale.sold_at >= start,
            Sale.sold_at < end,
        )
    ).all()
    return sum(int(r[0] or 0) for r in rows)


def _trend_for_product(
    session: Session, product_id: int, threshold_pct: float = 0.3, window_days: int = 14
) -> TrendResult:
    """Compute trend for one product."""
    product = session.get(Product, product_id)
    if product is None:
        return TrendResult(product_id, "?", 0, 0, None, "new")

    now = datetime.now(timezone.utc)
    recent_start = now - timedelta(days=window_days)
    prior_start = now - timedelta(days=window_days * 2)

    recent = _sales_count(session, product_id, recent_start, now)
    prior = _sales_count(session, product_id, prior_start, recent_start)

    if prior == 0:
        if recent == 0:
            return TrendResult(product_id, product.name, 0, 0, None, "stable")
        return TrendResult(product_id, product.name, recent, 0, None, "new")

    change_pct = (recent - prior) / prior
    if change_pct > threshold_pct:
        direction = "rising"
    elif change_pct < -threshold_pct:
        direction = "churning"
    else:
        direction = "stable"

    return TrendResult(product_id, product.name, recent, prior, change_pct, direction)


def _batch_trend_counts(
    session: Session,
    product_ids: list[int],
    window_days: int = 14,
) -> tuple[dict[int, int], dict[int, int]]:
    """Batch-load recent + prior sales counts in 2 queries.

    Returns (recent_by_pid, prior_by_pid).
    """
    if not product_ids:
        return {}, {}
    now = datetime.now(timezone.utc)
    recent_start = now - timedelta(days=window_days)
    prior_start = now - timedelta(days=window_days * 2)

    recent_rows = session.execute(
        select(Sale.product_id, Sale.qty).where(
            Sale.product_id.in_(product_ids),
            Sale.voided_at.is_(None),
            Sale.sold_at >= recent_start,
        )
    ).all()
    prior_rows = session.execute(
        select(Sale.product_id, Sale.qty).where(
            Sale.product_id.in_(product_ids),
            Sale.voided_at.is_(None),
            Sale.sold_at >= prior_start,
            Sale.sold_at < recent_start,
        )
    ).all()

    recent_by_pid: dict[int, int] = {pid: 0 for pid in product_ids}
    for pid, qty in recent_rows:
        recent_by_pid[pid] = recent_by_pid.get(pid, 0) + int(qty or 0)
    prior_by_pid: dict[int, int] = {pid: 0 for pid in product_ids}
    for pid, qty in prior_rows:
        prior_by_pid[pid] = prior_by_pid.get(pid, 0) + int(qty or 0)
    return recent_by_pid, prior_by_pid


def _classify_trend(
    product_id: int,
    product_name: str,
    recent: int,
    prior: int,
    threshold_pct: float,
) -> TrendResult:
    """Classify one trend from pre-computed counts."""
    if prior == 0:
        if recent == 0:
            return TrendResult(product_id, product_name, 0, 0, None, "stable")
        return TrendResult(product_id, product_name, recent, 0, None, "new")
    change_pct = (recent - prior) / prior
    if change_pct > threshold_pct:
        direction = "rising"
    elif change_pct < -threshold_pct:
        direction = "churning"
    else:
        direction = "stable"
    return TrendResult(product_id, product_name, recent, prior, change_pct, direction)


def churning_products(
    session: Session, threshold_pct: float = 0.3, window_days: int = 14
) -> list[TrendResult]:
    """Products whose sales in last N days dropped > threshold from prior N."""
    products = list(session.scalars(select(Product)).all())
    if not products:
        return []
    recent_by_pid, prior_by_pid = _batch_trend_counts(
        session,
        [p.id for p in products],
        window_days,
    )
    out = []
    for p in products:
        trend = _classify_trend(
            p.id,
            p.name,
            recent_by_pid.get(p.id, 0),
            prior_by_pid.get(p.id, 0),
            threshold_pct,
        )
        if trend.direction == "churning":
            out.append(trend)
    out.sort(key=lambda t: t.change_pct or 0)
    return out


def rising_products(
    session: Session, threshold_pct: float = 0.3, window_days: int = 14
) -> list[TrendResult]:
    """Products whose sales grew > threshold."""
    products = list(session.scalars(select(Product)).all())
    if not products:
        return []
    recent_by_pid, prior_by_pid = _batch_trend_counts(
        session,
        [p.id for p in products],
        window_days,
    )
    out = []
    for p in products:
        trend = _classify_trend(
            p.id,
            p.name,
            recent_by_pid.get(p.id, 0),
            prior_by_pid.get(p.id, 0),
            threshold_pct,
        )
        if trend.direction == "rising":
            out.append(trend)
    out.sort(key=lambda t: t.change_pct or 0, reverse=True)
    return out


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------


def sales_summary(session: Session) -> dict:
    """Combined summary."""
    return {
        "by_hour": sales_by_hour(session),
        "by_dow": sales_by_day_of_week(session),
        "by_month": sales_by_month(session),
        "peak_hour": peak_hour(session),
        "peak_dow": peak_day_of_week(session),
    }


def customer_reorder_rates(
    session: Session,
    since_days: int = 90,
    top_n: int = 10,
) -> dict:
    """Per-customer reorder rate + avg gap between orders.

    BACKLOG #35 (2026-10-02): companion to `customer_retention()`,
    which only counts new vs returning. This helper quantifies
    repeat-purchase intensity for the loyalty dashboard.

    Definitions:
    - "reorder" = customer made 2+ orders in the window
    - "reorder rate" = fraction of customers who reordered
    - "days between orders" = local-time gap between consecutive
      orders for the same customer (averaged across all gaps)

    Returns dict with:
      - total_customers: distinct customer count in window
      - customers_with_2plus_orders: distinct customers with 2+ sales
      - reorder_rate: customers_with_2plus / total_customers (0..1)
      - avg_days_between_orders: mean of all consecutive-order gaps
      - median_days_between_orders: median of all gaps (0 if no gaps)
      - top_repeaters: list of {customer_id, customer_name,
        total_orders, total_gs} sorted by total_orders desc

    No-data case: returns zeros + empty top_repeaters (so templates
    can render an empty state without special-casing).
    """

    from app.rms.config import ASUNCION_TZ

    cutoff = datetime.now(ASUNCION_TZ) - timedelta(days=since_days)
    sales_rows = _fetch_sales_in_window(session, cutoff)
    by_customer = _group_sales_by_customer(sales_rows)

    total_customers = len(by_customer)
    repeaters = {cid: orders for cid, orders in by_customer.items() if len(orders) >= 2}
    customers_with_2plus = len(repeaters)

    reorder_rate = (customers_with_2plus / total_customers) if total_customers else 0.0
    all_gaps_days = _compute_order_gaps(repeaters)
    avg_gap, median_gap = _compute_gap_stats(all_gaps_days)
    repeater_stats = _build_repeater_stats(repeaters, top_n)
    _enrich_with_customer_names(session, repeater_stats)

    return {
        "total_customers": total_customers,
        "customers_with_2plus_orders": customers_with_2plus,
        "reorder_rate": round(reorder_rate, 4),
        "avg_days_between_orders": round(avg_gap, 1),
        "median_days_between_orders": round(median_gap, 1),
        "top_repeaters": repeater_stats,
    }


def _fetch_sales_in_window(session, cutoff):
    """Fetch all valid sales in the time window.

    Extracted from customer_reorder_rates to reduce complexity.
    """
    return session.execute(
        select(
            Sale.customer_id,
            Sale.sold_at,
            Sale.qty,
            Sale.unit_price_gs,
            Sale.discount_gs,
        )
        .where(
            Sale.voided_at.is_(None),
            Sale.customer_id.isnot(None),
            Sale.sold_at >= cutoff,
        )
        .order_by(Sale.customer_id, Sale.sold_at)
    ).all()


def _group_sales_by_customer(sales_rows) -> dict[int, list[tuple]]:
    """Group sales by customer, computing line totals and local times.

    Extracted from customer_reorder_rates to reduce complexity.
    """
    from app.rms.config import ASUNCION_TZ

    by_customer: dict[int, list[tuple[datetime, int]]] = {}
    for cid, sold_at, qty_v, unit_price_v, discount_v in sales_rows:
        if sold_at is None:
            continue
        local_dt = sold_at.astimezone(ASUNCION_TZ) if sold_at.tzinfo else sold_at
        line_total = round(float(unit_price_v or 0) * float(qty_v or 0)) - int(discount_v or 0)
        by_customer.setdefault(int(cid), []).append((local_dt, line_total))
    return by_customer


def _compute_order_gaps(repeaters: dict) -> list[float]:
    """Compute gaps in days between consecutive orders for each repeater.

    Extracted from customer_reorder_rates to reduce complexity.
    """
    all_gaps: list[float] = []
    for orders in repeaters.values():
        timestamps = sorted(ts for ts, _ in orders)
        for prev, curr in itertools.pairwise(timestamps):
            gap = (curr - prev).total_seconds() / 86400.0
            if gap >= 0:
                all_gaps.append(gap)
    return all_gaps


def _compute_gap_stats(all_gaps_days: list[float]) -> tuple[float, float]:
    """Compute avg and median gap in days.

    Extracted from customer_reorder_rates to reduce complexity.
    """
    from statistics import median

    if not all_gaps_days:
        return 0.0, 0.0
    avg = sum(all_gaps_days) / len(all_gaps_days)
    med = float(median(all_gaps_days))
    return avg, med


def _build_repeater_stats(repeaters: dict, top_n: int) -> list[dict]:
    """Build sorted repeater stats list, truncated to top_n.

    Extracted from customer_reorder_rates to reduce complexity.
    """
    stats = [
        {
            "customer_id": cid,
            "customer_name": "",
            "total_orders": len(orders),
            "total_gs": sum(total for _, total in orders),
        }
        for cid, orders in repeaters.items()
    ]
    stats.sort(key=lambda r: (r["total_orders"], r["total_gs"]), reverse=True)
    return stats[:top_n]


def _enrich_with_customer_names(session, repeater_stats: list[dict]) -> None:
    """Enrich repeater stats with customer names.

    Extracted from customer_reorder_rates to reduce complexity.
    """
    from sqlalchemy import select

    from app.rms.models import Customer

    if not repeater_stats:
        return
    ids = [r["customer_id"] for r in repeater_stats]
    names_by_id = {
        c.id: c.name for c in session.scalars(select(Customer).where(Customer.id.in_(ids))).all()
    }
    for r in repeater_stats:
        r["customer_name"] = names_by_id.get(r["customer_id"], "?")


def customer_retention(
    session: Session,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> dict:
    """New vs returning customers in a period.

    Returns counts of:
    - new_customers: customers with their first-ever sale in the window
    - returning_customers: customers who also had sales before the window
    """
    if end_date is None:
        end_date = datetime.now(timezone.utc)
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # All customers who bought in the window
    window_customers = set(
        r[0]
        for r in session.execute(
            select(Sale.customer_id)
            .where(
                Sale.sold_at >= start_date,
                Sale.sold_at <= end_date,
                Sale.voided_at.is_(None),
                Sale.customer_id.isnot(None),
            )
            .distinct()
        ).all()
    )

    if not window_customers:
        return {"new_customers": 0, "returning_customers": 0, "total": 0}

    # Customers with sales BEFORE the window
    prior_customers = set(
        r[0]
        for r in session.execute(
            select(Sale.customer_id)
            .where(
                Sale.sold_at < start_date,
                Sale.voided_at.is_(None),
                Sale.customer_id.isnot(None),
            )
            .distinct()
        ).all()
    )

    new_c = window_customers - prior_customers
    returning_c = window_customers & prior_customers

    return {
        "new_customers": len(new_c),
        "returning_customers": len(returning_c),
        "total": len(window_customers),
    }


def _waste_per_ingredient_rows(
    session: Session,
    since: datetime,
) -> list[dict]:
    """Raw aggregate: ingredient_id, total_waste_gs, event_count.

    Helper for `waste_roi_by_ingredient` (joins on Ingredient for
    the unit + name) and the trend helpers.
    """
    from sqlalchemy import select

    from app.rms.models import Ingredient, WasteLog

    rows = session.execute(
        select(
            WasteLog.ingredient_id,
            func.coalesce(func.sum(WasteLog.cost_gs), 0).label("total_waste_gs"),
            func.count(WasteLog.id).label("event_count"),
        )
        .where(WasteLog.recorded_at >= since)
        .group_by(WasteLog.ingredient_id)
    ).all()
    if not rows:
        return []
    # One-shot hydration of names + units.
    ids = [int(r[0]) for r in rows]
    ingredients = {
        i.id: (i.name, i.unit)
        for i in session.scalars(select(Ingredient).where(Ingredient.id.in_(ids))).all()
    }
    out: list[dict] = []
    for ing_id, total_waste, count in rows:
        name, unit = ingredients.get(int(ing_id), ("?", "?"))
        out.append(
            {
                "ingredient_id": int(ing_id),
                "ingredient_name": name,
                "unit": unit,
                "total_waste_gs": int(total_waste),
                "event_count": int(count),
            }
        )
    return out


def waste_roi_by_ingredient(
    session: Session,
    since_days: int = 90,
) -> list[dict]:
    """Per-ingredient waste cost over the window.

    BACKLOG #34 (2026-10-02): waste ROI per ingredient. We don't
    compute the full "ROI" formula since we don't have a clean
    "consumed-at-cost" series (RecipeLine.qty × ingredient price at
    sale time would need a complex join). What we DO have reliably is
    WasteLog.cost_gs, which is denormalized at insert time using the
    ingredient's price snapshot — so total_waste_gs is the most
    accurate waste-money figure available.

    waste_pct = total_waste_gs / (total_waste_gs + total_consumed_gs)
    — but total_consumed_gs requires walking Sale → RecipeLine →
    IngredientPriceEvent, which is expensive. For v1 we report the
    waste stats and let the operator eyeball the % against their
    known daily revenue from `/avikeled/dashboard`.

    Returns a list of dicts sorted by total_waste_gs desc so the
    operator can spot the biggest money leaks first.
    """
    from app.rms.config import ASUNCION_TZ

    cutoff = datetime.now(ASUNCION_TZ) - timedelta(days=since_days)
    rows = _waste_per_ingredient_rows(session, cutoff)

    out: list[dict] = []
    for r in rows:
        avg = (r["total_waste_gs"] / r["event_count"]) if r["event_count"] else 0.0
        out.append(
            {
                **r,
                "total_consumed_gs": 0,  # v1: leave to operator's dashboard
                "waste_pct": 0.0,  # v1: can't compute without consumed
                "avg_waste_per_event_gs": round(avg, 1),
                "window_days": since_days,
            }
        )
    out.sort(key=lambda r: r["total_waste_gs"], reverse=True)
    return out


def waste_vs_purchase_trend(
    session: Session,
    ingredient_id: int,
    since_days: int = 180,
) -> list[dict]:
    """Per-month waste cost trend for one ingredient.

    Returns list of {year, month, cost_gs, event_count} rows. Months
    with zero waste are NOT included (lets the chart render gaps
    cleanly).
    """
    from sqlalchemy import select

    from app.rms.config import ASUNCION_TZ
    from app.rms.models import WasteLog

    cutoff = datetime.now(ASUNCION_TZ) - timedelta(days=since_days)
    # strftime works on both SQLite and Postgres; equivalent to
    # EXTRACT(YEAR FROM ...) for the bucketing we need.
    year_expr = func.cast(func.strftime("%Y", WasteLog.recorded_at), Integer)
    month_expr = func.cast(func.strftime("%m", WasteLog.recorded_at), Integer)
    rows = session.execute(
        select(
            year_expr.label("y"),
            month_expr.label("m"),
            func.sum(WasteLog.cost_gs).label("cost_gs"),
            func.count(WasteLog.id).label("event_count"),
        )
        .where(
            WasteLog.ingredient_id == ingredient_id,
            WasteLog.recorded_at >= cutoff,
        )
        .group_by("y", "m")
        .order_by("y", "m")
    ).all()

    return [
        {
            "year": int(y),
            "month": int(m),
            "cost_gs": int(cost_gs or 0),
            "event_count": int(count),
        }
        for y, m, cost_gs, count in rows
    ]


__all__ = [
    "TrendResult",
    "churning_products",
    "customer_reorder_rates",
    "customer_retention",
    "peak_day_of_week",
    "peak_hour",
    "product_affinity",
    "rising_products",
    "sales_by_day_of_week",
    "sales_by_hour",
    "sales_by_month",
    "sales_heatmap",
    "sales_summary",
    "top_pairs",
    "waste_roi_by_ingredient",
    "waste_vs_purchase_trend",
]
