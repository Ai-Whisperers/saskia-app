"""app/routers/suppliers.py — /suppliers CRUD (audit items 249, 250, 284)."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.dependencies import get_session
from app.rms.models import Ingredient, Supplier
from app.services.template_render import render

router = APIRouter(prefix="/suppliers", dependencies=[Depends(require_login)])


@router.get("", response_class=HTMLResponse)
def suppliers_list(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    """List all suppliers."""
    suppliers = session.scalars(select(Supplier).order_by(Supplier.name)).all()
    return render(request, "suppliers.html", {
        "suppliers": list(suppliers),
        "total": len(suppliers),
        "page_start": 1,
        "page_end": len(suppliers),
    })


@router.get("/nuevo", response_class=HTMLResponse)
def supplier_new(request: Request) -> HTMLResponse:
    """New supplier form."""
    return render(request, "supplier_form.html", {"mode": "new", "supplier": None})


@router.post("/nuevo")
def supplier_create(
    request: Request,
    name: str = Form(""),
    contact_name: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    address: str = Form(""),
    notes: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Create a supplier.

    Centralized validation (app.rms.validation):
      - name is required, max 120 chars
      - phone must be digits (Paraguay format)
      - email must be RFC-shaped
      - notes/address/contact_name max 500 chars
    """
    from app.rms.validation import (
        require_text, optional_text, validate_email, validate_phone,
    )

    name_clean = require_text(name, field="nombre", max_len=120)
    contact_clean = optional_text(contact_name, max_len=120)
    phone_clean = validate_phone(phone)
    email_clean = validate_email(email)
    address_clean = optional_text(address, max_len=200)
    notes_clean = optional_text(notes, max_len=2000)

    supplier = Supplier(
        name=name_clean,
        contact_name=contact_clean,
        phone=phone_clean,
        email=email_clean,
        address=address_clean,
        notes=notes_clean,
    )
    session.add(supplier)
    session.commit()
    return RedirectResponse(url="/suppliers", status_code=303)


@router.get("/{s_id}/editar", response_class=HTMLResponse)
def supplier_edit(s_id: int, request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    """Edit supplier form."""
    supplier = session.get(Supplier, s_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return render(request, "supplier_form.html", {"mode": "edit", "supplier": supplier})


@router.post("/{s_id}/editar")
def supplier_update(
    s_id: int,
    request: Request,
    name: str = Form(""),
    contact_name: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    address: str = Form(""),
    notes: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Update a supplier."""
    from app.rms.validation import (
        require_text, optional_text, validate_email, validate_phone,
    )

    supplier = session.get(Supplier, s_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    supplier.name = require_text(name, field="nombre", max_len=120)
    supplier.contact_name = optional_text(contact_name, max_len=120)
    supplier.phone = validate_phone(phone)
    supplier.email = validate_email(email)
    supplier.address = optional_text(address, max_len=200)
    supplier.notes = optional_text(notes, max_len=2000)
    session.commit()
    return RedirectResponse(url="/suppliers", status_code=303)


@router.post("/{s_id}/eliminar")
def supplier_delete(s_id: int, request: Request, session: Session = Depends(get_session)) -> RedirectResponse:
    """Delete a supplier (only if no ingredients linked)."""
    supplier = session.get(Supplier, s_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    # Check if any ingredients are linked
    if supplier.ingredients:
        raise HTTPException(
            status_code=400,
            detail=f"No se puede eliminar: {len(supplier.ingredients)} ingredientes están vinculados a este proveedor."
        )

    session.delete(supplier)
    session.commit()
    return RedirectResponse(url="/suppliers", status_code=303)


@router.get("/{s_id}/ordenes", response_class=HTMLResponse)
def supplier_orders(
    s_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Show all ingredients from this supplier that need reordering, with a WhatsApp link."""
    supplier = session.get(Supplier, s_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    # Get all ingredients from this supplier that are below minimum
    from app.rms.reorder import compute_reorder_list
    all_items = compute_reorder_list(session)
    supplier_items = [
        i for i in all_items
        if session.get(Ingredient, i.ingredient_id) and
           session.get(Ingredient, i.ingredient_id).supplier_id == s_id
    ]

    # Build WhatsApp text
    lines = [f"*Pedido a {supplier.name}*", ""]
    if supplier.contact_name:
        lines.append(f"Contacto: {supplier.contact_name}")
        lines.append("")
    if not supplier_items:
        lines.append("No hay ingredientes bajo mínimo para reponer.")
    else:
        for item in supplier_items:
            ing = session.get(Ingredient, item.ingredient_id)
            lines.append(f"• {item.name}: {item.suggested_qty:.2f} {item.unit} "
                         f"(stock: {item.current_stock:.2f}, mín: {item.min_stock:.2f})")
        lines.append("")
        lines.append(f"Total estimado: Gs. {sum(i.estimated_cost_gs for i in supplier_items):,}".replace(",", "."))

    text = "\n".join(lines).strip()
    encoded_text = quote(text, safe="")
    wa_url = f"https://wa.me/{supplier.phone.replace('+', '').replace(' ', '') if supplier.phone else ''}?text={encoded_text}" if supplier.phone else ""

    return render(request, "supplier_orders.html", {
        "supplier": supplier,
        "items": supplier_items,
        "wa_url": wa_url,
        "total_cost": sum(i.estimated_cost_gs for i in supplier_items),
    })


__all__ = ["router"]
