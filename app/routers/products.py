"""app/routers/products.py — CRUD endpoints for products.

Per dev plan §9 Task 4.
"""

from __future__ import annotations

import csv
import io
import secrets as pysecrets
from datetime import datetime, timedelta, timezone

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from loguru import logger
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.auth import require_login_or_disabled as require_login
from app.rms.costing import batch_products_cost_margin, product_margin, product_unit_cost_gs
from app.rms.dependencies import get_session
from app.rms.models import Customer, Product, Recipe, Sale
from app.rms.observability import record_audit
from app.rms.rate_limit import read_rate_limit_dependency
from app.services.template_render import render

router = APIRouter(prefix="/productos", dependencies=[Depends(require_login)])


# C2 — Public router for the customer-facing tablet menu.
# Mounted at app root so the URL is `/m/{slug}` (short enough to type
# on a 1280×720 tablet). The slug is the product's `tablet_slug`
# column; products without a slug or with `tablet_visible=False`
# are not addressable through this router.
public_router = APIRouter()


@router.get(
    "/api/search",
    response_class=JSONResponse,
    dependencies=[Depends(read_rate_limit_dependency(60, route_tag="api.search.products"))],
)
def products_api_search(
    q: str = Query("", description="Search query"),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Search products by name/portion/sku for combobox pickers.

    Used by /pedidos/nuevo and /merma to filter a list of 30+ products
    quickly without scrolling a native <select>. Returns up to `limit`
    matching products ordered by name.

    BACKLOG #10: rate-limited at 60 reads/minute/IP via the
    `read_rate_limit_dependency` (audit-log sliding window). Bypassed
    when AIW_SASKIA_AUTH_DISABLED=1 (tests).
    """
    if not q or q.strip() == "":
        # No query: return all available (most-used come first).
        rows = session.scalars(select(Product).order_by(Product.name).limit(limit)).all()
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
            "sold_by_weight": bool(p.sold_by_weight),
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


@router.get("/api/tags", response_class=JSONResponse)
def products_api_tags(
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Return distinct non-empty tags across all products."""
    rows = session.scalars(
        select(Product.tags).where(Product.tags.is_not(None)).where(Product.tags != "").distinct()
    ).all()
    all_tags: set[str] = set()
    for row in rows:
        for t_ in (t__.strip() for t__ in row.split(",")):
            if t_:
                all_tags.add(t_)
    return JSONResponse({"tags": sorted(all_tags)})


@router.get("/api/categories", response_class=JSONResponse)
def products_api_categories(
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Return distinct non-empty categories across all products."""
    rows = session.scalars(
        select(Product.category)
        .where(Product.category.is_not(None))
        .where(Product.category != "")
        .distinct()
    ).all()
    return JSONResponse({"categories": sorted(r for r in rows if r)})


@router.get("", response_class=HTMLResponse)
def products_list(
    request: Request,
    q: str | None = None,
    has_recipe: str | None = None,
    margen: str | None = Query(None, description="Filter by margin state: negativo/bajo/ok/alto"),
    disponibles: str | None = Query(None, description="Filter availability: si/no"),
    tag: str | None = Query(None, description="Filter by tag (partial match on tags field)"),
    category: str | None = Query(None, description="Filter by category (exact match)"),
    sort: str | None = Query(
        None, description="Sort column: name, sale_price_gs, cost_gs, margin_gs"
    ),
    dir: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """List all products with cost + margin. Batch-loads to avoid N+1.
    Paginated at 50/page. Dead products (never sold) are flagged.

    Optional filter (?q=substring, ?has_recipe=yes/no).
    """
    PER_PAGE = 50

    # Build base query with filters
    stmt, count_stmt = _build_products_query(q, has_recipe, disponibles, tag, category)

    # Apply filters that affect pagination
    margen_sel = (margen or "").strip()
    disp_sel = (disponibles or "").strip()
    tag_sel = (tag or "").strip()
    category_sel = (category or "").strip()

    # Count total
    total = session.scalar(count_stmt) or 0
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    page = min(page, total_pages)

    # Load supporting data
    sold_product_ids = _load_sold_product_ids(session)
    produced_by_pid = _load_production_stats(session)

    # Apply pagination and eager-load
    offset = (page - 1) * PER_PAGE
    stmt = stmt.offset(offset).limit(PER_PAGE)
    stmt = stmt.options(selectinload(Product.recipe))
    products = session.scalars(stmt).all()

    # Decorate products with cost, margin, prime cost
    decorated = _decorate_products_with_costs(session, list(products))

    # Add production stats
    _add_production_stats_to_products(decorated, produced_by_pid, sold_product_ids)

    # Add cost freshness
    _add_cost_freshness(session, decorated, list(products))

    # Apply margin filter (post-costing, in-memory)
    if margen_sel:
        decorated = _filter_by_margin(decorated, margen_sel)
        total = len(decorated)

    # Apply in-memory sort
    if sort and sort in ("name", "sale_price_gs", "cost_gs", "margin_gs"):
        reverse = dir == "desc"
        decorated.sort(key=lambda r: r.get(sort) or 0, reverse=reverse)

    return render(
        request,
        "productos.html",
        _build_template_context(
            decorated,
            q,
            has_recipe,
            margen_sel,
            disp_sel,
            tag_sel,
            category_sel,
            sort,
            dir,
            page,
            total_pages,
            total,
            PER_PAGE,
            session,
        ),
    )


def _build_products_query(
    q: str | None,
    has_recipe: str | None,
    disponibles: str | None,
    tag: str | None,
    category: str | None,
) -> tuple:
    """Build the base products query with filters applied.

    Returns (stmt, count_stmt).
    Extracted from products_list to reduce complexity.
    """
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

    disp_sel = (disponibles or "").strip()
    if disp_sel == "si":
        stmt = stmt.where(Product.is_available.is_(True))
        count_stmt = count_stmt.where(Product.is_available.is_(True))
    elif disp_sel == "no":
        stmt = stmt.where(Product.is_available.is_(False))
        count_stmt = count_stmt.where(Product.is_available.is_(False))

    tag_sel = (tag or "").strip()
    if tag_sel:
        stmt = stmt.where(Product.tags.ilike(f"%{tag_sel}%"))
        count_stmt = count_stmt.where(Product.tags.ilike(f"%{tag_sel}%"))

    category_sel = (category or "").strip()
    if category_sel:
        stmt = stmt.where(Product.category == category_sel)
        count_stmt = count_stmt.where(Product.category == category_sel)

    return stmt, count_stmt


def _load_sold_product_ids(session: Session) -> set:
    """Load set of product IDs that have at least one sale.

    Extracted from products_list to reduce complexity.
    """
    return set(session.scalars(select(Sale.product_id).distinct()).all())


def _load_production_stats(session: Session) -> dict[int, dict]:
    """Load production completion stats per product.

    Returns dict mapping product_id to {total, last_date, last_30d}.
    Extracted from products_list to reduce complexity.
    """
    from app.rms.models import ProductionCompletion

    produced_rows = session.execute(
        select(
            ProductionCompletion.product_id,
            func.sum(ProductionCompletion.completed_qty),
            func.max(ProductionCompletion.for_date),
            func.sum(
                case(
                    (
                        ProductionCompletion.for_date >= func.date("now", "-30 day"),
                        ProductionCompletion.completed_qty,
                    ),
                    else_=0.0,
                )
            ),
        ).group_by(ProductionCompletion.product_id)
    ).all()
    return {
        r[0]: {"total": float(r[1] or 0.0), "last_date": r[2], "last_30d": float(r[3] or 0.0)}
        for r in produced_rows
    }


def _decorate_products_with_costs(session: Session, products: list) -> list[dict]:
    """Decorate products with cost, margin, and prime cost data.

    Extracted from products_list to reduce complexity.
    """
    from app.rms.prime_cost import batch_compute_prime_cost, compute_prime_cost

    # One batch call replaces N+1 cost/margin queries (Neon round-trips).
    batch_results = batch_products_cost_margin(session, products)
    # Batched prime cost (compliance-info singleton + product.recipe
    # eager-loaded) — avoids the per-product N+1 that this route had
    # before. Falls back to the per-product path only on cache misses.
    try:
        prime_batch = batch_compute_prime_cost(session, products)
    except Exception:
        prime_batch = {}

    decorated = []
    for p in products:
        cost, margin = batch_results.get(
            p.id,
            (
                product_unit_cost_gs(session, p.id),
                product_margin(session, p.id),
            ),
        )
        pc = prime_batch.get(p.id) or compute_prime_cost(session, p.id)
        decorated.append(_build_product_dict(p, cost, margin, pc))
    return decorated


def _build_product_dict(p: Product, cost: object, margin: tuple, pc: object) -> dict:
    """Build a decorated product dict with all cost/margin fields.

    Extracted from products_list to reduce complexity.
    """
    return {
        "id": p.id,
        "name": p.name,
        "sku": p.sku,
        "image_url": p.image_url,
        "is_available": p.is_available,
        "is_favorite": bool(p.is_favorite),
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
    }


def _add_production_stats_to_products(
    decorated: list[dict],
    produced_by_pid: dict[int, dict],
    sold_product_ids: set,
) -> None:
    """Add production stats and dead-product flag to decorated products.

    Extracted from products_list to reduce complexity.
    """
    for r in decorated:
        r["is_dead"] = r["id"] not in sold_product_ids
        # T-2026-10-05: actual production totals (from close-day
        # records). lifetime total, last-30d, and last produced date.
        stats = produced_by_pid.get(r["id"], {})
        r["produced_total"] = stats.get("total", 0.0)
        r["produced_last_30d"] = stats.get("last_30d", 0.0)
        r["produced_last_date"] = stats.get("last_date")


def _add_cost_freshness(session: Session, decorated: list[dict], products: list) -> None:
    """Add cost freshness timestamp to each product.

    Extracted from products_list to reduce complexity.
    """
    from app.rms.cost_freshness import product_cost_freshness

    freshness = product_cost_freshness(session, products)
    for r in decorated:
        r["cost_updated_at"] = freshness.get(r["id"])


def _filter_by_margin(decorated: list[dict], margen_sel: str) -> list[dict]:
    """Filter products by margin state.

    States: negativo (<0), bajo (<30%), ok (30-70%), alto (>70%).
    Extracted from products_list to reduce complexity.
    """

    def _mstate(r: dict) -> str:
        if r["margin_ratio"] is None:
            return "sin-datos"
        pct = r["margin_ratio"] * 100
        if pct < 0:
            return "negativo"
        if pct < 30:
            return "bajo"
        if pct <= 70:
            return "ok"
        return "alto"

    return [r for r in decorated if _mstate(r) == margen_sel]


def _build_template_context(
    decorated: list[dict],
    q: str | None,
    has_recipe: str | None,
    margen_sel: str,
    disp_sel: str,
    tag_sel: str,
    category_sel: str,
    sort: str | None,
    dir: str,
    page: int,
    total_pages: int,
    total: int,
    PER_PAGE: int,
    session: Session,
) -> dict:
    """Build the template context dict for the products page.

    Extracted from products_list to reduce complexity.
    """
    return {
        "products": decorated,
        "q": q or "",
        "has_recipe": has_recipe or "",
        "margen_sel": margen_sel,
        "disp_sel": disp_sel,
        "tag_sel": tag_sel,
        "category_sel": category_sel,
        # UI-V2: reference 'now' for the cost-freshness column.
        "now_utc": datetime.now(timezone.utc).replace(tzinfo=None),
        "total_all": session.scalar(select(func.count()).select_from(Product)) or 0,
        "sort": sort or "",
        "dir": dir,
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "per_page": PER_PAGE,
        "page_start": (page - 1) * PER_PAGE + 1,
        "page_end": min(page * PER_PAGE, total),
    }


@router.get("/export.csv")
def products_export_csv(
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    """Export all products as a CSV download."""
    products = session.scalars(select(Product).order_by(Product.name)).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "name",
            "sku",
            "is_available",
            "portion_label",
            "sale_price_gs",
            "recipe_id",
            "cost_gs",
            "notes",
        ]
    )
    for p in products:
        cost = product_unit_cost_gs(session, p.id)
        writer.writerow(
            [
                p.id,
                p.name,
                p.sku or "",
                p.is_available,
                p.portion_label,
                p.sale_price_gs,
                p.recipe_id or "",
                cost.batch_cost_gs if cost else "",
                p.notes or "",
            ]
        )

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
    from app.rms.tagging import list_tags_for_kind

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
    tablet_slug: str = Form(""),
    # Optional so an unchecked checkbox (which the browser omits from
    # form data) is detected as missing. The new-product form renders
    # the checkbox checked by default, so realistic POSTs still send
    # ``tablet_visible=on``; this default of None only kicks in when
    # a hand-crafted POST omits the field.
    tablet_visible: str | None = Form(None),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Create new product.

    Centralized validation (app.rms.validation) returns Spanish 400s on
    bad input. Tags are stored as a comma-separated string per the model.
    """
    clean_name, portion_label_clean, price, rid, available = _extract_basic_fields(
        name, portion_label, sale_price_gs, recipe_id, is_available
    )
    notes_clean, sku_clean, image_url_clean = _extract_meta_fields(notes, sku, image_url)
    category_clean, tags_clean = _extract_category_tags(category, tags)
    mayorista_price = _parse_mayorista_price(mayorista_price_gs)
    iva_clean = _validate_iva_rate(iva_rate)
    requires_rspa_bool, rspa_number_clean, rspa_expiry_clean = _extract_rspa_fields(
        requires_rspa, rspa_number, rspa_expiry
    )
    tablet_visible_bool, tablet_slug_clean = _extract_tablet_fields(clean_name, tablet_slug, tablet_visible)

    # Wave 2 — auto-fill category + tags from the linked recipe if operator
    # left either blank. Recipe's family → category, dietary_tags → tags.
    category_clean, tags_clean = _autofill_from_recipe(
        session, rid, category_clean, tags_clean
    )

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
        tablet_slug=tablet_slug_clean,
        tablet_visible=tablet_visible_bool,
    )
    session.add(product)
    _commit_product_with_audit(request, session, product, clean_name, price, tablet_slug_clean)
    return RedirectResponse(url="/productos", status_code=303)


def _extract_basic_fields(
    name: str, portion_label: str, sale_price_gs: str, recipe_id: str, is_available: str
) -> tuple[str, str, int, int | None, bool]:
    """Extract and validate basic product fields.

    Extracted from product_create to reduce complexity.
    """
    from app.rms.validation import optional_text, parse_money_gs, require_text

    clean_name = require_text(name, field="nombre", max_len=120)
    portion_label_clean = optional_text(portion_label, max_len=60) or "1 unidad"
    price = parse_money_gs(sale_price_gs, allow_zero=True)
    if price < 0:
        raise HTTPException(status_code=400, detail="Precio no puede ser negativo")
    rid = int(recipe_id) if recipe_id else None
    available = is_available == "on"
    return clean_name, portion_label_clean, price, rid, available


def _extract_meta_fields(notes: str, sku: str, image_url: str) -> tuple:
    """Extract and validate meta fields (notes, sku, image_url).

    Extracted from product_create to reduce complexity.
    """
    from app.rms.validation import optional_text, validate_url

    notes_clean = optional_text(notes, max_len=2000)
    sku_clean = optional_text(sku, max_len=32)
    image_url_clean = validate_url(image_url)
    return notes_clean, sku_clean, image_url_clean


def _extract_category_tags(category: str, tags: str) -> tuple:
    """Extract and validate category and tags fields.

    Extracted from product_create to reduce complexity.
    """
    from app.rms.validation import optional_text

    category_clean = optional_text(category, max_len=32)
    tags_clean = optional_text(tags, max_len=500)
    return category_clean, tags_clean


def _parse_mayorista_price(mayorista_price_gs: str) -> int | None:
    """Parse the wholesale (mayorista) price.

    Extracted from product_create to reduce complexity.
    """
    from app.rms.validation import parse_money_gs

    if not mayorista_price_gs.strip():
        return None
    return parse_money_gs(mayorista_price_gs, allow_zero=True)


def _validate_iva_rate(iva_rate: str) -> str:
    """Validate the IVA rate against allowed values.

    Extracted from product_create to reduce complexity.
    """
    valid_values = ("10", "5", "0", "exento")
    return iva_rate if iva_rate in valid_values else "10"


def _extract_rspa_fields(
    requires_rspa: str, rspa_number: str, rspa_expiry: str
) -> tuple[bool, str | None, str | None]:
    """Extract and validate RSPA fields.

    Extracted from product_create to reduce complexity.
    """
    from app.rms.validation import optional_text, parse_date_iso

    requires_rspa_bool = requires_rspa == "on"
    rspa_number_clean = optional_text(rspa_number, max_len=30)
    rspa_expiry_clean = parse_date_iso(rspa_expiry) if rspa_expiry.strip() else None
    return requires_rspa_bool, rspa_number_clean, rspa_expiry_clean


def _extract_tablet_fields(clean_name: str, tablet_slug: str, tablet_visible: str | None) -> tuple[bool, str]:
    """Extract and validate tablet visibility and slug fields.

    C2 — tablet-menu visibility. Slug is auto-generated from the
    product name when the operator leaves it blank (so 95% of products
    are zero-effort to publish). Manual override wins on user input.
    Extracted from product_create to reduce complexity.
    """
    from app.rms.validation import slugify, validate_slug

    tablet_visible_bool = tablet_visible == "on"
    tablet_slug_clean = validate_slug(tablet_slug or slugify(clean_name), field="slug")
    return tablet_visible_bool, tablet_slug_clean


def _autofill_from_recipe(
    session, rid: int | None, category_clean: str | None, tags_clean: str | None
) -> tuple[str | None, str | None]:
    """Auto-fill category + tags from the linked recipe if operator left blank.

    Wave 2 — Recipe's family → category, dietary_tags → tags.
    Extracted from product_create to reduce complexity.
    """
    if not rid or (category_clean and tags_clean):
        return category_clean, tags_clean
    from app.rms.models import Recipe

    linked_recipe = session.get(Recipe, rid)
    if linked_recipe is None:
        return category_clean, tags_clean
    if not category_clean and linked_recipe.family:
        category_clean = linked_recipe.family
    if not tags_clean and linked_recipe.dietary_tags:
        tags_clean = linked_recipe.dietary_tags
    return category_clean, tags_clean


def _commit_product_with_audit(
    request: Request,
    session,
    product: Product,
    clean_name: str,
    price: int,
    tablet_slug_clean: str,
) -> None:
    """Commit the new product and record audit entry.

    Distinguishes name vs slug uniqueness conflicts so the operator
    gets a useful error. C2 — slug uniqueness is independent of name.
    Extracted from product_create to reduce complexity.
    """
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        slug_taken = _is_slug_taken(session, tablet_slug_clean)
        if slug_taken:
            raise HTTPException(
                status_code=409,
                detail=f"Ya existe otro producto con slug {tablet_slug_clean!r}. "
                "Elegí otro slug para el menú.",
            ) from None
        raise HTTPException(
            status_code=409, detail=f"Ya existe un producto con nombre {clean_name!r}"
        ) from None

    record_audit(
        request,
        session=session,
        action="write.product.create",
        target_type="product",
        target_id=product.id,
        detail={"name": clean_name, "price_gs": price},
    )
    session.commit()


def _is_slug_taken(session, tablet_slug_clean: str) -> bool:
    """Check if a tablet slug is already taken.

    Extracted from _commit_product_with_audit to reduce complexity.
    """
    if not tablet_slug_clean:
        return False
    return (
        session.scalar(select(Product).where(Product.tablet_slug == tablet_slug_clean))
        is not None
    )


@router.get("/{p_id}/editar", response_class=HTMLResponse)
def product_edit(
    p_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Show edit form. Passes DB-driven catalogs (see product_new)."""
    from app.rms.categories import list_categories as list_cats
    from app.rms.settings_runtime import get_pricing_markup
    from app.rms.tagging import list_tags_for_kind

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
    tablet_slug: str = Form(""),
    # Optional so an unchecked checkbox (which the browser omits from
    # form data) is detected as missing rather than defaulting to "on".
    tablet_visible: str | None = Form(None),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Update existing product."""
    from app.rms.validation import (
        optional_text,
        parse_date_iso,
        parse_money_gs,
        require_text,
        slugify,
        validate_slug,
        validate_url,
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
    mayorista_price = (
        parse_money_gs(mayorista_price_gs, allow_zero=True) if mayorista_price_gs.strip() else None
    )

    # IVA rate — validated against allowed values.
    iva_valid = iva_rate in ("10", "5", "0", "exento")
    iva_clean = iva_rate if iva_valid else "10"

    # RSPA fields.
    requires_rspa_bool = requires_rspa == "on"
    rspa_number_clean = optional_text(rspa_number, max_len=30)
    rspa_expiry_clean = parse_date_iso(rspa_expiry) if rspa_expiry.strip() else None

    # C2 — tablet-menu visibility. Slug auto-generates from the name on
    # blank input; the operator can also type a custom slug.
    tablet_visible_bool = tablet_visible == "on"
    tablet_slug_clean = validate_slug(tablet_slug or slugify(clean_name), field="slug")

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
    p.tablet_slug = tablet_slug_clean
    p.tablet_visible = tablet_visible_bool
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        # C2 — slug uniqueness is independent of name. A duplicate slug
        # on update raises IntegrityError just like a duplicate name.
        slug_taken = (
            tablet_slug_clean
            and session.scalar(
                select(Product).where(Product.tablet_slug == tablet_slug_clean, Product.id != p_id)
            )
            is not None
        )
        if slug_taken:
            raise HTTPException(
                status_code=409,
                detail=f"Ya existe otro producto con slug {tablet_slug_clean!r}. "
                "Elegí otro slug para el menú.",
            ) from None
        raise HTTPException(
            status_code=409, detail=f"Ya existe otro producto con nombre {clean_name!r}"
        ) from None
    record_audit(
        request,
        session=session,
        action="write.product.update",
        target_type="product",
        target_id=p.id,
        detail={"name": clean_name, "price_gs": price},
    )
    session.commit()
    return RedirectResponse(url="/productos", status_code=303)


@router.post("/{p_id}/favorito")
def product_toggle_favorite(
    p_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Toggle product.is_favorite (P3 UX): favorites pin to the ventas
    POS quick-sell grid even with zero recent sales."""
    p = session.get(Product, p_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    p.is_favorite = not p.is_favorite
    session.commit()
    record_audit(
        request,
        session=session,
        action="write.product.update",
        target_type="product",
        target_id=p_id,
        detail={"favorite": p.is_favorite, "name": p.name},
    )
    session.commit()
    # Back to wherever the toggle came from (keep filters/sort/page)
    return RedirectResponse(url=request.headers.get("referer") or "/productos", status_code=303)


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

    deleted_name = p.name
    session.delete(p)
    record_audit(
        request,
        session=session,
        action="write.product.delete",
        target_type="product",
        target_id=p_id,
        detail={"name": deleted_name},
    )
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
    return RedirectResponse(
        url=f"/productos?flash=products_bulk_deleted:{deleted}:{skipped}",
        status_code=303,
    )


# ─── Bulk edit ──────────────────────────────────────────────────────────────────


@router.post("/bulk-edit")
async def product_bulk_edit(
    request: Request,
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Bulk-edit products: price_pct (±% on sale_price_gs),
    set_availability (bool), set_category (string)."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "JSON body required"})

    product_ids: list[int] = body.get("product_ids", [])
    action: str = body.get("action", "")
    value: float | bool | str = body.get("value")

    if not product_ids or not action:
        return JSONResponse(status_code=400, content={"error": "product_ids and action required"})

    valid_actions = {"price_pct", "set_availability", "set_category"}
    if action not in valid_actions:
        return JSONResponse(
            status_code=400, content={"error": f"action must be one of {valid_actions}"}
        )

    updated = 0
    for pid in product_ids:
        p = session.get(Product, pid)
        if p is None:
            continue
        if action == "price_pct":
            if not isinstance(value, (int, float)):
                return JSONResponse(
                    status_code=400, content={"error": "price_pct requires numeric value"}
                )
            p.sale_price_gs = max(0, int(p.sale_price_gs * (1 + float(value) / 100)))
        elif action == "set_availability":
            p.is_available = bool(value)
        elif action == "set_category":
            p.category = str(value)[:32]
        updated += 1

    session.commit()
    return JSONResponse({"updated": updated})


# ─── API helpers ───────────────────────────────────────────────────────────────


@router.get("/importar", response_class=HTMLResponse)
def products_import_page(request: Request) -> HTMLResponse:
    """Show the CSV import form."""
    return render(request, "productos_importar.html", {})


@router.post("/importar")
async def products_import_csv(
    request: Request,
    file: UploadFile | None = File(None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Parse uploaded CSV, find-or-create each product, return results."""
    from app.rms.validation import optional_text, parse_money_gs

    # FastAPI's multipart parser populates `file` via the File(...) param
    # declaration above. Previously this called `request._form()` (a
    # private Starlette attr that's None on every sync handler), which
    # raised 'NoneType is not callable' on the test client. Tier 3 smoke
    # (2026-10-01) caught the regression.
    if not file or not hasattr(file, "filename"):
        return render(
            request, "productos_importar.html", {"error": "No se recibió ningún archivo."}
        )

    content = (await file.read()).decode("utf-8", errors="replace")
    reader = csv.DictReader(content.splitlines())
    if reader.fieldnames is None:
        return render(
            request, "productos_importar.html", {"error": "El archivo no parece ser un CSV válido."}
        )

    expected = {
        "name",
        "sku",
        "category",
        "portion_label",
        "sale_price_gs",
        "yield_percentage",
        "tags",
    }
    if not expected.issubset(reader.fieldnames):
        return render(
            request,
            "productos_importar.html",
            {
                "error": f"Columnas requeridas faltantes. Esperado: {', '.join(sorted(expected))}. Encontrado: {', '.join(reader.fieldnames)}"
            },
        )

    created = 0
    updated = 0
    errors: list[dict] = []

    for row_num, row in enumerate(reader, start=2):
        try:
            name = (row.get("name") or "").strip()
            if not name:
                errors.append({"row": row_num, "error": "Nombre vacío"})
                continue

            # Find or create
            existing = session.scalars(
                select(Product).where(func.lower(Product.name) == name.lower()).limit(1)
            ).first()

            sku = optional_text(row.get("sku", ""), max_len=32)
            category = optional_text(row.get("category", ""), max_len=32)
            portion_label = optional_text(row.get("portion_label", ""), max_len=60) or "1 unidad"
            price = parse_money_gs(row.get("sale_price_gs", ""), allow_zero=True)
            tags = optional_text(row.get("tags", ""), max_len=500)

            if existing:
                existing.sku = sku
                existing.category = category
                existing.portion_label = portion_label
                existing.sale_price_gs = price
                existing.tags = tags
                updated += 1
            else:
                product = Product(
                    name=name,
                    sku=sku,
                    category=category,
                    portion_label=portion_label,
                    sale_price_gs=price,
                    tags=tags,
                    is_available=True,
                )
                session.add(product)
                created += 1
            session.commit()
        except Exception as e:
            session.rollback()
            errors.append({"row": row_num, "error": str(e)})

    return render(
        request,
        "productos_importar.html",
        {
            "created": created,
            "updated": updated,
            "errors": errors,
        },
    )


__all__ = ["public_router", "router"]


@router.post("/upload-image")
async def product_upload_image(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Upload a product image.

    BACKLOG #37 (2026-10-02): When Supabase Storage is enabled (env
    configured + reachable), uploads go to the `product-images` bucket
    and the response carries a public Supabase URL. Otherwise falls
    back to local `app/static/uploads/` (the prior behavior) so the
    route stays functional in dev / when the Supabase project is down.

    Accepts: png, jpg, jpeg, webp, gif. Max 5 MB.
    Returns: {"url": "<public_url>", "filename": "...", "size": N,
              "backend": "supabase_storage" | "local"}
    """

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

    original_name = file.filename or "image"

    # Try Supabase Storage first when enabled.
    from app.rms.storage import (
        is_storage_enabled,
        upload_product_image,
    )

    if is_storage_enabled():
        try:
            result = upload_product_image(content_bytes, file.content_type, original_name)
            return JSONResponse(result)
        except ValueError as exc:
            msg = str(exc)
            if msg.startswith("unsupported_content_type"):
                raise HTTPException(status_code=415, detail=msg) from exc
            if msg == "empty_content":
                raise HTTPException(status_code=400, detail=msg) from exc
            if msg.startswith("too_large"):
                raise HTTPException(status_code=413, detail=msg) from exc
            raise HTTPException(status_code=500, detail=msg) from exc
        except Exception:
            # Supabase rejected (DNS, network, RLS, 4xx from bad path).
            # Log + fall back to local storage so the operator's upload
            # still succeeds. /healthz/summary will surface the supabase
            # issue separately via the deps probe.
            logger.exception("supabase storage upload failed, falling back to local")
            # Don't 503 the user — the local fallback is the safer path.

    # --- Local filesystem fallback ---
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
    return JSONResponse(
        {
            "url": url,
            "filename": name,
            "size": len(content_bytes),
            "backend": "local",
        }
    )


# ─── C2 — Public tablet menu (/m/{slug}) ──────────────────────────────────────
# No auth, no sidebar, mobile-first CSS for a 1280×720 walk-in tablet.
# Each product has its OWN /m/{slug} page so the bakery can deep-link a
# single item to WhatsApp ("mirá nuestro chipa: sazon.app/m/chipa-guazu").
# A slug that doesn't match any visible product 404s — same behavior as
# /p/{token} so an attacker can't enumerate the catalog by varying the slug.


def _public_branding(session: Session) -> dict:
    """Per-shop branding for public pages (/menu, /m/{slug}).

    Priority: SettingsKV("shop_name") -> Tenant.business_name -> "Sazon".
    Accent color: Tenant.primary_color (hex); currency: Tenant.currency.
    Single-tenant app: first Tenant row is THE shop.
    """
    from app.rms.models import SettingsKV, Tenant

    tenant = session.scalars(select(Tenant).limit(1)).first()
    business = (getattr(tenant, "business_name", "") or "").strip()
    primary = (getattr(tenant, "primary_color", "") or "").strip()
    currency = (getattr(tenant, "currency", "") or "").strip() or "Gs."

    kv = session.get(SettingsKV, "shop_name")
    kv_name = ""
    if kv is not None:
        try:
            import json as _json

            raw = getattr(kv, "value_json", "") or ""
            val = _json.loads(raw) if raw else ""
            kv_name = (
                str(val).strip() if not isinstance(val, dict) else str(val.get("name", "")).strip()
            )
        except Exception:
            kv_name = ""

    name = kv_name or business or "Sazon"
    return {"shop_name": name, "brand_color": primary, "currency_label": currency}


@public_router.get("/m/{slug}", response_class=HTMLResponse)
def public_menu(
    request: Request,
    slug: str,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Public tablet-menu page for one product. No auth required.

    URL: /m/{tablet_slug}

    Returns 200 with the tablet template if a product exists with
    ``tablet_slug == slug`` and ``tablet_visible`` is True.
    Returns 404 otherwise — never leaks the existence of hidden products.
    """
    from app.rms.models import Product

    slug_clean = (slug or "").strip()
    if not slug_clean:
        raise HTTPException(status_code=404, detail="Menú no encontrado")

    product = session.scalar(
        select(Product).where(
            Product.tablet_slug == slug_clean,
            Product.tablet_visible.is_(True),
        )
    )
    if product is None:
        # Same 404 message whether the slug doesn't exist OR is hidden,
        # so an attacker can't enumerate the hidden catalog.
        raise HTTPException(status_code=404, detail="Menú no encontrado")

    # Build the card payload. We only surface what a customer needs:
    # name, photo, portion label, price. No cost / margin / stock.
    payload = {
        "id": product.id,
        "name": product.name,
        "portion_label": product.portion_label or "",
        "sale_price_gs": product.sale_price_gs,
        "image_url": product.image_url or "",
        "category": product.category or "",
        "tags": [t.strip() for t in (product.tags or "").split(",") if t.strip()],
        "notes": product.notes or "",
        "tablet_slug": product.tablet_slug or "",
    }
    return render(
        request,
        "menu_tablet.html",
        {
            "product": payload,
            **_public_branding(session),
        },
    )


# ─── Public full-catalog menu (/menu) ─────────────────────────────────────────
# No auth. Every available product with tablet_visible=True, grouped by
# category, in one scrollable page. This is the link to print on the door
# sticker / WhatsApp bio — /m/{slug} deep-links one item, /menu shows all.

# Canonical category display order; unknown categories append alphabetically.
_MENU_CATEGORY_ORDER = ["panaderia", "pasteleria", "bebida", "otro"]
_MENU_CATEGORY_LABELS = {
    "panaderia": "Panadería",
    "pasteleria": "Pastelería",
    "bebida": "Bebidas",
    "otro": "Otros",
}


@public_router.get("/menu", response_class=HTMLResponse)
def public_menu_catalog(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Public, no-login menu page: the whole visible catalog.

    Only products with ``is_available`` AND ``tablet_visible`` are listed —
    the operator already controls per-product visibility from the producto
    form, so /menu never leaks hidden or out-of-stock items. Grouped by
    category with in-page anchors; prices formatted in Gs.
    """
    from app.rms.models import Product

    products = session.scalars(
        select(Product)
        .where(Product.is_available.is_(True), Product.tablet_visible.is_(True))
        .order_by(Product.category, Product.name)
    ).all()

    # Group, preserving canonical category order then alphabetic extras.
    groups: dict[str, list[dict]] = {}
    for p in products:
        cat = (p.category or "otro").strip().lower() or "otro"
        groups.setdefault(cat, []).append(
            {
                "id": p.id,
                "name": p.name,
                "portion_label": p.portion_label or "",
                "sale_price_gs": p.sale_price_gs,
                "image_url": p.image_url or "",
                "tablet_slug": p.tablet_slug or "",
                "notes": p.notes or "",
                "tags": [t.strip() for t in (p.tags or "").split(",") if t.strip()],
            }
        )

    ordered_keys = [c for c in _MENU_CATEGORY_ORDER if c in groups]
    ordered_keys += sorted(k for k in groups if k not in _MENU_CATEGORY_ORDER)

    menu_groups = [
        {
            "key": k,
            "label": _MENU_CATEGORY_LABELS.get(k, k.title()),
            # NOTE: key must not be 'items' — dict.items() is a method, so
            # Jinja's `g.items` in the template would resolve to the method,
            # not this list.
            "products": groups[k],
        }
        for k in ordered_keys
    ]

    # WhatsApp ordering: the shop's order-taking number lives in SettingsKV
    # key 'shop_whatsapp' (digits only, e.g. 595981123456). No number set ->
    # the cart/order UI stays hidden (menu is then a pure brochure).
    from app.rms.models import SettingsKV

    wa_row = session.get(SettingsKV, "shop_whatsapp")
    shop_whatsapp = ""
    if wa_row is not None:
        raw = str(getattr(wa_row, "value_json", "") or "")
        shop_whatsapp = "".join(c for c in raw if c.isdigit())

    return render(
        request,
        "menu_publico.html",
        {
            "menu_groups": menu_groups,
            "total_items": len(products),
            **_public_branding(session),
            "shop_whatsapp": shop_whatsapp,
        },
    )


@router.get("/{p_id}", response_class=HTMLResponse)
def product_detail(
    p_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Customer-facing product detail page with metrics, recipes-using, recent sales.

    URL: /productos/{id}
    Shows product name, metrics strip, recipes using this product, recent sales.
    """
    p = session.get(Product, p_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    # Compute metrics using existing service modules or direct SQL queries
    from sqlalchemy import text

    from app.rms.costing import product_margin, product_unit_cost_gs

    # Current stock - use direct SQL query since no service function exists
    stock_query = text("""
        SELECT COALESCE(SUM(stock_qty), 0.0)
        FROM ingredient
        WHERE name = (SELECT name FROM product WHERE id = :p_id)
    """)
    stock_result = session.execute(stock_query, {"p_id": p_id}).scalar_one_or_none()

    # Current cost and margin
    cost = product_unit_cost_gs(session, p_id)
    margin = product_margin(session, p_id)

    # 30-day metrics - use direct SQL query since no service function exists
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    # Get last 30 days units sold and revenue
    sales_metrics = session.execute(
        select(func.sum(Sale.qty), func.sum(Sale.unit_price_gs * Sale.qty))
        .where(Sale.sold_at >= thirty_days_ago, Sale.product_id == p_id)
        .where(Sale.voided_at.is_(None))
    ).one()

    last_30d_units = sales_metrics[0] or 0
    last_30d_revenue = sales_metrics[1] or 0

    # Recipes using this product (max 10) - use direct SQL query
    recipes_query = text("""
        SELECT DISTINCT r.* FROM recipe r
        JOIN recipe_line rl ON r.id = rl.line_ref_id
        WHERE rl.line_ref_id = :p_id AND rl.line_kind = 'ingredient'
        LIMIT 10
    """)
    recipes_using = session.execute(recipes_query, {"p_id": p_id}).fetchall()

    # Recent sales (last 20, exclude voided) - use direct SQL query
    recent_sales = session.execute(
        select(Sale.sold_at, Customer.name, Sale.qty, Sale.unit_price_gs * Sale.qty)
        .join(Customer, Customer.id == Sale.customer_id, isouter=True)
        .where(Sale.product_id == p_id)
        .where(Sale.voided_at.is_(None))
        .order_by(Sale.sold_at.desc())
        .limit(20)
    ).all()

    # Margin percentage
    avg_margin_pct = None
    if margin and margin[1] is not None:
        avg_margin_pct = margin[1] * 100

    # Check if out of stock
    is_out_of_stock = stock_result is not None and stock_result <= 0

    return render(
        request,
        "producto_detalle.html",
        {
            "product": p,
            "current_stock": stock_result,
            "current_cost": cost,
            "current_price": p.sale_price_gs,
            "avg_margin_pct": avg_margin_pct,
            "last_30d_units": last_30d_units,
            "last_30d_revenue": last_30d_revenue,
            "recipes_using": recipes_using,
            "recent_sales": recent_sales,
            "is_out_of_stock": is_out_of_stock,
        },
    )
