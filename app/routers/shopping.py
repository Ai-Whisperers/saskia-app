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

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
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


_FLOAT_LONG = __import__("re").compile(r"\d+\.\d{3,}")


def _clean_purpose(text: str | None) -> str | None:
    """Round long floats in purpose text (0.253333333333326 → 0.25)."""
    if not text:
        return text
    return _FLOAT_LONG.sub(lambda m: f"{float(m.group(0)):.2f}", text)


def consolidate_open_items(session: Session) -> int:
    """Merge open items sharing (ingredient_id, unit) into one row.

    Three flows create items (planner save, sync-low-stock, plan→list) and
    each used to write its own row — the list showed the same ingredient
    2-3×. Idempotent: merges are only possible while duplicates exist.
    Returns the number of rows deleted.

    Merged purpose keeps short keys: 'Plan #1 (1× Carrot Cake...)' →
    'Plan #1'; 'Auto: stock ...' → 'Auto'; joined with ' + '.
    """
    import re as _re

    open_items = session.execute(
        select(ShoppingListItem).where(ShoppingListItem.purchased.is_(False))
    ).scalars().all()
    buckets: dict[tuple, list] = {}
    for it in open_items:
        buckets.setdefault((it.ingredient_id, it.unit), []).append(it)

    deleted = 0
    for (ing_id, _unit), rows in buckets.items():
        if len(rows) < 2:
            # Still clean float garbage in single rows.
            for it in rows:
                clean = _clean_purpose(it.purpose_text)
                if clean != it.purpose_text:
                    it.purpose_text = clean
            continue
        keep = rows[0]  # newest (ordered by created_at desc)
        keep.qty_to_buy = sum(float(r.qty_to_buy or 0) for r in rows)
        keys: list[str] = []
        for r in rows:
            p = r.purpose_text or ""
            m = _re.match(r"(Plan #\d+[^+]*)", p)
            key = m.group(1).strip() if m else ("Auto" if p.startswith("Auto") else p[:40])
            if key and key not in keys:
                keys.append(key)
        keep.purpose_text = " + ".join(keys) if keys else None
        for r in rows[1:]:
            session.delete(r)
            deleted += 1
    session.commit()
    return deleted


def _whatsapp_href(supplier, rows) -> str | None:
    """Prefilled wa.me link for a supplier's open items (Py py-side so no
    custom Jinja filter is needed). Normalizes PY phones: 9-digit local
    numbers get 595 prefix; already-international (starts with +) keep."""
    from urllib.parse import quote

    if supplier is None or not supplier.phone:
        return None
    open_rows = [r for r in rows if not r.purchased]
    if not open_rows:
        return None
    digits = "".join(c for c in supplier.phone if c.isdigit())
    if digits.startswith("595"):
        pass
    elif len(digits) == 9:  # PY mobile without country code
        digits = "595" + digits
    names = "\n".join(
        f"• {r.ingredient.name} ({r.qty_to_buy:g} {r.unit})"
        for r in open_rows
        if r.ingredient is not None
    )
    text = f"Hola! Quiero hacer un pedido:\n{names}\nGracias!"
    return f"https://wa.me/{digits}?text={quote(text)}"


