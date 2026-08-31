"""app/routers/inventory.py — CRUD endpoints for ingredients.

Per dev plan §9 Task 3.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.rms.models import Ingredient, RecipeLine
from app.rms.units import Unit
from app.services.template_render import render

router = APIRouter(prefix="/inventario")


def get_session(request: Request) -> Session:
    """Open a DB session from app.state.session_factory."""
    return request.app.state.session_factory()


@router.get("", response_class=HTMLResponse)
def inventory_list(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    """List all ingredients with stock badge."""
    ingredients = session.scalars(select(Ingredient).order_by(Ingredient.name)).all()
    return render(
        request,
        "inventario.html",
        {"ingredients": ingredients},
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
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409, detail=f"Ya existe otro ingrediente con nombre {name!r}"
        ) from None
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
