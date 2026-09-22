"""app/routers/inventory.py — CRUD endpoints for ingredients.

Per dev plan §9 Task 3.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.charts import sparkline
from app.rms.dependencies import get_session
from app.rms.models import Ingredient, IngredientPriceEvent, RecipeLine, Recipe, StockMovement
from app.rms.price_history import price_history, price_stats, record_price_event
from app.rms.units import Unit
from app.services.template_render import render

router = APIRouter(prefix="/inventario", dependencies=[Depends(require_login)])


@router.get("/export.csv")
def inventory_export_csv(
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    """Export all ingredients as a CSV download."""
    ingredients = session.scalars(select(Ingredient).order_by(Ingredient.name)).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "name", "unit", "category", "stock_qty", "min_stock_qty",
        "purchase_price_gs", "opening_stock_qty", "opening_stock_date",
        "reorder_point", "notes",
    ])
    for i in ingredients:
        writer.writerow([
            i.id,
            i.name,
            i.unit,
            i.category or "",
            i.stock_qty,
            i.min_stock_qty,
            i.purchase_price_gs or "",
            i.opening_stock_qty or "",
            i.opening_stock_date or "",
            i.reorder_point or "",
            i.notes or "",
        ])

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=rms-inventory-{timestamp}.csv"},
    )


@router.get("", response_class=HTMLResponse)
def inventory_list(
    request: Request,
    sort: str | None = Query(None, description="Sort column: name, stock_qty, unit, min_stock_level, purchase_price_gs"),
    dir: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """List all ingredients with stock badge. Paginated at 50/page."""
    PER_PAGE = 50

    stmt = select(Ingredient)
    count_stmt = select(func.count()).select_from(Ingredient)

    # Count total
    total = session.scalar(count_stmt) or 0
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    page = min(page, total_pages)

    # Sorting
    if sort and sort in ("name", "stock_qty", "unit", "min_stock_level", "purchase_price_gs"):
        col = getattr(Ingredient, sort)
        stmt = stmt.order_by(col.desc() if dir == "desc" else col.asc())
    else:
        stmt = stmt.order_by(Ingredient.name)

    # Pagination
    offset = (page - 1) * PER_PAGE
    stmt = stmt.offset(offset).limit(PER_PAGE)
    ingredients = session.scalars(stmt).all()

    # Phase D — Q1 surface: price-history enrichment per ingredient.
    # Ingredients with >=2 events in the last 90d get a muted min/max line
    # under the price cell; >=3 events also get a sparkline SVG.
    price_info: dict[int, dict] = {}
    ing_ids_with_events = set(
        session.scalars(
            select(IngredientPriceEvent.ingredient_id).distinct()
        ).all()
    )
    for ing in ingredients:
        if ing.id not in ing_ids_with_events:
            continue
        stats = price_stats(session, ing.id, days=90)
        if stats["count"] >= 2:
            info: dict = {"stats": stats, "sparkline_svg": ""}
            if stats["count"] >= 3:
                history = price_history(session, ing.id, days=90)
                info["sparkline_svg"] = sparkline(
                    [p for _, p in history],
                    label=f"histórico de precio de {ing.name}",
                )
            price_info[ing.id] = info

    return render(
        request,
        "inventario.html",
        {
            "ingredients": ingredients,
            "price_info": price_info,
            "sort": sort or "",
            "dir": dir,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "per_page": PER_PAGE,
            "page_start": (page - 1) * PER_PAGE + 1,
            "page_end": min(page * PER_PAGE, total),
        },
    )


@router.get("/{ing_id}", response_class=HTMLResponse)
def inventory_detail(
    ing_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Show ingredient detail page with 'used in recipes' list."""
    ing = session.get(Ingredient, ing_id)
    if ing is None:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")

    # Find all recipes that use this ingredient
    recipe_lines = session.scalars(
        select(RecipeLine).where(
            RecipeLine.line_kind == "ingredient",
            RecipeLine.line_ref_id == ing_id,
        )
    ).all()

    recipes = []
    for line in recipe_lines:
        recipe = session.get(Recipe, line.recipe_id)
        if recipe:
            recipes.append({
                "id": recipe.id,
                "name": recipe.name,
                "qty": line.qty,
                "line_unit": line.line_unit,
            })

    return render(
        request,
        "ingrediente_detalle.html",
        {"ingredient": ing, "recipes": recipes},
    )


