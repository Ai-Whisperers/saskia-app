"""app/rms/price_history.py — ingredient purchase-price time series.

Per Phase B (Q1 core) of the Saskia review round 1 (Thu 18-sep 2026).

Saskia's review calls for a price-history surface on /inventario (min /
current / max strip + 90-day sparkline) and a dashboard insight flagging
ingredients with >20% fluctuation in the last month. To power both we
need a real time series — `Ingredient.purchase_price_gs` alone only
holds the current value, not the history.

This module owns:
- `record_price_event()` — insert an event + update Ingredient in one
  atomic write. The router calls this; never write the price column
  directly anywhere else.
- `price_history()` — return (recorded_at_utc, price_gs) tuples in
  ascending order for a given ingredient, filtered to the last `days`.
- `price_stats()` — min / max / avg / current / count for the window.
  Used by the /inventario row strip and the dashboard insight.

Append-only discipline: this table is never UPDATEd. If an operator
enters the wrong price by mistake, the correction is a new event — not
an edit. Historical reports don't retroactively change when the
current price moves.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import Ingredient, IngredientPriceEvent

_ALLOWED_SOURCES = frozenset({"restock", "manual", "excel_import", "csv_upload"})


def record_price_event(
    session: Session,
    ingredient_id: int,
    price_gs: int,
    source: str = "restock",
    at: datetime | None = None,
    supplier_id: int | None = None,
) -> IngredientPriceEvent:
    """Append a purchase-price event and update the ingredient's current price.

    Caller commits. The function does NOT commit on its own (so it can be
    composed into a larger transaction).

    Args:
        session: SQLAlchemy session.
        ingredient_id: PK of the ingredient.
        price_gs: integer Gs. (no decimals; matches the money rule).
        source: one of "restock", "manual", "excel_import", "csv_upload".
            Other values raise ValueError. csv_upload added 2026-10-01
            for the bulk price import path.
        at: override the recorded_at timestamp (used by the CSV upload
            to backdate historical rows).
        supplier_id: tag the event with the supplier that quoted this
            price. NULL when unknown (e.g. legacy restocks). Migration 073
            added the column. The reorder/registrar endpoint passes the
            chosen supplier when available so /reorder's per-row dropdown
            can fill in real prices over time.

    Returns:
        The newly-created IngredientPriceEvent row (flushed; has its id).
    """
    if source not in _ALLOWED_SOURCES:
        allowed = ", ".join(sorted(_ALLOWED_SOURCES))
        raise ValueError(f"unknown source: {source!r}. Allowed: {allowed}")

    ingredient = session.get(Ingredient, ingredient_id)
    if ingredient is None:
        raise ValueError(f"ingredient {ingredient_id} not found")

    now_utc = at or datetime.now(timezone.utc)
    event = IngredientPriceEvent(
        ingredient_id=ingredient_id,
        price_gs=price_gs,
        recorded_at=now_utc,
        source=source,
        supplier_id=supplier_id,
    )
    session.add(event)
    session.flush()  # assigns event.id so callers can read it

    # Update the denormalized "current price" fields on the ingredient so
    # the rest of the app (costing, sales, dashboards) keeps working with
    # the same single-source-of-truth it always has.
    ingredient.purchase_price_gs = price_gs
    # Store as naive UTC datetime to match the rest of the column types
    # in this DB (DateTime, not TIMESTAMPTZ).
    ingredient.purchase_price_updated_at = now_utc.replace(tzinfo=None)

    return event


def price_history(
    session: Session,
    ingredient_id: int,
    days: int = 90,
) -> list[tuple[datetime, int]]:
    """Return (recorded_at_utc, price_gs) tuples for an ingredient, ascending.

    `days` is a sliding window from now (UTC). Events with recorded_at
    older than `now - days` are excluded.

    Returns an empty list when the ingredient has no events in the window.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = session.execute(
        select(IngredientPriceEvent.recorded_at, IngredientPriceEvent.price_gs)
        .where(IngredientPriceEvent.ingredient_id == ingredient_id)
        .where(IngredientPriceEvent.recorded_at >= cutoff)
        .order_by(IngredientPriceEvent.recorded_at.asc())
    ).all()
    return [(ts, int(price)) for ts, price in rows]


