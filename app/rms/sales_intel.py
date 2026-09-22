"""app/rms/sales_intel.py — time patterns, product affinity, churn/rising.

Answers:
- When are my peak hours / days / months?
- What products are bought together (market basket)?
- Which products are declining (churn) or trending up?
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import Product, Sale

# ---------------------------------------------------------------------------
# Time-pattern functions
# ---------------------------------------------------------------------------

def sales_by_hour(session: Session) -> dict[int, int]:
    """Count of sales per hour 0-23."""
    rows = session.execute(
        select(Sale.sold_at).where(Sale.voided_at.is_(None))
    ).all()
    counts: Counter[int] = Counter()
    for (sold_at,) in rows:
        if sold_at is None:
            continue
        counts[sold_at.hour] += 1
    return {h: counts.get(h, 0) for h in range(24)}


def sales_by_day_of_week(session: Session) -> dict[int, int]:
    """Count of sales per weekday (0=Mon, 6=Sun)."""
    rows = session.execute(
        select(Sale.sold_at).where(Sale.voided_at.is_(None))
    ).all()
    counts: Counter[int] = Counter()
    for (sold_at,) in rows:
        if sold_at is None:
            continue
        counts[sold_at.weekday()] += 1
    return {d: counts.get(d, 0) for d in range(7)}


def sales_by_month(session: Session) -> dict[str, int]:
    """Count of sales per YYYY-MM."""
    rows = session.execute(
        select(Sale.sold_at).where(Sale.voided_at.is_(None))
    ).all()
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


def product_affinity(session: Session,
                     min_cooccurrence: int = 2) -> dict[tuple[int, int], int]:
    """Co-occurrence count of (product_a, product_b) pairs in same basket.

    A "basket" is sales of multiple products within _BASKET_WINDOW_HOURS
    (or sales from the same customer if customer_id is set).

    Returns dict with (smaller_id, larger_id) → count, only pairs with
    count >= min_cooccurrence.
    """
    sales = list(session.execute(
        select(Sale.sold_at, Sale.product_id, Sale.customer_id)
        .where(Sale.voided_at.is_(None))
        .order_by(Sale.sold_at)
    ).all())

    # Group sales into baskets.
    baskets: list[set[int]] = []
    current_basket: list[tuple[datetime, int]] = []
    for sold_at, product_id, customer_id in sales:
        if current_basket:
            prev_time, _ = current_basket[-1]
            if (sold_at - prev_time) > timedelta(hours=_BASKET_WINDOW_HOURS):
                # New basket.
                if current_basket:
                    baskets.append({pid for _, pid in current_basket})
                current_basket = []
        current_basket.append((sold_at, product_id))
    if current_basket:
        baskets.append({pid for _, pid in current_basket})

    # Count co-occurrences.
    pair_counts: Counter[tuple[int, int]] = Counter()
    for basket in baskets:
        products = sorted(basket)
        for i in range(len(products)):
            for j in range(i + 1, len(products)):
                pair_counts[(products[i], products[j])] += 1

    return {pair: count for pair, count in pair_counts.items()
            if count >= min_cooccurrence}


def top_pairs(session: Session, n: int = 10) -> list[dict]:
    """Top N product pairs by co-occurrence."""
    pairs = product_affinity(session, min_cooccurrence=1)
    top = sorted(pairs.items(), key=lambda kv: kv[1], reverse=True)[:n]

    out = []
    for (a, b), count in top:
        prod_a = session.get(Product, a)
        prod_b = session.get(Product, b)
        out.append({
            "product_a_id": a,
            "product_a_name": prod_a.name if prod_a else None,
            "product_b_id": b,
            "product_b_name": prod_b.name if prod_b else None,
            "count": count,
        })
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


def _sales_count(session: Session, product_id: int,
                 start: datetime, end: datetime) -> int:
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


def _trend_for_product(session: Session, product_id: int,
                       threshold_pct: float = 0.3,
                       window_days: int = 14) -> TrendResult:
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

    return TrendResult(product_id, product.name, recent, prior, change_pct,
                       direction)


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
    return TrendResult(product_id, product_name, recent, prior, change_pct,
                       direction)


def churning_products(session: Session, threshold_pct: float = 0.3,
                      window_days: int = 14) -> list[TrendResult]:
    """Products whose sales in last N days dropped > threshold from prior N."""
    products = list(session.scalars(select(Product)).all())
    if not products:
        return []
    recent_by_pid, prior_by_pid = _batch_trend_counts(
        session, [p.id for p in products], window_days,
    )
    out = []
    for p in products:
        trend = _classify_trend(
            p.id, p.name,
            recent_by_pid.get(p.id, 0),
            prior_by_pid.get(p.id, 0),
            threshold_pct,
        )
        if trend.direction == "churning":
            out.append(trend)
    out.sort(key=lambda t: t.change_pct or 0)
    return out


def rising_products(session: Session, threshold_pct: float = 0.3,
                    window_days: int = 14) -> list[TrendResult]:
    """Products whose sales grew > threshold."""
    products = list(session.scalars(select(Product)).all())
    if not products:
        return []
    recent_by_pid, prior_by_pid = _batch_trend_counts(
        session, [p.id for p in products], window_days,
    )
    out = []
    for p in products:
        trend = _classify_trend(
            p.id, p.name,
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
        r[0] for r in session.execute(
            select(Sale.customer_id).where(
                Sale.sold_at >= start_date,
                Sale.sold_at <= end_date,
                Sale.voided_at.is_(None),
                Sale.customer_id.isnot(None),
            ).distinct()
        ).all()
    )

    if not window_customers:
        return {"new_customers": 0, "returning_customers": 0, "total": 0}

    # Customers with sales BEFORE the window
    prior_customers = set(
        r[0] for r in session.execute(
            select(Sale.customer_id).where(
                Sale.sold_at < start_date,
                Sale.voided_at.is_(None),
                Sale.customer_id.isnot(None),
            ).distinct()
        ).all()
    )

    new_c = window_customers - prior_customers
    returning_c = window_customers & prior_customers

    return {
        "new_customers": len(new_c),
        "returning_customers": len(returning_c),
        "total": len(window_customers),
    }


__all__ = [
    "TrendResult",
    "churning_products",
    "peak_day_of_week",
    "peak_hour",
    "product_affinity",
    "rising_products",
    "sales_by_day_of_week",
    "sales_by_hour",
    "sales_by_month",
    "sales_summary",
    "top_pairs",
]
