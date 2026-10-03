"""app/rms/supplier_history.py — per-ingredient supplier lock + audit.

Migration 072 (2026-09-30) added columns to ``ingredient`` so the
``/reorder`` page can:

  1. Pre-select the right supplier on the dropdown
     (``last_purchase_supplier_id``) — "where she last bought this".
  2. Optionally pin a supplier to an ingredient (``locked_supplier_id``)
     so she doesn't need to re-pick it every restock — MANUAL toggle
     only (no auto-streak). Set via the 🔒 button on /reorder or in
     /inventario.
  3. Show other suppliers' prices inline on the dropdown as the data
     fills in (from ``IngredientPriceEvent`` history keyed to supplier).

Design rationale (replaces earlier 3-streak auto-lock):

  Auto-locking the dropdown from observed behaviour was tempting but
  produced surprise moments ("why is harina pinned to Stock PY?"). The
  operator's mental model is "some ingredients are specialty — I want
  to mark them and forget about them." Manual toggle wins:

    * She knows better than the algorithm when something is specialty.
    * "Set once, never think about it again" is the "easy and nice" UX.
    * No "auto-lock happened, I don't know why" surprises.

  The ``purchase_streak_count`` column is kept (and incremented on every
  restock) purely for **analytics**: future dashboards can surface "you
  buy harina from Stock PY 87% of the time — lock it?" suggestions,
  but no behaviour change happens automatically.

This module owns:

  - ``record_purchase_supplier()`` — called from /reorder/registrar
    after every restock. Updates the most-recent pointer + streak
    counter. Never sets/clears the lock automatically.
  - ``lock_supplier()`` / ``unlock_supplier()`` — manual toggle
    endpoints. Both write an audit row.
  - ``get_effective_supplier_id()`` — pick the dropdown default.
    Priority: locked > last_purchase > supplier_id.

Side-effect discipline: every state change here writes ONE audit row
via ``audit_record()``. The audit log is the source of truth for
"who locked/unlocked what when" — the ``ingredient.locked_supplier_id``
column is the current cache.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.rms.audit import record as audit_record
from app.rms.models import Ingredient

# Kept for analytics. No auto-lock behaviour anymore; the constant is
# exported because the supplier-suggestion dashboard (planned) will
# surface "lock this?" when streak crosses this threshold.
STREAK_SUGGEST_THRESHOLD = 3


def get_effective_supplier_id(ing: Ingredient) -> Optional[int]:
    """Pick the supplier the dropdown should default to on /reorder.

    Priority:
      1. ``locked_supplier_id`` (manual lock from the 🔒 button) — wins
         because she explicitly asked for it.
      2. ``last_purchase_supplier_id`` — the most recent actual purchase.
         Pre-seeded from ``supplier_id`` on migration 072 so existing
         ingredients don't show "sin registro" on first load.
      3. ``supplier_id`` — the legacy parent-level default. Used as a
         last-resort fallback.
      4. ``None`` — she has no supplier on file; the dropdown renders
         an empty cell with a "Elegir proveedor" prompt.
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
    """Update the most-recent pointer + streak after a successful restock.

    Does NOT change ``locked_supplier_id`` (manual-only). If the new
    purchase is from a supplier that ISN'T the locked one, the streak
    counter still increments because the streak is "how often am I
    actually buying from here" — useful for analytics.

    Args:
        session: SQLAlchemy session. Caller commits.
        ingredient_id: The ingredient just restocked.
        supplier_id: The supplier she actually bought from on this restock.

    Raises:
        ValueError: If the ingredient doesn't exist.
    """
    ing = session.get(Ingredient, ingredient_id)
    if ing is None:
        raise ValueError(f"ingredient {ingredient_id} not found")

    previous = ing.last_purchase_supplier_id

    ing.last_purchase_supplier_id = supplier_id
    ing.last_purchase_at = datetime.now(timezone.utc)

    if previous == supplier_id:
        ing.purchase_streak_count = (ing.purchase_streak_count or 0) + 1
    else:
        ing.purchase_streak_count = 1


def lock_supplier(
    session: Session,
    ingredient_id: int,
    supplier_id: int,
    *,
    actor: str = "system",
    reason: str = "",
) -> None:
    """Manually pin an ingredient to a supplier.

    Sets ``locked_supplier_id = supplier_id`` and writes an audit row
    so we can answer "who locked what when" later.

    Args:
        session: SQLAlchemy session. Caller commits.
        ingredient_id: The ingredient to lock.
        supplier_id: The supplier to pin it to.
        actor: Username who triggered the lock (for audit).
        reason: Free-text reason (optional).
    """
    ing = session.get(Ingredient, ingredient_id)
    if ing is None:
        raise ValueError(f"ingredient {ingredient_id} not found")
    if ing.locked_supplier_id == supplier_id:
        return  # already locked to this supplier — no-op

    previous = ing.locked_supplier_id
    ing.locked_supplier_id = supplier_id

    audit_record(
        session,
        action="ingredient.supplier.lock",
        user_id=actor,
        target_type="ingredient",
        target_id=str(ingredient_id),
        detail={
            "supplier_id": supplier_id,
            "previous_locked_supplier_id": previous,
            "reason": reason,
        },
    )


def unlock_supplier(
    session: Session,
    ingredient_id: int,
    *,
    actor: str = "system",
    reason: str = "",
) -> None:
    """Manually clear the lock on an ingredient.

    No-op if there is no lock. Writes an audit row with the supplier
    that was previously locked.
    """
    ing = session.get(Ingredient, ingredient_id)
    if ing is None:
        raise ValueError(f"ingredient {ingredient_id} not found")
    if ing.locked_supplier_id is None:
        return

    previous = ing.locked_supplier_id
    ing.locked_supplier_id = None

    audit_record(
        session,
        action="ingredient.supplier.unlock",
        user_id=actor,
        target_type="ingredient",
        target_id=str(ingredient_id),
        detail={
            "previous_locked_supplier_id": previous,
            "reason": reason,
        },
    )


# Backwards-compat alias for tests + the audit module. The old name is
# still imported in a couple of test files; keep it as a no-op so we
# don't break them mid-refactor.
def clear_lock(session: Session, ingredient_id: int) -> None:
    """Deprecated. Use ``unlock_supplier()`` instead."""
    unlock_supplier(session, ingredient_id)


# LOCK_THRESHOLD used to be the auto-lock threshold; renamed to
# STREAK_SUGGEST_THRESHOLD and exported under the old name for any
# external code that still imports it (analytics dashboards, etc.).
LOCK_THRESHOLD = STREAK_SUGGEST_THRESHOLD


__all__ = [
    "LOCK_THRESHOLD",
    "STREAK_SUGGEST_THRESHOLD",
    "clear_lock",
    "get_effective_supplier_id",
    "lock_supplier",
    "record_purchase_supplier",
    "unlock_supplier",
]
