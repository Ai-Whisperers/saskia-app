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
from app.rms.price_history import batch_price_stats, record_price_event
from app.rms.rate_limit import is_write_rate_limited
from app.rms.reorder import compute_reorder_list
from app.rms.reorder_supplier_prices import get_supplier_price_options
from app.rms.supplier_history import (
    LOCK_THRESHOLD,
    get_effective_supplier_id,
    record_purchase_supplier,
)
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

    # Build ingredient_id -> (supplier_name, supplier_phone) map for WhatsApp links.
    # Migration 072 (P2 reorder redesign): the dropdown now defaults to
    # `effective_supplier_id` (locked > last_purchase > parent supplier_id),
    # so the supplier phone/name lookup should mirror that priority.
    supplier_map: dict[int, tuple[str | None, str]] = {}
    effective_supplier_map: dict[int, int | None] = {}
    locked_supplier_map: dict[int, int | None] = {}
    for item in items:
        ing = session.get(Ingredient, item.ingredient_id)
        if ing is None:
            supplier_map[item.ingredient_id] = (None, "")
            effective_supplier_map[item.ingredient_id] = None
            locked_supplier_map[item.ingredient_id] = None
            continue
        eff_id = get_effective_supplier_id(ing)
        effective_supplier_map[item.ingredient_id] = eff_id
        locked_supplier_map[item.ingredient_id] = ing.locked_supplier_id
        # Pick the supplier object to show name + phone from
        eff_supplier = (
            session.get(Supplier, eff_id) if eff_id is not None else None
        )
        if eff_supplier is not None:
            supplier_map[item.ingredient_id] = (eff_supplier.name, eff_supplier.phone or "")
        elif ing.supplier is not None:
            # Fallback to the legacy parent supplier even though it's not
            # the effective one — better than showing "sin proveedor".
            supplier_map[item.ingredient_id] = (ing.supplier.name, ing.supplier.phone or "")
        else:
            supplier_map[item.ingredient_id] = (None, "")

    # Per-supplier price options for every active supplier (used to render
    # the inline prices in the dropdown). One query per ingredient — N+1
    # is acceptable here because N is bounded by the number of ingredients
    # below minimum (typically <30). If this becomes a bottleneck, batch
    # the lookup in a single SQL query.
    supplier_prices_map: dict[int, dict[int, int | None]] = {}
    for item in items:
        supplier_prices_map[item.ingredient_id] = get_supplier_price_options(
            session, item.ingredient_id
        )

    # All active suppliers, ordered by name ASC. The template iterates
    # this list once to render every dropdown identically.
    all_suppliers = session.scalars(
        select(Supplier).where(Supplier.is_active == True).order_by(Supplier.name)
    ).all()
    supplier_options = [
        {"id": s.id, "name": s.name, "phone": s.phone or ""} for s in all_suppliers
    ]

    # Price-history stats per ingredient (used for the sparkline on /reorder).
    # Single SQL query covers all items; 90-day window.
    ingredient_ids = [i.ingredient_id for i in items]
    price_stats = batch_price_stats(session, ingredient_ids, days=90)

    # Predictive forecast (BACKLOG #7): avg_daily consumption + days_of_stock.
    # Single batched query for all items (no N+1).
    from app.rms.forecast import batch_forecast_ingredients
    forecast_objs = batch_forecast_ingredients(session, ingredient_ids, days_back=30)
    forecast_map: dict[int, dict] = {
        ing_id: {
            "avg_daily": fc.avg_daily_consumption,
            "days_of_stock": fc.days_of_stock,
            "trend_pct": fc.trend_pct,
            "projected_stockout_at": fc.projected_stockout_at,
            "recommended_restock_qty": fc.recommended_restock_qty,
        }
        for ing_id, fc in forecast_objs.items()
    }

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
                    "effective_supplier_id": effective_supplier_map.get(i.ingredient_id),
                    "locked_supplier_id": locked_supplier_map.get(i.ingredient_id),
                }
                for i in items
            ],
            "supplier_options": supplier_options,
            "total_estimated_cost_gs": total_cost,
            "count": len(items),
            "lock_threshold": LOCK_THRESHOLD,
        })

    return render(request, "reorder.html", {
        "items": items,
        "total_cost_gs": total_cost,
        "count": len(items),
        "supplier_map": supplier_map,
        "effective_supplier_map": effective_supplier_map,
        "locked_supplier_map": locked_supplier_map,
        "supplier_prices_map": supplier_prices_map,
        "supplier_options": supplier_options,
        "lock_threshold": LOCK_THRESHOLD,
        "price_stats": price_stats,
        "forecast_map": forecast_map,
        "page_start": 1,
        "page_end": len(items),
    })


