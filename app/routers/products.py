"""app/routers/products.py — CRUD endpoints for products.

Per dev plan §9 Task 4.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.costing import batch_products_cost_margin, product_margin, product_unit_cost_gs
from app.rms.models import Product, Recipe, Sale
from app.rms.money import parse_gs
from app.services.template_render import render

router = APIRouter(prefix="/productos", dependencies=[Depends(require_login)])


def get_session(request: Request) -> Session:
    return request.app.state.session_factory()


def _decorate(session: Session, p: Product) -> dict:
    """Compute cost/margin columns for a product row."""
    cost = product_unit_cost_gs(session, p.id)
    margin = product_margin(session, p.id)
    return {
        "id": p.id,
        "name": p.name,
        "portion_label": p.portion_label,
        "sale_price_gs": p.sale_price_gs,
        "recipe_id": p.recipe_id,
        "recipe_name": p.recipe.name if p.recipe else None,
        "cost_gs": cost.batch_cost_gs,
        "margin_gs": margin[0],
        "margin_ratio": margin[1],
        "notes": p.notes,
    }


@router.get("", response_class=HTMLResponse)
def products_list(
    request: Request,
    q: str | None = None,
    has_recipe: str | None = None,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """List all products with cost + margin. Batch-loads to avoid N+1.

    Optional filter (?q=substring, ?has_recipe=yes/no).
    """
    stmt = select(Product).order_by(Product.name)
    if q:
        stmt = stmt.where(func.lower(Product.name).like(f"%{q.lower()}%"))
    if has_recipe == "yes":
        stmt = stmt.where(Product.recipe_id.is_not(None))
    elif has_recipe == "no":
        stmt = stmt.where(Product.recipe_id.is_(None))
    products = session.scalars(stmt).all()
    # One batch call replaces N+1 cost/margin queries (Neon round-trips).
    batch_results = batch_products_cost_margin(session, list(products))
    decorated = []
    for p in products:
        cost, margin = batch_results.get(
            p.id,
            (
                product_unit_cost_gs(session, p.id),
                product_margin(session, p.id),
            ),
        )
        decorated.append(
            {
                "id": p.id,
                "name": p.name,
                "portion_label": p.portion_label,
                "sale_price_gs": p.sale_price_gs,
                "recipe_id": p.recipe_id,
                "recipe_name": p.recipe.name if p.recipe else None,
                "cost_gs": cost.batch_cost_gs,
                "margin_gs": margin[0],
                "margin_ratio": margin[1],
                "notes": p.notes,
            }
        )
    return render(request, "productos.html", {"products": decorated, "q": q or "", "has_recipe": has_recipe or ""})


@router.get("/nuevo", response_class=HTMLResponse)
def product_new(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    """Show new-product form."""
    recipes = session.scalars(select(Recipe).order_by(Recipe.name)).all()
    return render(
        request,
        "producto_form.html",
        {"mode": "new", "product": None, "action": "Nuevo", "recipes": recipes},
    )


@router.post("/nuevo")
def product_create(
    request: Request,
    name: str = Form(...),
    portion_label: str = Form("1 unidad"),
    sale_price_gs: str = Form(...),
    recipe_id: str = Form(""),
    notes: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Create new product."""
    try:
        price = parse_gs(sale_price_gs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Precio inválido: {e}") from e

    rid = int(recipe_id) if recipe_id else None

    product = Product(
        name=name.strip(),
        portion_label=portion_label.strip() or "1 unidad",
        sale_price_gs=price,
        recipe_id=rid,
        notes=notes.strip() or None,
    )
    session.add(product)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409, detail=f"Ya existe un producto con nombre {name!r}"
        ) from None
    return RedirectResponse(url="/productos", status_code=303)


@router.get("/{p_id}/editar", response_class=HTMLResponse)
def product_edit(
    p_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Show edit form."""
    p = session.get(Product, p_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    recipes = session.scalars(select(Recipe).order_by(Recipe.name)).all()
    return render(
        request,
        "producto_form.html",
        {"mode": "edit", "product": p, "action": "Editar", "recipes": recipes},
    )


@router.post("/{p_id}/editar")
def product_update(
    p_id: int,
    request: Request,
    name: str = Form(...),
    portion_label: str = Form("1 unidad"),
    sale_price_gs: str = Form(...),
    recipe_id: str = Form(""),
    notes: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Update existing product."""
    p = session.get(Product, p_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    try:
        price = parse_gs(sale_price_gs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Precio inválido: {e}") from e

    rid = int(recipe_id) if recipe_id else None
    p.name = name.strip()
    p.portion_label = portion_label.strip() or "1 unidad"
    p.sale_price_gs = price
    p.recipe_id = rid
    p.notes = notes.strip() or None
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409, detail=f"Ya existe otro producto con nombre {name!r}"
        ) from None
    return RedirectResponse(url="/productos", status_code=303)


@router.post("/{p_id}/eliminar")
def product_delete(
    p_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Delete product. Blocked if sales exist."""
    p = session.get(Product, p_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    usage = session.scalar(select(Sale).where(Sale.product_id == p_id).limit(1))
    if usage is not None:
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar: hay ventas registradas. Anulá las ventas primero.",
        )

    session.delete(p)
    session.commit()
    return RedirectResponse(url="/productos", status_code=303)


__all__ = ["router"]
