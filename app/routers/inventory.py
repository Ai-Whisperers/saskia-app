"""app/routers/inventory.py — CRUD endpoints for ingredients.

Per dev plan §9 Task 3.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.charts import sparkline
from app.rms.dependencies import get_session
from app.rms.models import Ingredient, IngredientPriceEvent, RecipeLine
from app.rms.price_history import price_history, price_stats, record_price_event
from app.rms.units import Unit
from app.services.template_render import render

router = APIRouter(prefix="/inventario", dependencies=[Depends(require_login)])


@router.get("", response_class=HTMLResponse)
def inventory_list(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    """List all ingredients with stock badge."""
    ingredients = session.scalars(select(Ingredient).order_by(Ingredient.name)).all()

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
        {"ingredients": ingredients, "price_info": price_info},
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

    ing = Ingredient(
        name=name.strip(),
        unit=unit_enum.value,
        stock_qty=stock_qty,
        min_stock_qty=min_stock_qty,
        purchase_price_gs=price,
        notes=notes.strip() or None,
    )
    session.add(ing)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409, detail=f"Ya existe un ingrediente con nombre {name!r}"
        ) from None

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
