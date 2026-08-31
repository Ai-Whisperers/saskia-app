"""app/routers/sales.py — Sale entry, history, void.

Per dev plan §9 Task 5.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.config import ASUNCION_TZ
from app.rms.costing import RecipeWithoutYield, apply_sale, void_sale
from app.rms.models import Product, Sale
from app.services.template_render import render

router = APIRouter(prefix="/ventas")


def get_session(request: Request) -> Session:
    return request.app.state.session_factory()


def _decorated(s: Sale) -> dict:
    return {
        "id": s.id,
        "sold_at": s.sold_at,
        "sold_at_str": s.sold_at.strftime("%d/%m/%Y %H:%M"),
        "product_id": s.product_id,
        "product_name": s.product.name if s.product else "(deleted)",
        "qty": s.qty,
        "unit_price_gs": s.unit_price_gs,
        "total_gs": int(round(s.qty * s.unit_price_gs)),
        "notes": s.notes,
        "voided_at": s.voided_at,
    }


@router.get("", response_class=HTMLResponse)
async def sales_list(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    products = session.scalars(select(Product).order_by(Product.name)).all()
    sales = session.scalars(select(Sale).order_by(Sale.sold_at.desc()).limit(50)).all()
    return render(
        request,
        "ventas.html",
        {
            "products": products,
            "sales": [_decorated(s) for s in sales],
            "now_local": datetime.now(ASUNCION_TZ).strftime("%Y-%m-%dT%H:%M"),
        },
    )


@router.post("/nueva")
async def sale_create(
    request: Request, session: Session = Depends(get_session)
) -> RedirectResponse:
    """Create a sale with stock drop."""
    form = await request.form()
    try:
        product_id = int(form.get("product_id", "0"))
        qty = float(form.get("qty", "0"))
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"Entrada inválida: {e}") from e

    if product_id <= 0 or qty <= 0:
        raise HTTPException(status_code=400, detail="Producto y cantidad son obligatorios")

    # Parse sold_at (defaults to now in Asunción TZ)
    sold_at_raw = str(form.get("sold_at", "")).strip()
    if sold_at_raw:
        try:
            # Form sends "YYYY-MM-DDTHH:MM" (no TZ). Treat as Asunción local.
            naive = datetime.fromisoformat(sold_at_raw)
            sold_at = naive.replace(tzinfo=ASUNCION_TZ).astimezone(ASUNCION_TZ)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Fecha inválida: {sold_at_raw!r}") from e
    else:
        sold_at = datetime.now(ASUNCION_TZ)

    notes = str(form.get("notes", "")).strip() or None

    try:
        apply_sale(session, product_id, qty, sold_at, notes)
    except RecipeWithoutYield as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return RedirectResponse(url="/ventas", status_code=303)


@router.post("/{sale_id}/anular")
async def sale_void(
    sale_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Void a sale and reverse stock."""
    try:
        void_sale(session, sale_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return RedirectResponse(url="/ventas", status_code=303)


__all__ = ["router"]
