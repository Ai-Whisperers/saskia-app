"""app/rms/reorder_supplier_prices.py — read-only per-supplier price lookup.

Migration 072 added columns to ``ingredient`` (last_purchase_supplier_id
+ locked_supplier_id + purchase_streak_count). The ``/reorder`` page
needs to show "what does each supplier charge for this ingredient?" on
the dropdown, so the operator can pick a different supplier when one is
on sale or she's running low on stock of the locked one.

Source of truth: there is no per-supplier price table yet (the
``ingredient_variant`` table is empty — see ``supplier_prices.py`` for
the richer comparison engine). The cheapest honest source for "what did
we pay last time at supplier X" is the most recent ``IngredientPriceEvent``
*somehow* associated with supplier X.

For now, until the operator starts recording per-supplier purchases
(every ``/reorder/registrar`` call will start writing them), the helper
returns:
  * ``current_gs`` — the parent-level ``purchase_price_gs`` (the "current
    catalog price"). Always returned for the locked supplier.
  * ``other_prices`` — empty dict (no data yet) until the operator records
    per-supplier purchases.

When the operator submits a restock with a specific supplier, the
helper starts to populate the per-supplier prices from the live price
event stream. This module deliberately does NOT fabricate or estimate
prices — empty data is shown as "sin registro" in the dropdown.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import Ingredient, IngredientPriceEvent, Supplier

# We don't have a per-supplier price history table yet. Once the operator
# has logged enough per-supplier purchases to fill in the dropdown
# prices, we can promote this to a real comparison view. For now, return
# the parent-level price for the locked/default supplier and leave the
# other suppliers' prices as None (UI shows "—").
#
# The price-event table has no supplier_id column (verified 2026-09-30 —
# the schema only tracks ingredient-level prices). Per-supplier prices
# will need a future migration to add supplier_id to
# ingredient_price_event. Until then, the dropdown shows "—" for
# suppliers we don't have data for.


def get_supplier_price_options(
    session: Session,
    ingredient_id: int,
) -> dict[int, Optional[int]]:
    """Return ``{supplier_id: price_gs_or_None}`` for every active supplier.

    ``price_gs_or_None`` is the **most recent** price the system has on
    record for that supplier + ingredient. Currently this is always the
    parent's ``purchase_price_gs`` (since we have no per-supplier
    history), returned for the effective supplier, and ``None`` for
    every other supplier. The UI shows "—" for ``None``.

    Returns a dict keyed by ``supplier.id``. Empty if the ingredient
    doesn't exist.
    """
    ing = session.get(Ingredient, ingredient_id)
    if ing is None:
        return {}

    # All active suppliers, sorted by name ASC. The dropdown shows them
    # alphabetically so the operator can scan visually — not by price,
    # because right now we only have one price per ingredient (the parent).
    suppliers = session.scalars(
        select(Supplier).where(Supplier.is_active).order_by(Supplier.name)
    ).all()

    effective_id = ing.locked_supplier_id or ing.last_purchase_supplier_id or ing.supplier_id

    out: dict[int, Optional[int]] = {}
    parent_price = ing.purchase_price_gs
    for s in suppliers:
        if s.id == effective_id:
            out[s.id] = parent_price
        else:
            # No per-supplier data yet → "—" in the dropdown. Once the
            # operator records per-supplier purchases, this will start
            # filling in (see future migration: add supplier_id to
            # ingredient_price_event).
            out[s.id] = None

    return out


def get_ingredient_price_history_count(
    session: Session,
    ingredient_id: int,
) -> int:
    """How many price events exist for this ingredient. Used by the /reorder
    template to decide whether to show the "history" badge or "—".
    """
    return (
        session.execute(
            select(IngredientPriceEvent).where(IngredientPriceEvent.ingredient_id == ingredient_id)
        )
        .all()
        .__len__()
    )


__all__ = [
    "get_ingredient_price_history_count",
    "get_supplier_price_options",
]
