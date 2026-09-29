"""app/routers/shopping.py — Shopping list module.

Routes:
  GET  /shopping-list              — show open list (all unpurchased)
  POST /shopping-list/{id}/mark    — mark item purchased
  POST /shopping-list/{id}/delete  — remove item
  POST /produccion-planner/{plan_id}/save-as-shopping-list — convert
                                          a ProductionPlan's shortages
                                          into ShoppingListItem rows

Source: HEREBUS_Shoppers_Sheet (Shopping_List); would be manually entered
or derived from Production Planner shortfalls.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.dependencies import get_session
from app.rms.errors import NotFound
from app.rms.models import (
    Ingredient,
    ProductionPlan,
    ShoppingListItem,
)
from app.rms.observability import record_audit
from app.services.template_render import render

router = APIRouter(prefix="/shopping-list", dependencies=[Depends(require_login)])


def price_field(p: float) -> int:
    """Format price as ₲."""
    try:
        return int(p)
    except (TypeError, ValueError):
        return 0


@router.get("", response_class=HTMLResponse)
def shopping_list_index(
    request: Request,
    show_purchased: bool = Query(False),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Show the shopping list. Default = open only (purchased=0)."""
    stmt = select(ShoppingListItem).order_by(
        ShoppingListItem.purchased,
        ShoppingListItem.created_at.desc(),
    )
    if not show_purchased:
        stmt = stmt.where(ShoppingListItem.purchased.is_(False))

    items = session.execute(stmt).scalars().all()

    total_gs = sum(
        price_field(i.qty_to_buy or 0) * (i.ingredient.purchase_price_gs or 0)
        for i in items
    )

    by_ingredient = {}
    for i in items:
        by_ingredient[i.ingredient_id] = by_ingredient.get(i.ingredient_id, 0) + i.qty_to_buy

    return render(
        request,
        "shopping_list.html",
        {
            "items": items,
            "total_gs": total_gs,
            "show_purchased": show_purchased,
            "by_ingredient": by_ingredient,
            "open_count": sum(1 for i in items if not i.purchased),
            "purchased_count": sum(1 for i in items if i.purchased),
        },
    )


@router.post("/{item_id}/mark-purchased")
def mark_purchased(
    request: Request,
    item_id: int,
    session: Session = Depends(get_session),
):
    item = session.get(ShoppingListItem, item_id)
    if not item:
        raise NotFound("ShoppingListItem", id=item_id)
    item.purchased = True
    item.purchased_at = datetime.now(timezone.utc)
    session.commit()
    logger.info(
        "shopping_item_purchased id={} ingredient_id={} qty={} {}",
        item.id, item.ingredient_id, item.qty_to_buy, item.unit,
    )
    record_audit(
        request, session=session,
        action="shopping.mark_purchased", target_type="ShoppingListItem",
        target_id=item.id, detail={"ingredient_id": item.ingredient_id},
    )
    return RedirectResponse(url="/shopping-list", status_code=303)


@router.post("/{item_id}/unmark")
def unmark_purchased(
    request: Request,
    item_id: int,
    session: Session = Depends(get_session),
):
    """Allow marking unpurchased (undo)."""
    item = session.get(ShoppingListItem, item_id)
    if not item:
        raise NotFound("ShoppingListItem", id=item_id)
    item.purchased = False
    item.purchased_at = None
    session.commit()
    logger.info("shopping_item_unmarked id={}", item.id)
    record_audit(
        request, session=session,
        action="shopping.unmark", target_type="ShoppingListItem",
        target_id=item.id,
    )
    return RedirectResponse(url="/shopping-list", status_code=303)


@router.post("/{item_id}/delete")
def delete_item(
    request: Request,
    item_id: int,
    session: Session = Depends(get_session),
):
    item = session.get(ShoppingListItem, item_id)
    if not item:
        raise NotFound("ShoppingListItem", id=item_id)
    session.delete(item)
    session.commit()
    logger.info("shopping_item_deleted id={}", item_id)
    record_audit(
        request, session=session,
        action="shopping.delete", target_type="ShoppingListItem",
        target_id=item_id,
    )
    return RedirectResponse(url="/shopping-list", status_code=303)


