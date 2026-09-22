"""app/routers/reorder.py — operator reorder suggestions.

GET /reorder                — HTML view
GET /reorder?format=json    — machine-readable for future /scripts integrations
POST /reorder/generate-po   — bulk generate purchase order as WhatsApp text
"""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import current_user_id
from app.auth import require_login_or_disabled as require_login
from app.rms.audit import record as audit_record
from app.rms.dependencies import get_session
from app.rms.models import Ingredient, Supplier
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
    # INV-03: exclude items without a price from the footer total. Their
    # estimated_cost_gs is already 0 (set in compute_reorder_list), so the
    # sum remains correct, but we keep this comment for clarity.
    total_cost = sum(i.estimated_cost_gs for i in items)

    # Build ingredient_id -> (supplier_name, supplier_phone) map for WhatsApp links
    supplier_map: dict[int, tuple[str | None, str]] = {}
    for item in items:
        if item.ingredient_id not in supplier_map:
            ing = session.get(Ingredient, item.ingredient_id)
            if ing and ing.supplier:
                supplier_map[item.ingredient_id] = (ing.supplier.name, ing.supplier.phone or "")
            else:
                supplier_map[item.ingredient_id] = (None, "")

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
                    "supplier_name": supplier_map.get(i.ingredient_id, (None, ""))[0],
                    "supplier_phone": supplier_map.get(i.ingredient_id, ("", ""))[1],
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
        "supplier_map": supplier_map,
        "page_start": 1,
        "page_end": len(items),
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


@router.post("/generate-po")
def reorder_generate_po(
    request: Request,
    selected: str = Form("", description="Comma-separated ingredient IDs"),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Generate a WhatsApp purchase order pre-fill link for selected ingredients.

    Redirects to a WhatsApp wa.me URL with the order text pre-filled.
    """
    if not selected:
        return RedirectResponse(url="/reorder", status_code=303)

    try:
        ids = [int(x.strip()) for x in selected.split(",") if x.strip()]
    except ValueError:
        return RedirectResponse(url="/reorder", status_code=303)

    items = compute_reorder_list(session)
    selected_items = [i for i in items if i.ingredient_id in ids]

    if not selected_items:
        return RedirectResponse(url="/reorder", status_code=303)

    # Group by supplier
    by_supplier: dict[str, list] = {}
    no_supplier: list = []
    for item in selected_items:
        ing = session.get(Ingredient, item.ingredient_id)
        supplier_name = ing.supplier.name if (ing and ing.supplier) else None
        if supplier_name:
            by_supplier.setdefault(supplier_name, []).append(item)
        else:
            no_supplier.append(item)

    # Build WhatsApp text
    lines = ["*Pedido de materiales*", ""]
    for supplier_name, sup_items in by_supplier.items():
        lines.append(f"📦 *{supplier_name}*")
        for item in sup_items:
            lines.append(f"  • {item.name}: {item.suggested_qty:.2f} {item.unit}")
        lines.append("")
    if no_supplier:
        lines.append("📦 *Sin proveedor asignado*")
        for item in no_supplier:
            lines.append(f"  • {item.name}: {item.suggested_qty:.2f} {item.unit}")
        lines.append("")

    text = "\n".join(lines).strip()
    # Encode for WhatsApp URL
    encoded = quote(text, safe="")
    wa_url = f"https://wa.me/?text={encoded}"

    audit_record(
        session,
        user_id=current_user_id(request) or "operator",
        action="write.reorder.generate_po",
        request=request,
        detail={"n_items": len(selected_items), "suppliers": list(by_supplier.keys())},
    )
    session.commit()

    return RedirectResponse(url=wa_url, status_code=303)


__all__ = ["router"]
