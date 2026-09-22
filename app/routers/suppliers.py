"""app/routers/suppliers.py — /suppliers CRUD (audit items 249, 250, 284)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.dependencies import get_session
from app.rms.models import Supplier
from app.services.template_render import render

router = APIRouter(prefix="/suppliers", dependencies=[Depends(require_login)])


@router.get("", response_class=HTMLResponse)
def suppliers_list(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    """List all suppliers."""
    suppliers = session.scalars(select(Supplier).order_by(Supplier.name)).all()
    return render(request, "suppliers.html", {"suppliers": list(suppliers)})


@router.get("/nuevo", response_class=HTMLResponse)
def supplier_new(request: Request) -> HTMLResponse:
    """New supplier form."""
    return render(request, "supplier_form.html", {"mode": "new", "supplier": None})


@router.post("/nuevo")
def supplier_create(
    request: Request,
    name: str = Form(...),
    contact_name: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    address: str = Form(""),
    notes: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Create a supplier."""
    if not name.strip():
        raise HTTPException(status_code=400, detail="Nombre es obligatorio")

    supplier = Supplier(
        name=name.strip(),
        contact_name=contact_name.strip() or None,
        phone=phone.strip() or None,
        email=email.strip() or None,
        address=address.strip() or None,
        notes=notes.strip() or None,
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
    name: str = Form(...),
    contact_name: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    address: str = Form(""),
    notes: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Update a supplier."""
    supplier = session.get(Supplier, s_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    if not name.strip():
        raise HTTPException(status_code=400, detail="Nombre es obligatorio")

    supplier.name = name.strip()
    supplier.contact_name = contact_name.strip() or None
    supplier.phone = phone.strip() or None
    supplier.email = email.strip() or None
    supplier.address = address.strip() or None
    supplier.notes = notes.strip() or None
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


__all__ = ["router"]
