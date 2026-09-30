"""app/rms/supplier_history.py — track per-ingredient purchase-supplier history.

Migration 072 (2026-09-30) added four columns to ``ingredient`` so the
``/reorder`` page can:

  1. Pre-select the right supplier on the dropdown (``last_purchase_supplier_id``).
  2. Show a "fijo" badge + auto-lock the dropdown when the same supplier
     has been used 3+ times in a row (``locked_supplier_id``).
  3. Show other suppliers' prices inline on the dropdown as the data fills in
     (from ``IngredientPriceEvent`` history keyed to supplier).

This module owns the **streak / lock** logic that gets called from
``/reorder/registrar`` after every successful restock. It's intentionally
small and side-effect free except for the targeted SQLAlchemy writes
described in each function.

Why a separate module instead of inlining in ``reorder.py``:
  - ``reorder.py`` is presentation-oriented (the ReorderItem dataclass +
    ``compute_reorder_list``). Mixing write-side state transitions there
    muddies the read-only contract.
  - Tests want to drive ``record_purchase_supplier`` directly without
    routing through HTTP.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.rms.models import Ingredient

# After this many consecutive buys from the same supplier, the dropdown
# on /reorder auto-locks to that supplier with a "fijo" badge. Once
# locked, picking a different supplier resets the streak to 1 (so the
# operator can re-learn a new supplier if circumstances change).
LOCK_THRESHOLD = 3


def get_effective_supplier_id(ing: Ingredient) -> Optional[int]:
    """Pick the supplier the dropdown should default to on /reorder.

    Priority:
      1. ``locked_supplier_id`` (the 3-streak auto-lock) — wins because it
         represents observed behaviour: she's been buying from here
         reliably for 3+ purchases in a row.
      2. ``last_purchase_supplier_id`` — the most recent actual purchase.
         Pre-seeded from ``supplier_id`` on migration 072 so existing
         ingredients don't show "sin registro" on first load.
      3. ``supplier_id`` — the legacy parent-level default. Used as a
         last-resort fallback.
      4. ``None`` — she has no supplier on file; the dropdown renders an
         empty cell with a "Elegir proveedor" prompt.
    """
    return (
        ing.locked_supplier_id
        or ing.last_purchase_supplier_id
        or ing.supplier_id
    )


def record_purchase_supplier(
    session: Session,
    ingredient_id: int,
    supplier_id: int,
) -> None:
    """Update streak / lock counters after a successful restock.

    Behaviour:
      * If the new purchase is from the same supplier as the most recent
        one (``last_purchase_supplier_id``), increment
        ``purchase_streak_count``.
      * Otherwise, reset the streak to 1 (the streak starts at 1, not 0,
        because this purchase itself counts as "1 in a row").
      * When the streak reaches ``LOCK_THRESHOLD`` (3), set
        ``locked_supplier_id`` so future visits to /reorder auto-default
        to this supplier with a "fijo" badge.
      * Picking a different supplier when one is already locked resets the
        streak (operator explicitly opted out — don't keep the lock).
      * ``last_purchase_supplier_id`` and ``last_purchase_at`` are always
        updated to the new values (most recent restock wins).

    Args:
        session: SQLAlchemy session. Caller is expected to ``commit()``
            after this returns.
        ingredient_id: The ingredient just restocked.
        supplier_id: The supplier she actually bought from on this restock.

    Raises:
        ValueError: If the ingredient doesn't exist.
    """
    ing = session.get(Ingredient, ingredient_id)
    if ing is None:
        raise ValueError(f"ingredient {ingredient_id} not found")

    now = datetime.now(timezone.utc)

    previous = ing.last_purchase_supplier_id
    locked = ing.locked_supplier_id

    # Always overwrite the "most recent" pointer — even if the operator
    # switches suppliers, the next visit to /reorder should default to the
    # supplier she used most recently.
    ing.last_purchase_supplier_id = supplier_id
    ing.last_purchase_at = now

    # Streak logic: same as before → +1; different → reset to 1.
    if previous == supplier_id:
        new_streak = (ing.purchase_streak_count or 0) + 1
    else:
        new_streak = 1

    ing.purchase_streak_count = new_streak

    # Lock logic: only promote to locked when the streak hits the threshold
    # AND we're not in the "operator just overrode the lock" state.
    # We DO re-lock if the streak crosses the threshold on the new supplier,
    # which is the correct behaviour: she's clearly committed.
    if new_streak >= LOCK_THRESHOLD:
        ing.locked_supplier_id = supplier_id
    elif locked is not None and locked != supplier_id and previous == locked:
        # Operator explicitly picked a different supplier from the one
        # that's currently locked (i.e. previous was the locked one, now
        # they're picking something else). Clear the lock so the dropdown
        # doesn't keep auto-snap. We only fire when previous actually was
        # the locked supplier — otherwise the lock came from somewhere
        # else and we shouldn't disturb it.
        ing.locked_supplier_id = None


def clear_lock(session: Session, ingredient_id: int) -> None:
    """Reset the auto-lock and streak for an ingredient.

    Useful when the operator explicitly says "stop locking this to
    Casa Rica — I want to re-decide each time" from the inventory edit
    page (future feature; not exposed in this PR).
    """
    ing = session.get(Ingredient, ingredient_id)
    if ing is None:
        return
    ing.locked_supplier_id = None
    ing.purchase_streak_count = 0


__all__ = [
    "LOCK_THRESHOLD",
    "clear_lock",
    "get_effective_supplier_id",
    "record_purchase_supplier",
]