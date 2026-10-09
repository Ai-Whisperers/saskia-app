"""Form validation endpoints for inline HTMX validation.

Provides: POST /api/validate/recipe, POST /api/validate/product.
Each returns {} if valid, or {"valid": false, "errors": {"field": "msg"}}.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.dependencies import get_session

router = APIRouter(prefix="/api/validate", dependencies=[Depends(require_login)])


@router.post("/recipe")
def validate_recipe(
    request: Request,
    name: str = Form(""),
    yield_qty: str = Form(""),
    difficulty: str = Form(""),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Validate recipe key fields on blur. Returns {} if valid, errors dict otherwise."""
    errors: dict[str, str] = {}

    # name: required, min 2 chars
    name_val = name.strip()
    if not name_val:
        errors["name"] = "El nombre es obligatorio."
    elif len(name_val) < 2:
        errors["name"] = "El nombre debe tener al menos 2 caracteres."

    # yield_qty: required, > 0
    if not yield_qty.strip():
        errors["yield_qty"] = "El rinde es obligatorio."
    else:
        try:
            qty = float(yield_qty)
            if qty <= 0:
                errors["yield_qty"] = "El rinde debe ser mayor a 0."
        except ValueError:
            errors["yield_qty"] = "El rinde debe ser un número."

    # difficulty: 1-5
    if difficulty.strip():
        try:
            dif = int(difficulty)
            if dif < 1 or dif > 5:
                errors["difficulty"] = "La dificultad debe estar entre 1 y 5."
        except ValueError:
            errors["difficulty"] = "La dificultad debe ser un número entre 1 y 5."

    if errors:
        return JSONResponse({"valid": False, "errors": errors})
    return JSONResponse({})


@router.post("/product")
def validate_product(
    request: Request,
    name: str = Form(""),
    sale_price_gs: str = Form(""),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Validate product key fields on blur. Returns {} if valid, errors dict otherwise."""
    errors: dict[str, str] = {}

    # name: required + duplicate check
    name_val = name.strip()
    if not name_val:
        errors["name"] = "El nombre es obligatorio."
    else:
        from sqlalchemy import func

        from app.rms.models import Product

        existing = (
            session.scalar(func.count())
            .select_from(Product)
            .where(func.lower(Product.name) == name_val.lower())
        )
        if session.scalar(existing) > 0:
            errors["name"] = "Ya existe un producto con este nombre."

    # sale_price_gs: required, > 0
    if not sale_price_gs.strip():
        errors["sale_price_gs"] = "El precio de venta es obligatorio."
    else:
        try:
            price = float(sale_price_gs.replace(".", "").replace(",", "."))
            if price <= 0:
                errors["sale_price_gs"] = "El precio debe ser mayor a 0."
        except ValueError:
            errors["sale_price_gs"] = "El precio debe ser un número válido."

    if errors:
        return JSONResponse({"valid": False, "errors": errors})
    return JSONResponse({})
