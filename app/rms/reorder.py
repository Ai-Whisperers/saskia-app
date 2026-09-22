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
    urgency: float  # 0.0 = out of stock, 1.0 = at min, >1.0 = above min (sort key only)
    urgency_label: str  # INV-03: "sin stock" / "bajo mínimo" / "OK" (Spanish)
    has_price: bool  # INV-03: false when purchase_price_gs is 0/None (line excluded from total)


def compute_reorder_list(session: Session) -> list[ReorderItem]:
    """Return all ingredients below their min_stock (or reorder_point if set), sorted by urgency.

    INV-03 (review Sept 18):
      - current_stock is clamped to ≥0 for display (oversells are recorded on the
        sale / merma, not masked here)
      - suggested_qty = max(0, max_q - clamped_stock) so a negative actual doesn't
        inflate the buy
      - urgency is converted to a Spanish label ("sin stock" / "bajo mínimo" /
        "OK") at the presentation layer, with the raw ratio still available as
        `urgency_ratio`
      - estimated_cost_gs stays at 0 when there's no purchase price; the
        template / footer total must exclude those lines.
    """
    items: list[ReorderItem] = []
    ingredients = session.query(Ingredient).all()
    for ing in ingredients:
        # Use reorder_point override if set, otherwise fall back to min_stock_qty
        effective_min = ing.reorder_point if ing.reorder_point is not None else ing.min_stock_qty
        # INV-03: clamp at 0 for display. The raw stock stays in the DB so the
        # oversell is visible in /merma and /ventas.
        display_stock = max(0.0, ing.stock_qty)
        if display_stock >= effective_min:
            continue
        # Fallback for max_stock_qty: 2x effective_min, or 10 if effective_min is 0.
        max_q = ing.max_stock_qty or (effective_min * 2 if effective_min > 0 else 10.0)
        # INV-03: suggested uses the CLAMPED stock so a negative actual doesn't
        # inflate the buy (e.g. manteca at -0.01 + max 2.00 should suggest 2.01,
        # not 4.01).
        suggested = max(0.0, max_q - display_stock)
        # INV-03: estimated_cost is 0 when no price is set. The footer total
        # excludes these lines (see template).
        has_price = ing.purchase_price_gs is not None and ing.purchase_price_gs > 0
        cost = int(suggested * (ing.purchase_price_gs or 0)) if has_price else 0
        urgency_ratio = (
            display_stock / max(effective_min, 0.001)
            if effective_min > 0
            else 0.0
        )
        # INV-03: Spanish urgency label per the review. The raw ratio is kept
        # for sorting only.
        if display_stock <= 0:
            urgency_label = "sin stock"
        elif display_stock < effective_min:
            urgency_label = "bajo mínimo"
        else:
            urgency_label = "OK"
        items.append(ReorderItem(
            ingredient_id=ing.id,
            name=ing.name,
            unit=ing.unit or "",
            current_stock=display_stock,
            min_stock=effective_min,
            max_stock=max_q,
            suggested_qty=suggested,
            estimated_cost_gs=cost,
            purchase_price_gs=ing.purchase_price_gs,
            urgency=urgency_ratio,
            urgency_label=urgency_label,
            has_price=has_price,
        ))
    # Smallest urgency ratio = most urgent first.
    items.sort(key=lambda i: i.urgency)
    return items


__all__ = ["ReorderItem", "compute_reorder_list"]