def batch_price_stats(
    session: Session, ingredient_ids: list[int], days: int = 90
) -> dict[int, dict]:
    """Return {ingredient_id: {current, min, max, avg, count}} for multiple ingredients.

    Replaces N separate price_stats() calls — 3 queries each (price_history × 2,
    then the same data re-parsed) → 1 query total.
    """
    if not ingredient_ids:
        return {}

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    rows = session.execute(
        select(
            IngredientPriceEvent.ingredient_id,
            IngredientPriceEvent.price_gs,
            IngredientPriceEvent.recorded_at,
        )
        .where(
            IngredientPriceEvent.ingredient_id.in_(ingredient_ids),
            IngredientPriceEvent.recorded_at >= cutoff,
        )
        .order_by(IngredientPriceEvent.ingredient_id, IngredientPriceEvent.recorded_at.asc())
    ).all()

    result: dict[int, dict] = {
        iid: {"current": None, "min": None, "max": None, "avg": None, "count": 0}
        for iid in ingredient_ids
    }
    for row in rows:
        iid, price_gs, _recorded_at = row
        d = result[iid]
        d["count"] += 1
        p = int(price_gs)
        if d["min"] is None or p < d["min"]:
            d["min"] = p
        if d["max"] is None or p > d["max"]:
            d["max"] = p
        d["current"] = p  # last in asc order

    for iid in ingredient_ids:
        d = result[iid]
        if d["count"] > 0:
            avg = sum(Decimal(r.price_gs) for r in rows if r.ingredient_id == iid) / Decimal(
                d["count"]
            )
            d["avg"] = int(avg)
        else:
            d["current"] = None

    return result


def price_stats(
    session: Session,
    ingredient_id: int,
    days: int = 90,
) -> dict:
    """Return min / max / avg / current / count over the last `days`.

    `current` is the most recent event's price (matches the ingredient's
    purchase_price_gs after the most recent write). `avg` uses Decimal so
    integer overflow doesn't bite for long histories.

    Empty window → all values None + count=0.
    """
    history = price_history(session, ingredient_id, days=days)
    if not history:
        return {"current": None, "min": None, "max": None, "avg": None, "count": 0}

    prices = [p for _, p in history]
    current = history[-1][1]
    mn = min(prices)
    mx = max(prices)
    # Decimal to avoid float drift; round at the persistence site if needed.
    avg = sum(Decimal(p) for p in prices) / Decimal(len(prices))
    return {
        "current": int(current),
        "min": int(mn),
        "max": int(mx),
        "avg": avg,
        "count": len(prices),
    }


