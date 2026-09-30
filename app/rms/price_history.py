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
        raise ValueError(
            f"unknown source: {source!r}. Allowed: {allowed}"
        )

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

    result: dict[int, dict] = {iid: {"current": None, "min": None, "max": None, "avg": None, "count": 0} for iid in ingredient_ids}
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
            avg = sum(
                Decimal(r.price_gs) for r in rows if r.ingredient_id == iid
            ) / Decimal(d["count"])
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


__all__ = [
    "batch_price_stats",
    "price_history",
    "price_stats",
    "record_price_event",
]
