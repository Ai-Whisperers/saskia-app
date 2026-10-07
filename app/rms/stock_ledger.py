"""app/rms/stock_ledger.py — the single helper for stock deltas + audit rows.

Reuse audit 2026-10-07 (docs/operations/2026-10-07-saskia-reuse-abstraction-audit.md):
22 construction sites for StockMovement, 10 of which bump
``ing.stock_qty`` AND write the audit row by hand, with two diverging
unit-conversion behaviors (shopping.py lands raw qty on mismatch;
reorder.py/waste.py raise). This module is the ONE way to do both.

Contract:
- apply_stock_delta(): bump stock_qty + write StockMovement. Caller
  commits (keeps transaction control at the route, matching the
  repo's safe_commit pattern).
- qty_to_stock_unit(): convert a qty in its source unit to the
  ingredient's stock unit. on_mismatch policy is EXPLICIT:
    * "raw"    — land the unconverted qty (kitchen reality; the
                 movement row records both units)
    * "raise"  — ValueError (fiscal/stockout paths that must not guess)
- apply_sale() in costing.py stays the sale-path SSOT (AGENTS.md rule 8
  — do NOT route sales through this module; the delegation is locked
  by tests/test_sale_create_writes_stock_movement.py).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.rms.models import Ingredient, StockMovement

MismatchPolicy = Literal["raw", "raise"]


def qty_to_stock_unit(
    qty: float,
    from_unit: str | None,
    ing: Ingredient,
    *,
    on_mismatch: MismatchPolicy = "raw",
) -> float:
    """Convert ``qty`` from ``from_unit`` to ``ing.unit``.

    Same-unit or empty units pass through unchanged. Cross-family
    (e.g. 'und' vs 'kg') follows ``on_mismatch``:
      - "raw": return the qty as-is (caller lands it; record both
        units in the movement reason)
      - "raise": raise ValueError (route maps to HTTP 400)
    """
    qty_f = float(qty or 0)
    if not from_unit or not ing.unit or from_unit == ing.unit:
        return qty_f

    from app.rms.units import Unit, can_convert, convert_qty

    try:
        src = Unit.coerce(from_unit)
        dst = Unit.coerce(ing.unit)
    except (ValueError, KeyError):
        if on_mismatch == "raise":
            raise ValueError(
                f"Unidad desconocida {from_unit!r} para {ing.unit!r}"
            ) from None
        return qty_f

    if not can_convert(src, dst):
        if on_mismatch == "raise":
            raise ValueError(
                f"No se puede convertir {from_unit} a {ing.unit} (familia distinta)"
            )
        return qty_f

    return float(convert_qty(qty_f, src, dst))


def apply_stock_delta(
    session: Session,
    ing: Ingredient,
    delta: float,
    *,
    movement_type: str,
    reason: str,
    reference_id: int | None = None,
    reference_type: str | None = None,
    created_by: str | None = None,
    recorded_at: datetime | None = None,
) -> StockMovement:
    """Bump ``ing.stock_qty`` by ``delta`` and write the audit movement.

    delta > 0 = stock in (compra, restock, ajuste +), delta < 0 = out
    (merma paths pass negative directly; sale decrements stay in
    costing.apply_sale per AGENTS.md rule 8).

    Does NOT commit — the route owns the transaction (safe_commit).
    Returns the movement row for further assertions.
    """
    delta_f = float(delta)
    ing.stock_qty = (ing.stock_qty or 0.0) + delta_f
    movement = StockMovement(
        ingredient_id=ing.id,
        movement_type=movement_type,
        qty=delta_f,
        reason=reason,
        reference_id=reference_id,
        reference_type=reference_type,
        recorded_at=recorded_at or datetime.now(timezone.utc),
        created_by=created_by,
    )
    session.add(movement)
    return movement
