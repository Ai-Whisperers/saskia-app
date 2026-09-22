"""app/routers/products.py — CRUD endpoints for products.

Per dev plan §9 Task 4.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.costing import batch_products_cost_margin, product_margin, product_unit_cost_gs
from app.rms.dependencies import get_session
from app.rms.models import Product, Recipe, Sale
from app.rms.money import parse_gs
from app.services.template_render import render

router = APIRouter(prefix="/productos", dependencies=[Depends(require_login)])


@router.get("/api/search", response_class=JSONResponse)
def products_api_search(
    q: str = Query("", description="Search query"),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Search products by name/portion/sku for combobox pickers.

    Used by /pedidos/nuevo and /merma to filter a list of 30+ products
    quickly without scrolling a native <select>. Returns up to `limit`
    matching products ordered by name.
    """
    if not q or q.strip() == "":
        # No query: return all available (most-used come first).
        rows = session.scalars(
            select(Product).order_by(Product.name).limit(limit)
        ).all()
    else:
        like = f"%{q.strip().lower()}%"
        rows = session.scalars(
            select(Product)
            .where(
                or_(
                    func.lower(Product.name).like(like),
                    func.lower(func.coalesce(Product.portion_label, "")).like(like),
                    func.coalesce(Product.sku, "").ilike(q.strip()),
                )
            )
            .order_by(Product.name)
            .limit(limit)
        ).all()
    payload = [
        {
            "id": p.id,
            "name": p.name,
            "portion_label": p.portion_label or "",
            "sale_price_gs": p.sale_price_gs,
            "sku": p.sku or "",
        }
        for p in rows
    ]
    return JSONResponse({"results": payload, "count": len(payload)})


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
    sort: str | None = Query(None, description="Sort column: name, sale_price_gs, cost_gs, margin_gs"),
    dir: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """List all products with cost + margin. Batch-loads to avoid N+1.
    Paginated at 50/page. Dead products (never sold) are flagged.

    Optional filter (?q=substring, ?has_recipe=yes/no).
    """
    PER_PAGE = 50
    stmt = select(Product)
    count_stmt = select(func.count()).select_from(Product)

    if q:
        stmt = stmt.where(func.lower(Product.name).like(f"%{q.lower()}%"))
        count_stmt = count_stmt.where(func.lower(Product.name).like(f"%{q.lower()}%"))
    if has_recipe == "yes":
        stmt = stmt.where(Product.recipe_id.is_not(None))
        count_stmt = count_stmt.where(Product.recipe_id.is_not(None))
    elif has_recipe == "no":
        stmt = stmt.where(Product.recipe_id.is_(None))
        count_stmt = count_stmt.where(Product.recipe_id.is_(None))

    # Count total
    total = session.scalar(count_stmt) or 0
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    page = min(page, total_pages)

    # Fetch product IDs with sales (for dead product detection)
    sold_product_ids = set(
        session.scalars(select(Sale.product_id).distinct()).all()
    )

    # Apply pagination
    offset = (page - 1) * PER_PAGE
    stmt = stmt.offset(offset).limit(PER_PAGE)

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
                "sku": p.sku,
                "is_available": p.is_available,
                "portion_label": p.portion_label,
                "sale_price_gs": p.sale_price_gs,
                "recipe_id": p.recipe_id,
                "recipe_name": p.recipe.name if p.recipe else None,
                "cost_gs": cost.batch_cost_gs,
                "margin_gs": margin[0],
                "margin_ratio": margin[1],
                "notes": p.notes,
                "is_dead": p.id not in sold_product_ids,
            }
        )

    # Apply in-memory sort
    if sort and sort in ("name", "sale_price_gs", "cost_gs", "margin_gs"):
        reverse = dir == "desc"
        decorated.sort(key=lambda r: r.get(sort) or 0, reverse=reverse)

    return render(request, "productos.html", {
        "products": decorated,
        "q": q or "",
        "has_recipe": has_recipe or "",
        "sort": sort or "",
        "dir": dir,
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "per_page": PER_PAGE,
        "page_start": (page - 1) * PER_PAGE + 1,
        "page_end": min(page * PER_PAGE, total),
    })


