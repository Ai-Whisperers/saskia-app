"""app/rms/eod_completions.py — production completion persistence (T5).

Saskia review: "Al final del día debe registrarse cuánto de la
producción se completó". Upsert semantics: one row per
(product_id, for_date); re-recording updates completed_qty in place.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import Product, ProductionCompletion


def upsert_completion(
    session: Session,
    *,
    product_id: int,
    for_date: date,
    completed_qty: float,
    notes: str | None = None,
) -> ProductionCompletion:
    """Insert or update the completion row for (product_id, for_date).

    Raises:
        ValueError: if completed_qty < 0.
        KeyError: if the product doesn't exist.
    """
    if completed_qty < 0:
        raise ValueError("completed_qty no puede ser negativo")

    product = session.get(Product, product_id)
    if product is None:
        raise KeyError(f"Product {product_id} not found")

    row = session.execute(
        select(ProductionCompletion).where(
            ProductionCompletion.product_id == product_id,
            ProductionCompletion.for_date == for_date,
        )
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if row is None:
        row = ProductionCompletion(
            product_id=product_id,
            for_date=for_date,
            completed_qty=completed_qty,
            recorded_at=now,
            notes=notes,
        )
        session.add(row)
    else:
        row.completed_qty = completed_qty
        row.recorded_at = now
        # T-2026-10-04 (Tier 5-K): stamp updated_at on every save so
        # the shift-execute concurrent-edit detector can compare.
        row.updated_at = now
        if notes is not None:
            row.notes = notes
    session.flush()
    return row


def completions_for_date(
    session: Session, for_date: date
) -> dict[int, float]:
    """Return {product_id: completed_qty} for a given date."""
    rows = session.execute(
        select(ProductionCompletion).where(ProductionCompletion.for_date == for_date)
    ).scalars().all()
    return {r.product_id: r.completed_qty for r in rows}


__all__ = ["completions_for_date", "upsert_completion"]
