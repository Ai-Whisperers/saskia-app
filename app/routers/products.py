"""app/routers/products.py — CRUD endpoints for products.

Per dev plan §9 Task 4.
"""

from __future__ import annotations

import csv
import io
import secrets as pysecrets
import shutil
from datetime import datetime, timezone
from pathlib import Path as FPath

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
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
            "image_url": p.image_url or "",
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
    margen: str | None = Query(None, description="Filter by margin state: negativo/bajo/ok/alto"),
    disponibles: str | None = Query(None, description="Filter availability: si/no"),
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

    # Margin/availability filters are post-costing (need unit costs first) —
    # count after decoration below. Track them here.
    margen_sel = (margen or "").strip()
    disp_sel = (disponibles or "").strip()
    if disp_sel == "si":
        stmt = stmt.where(Product.is_available.is_(True))
        count_stmt = count_stmt.where(Product.is_available.is_(True))
    elif disp_sel == "no":
        stmt = stmt.where(Product.is_available.is_(False))
        count_stmt = count_stmt.where(Product.is_available.is_(False))

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
    # Phase 1.D — prime cost for each product (batch-safe; new function).
    from app.rms.prime_cost import compute_prime_cost
    for p in products:
        cost, margin = batch_results.get(
            p.id,
            (
                product_unit_cost_gs(session, p.id),
                product_margin(session, p.id),
            ),
        )
        pc = compute_prime_cost(session, p.id)
        decorated.append(
            {
                "id": p.id,
                "name": p.name,
                "sku": p.sku,
                "image_url": p.image_url,
                "is_available": p.is_available,
                "portion_label": p.portion_label,
                "sale_price_gs": p.sale_price_gs,
                "recipe_id": p.recipe_id,
                "recipe_name": p.recipe.name if p.recipe else None,
                "cost_gs": cost.batch_cost_gs,
                "margin_gs": margin[0],
                "margin_ratio": margin[1],
                # Phase 1.D — prime cost
                "prime_cost_gs": pc.prime_cost_gs,
                "prime_cost_pct": pc.prime_cost_pct_of_sale,
                "labor_cost_gs": pc.labor_cost_gs,
                "overhead_cost_gs": pc.overhead_cost_gs,
                "notes": p.notes,
                "mayorista_price_gs": p.mayorista_price_gs,
                "is_dead": p.id not in sold_product_ids,
            }
        )

    # Margin state filter (post-costing, in-memory): negativo <0, bajo <30%, ok 30-70%, alto >70%
    if margen_sel:
        def _mstate(r):
            if r["margin_ratio"] is None: return "sin-datos"
            pct = r["margin_ratio"] * 100
            if pct < 0: return "negativo"
            if pct < 30: return "bajo"
            if pct <= 70: return "ok"
            return "alto"
        decorated = [r for r in decorated if _mstate(r) == margen_sel]
        total = len(decorated)

    # Apply in-memory sort
    if sort and sort in ("name", "sale_price_gs", "cost_gs", "margin_gs"):
        reverse = dir == "desc"
        decorated.sort(key=lambda r: r.get(sort) or 0, reverse=reverse)

    return render(request, "productos.html", {
        "products": decorated,
        "q": q or "",
        "has_recipe": has_recipe or "",
        "margen_sel": margen_sel,
        "disp_sel": disp_sel,
        "total_all": session.scalar(select(func.count()).select_from(Product)) or 0,
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
    """Show new-product form.

    Passes DB-driven catalogs:
      - product_categories: rows from `category` WHERE scope='product'
      - dietary_tags: rows from `tag` WHERE kind='product'
    Both lists drive the category_picker / tag_picker macros. Hardcoded
    fallback removed in static-content audit phase 1.
    """
    from app.rms.categories import list_categories as list_cats
    from app.rms.settings_runtime import get_pricing_markup
    from app.rms.tags import list_tags_for_kind

    recipes = session.scalars(select(Recipe).order_by(Recipe.name)).all()
    return render(
        request,
        "producto_form.html",
        {
            "mode": "new",
            "product": None,
            "action": "Nuevo",
            "recipes": recipes,
            "product_categories": list_cats(session, "product"),
            "dietary_tags": list_tags_for_kind(session, "product"),
            "pricing_markup": get_pricing_markup(session),
        },
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
    mayorista_price_gs: str = Form(""),
    iva_rate: str = Form("10"),
    requires_rspa: str = Form(""),
    rspa_number: str = Form(""),
    rspa_expiry: str = Form(""),
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

    # Wholesale price (mayorista) — optional B2B field.
    mayorista_price = parse_money_gs(mayorista_price_gs, allow_zero=True) if mayorista_price_gs.strip() else None

    # IVA rate — validated against allowed values.
    iva_valid = iva_rate in ("10", "5", "0", "exento")
    iva_clean = iva_rate if iva_valid else "10"

    # RSPA fields.
    requires_rspa_bool = requires_rspa == "on"
    rspa_number_clean = optional_text(rspa_number, max_len=30)
    rspa_expiry_clean = parse_date_iso(rspa_expiry) if rspa_expiry.strip() else None

    # Wave 2 — auto-fill category + tags from the linked recipe if operator
    # left either blank. Recipe's family → category, dietary_tags → tags.
    if rid and (not category_clean or not tags_clean):
        from app.rms.models import Recipe
        linked_recipe = session.get(Recipe, rid)
        if linked_recipe:
            if not category_clean and linked_recipe.family:
                category_clean = linked_recipe.family
            if not tags_clean and linked_recipe.dietary_tags:
                tags_clean = linked_recipe.dietary_tags

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
        mayorista_price_gs=mayorista_price,
        iva_rate=iva_clean,
        requires_rspa=requires_rspa_bool,
        rspa_number=rspa_number_clean,
        rspa_expiry=rspa_expiry_clean,
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
    """Show edit form. Passes DB-driven catalogs (see product_new)."""
    from app.rms.categories import list_categories as list_cats
    from app.rms.settings_runtime import get_pricing_markup
    from app.rms.tags import list_tags_for_kind

    p = session.get(Product, p_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    recipes = session.scalars(select(Recipe).order_by(Recipe.name)).all()
    return render(
        request,
        "producto_form.html",
        {
            "mode": "edit",
            "product": p,
            "action": "Editar",
            "recipes": recipes,
            "product_categories": list_cats(session, "product"),
            "dietary_tags": list_tags_for_kind(session, "product"),
            "pricing_markup": get_pricing_markup(session),
        },
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
    mayorista_price_gs: str = Form(""),
    iva_rate: str = Form("10"),
    requires_rspa: str = Form(""),
    rspa_number: str = Form(""),
    rspa_expiry: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Update existing product."""
    from app.rms.validation import (
        require_text, optional_text, parse_money_gs, validate_url, parse_date_iso,
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

    # Wholesale price (mayorista) — optional B2B field.
    mayorista_price = parse_money_gs(mayorista_price_gs, allow_zero=True) if mayorista_price_gs.strip() else None

    # IVA rate — validated against allowed values.
    iva_valid = iva_rate in ("10", "5", "0", "exento")
    iva_clean = iva_rate if iva_valid else "10"

    # RSPA fields.
    requires_rspa_bool = requires_rspa == "on"
    rspa_number_clean = optional_text(rspa_number, max_len=30)
    rspa_expiry_clean = parse_date_iso(rspa_expiry) if rspa_expiry.strip() else None

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
    p.mayorista_price_gs = mayorista_price
    p.iva_rate = iva_clean
    p.requires_rspa = requires_rspa_bool
    p.rspa_number = rspa_number_clean
    p.rspa_expiry = rspa_expiry_clean
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

@router.post("/upload-image")
async def product_upload_image(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Upload a product image. Stores in app/static/uploads/ and returns the URL.

    Accepts: png, jpg, jpeg, webp, gif. Max 5 MB.
    Returns: {"url": "/static/uploads/", "filename": "..."}
    """
    from app.auth import using_supabase, _supabase_enabled

    # Re-use the same auth as the rest of the products router
    _ = session  # keep signature; auth is enforced by router-level dependency

    # Validate content type
    allowed_types = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=415,
            detail=f"Tipo de archivo no permitido: {file.content_type}. Usa PNG, JPG, WebP o GIF.",
        )

    # Read content (max 5 MB)
    content_bytes = await file.read()
    if not content_bytes:
        raise HTTPException(
            status_code=400,
            detail="Archivo vacío.",
        )
    max_size = 5 * 1024 * 1024
    if len(content_bytes) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"Imagen muy grande ({len(content_bytes) // 1024} KB). Máximo 5 MB.",
        )

    # Generate a unique filename: <random>.<ext>
    ext_map = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    ext = ext_map[file.content_type]
    name = f"{datetime.now(timezone.utc).strftime('%Y%m%d')}-{pysecrets.token_hex(8)}{ext}"

    # Save to app/static/uploads/ (portable: resolved from the package,
    # never a hardcoded absolute host path)
    from app.rms.static_paths import app_root

    uploads_dir = app_root() / "static" / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    target = uploads_dir / name
    target.write_bytes(content_bytes)

    url = f"/static/uploads/{name}"
    return JSONResponse({"url": url, "filename": name, "size": len(content_bytes)})
