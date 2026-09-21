"""app/routers/reorder.py — operator reorder suggestions.

GET /reorder                — HTML view
GET /reorder?format=json    — machine-readable for future /scripts integrations
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import current_user_id
from app.auth import require_login_or_disabled as require_login
from app.rms.audit import record as audit_record
from app.rms.dependencies import get_session
from app.rms.models import Ingredient
from app.rms.price_history import record_price_event
from app.rms.rate_limit import is_write_rate_limited
from app.rms.reorder import compute_reorder_list
from app.services.template_render import render

router = APIRouter(prefix="/reorder", dependencies=[Depends(require_login)])


@router.get("", response_class=HTMLResponse, response_model=None)
def reorder_view(
    request: Request,
    format: str = Query("html", pattern="^(html|json)$"),
    session: Session = Depends(get_session),
) -> HTMLResponse | JSONResponse:
    """Show ingredients that need reordering.

    HTML mode: ranked table grouped by urgency.
    JSON mode: structured payload for tooling.
    """
    items = compute_reorder_list(session)
    total_cost = sum(i.estimated_cost_gs for i in items)

    if format == "json":
        return JSONResponse({
            "items": [
                {
                    "ingredient_id": i.ingredient_id,
                    "name": i.name,
                    "unit": i.unit,
                    "current_stock": i.current_stock,
                    "min_stock": i.min_stock,
                    "max_stock": i.max_stock,
                    "suggested_qty": i.suggested_qty,
                    "estimated_cost_gs": i.estimated_cost_gs,
                    "purchase_price_gs": i.purchase_price_gs,
                    "urgency": i.urgency,
                }
                for i in items
            ],
            "total_estimated_cost_gs": total_cost,
            "count": len(items),
        })

    return render(request, "reorder.html", {
        "items": items,
        "total_cost_gs": total_cost,
        "count": len(items),
    })


@router.post("/registrar")
def reorder_registrar(
    request: Request,
    ingredient_id: int = Form(...),
    qty: float = Form(...),
    price_gs: int = Form(...),
    notes: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Record a purchase: bump stock, append a 'restock' price event.

    Phase D — Q1 surface. Saskia: cada vez que restockea carga los
    precios, así los paneles muestran cuánto gana realmente aunque los
    precios fluctúen.
    """
    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )

    if qty <= 0:
        raise HTTPException(status_code=400, detail="La cantidad debe ser mayor a 0")
    if price_gs < 0:
        raise HTTPException(status_code=400, detail="El precio no puede ser negativo")

    ing = session.get(Ingredient, ingredient_id)
    if ing is None:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")

    ing.stock_qty = ing.stock_qty + qty
    record_price_event(session, ingredient_id, price_gs, source="restock")
    audit_record(
        session,
        user_id=current_user_id(request) or "operator",
        action="write.reorder.restock",
        request=request,
        detail={
            "ingredient_id": ingredient_id,
            "qty": qty,
            "price_gs": price_gs,
            "notes": notes or None,
        },
    )
    session.commit()
    return RedirectResponse(url="/reorder", status_code=303)


__all__ = ["router"]