def cheapest_supplier(
    session: Session,
    ingredient_id: int,
    days: int = 90,
) -> dict | None:
    """Return the supplier with the lowest recorded price for an ingredient.

    Aggregates by ``supplier_id`` (NULL treated as one bucket: "sin
    proveedor"), returns the bucket with the lowest mean price. Only
    suppliers with at least one event in the window are considered.

    Returns:
        {"supplier_id": int | None,
         "supplier_name": str | None,
         "avg_price_gs": int,
         "event_count": int}
        or None if the ingredient has no events in the window.

    Used by /reorder to surface the cheapest supplier hint next to the
    picker dropdown (Q4 multi-supplier).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = session.execute(
        select(
            IngredientPriceEvent.supplier_id,
            IngredientPriceEvent.price_gs,
        )
        .where(IngredientPriceEvent.ingredient_id == ingredient_id)
        .where(IngredientPriceEvent.recorded_at >= cutoff)
    ).all()

    if not rows:
        return None

    # Bucket by supplier_id; compute mean per bucket.
    buckets: dict[int | None, list[int]] = {}
    for supplier_id, price in rows:
        buckets.setdefault(supplier_id, []).append(int(price))

    # Pick the bucket with the lowest mean price.
    # ``best_set`` distinguishes "no winner yet" from "winner is None
    # (legacy NULL-supplier bucket)" — using ``best_supplier_id is None``
    # as the uninitialized check is ambiguous after the first iteration.
    best_set = False
    best_supplier_id: int | None = None
    best_avg: int = 0
    best_count: int = 0
    for sid, prices in buckets.items():
        avg = sum(prices) // len(prices)
        if not best_set or avg < best_avg or (avg == best_avg and len(prices) > best_count):
            best_supplier_id = sid
            best_avg = avg
            best_count = len(prices)
            best_set = True

    supplier_name: str | None = None
    if best_supplier_id is not None:
        from app.rms.models import Supplier

        sup = session.get(Supplier, best_supplier_id)
        if sup is not None:
            supplier_name = sup.name

    return {
        "supplier_id": best_supplier_id,
        "supplier_name": supplier_name,
        "avg_price_gs": int(best_avg),
        "event_count": best_count,
    }


def batch_cheapest_supplier(
    session: Session, ingredient_ids: list[int], days: int = 90
) -> dict[int, dict | None]:
    """Same as ``cheapest_supplier`` but for many ingredients in one query.

    Returns ``{ingredient_id: cheapest_dict | None}``. Used by /reorder
    to render a per-row "proveedor más barato" hint without N+1.
    """
    if not ingredient_ids:
        return {}

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = session.execute(
        select(
            IngredientPriceEvent.ingredient_id,
            IngredientPriceEvent.supplier_id,
            IngredientPriceEvent.price_gs,
        ).where(
            IngredientPriceEvent.ingredient_id.in_(ingredient_ids),
            IngredientPriceEvent.recorded_at >= cutoff,
        )
    ).all()

    # Group (ingredient_id, supplier_id) buckets.
    buckets: dict[int, dict[int | None, list[int]]] = {}
    for iid, sid, price in rows:
        per_ing = buckets.setdefault(int(iid), {})
        per_ing.setdefault(int(sid) if sid is not None else None, []).append(int(price))

    # Resolve supplier names in one query.
    supplier_ids = {
        sid for per_ing in buckets.values() for sid in per_ing.keys() if sid is not None
    }
    supplier_names: dict[int, str] = {}
    if supplier_ids:
        from app.rms.models import Supplier

        sup_rows = session.execute(
            select(Supplier.id, Supplier.name).where(Supplier.id.in_(supplier_ids))
        ).all()
        supplier_names = {int(sid): name for sid, name in sup_rows}

    # Pick the cheapest per ingredient.
    result: dict[int, dict | None] = {}
    for iid in ingredient_ids:
        per_ing = buckets.get(int(iid))
        if not per_ing:
            result[int(iid)] = None
            continue
        best_set = False
        best_sid: int | None = None
        best_avg = 0
        best_count = 0
        for sid, prices in per_ing.items():
            avg = sum(prices) // len(prices)
            if not best_set or avg < best_avg or (avg == best_avg and len(prices) > best_count):
                best_sid = sid
                best_avg = avg
                best_count = len(prices)
                best_set = True
        result[int(iid)] = {
            "supplier_id": best_sid,
            "supplier_name": supplier_names.get(best_sid) if best_sid else None,
            "avg_price_gs": int(best_avg),
            "event_count": best_count,
        }
    return result


def supplier_volatility(
    session: Session,
    since_days: int = 90,
) -> list[dict]:
    """Per-supplier price volatility leaderboard.

    BACKLOG #31 (2026-10-02): audit noted 0 IngredientPriceEvent rows
    in production, but the schema + supplier_id FK exist. This helper
    ingests whatever price events are present and surfaces:

      - ingredient_count: distinct ingredients the supplier sells
      - event_count:     total price events in the window
      - min/max/avg:     ₲ stats across all events
      - volatility_score:(max-min)/avg — high = erratic pricing
      - trend_direction: 'up' | 'down' | 'stable'
                         comparing latest vs first event
      - days_since_last_event: days between window-end and last event
      - current_price_gs:        latest event's price

    Sorted by volatility_score desc so the operator sees the most
    unstable suppliers first. Excludes NULL supplier_id (these are
    typically bulk imports that didn't tag a supplier — keep them
    off the leaderboard; the operator can still see them on the
    global price-history view).

    Returns [] when no suppliers have price events in the window.
    """
    from datetime import timezone

    from sqlalchemy import select

    from app.rms.models import IngredientPriceEvent, Supplier

    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
    now_utc = datetime.now(timezone.utc)

    # Single query: every (supplier_id, ingredient_id, price_gs,
    # recorded_at) in the window, ordered so we can compute the
    # first/last price for trend_direction cheaply.
    rows = session.execute(
        select(
            IngredientPriceEvent.supplier_id,
            IngredientPriceEvent.ingredient_id,
            IngredientPriceEvent.price_gs,
            IngredientPriceEvent.recorded_at,
        )
        .where(
            IngredientPriceEvent.supplier_id.isnot(None),
            IngredientPriceEvent.recorded_at >= cutoff,
        )
        .order_by(
            IngredientPriceEvent.supplier_id,
            IngredientPriceEvent.recorded_at,
        )
    ).all()

    if not rows:
        return []

    # Bucket by supplier.
    by_supplier: dict[int, list[tuple[int, datetime, int]]] = {}
    for sup_id, ing_id, price_gs, recorded_at in rows:
        by_supplier.setdefault(int(sup_id), []).append((int(ing_id), recorded_at, int(price_gs)))

    # Hydrate supplier names in one query.
    sup_ids = list(by_supplier.keys())
    names_by_id = {
        s.id: s.name
        for s in session.scalars(select(Supplier).where(Supplier.id.in_(sup_ids))).all()
    }

    out: list[dict] = []
    for sup_id, events in by_supplier.items():
        ingredients = {ing_id for ing_id, _, _ in events}
        prices = [price for _, _, price in events]
        first_price = prices[0]
        last_price = prices[-1]
        min_p = min(prices)
        max_p = max(prices)
        avg_p = sum(prices) / len(prices)
        # volatility = relative spread. Use avg as denominator; if avg
        # is zero (all ₲0 events), score 0.
        if avg_p > 0:
            volatility = (max_p - min_p) / avg_p
        else:
            volatility = 0.0
        # Trend: compare last to first. 5% threshold for "stable" so
        # tiny floating-point noise doesn't flip the badge.
        if first_price > 0:
            delta_pct = (last_price - first_price) / first_price
        else:
            delta_pct = 0.0
        if delta_pct > 0.05:
            trend = "up"
        elif delta_pct < -0.05:
            trend = "down"
        else:
            trend = "stable"
        # Days since last event (relative to now UTC).
        last_recorded = events[-1][1]
        # recorded_at is naive UTC; treat as UTC for diff.
        if last_recorded.tzinfo is None:
            last_recorded = last_recorded.replace(tzinfo=timezone.utc)
        days_stale = max(0, int((now_utc - last_recorded).total_seconds() // 86400))

        out.append(
            {
                "supplier_id": sup_id,
                "supplier_name": names_by_id.get(sup_id, "?"),
                "ingredient_count": len(ingredients),
                "event_count": len(events),
                "min_price_gs": min_p,
                "max_price_gs": max_p,
                "avg_price_gs": round(avg_p, 1),
                "volatility_score": round(volatility, 3),
                "trend_direction": trend,
                "days_since_last_event": days_stale,
                "current_price_gs": last_price,
            }
        )

    out.sort(key=lambda r: r["volatility_score"], reverse=True)
    return out


__all__ = [
    "batch_cheapest_supplier",
    "batch_price_stats",
    "cheapest_supplier",
    "price_history",
    "price_stats",
    "record_price_event",
    "supplier_volatility",
]