@router.get("", response_class=HTMLResponse)
def shopping_list_index(
    request: Request,
    show_purchased: bool = Query(False),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Show the shopping list. Default = open only (purchased=0).

    Starts by consolidating duplicate open items (planner + auto-sync +
    plan→list flows each wrote their own rows) so Saskia always sees one
    row per ingredient.
    """
    consolidate_open_items(session)

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

    # Sprint shopping-list: group open items by the ingredient's supplier so
    # Saskia can call each proveedor once. Open (unpurchased) items group
    # first (that's the calling list); purchased items land in "Comprados".
    supplier_groups: list[dict] = []
    if items:
        groups: dict[tuple, dict] = {}
        for i in items:
            sup = i.ingredient.supplier if i.ingredient else None
            key = ("none", None) if sup is None else (sup.id, sup.name)
            g = groups.setdefault(key, {"supplier": sup, "rows": []})
            g["rows"].append(i)
        # Named suppliers first (alphabetical), "Sin proveedor" last.
        for g in groups.values():
            g["open_total_gs"] = sum(
                (i.ingredient.purchase_price_gs or 0) * (i.qty_to_buy or 0)
                for i in g["rows"]
                if not i.purchased
            )
            g["wa_href"] = _whatsapp_href(g["supplier"], g["rows"])
        supplier_groups = sorted(
            groups.values(),
            key=lambda g: (
                g["supplier"] is None,
                g["supplier"].name if g["supplier"] else "",
            ),
        )

    return render(
        request,
        "shopping_list.html",
        {
            "items": items,
            "total_gs": total_gs,
            "show_purchased": show_purchased,
            "by_ingredient": by_ingredient,
            "supplier_groups": supplier_groups,
            "open_count": sum(1 for i in items if not i.purchased),
            "purchased_count": sum(1 for i in items if i.purchased),
        },
    )


@router.post("/{item_id}/mark-purchased")
def mark_purchased(
    request: Request,
    item_id: int,
    session: Session = Depends(get_session),
) -> object:
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
) -> object:
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
) -> object:
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


@router.post("/from-production-plan")
def from_production_plan(
    request: Request,
    for_date: date = Form(...),
    session: Session = Depends(get_session),
) -> object:
    """One click: today's production plan shortages → shopping list.

    Takes plan_production(for_date).lines (sub-recipes exploded via
    explode_recipe), keeps only rows with qty_to_buy > 0, and appends
    them as ShoppingListItem rows (deduped against open items — an
    ingredient already on the open list is topped up to the max of the
    two quantities, never duplicated).

    purpose_text carries the date so Saskia can see WHY she's buying
    ("Plan producción 2026-09-30"). Items are NOT tied to a
    ProductionPlan row because the day plan is computed on the fly, not
    persisted; the FK stays for the recipe-planner flow.
    """
    from app.rms.production import plan_production
    from app.rms.rate_limit import is_write_rate_limited

    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )

    plan = plan_production(session, for_date=for_date)
    shortages = [ln for ln in plan.lines if ln.qty_to_buy > 0]
    if not shortages:
        return RedirectResponse(
            url=f"/shopping-list?from_plan=0&for_date={for_date.isoformat()}",
            status_code=303,
        )

    existing = session.execute(
        select(ShoppingListItem).where(ShoppingListItem.purchased.is_(False))
    ).scalars().all()
    existing_by_ing = {}
    for i in existing:
        existing_by_ing[i.ingredient_id] = existing_by_ing.get(
            i.ingredient_id, 0
        ) + float(i.qty_to_buy)

    purpose = f"Plan producción {for_date.isoformat()}"
    added = 0
    for ln in shortages:
        have = existing_by_ing.get(ln.ingredient_id, 0.0)
        need = float(ln.qty_to_buy)
        if ln.ingredient_id in existing_by_ing:
            # Top up the open item if the plan needs more than already listed.
            if need > have:
                delta = need - have
                for i in existing:
                    if i.ingredient_id == ln.ingredient_id:
                        i.qty_to_buy += delta
                        break
                added += 1
            continue
        session.add(
            ShoppingListItem(
                ingredient_id=ln.ingredient_id,
                qty_to_buy=need,
                unit=ln.unit,
                purpose_text=purpose,
            )
        )
        existing_by_ing[ln.ingredient_id] = need
        added += 1
    session.commit()
    return RedirectResponse(
        url=f"/shopping-list?from_plan={added}&for_date={for_date.isoformat()}",
        status_code=303,
    )


@router.post("/sync-low-stock")
def sync_low_stock(
    session: Session = Depends(get_session),
) -> object:
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
) -> object:
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
) -> object:
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
