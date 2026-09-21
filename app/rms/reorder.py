"""app/rms/reorder.py — generates reorder suggestions from current stock state.

For each ingredient where stock_qty < min_stock_qty, suggest:
    suggested_qty = max(0, max_stock_qty - stock_qty)
    estimated_cost_gs = suggested_qty * purchase_price_gs

If max_stock_qty is not set (NULL or 0), fall back to 2x min_stock_qty.

Output is sorted by urgency:
    urgency = stock_qty / max(min_stock_qty, 0.001)  — smaller = more urgent
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.rms.models import Ingredient


@dataclass
class ReorderItem:
    """A single ingredient that needs reordering."""

    ingredient_id: int
    name: str
    unit: str
    current_stock: float
    min_stock: float
    max_stock: float
    suggested_qty: float
    estimated_cost_gs: int
    purchase_price_gs: int | None  # current price, prefilled in the restock form
    urgency: float  # 0.0 = out of stock, 1.0 = at min, >1.0 = above min


def compute_reorder_list(session: Session) -> list[ReorderItem]:
    """Return all ingredients below their min_stock, sorted by urgency."""
    items: list[ReorderItem] = []
    ingredients = session.query(Ingredient).all()
    for ing in ingredients:
        if ing.stock_qty >= ing.min_stock_qty:
            continue
        # Fallback for max_stock_qty: 2x min, or 10 if min is 0.
        max_q = ing.max_stock_qty or (ing.min_stock_qty * 2 if ing.min_stock_qty > 0 else 10.0)
        suggested = max(0.0, max_q - ing.stock_qty)
        cost = int(suggested * (ing.purchase_price_gs or 0))
        urgency = (
            ing.stock_qty / max(ing.min_stock_qty, 0.001)
            if ing.min_stock_qty > 0
            else 0.0
        )
        items.append(ReorderItem(
            ingredient_id=ing.id,
            name=ing.name,
            unit=ing.unit or "",
            current_stock=ing.stock_qty,
            min_stock=ing.min_stock_qty,
            max_stock=max_q,
            suggested_qty=suggested,
            estimated_cost_gs=cost,
            purchase_price_gs=ing.purchase_price_gs,
            urgency=urgency,
        ))
    # Smallest urgency ratio = most urgent first.
    items.sort(key=lambda i: i.urgency)
    return items


__all__ = ["ReorderItem", "compute_reorder_list"]