@router.get("/export.csv")
def products_export_csv(
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    """Export all products as a CSV download."""
    products = session.scalars(select(Product).order_by(Product.name)).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "name", "sku", "is_available", "portion_label",
        "sale_price_gs", "recipe_id", "cost_gs", "notes",
    ])
    for p in products:
        cost = product_unit_cost_gs(session, p.id)
        writer.writerow([
            p.id,
            p.name,
            p.sku or "",
            p.is_available,
            p.portion_label,
            p.sale_price_gs,
            p.recipe_id or "",
            cost.batch_cost_gs if cost else "",
            p.notes or "",
        ])

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=rms-products-{timestamp}.csv"},
    )


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
    name: str = Form(""),
    portion_label: str = Form("1 unidad"),
    sale_price_gs: str = Form(""),
    recipe_id: str = Form(""),
    notes: str = Form(""),
    sku: str = Form(""),
    is_available: str = Form("on"),
    image_url: str = Form(""),
    category: str = Form(""),
    tags: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Create new product.

    Centralized validation (app.rms.validation) returns Spanish 400s on
    bad input. Tags are stored as a comma-separated string per the model.
    """
    from app.rms.validation import (
        require_text, optional_text, parse_money_gs, parse_date_iso,
        validate_url, parse_quantity,
    )

    clean_name = require_text(name, field="nombre", max_len=120)
    portion_label_clean = optional_text(portion_label, max_len=60) or "1 unidad"
    price = parse_money_gs(sale_price_gs, allow_zero=True)
    if price < 0:
        raise HTTPException(status_code=400, detail="Precio no puede ser negativo")

    rid = int(recipe_id) if recipe_id else None
    available = is_available == "on"
    notes_clean = optional_text(notes, max_len=2000)
    sku_clean = optional_text(sku, max_len=32)
    image_url_clean = validate_url(image_url)
    category_clean = optional_text(category, max_len=32)
    tags_clean = optional_text(tags, max_len=500)

    product = Product(
        name=clean_name,
        portion_label=portion_label_clean,
        sale_price_gs=price,
        recipe_id=rid,
        notes=notes_clean,
        sku=sku_clean,
        is_available=available,
        image_url=image_url_clean,
        category=category_clean,
        tags=tags_clean,
    )
    session.add(product)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409, detail=f"Ya existe un producto con nombre {clean_name!r}"
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
    name: str = Form(""),
    portion_label: str = Form("1 unidad"),
    sale_price_gs: str = Form(""),
    recipe_id: str = Form(""),
    notes: str = Form(""),
    sku: str = Form(""),
    is_available: str = Form("on"),
    image_url: str = Form(""),
    category: str = Form(""),
    tags: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Update existing product."""
    from app.rms.validation import (
        require_text, optional_text, parse_money_gs, validate_url,
    )

    p = session.get(Product, p_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    clean_name = require_text(name, field="nombre", max_len=120)
    portion_label_clean = optional_text(portion_label, max_len=60) or "1 unidad"
    price = parse_money_gs(sale_price_gs, allow_zero=True)
    if price < 0:
        raise HTTPException(status_code=400, detail="Precio no puede ser negativo")

    rid = int(recipe_id) if recipe_id else None
    available = is_available == "on"
    notes_clean = optional_text(notes, max_len=2000)
    sku_clean = optional_text(sku, max_len=32)
    image_url_clean = validate_url(image_url)
    category_clean = optional_text(category, max_len=32)
    tags_clean = optional_text(tags, max_len=500)

    p.name = clean_name
    p.portion_label = portion_label_clean
    p.sale_price_gs = price
    p.recipe_id = rid
    p.notes = notes_clean
    p.sku = sku_clean
    p.is_available = available
    p.image_url = image_url_clean
    p.category = category_clean
    p.tags = tags_clean
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409, detail=f"Ya existe otro producto con nombre {clean_name!r}"
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


@router.post("/bulk-eliminar")
def product_bulk_delete(
    request: Request,
    ids: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Delete multiple products at once. Skips any that have sales."""
    deleted = 0
    skipped = 0
    for pid in ids.split(","):
        pid = pid.strip()
        if not pid:
            continue
        try:
            p = session.get(Product, int(pid))
        except ValueError:
            continue
        if p is None:
            continue
        usage = session.scalar(select(Sale).where(Sale.product_id == p.id).limit(1))
        if usage is not None:
            skipped += 1
            continue
        session.delete(p)
        deleted += 1

    session.commit()
    flash = f"{deleted} producto(s) eliminado(s)"
    if skipped:
        flash += f", {skipped} omitido(s) por tener ventas"
    return RedirectResponse(url=f"/productos?flash={flash}", status_code=303)


__all__ = ["router"]