@router.get("/nuevo", response_class=HTMLResponse)
def inventory_new(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    """Show the new-ingredient form."""
    return render(
        request,
        "inventario_form.html",
        {"mode": "new", "ingredient": None, "action": "Nuevo", "units": [u.value for u in Unit]},
    )


@router.post("/nuevo")
def inventory_create(
    request: Request,
    name: str = Form(...),
    unit: str = Form(...),
    stock_qty: float = Form(0.0),
    min_stock_qty: float = Form(0.0),
    purchase_price_gs: str = Form(""),
    notes: str = Form(""),
    category: str = Form(""),
    opening_stock_qty: str = Form(""),
    opening_stock_date: str = Form(""),
    reorder_point: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Create new ingredient."""
    try:
        unit_enum = Unit.coerce(unit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Unidad inválida: {e}") from e

    price = _parse_price(purchase_price_gs)
    if stock_qty < 0:
        raise HTTPException(status_code=400, detail="Stock no puede ser negativo")
    if min_stock_qty < 0:
        raise HTTPException(status_code=400, detail="Stock mínimo no puede ser negativo")

    opening_qty = float(opening_stock_qty) if opening_stock_qty.strip() else None
    opening_date = opening_stock_date.strip() or None
    reorder = float(reorder_point) if reorder_point.strip() else None

    ing = Ingredient(
        name=name.strip(),
        unit=unit_enum.value,
        stock_qty=stock_qty,
        min_stock_qty=min_stock_qty,
        purchase_price_gs=price,
        notes=notes.strip() or None,
        category=category.strip() or None,
        opening_stock_qty=opening_qty,
        opening_stock_date=opening_date,
        reorder_point=reorder,
    )
    session.add(ing)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409, detail=f"Ya existe un ingrediente con nombre {name!r}"
        ) from None

    # Record an initial stock movement if opening stock was set
    if opening_qty is not None and opening_qty != stock_qty:
        from app.auth import current_user_id
        user_id = current_user_id(request) or "operator"
        movement = StockMovement(
            ingredient_id=ing.id,
            movement_type="initial",
            qty=opening_qty,
            reason="stock inicial",
            reference_id=None,
            reference_type=None,
            recorded_at=datetime.now(timezone.utc),
            created_by=user_id,
        )
        session.add(movement)
        session.commit()

    # Phase B — Q1 core: when an operator creates an ingredient with a price,
    # record the first price event so the history starts populated.
    if price is not None:
        try:
            record_price_event(session, ing.id, price, source="manual")
            session.commit()
        except Exception:
            # Don't fail the whole request on a price-history write error.
            from loguru import logger

            logger.warning(
                f"record_price_event failed for new ingredient {ing.id}",
                exc_info=True,
            )

    return RedirectResponse(url="/inventario", status_code=303)


@router.get("/{ing_id}/editar", response_class=HTMLResponse)
def inventory_edit(
    ing_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Show the edit form for an ingredient."""
    ing = session.get(Ingredient, ing_id)
    if ing is None:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")
    return render(
        request,
        "inventario_form.html",
        {"mode": "edit", "ingredient": ing, "action": "Editar", "units": [u.value for u in Unit]},
    )


@router.post("/{ing_id}/editar")
def inventory_update(
    ing_id: int,
    request: Request,
    name: str = Form(...),
    unit: str = Form(...),
    stock_qty: float = Form(0.0),
    min_stock_qty: float = Form(0.0),
    purchase_price_gs: str = Form(""),
    notes: str = Form(""),
    category: str = Form(""),
    opening_stock_qty: str = Form(""),
    opening_stock_date: str = Form(""),
    reorder_point: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Update an existing ingredient."""
    ing = session.get(Ingredient, ing_id)
    if ing is None:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")

    try:
        unit_enum = Unit.coerce(unit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Unidad inválida: {e}") from e

    price = _parse_price(purchase_price_gs)
    ing.name = name.strip()
    ing.unit = unit_enum.value
    ing.stock_qty = stock_qty
    ing.min_stock_qty = min_stock_qty
    ing.purchase_price_gs = price
    ing.notes = notes.strip() or None
    ing.category = category.strip() or None
    ing.opening_stock_qty = float(opening_stock_qty) if opening_stock_qty.strip() else None
    ing.opening_stock_date = opening_stock_date.strip() or None
    ing.reorder_point = float(reorder_point) if reorder_point.strip() else None

    # Phase B — Q1 core: record a price event when the operator changes the
    # price. We always record when the new price is non-null — even if it
    # matches the previous value (auditability beats optimization here).
    should_record = price is not None

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409, detail=f"Ya existe otro ingrediente con nombre {name!r}"
        ) from None

    if should_record:
        try:
            record_price_event(session, ing.id, price, source="manual")
            session.commit()
        except Exception:
            from loguru import logger

            logger.warning(
                f"record_price_event failed for ingredient {ing.id} update",
                exc_info=True,
            )

    return RedirectResponse(url="/inventario", status_code=303)


@router.post("/{ing_id}/eliminar")
def inventory_delete(
    ing_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Delete an ingredient. Blocked if it's used in a recipe."""
    ing = session.get(Ingredient, ing_id)
    if ing is None:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")

    # Check if ingredient is on any recipe
    usage = session.scalar(
        select(RecipeLine)
        .where(
            RecipeLine.line_kind == "ingredient",
            RecipeLine.line_ref_id == ing_id,
        )
        .limit(1)
    )
    if usage is not None:
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar: el ingrediente está en una receta. Quitá la línea primero.",
        )

    session.delete(ing)
    session.commit()
    return RedirectResponse(url="/inventario", status_code=303)


@router.post("/{ing_id}/ajustar")
def inventory_adjust(
    ing_id: int,
    request: Request,
    adjustment: float = Form(...),
    reason: str = Form(""),
    confirm_negative: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Record a stock adjustment (wastage, breakage, count correction).
    Pass positive adjustment to add stock, negative to remove.
    Writes a StockMovement record for auditability.

    If the adjustment would drive stock negative and confirm_negative is not
    'yes', the request is rejected — the caller must show a confirmation
    modal first.
    """
    ing = session.get(Ingredient, ing_id)
    if ing is None:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")

    if adjustment == 0:
        return RedirectResponse(url="/inventario", status_code=303)

    # Reject negative resulting stock without explicit confirmation
    if ing.stock_qty + adjustment < 0 and confirm_negative != "yes":
        from urllib.parse import urlencode
        params = urlencode({
            "flash": f"no_confirm:La operación llevaría stock de {ing.name} a {ing.stock_qty + adjustment:.2f} {ing.unit}. Confirmá haciendo click en Ajustar de nuevo.",
            "ing_id": ing_id,
        })
        return RedirectResponse(url=f"/inventario?{params}", status_code=303)

    from app.auth import current_user_id

    user_id = current_user_id(request) or "operator"

    # StockMovement: positive qty = stock in, negative = stock out
    movement = StockMovement(
        ingredient_id=ing_id,
        movement_type="adjustment",
        qty=adjustment,
        reason=reason.strip() or None,
        reference_id=None,
        reference_type=None,
        recorded_at=datetime.now(timezone.utc),
        created_by=user_id,
    )
    session.add(movement)

    ing.stock_qty = max(0.0, ing.stock_qty + adjustment)
    session.commit()
    return RedirectResponse(url="/inventario", status_code=303)


@router.get("/{ing_id}/movimientos", response_class=HTMLResponse)
def inventory_movements(
    ing_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Show the movement history for one ingredient."""
    ing = session.get(Ingredient, ing_id)
    if ing is None:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")

    movements = session.scalars(
        select(StockMovement)
        .where(StockMovement.ingredient_id == ing_id)
        .order_by(StockMovement.recorded_at.desc())
        .limit(200)
    ).all()

    # Current stock for display
    current_stock = ing.stock_qty

    # Running balance: start from current stock and walk backwards
    balance = current_stock
    enriched = []
    for m in reversed(movements):
        prev_balance = balance
        balance = balance - m.qty  # reverse the movement to get prior state
        enriched.append({
            "id": m.id,
            "movement_type": m.movement_type,
            "qty": m.qty,
            "reason": m.reason,
            "reference_id": m.reference_id,
            "reference_type": m.reference_type,
            "recorded_at": m.recorded_at,
            "created_by": m.created_by,
            "balance_before": balance,
            "balance_after": prev_balance,
        })

    return render(
        request,
        "inventario_movimientos.html",
        {
            "ingredient": ing,
            "movements": enriched,
            "current_stock": current_stock,
        },
    )


def _parse_price(raw: str) -> int | None:
    """Parse the purchase_price_gs form field. Empty string → None."""
    raw = raw.strip()
    if not raw:
        return None
    try:
        from app.rms.money import parse_gs

        return parse_gs(raw)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"Precio inválido: {raw!r}") from e


__all__ = ["router"]
