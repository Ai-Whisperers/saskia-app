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


# Fallback target stock when max_stock_qty is NULL/0: 2× effective_min,
# or 10 when effective_min is 0 (matches prior one-liner).
_MIN_MAX_STOCK = 10.0
_URGENCY_DENOM_FLOOR = 0.001  # avoid div-by-zero when effective_min is 0


def _effective_min(ing: Ingredient) -> float:
    """Return the effective reorder threshold for an ingredient.

    `reorder_point` overrides `min_stock_qty` when set; otherwise the
    legacy min_stock_qty is used. INV-03 spec.
    """
    return ing.reorder_point if ing.reorder_point is not None else ing.min_stock_qty


def _urgency_label(display_stock: float, effective_min: float) -> str:
    """INV-03 Spanish urgency label — see tests/test_phase2_review_tickets.py."""
    if display_stock <= 0:
        return "sin stock"
    if display_stock < effective_min:
        return "bajo mínimo"
    return "OK"


def _target_max_qty(effective_min: float, raw_max: float | None) -> float:
    """Choose the max stock target, falling back to 2× effective_min.

    The fallback uses `_MIN_MAX_STOCK` (10) when effective_min is 0 to
    avoid a zero-qty buy suggestion on a fresh ingredient.
    """
    if raw_max:
        return raw_max
    return effective_min * 2 if effective_min > 0 else _MIN_MAX_STOCK


def _urgency_ratio(display_stock: float, effective_min: float) -> float:
    """`stock_qty / min_stock_qty` clamped to avoid div-by-zero."""
    if effective_min <= 0:
        return 0.0
    return display_stock / max(effective_min, _URGENCY_DENOM_FLOOR)


def _build_reorder_item(ing: Ingredient) -> ReorderItem | None:
    """Build a `ReorderItem` for an ingredient below its effective min.

    Returns None when the ingredient is at or above the threshold — they
    don't need reordering and must be filtered out of the result list.
    INV-03 clamping rules are honored here (display stock ≥ 0, no-price
    items get cost 0, urgency label uses display stock not raw stock).
    """
    effective_min = _effective_min(ing)
    # INV-03: clamp at 0 for display. The raw stock stays in the DB so the
    # oversell is visible in /merma and /ventas.
    display_stock = max(0.0, ing.stock_qty)
    if display_stock >= effective_min:
        return None

    # INV-03: suggested uses the CLAMPED stock so a negative actual doesn't
    # inflate the buy (e.g. manteca at -0.01 + max 2.00 should suggest 2.01,
    # not 4.01).
    max_q = _target_max_qty(effective_min, ing.max_stock_qty)
    suggested = max(0.0, max_q - display_stock)

    # INV-03: estimated_cost is 0 when no price is set. The footer total
    # excludes these lines (see template).
    has_price = ing.purchase_price_gs is not None and ing.purchase_price_gs > 0
    cost = int(suggested * (ing.purchase_price_gs or 0)) if has_price else 0

    urgency_ratio = _urgency_ratio(display_stock, effective_min)
    urgency_label = _urgency_label(display_stock, effective_min)

    return ReorderItem(
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
    )


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

    Behavior (CHARACTER-FOR-CHARACTER identical to the pre-refactor function):
      - query is `session.query(Ingredient).all()`
      - items are filtered by `display_stock >= effective_min → skip`
      - max_q fallback: `raw_max or (effective_min*2 if effective_min>0 else 10.0)`
      - suggested = `max(0.0, max_q - display_stock)`
      - cost = `int(suggested * price) if has_price else 0`
        where `has_price = purchase_price_gs is not None and > 0`
      - urgency_ratio = `display_stock / max(effective_min, 0.001)` if `effective_min > 0` else `0.0`
      - urgency_label = "sin stock" if `display_stock <= 0`,
                       "bajo minimum" if `display_stock < effective_min`,
                       else "OK"
      - sort: smallest urgency_ratio first (`items.sort(key=lambda i: i.urgency)`)
    """
    return sorted(
        (
            item
            for ing in session.query(Ingredient).all()
            for item in [_build_reorder_item(ing)]
            if item is not None
        ),
        key=lambda i: i.urgency,
    )


__all__ = ["ReorderItem", "compute_reorder_list"]
