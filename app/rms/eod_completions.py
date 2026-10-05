"""app/rms/eod_completions.py — production completion persistence (T5).

the operator review: "Al final del día debe registrarse cuánto de la
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
            updated_at=now,  # T-2026-10-04 (Tier 5-K): track edit time.
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
        row.updated_at = now  # T-2026-10-04 (Tier 5-K): bump on each save.
    session.flush()
    return row


def completions_for_date(session: Session, for_date: date) -> dict[int, float]:
    """Return {product_id: completed_qty} for a given date."""
    rows = (
        session.execute(
            select(ProductionCompletion).where(ProductionCompletion.for_date == for_date)
        )
        .scalars()
        .all()
    )
    return {r.product_id: r.completed_qty for r in rows}


def close_day_for_product(
    session: Session,
    *,
    product_id: int,
    for_date: date,
    closure_notes: str | None = None,
    status: str = "done",
    completed_qty: float = 0.0,
) -> ProductionCompletion:
    """Mark a single product's completion as closed (status='done' or 'cancelled').

    PRODUCCION-V2 Fase 2: the cook taps "Cerrar turno" on each row at end
    of shift. The row flips from 'open' to 'done' (or 'cancelled' when
    they actually baked nothing and just want to record that). The
    optional closure_notes is the cook's free-text justification when
    completed_qty is 0 (e.g. "no se vendió", "cerrado por feriado",
    "error de carga"). The audit is captured by the router via
    production_plan_audit (we don't re-audit here to avoid double-logging).

    Idempotent: re-closing a row keeps the same closure_notes unless the
    caller passes a new value. Status transitions are allowed in either
    direction (open ↔ done, open ↔ cancelled) but not done ↔ cancelled
    directly (the cook must reopen first); this is enforced by the
    caller, not here, to keep the helper single-purpose.

    Raises:
        KeyError: if the product doesn't exist.
        ValueError: if status is not in ('done', 'cancelled', 'open').
    """
    if status not in ("open", "done", "cancelled"):
        raise ValueError(f"status must be open|done|cancelled; got {status!r}")
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
        # No completion row yet — create one with completed_qty=0 so the
        # audit log + dashboard see the closure. The cook didn't bake
        # anything for this product, but the day is still "closed" in
        # the sense that the operator has reviewed it.
        row = ProductionCompletion(
            product_id=product_id,
            for_date=for_date,
            completed_qty=completed_qty,
            recorded_at=now,
            status=status,
            closure_notes=closure_notes,
            updated_at=now,
        )
        session.add(row)
    else:
        row.status = status
        # T-2026-10-05: close-day now carries the actual produced qty
        # (single data-entry point on /produccion). 0 means "not set" —
        # keep the previous value instead of wiping a real number.
        if completed_qty > 0 or row.completed_qty in (None, 0.0):
            row.completed_qty = completed_qty
        if closure_notes is not None:
            row.closure_notes = closure_notes
        row.updated_at = now
    session.flush()
    return row


__all__ = ["close_day_for_product", "completions_for_date", "upsert_completion"]