@router.post("/registrar")
def reorder_registrar(
    request: Request,
    ingredient_id: int = Form(...),
    qty: float = Form(...),
    qty_unit: str = Form(""),
    price_gs: int = Form(...),
    notes: str = Form(""),
    supplier_id: int | None = Form(None),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Record a purchase: bump stock, append a 'restock' price event.

    Phase D — Q1 surface. Saskia: cada vez que restockea carga los
    precios, así los paneles muestran cuánto gana realmente aunque los
    precios fluctúen.

    MER-01 (cross-cutting): qty_unit lets the operator enter the buy in
    any unit from the same family as the ingredient's stock unit (e.g.
    5000 g instead of 5 kg). Cross-family conversion raises a 400.

    Migration 072 (P2 reorder redesign): ``supplier_id`` is optional
    but tracked when provided. When supplied, ``record_purchase_supplier``
    updates the streak counter and may auto-lock the dropdown on the
    next visit to /reorder (after 3 consecutive buys from the same
    supplier). When omitted, we leave the existing last-purchase pointer
    intact (operator skipped the dropdown — e.g. used the keyboard
    shortcut to submit without picking one).
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

    # Validate the supplier_id FK when supplied so a malformed POST can't
    # silently write garbage into the streak/lock columns.
    chosen_supplier_id: int | None = None
    if supplier_id is not None:
        sup = session.get(Supplier, supplier_id)
        if sup is None:
            raise HTTPException(status_code=400, detail="Proveedor inválido")
        chosen_supplier_id = sup.id

    # Convert qty from the form unit to the ingredient's stock unit so
    # "5000 g" on the form lands as +5.00 kg on the ingredient.
    from app.rms.units import Unit, can_convert, convert_qty
    qty_in_stock_unit = qty
    if qty_unit and ing.unit and qty_unit != ing.unit:
        from_unit = Unit.coerce(qty_unit)
        to_unit = Unit.coerce(ing.unit)
        if not can_convert(from_unit, to_unit):
            raise HTTPException(
                status_code=400,
                detail=f"No se puede convertir {qty_unit} a {ing.unit} (familia distinta)",
            )
        qty_in_stock_unit = float(convert_qty(qty, from_unit, to_unit))

    ing.stock_qty = ing.stock_qty + qty_in_stock_unit
    record_price_event(session, ingredient_id, price_gs, source="restock")
    if chosen_supplier_id is not None:
        record_purchase_supplier(session, ingredient_id, chosen_supplier_id)
    audit_record(
        session,
        user_id=current_user_id(request) or "operator",
        action="write.reorder.restock",
        request=request,
        detail={
            "ingredient_id": ingredient_id,
            "qty": qty_in_stock_unit,
            "qty_unit": qty_unit or ing.unit,
            "price_gs": price_gs,
            "supplier_id": chosen_supplier_id,
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
        lines.extend(f"  • {item.name}: {item.suggested_qty:.2f} {item.unit}" for item in sup_items)
        lines.append("")
    if no_supplier:
        lines.append("📦 *Sin proveedor asignado*")
        lines.extend(f"  • {item.name}: {item.suggested_qty:.2f} {item.unit}" for item in no_supplier)
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