@router.post("/sync-low-stock")
def sync_low_stock(
    session: Session = Depends(get_session),
):
    """Bulk-add all ingredients where stock < min to the shopping list.

    Idempotent: skips ingredients already in an open shopping list item.
    """
    from app.rms.models import Ingredient

    low_stock = session.execute(
        select(Ingredient).where(
            Ingredient.min_stock_qty > 0,
            Ingredient.stock_qty < Ingredient.min_stock_qty,
        )
    ).scalars().all()

    existing = session.execute(
        select(ShoppingListItem).where(ShoppingListItem.purchased.is_(False))
    ).scalars().all()
    existing_ing_ids = {i.ingredient_id for i in existing}

    added = 0
    for ing in low_stock:
        if ing.id in existing_ing_ids:
            continue

        # For now, use a simple descriptive format instead of looking up recipes
        # This avoids circular import issues while still being more meaningful than "Auto: stock"
        purpose_text = f"Reposición: {ing.name}"

        needed = (ing.min_stock_qty - ing.stock_qty) * 2
        if needed <= 0:
            continue
        item = ShoppingListItem(
            ingredient_id=ing.id,
            qty_to_buy=needed,
            unit=ing.unit,
            purpose_text=purpose_text,
        )
        session.add(item)
        added += 1
    session.commit()
    return RedirectResponse(
        url=f"/shopping-list?from_sync={added}",
        status_code=303,
    )


@router.post("/add")
def add_item(
    request: Request,
    ingredient_id: int = Form(...),
    qty_to_buy: float = Form(...),
    unit: str = Form(...),
    purpose_text: str = Form(""),
    session: Session = Depends(get_session),
):
    """Manual addition to the shopping list."""
    ing = session.get(Ingredient, ingredient_id)
    if not ing or qty_to_buy <= 0:
        return RedirectResponse(url="/shopping-list", status_code=303)
    item = ShoppingListItem(
        ingredient_id=ingredient_id,
        qty_to_buy=qty_to_buy,
        unit=unit or ing.unit,
        purpose_text=purpose_text or "Manual addition",
    )
    session.add(item)
    session.commit()
    return RedirectResponse(url="/shopping-list", status_code=303)


# ──────────────────────────────────────────────────────────────────
# Cross-router endpoint: convert a Production Plan to Shopping List
# ──────────────────────────────────────────────────────────────────


@router.post("/save-plan/{plan_id}")
def save_plan_as_shopping_list(
    plan_id: int,
    session: Session = Depends(get_session),
):
    """Convert a ProductionPlan's ingredient shortage into ShoppingListItem rows.

    Triggered from /produccion-planner — the planning flow ends here.
    Only items where qty_needed > stock_available get added.
    """
    plan = session.get(ProductionPlan, plan_id)
    if not plan:
        return RedirectResponse(url="/shopping-list", status_code=303)

    n_added = 0
    for line in plan.recipe.lines:
        if line.line_kind != "ingredient":
            continue
        ing = session.get(Ingredient, line.line_ref_id)
        if not ing:
            continue
        qty_needed = (line.qty or 0) * plan.batches_qty
        shortage = round(max(0, qty_needed - ing.stock_qty), 4)
        if shortage <= 0:
            continue
        item = ShoppingListItem(
            ingredient_id=ing.id,
            production_plan_id=plan.id,
            qty_to_buy=shortage,
            unit=line.line_unit or ing.unit,
            purpose_text=f"Plan #{plan.id} ({plan.batches_qty}× {plan.recipe.name})",
        )
        session.add(item)
        n_added += 1
    plan.status = "planned"
    session.commit()
    return RedirectResponse(
        url=f"/shopping-list?from_plan={plan.id}&n_added={n_added}",
        status_code=303,
    )


__all__ = ["router"]
