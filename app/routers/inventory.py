"""app/routers/inventory.py — CRUD endpoints for ingredients.

Per dev plan §9 Task 3.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from loguru import logger
from sqlalchemy import case as sql_case
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import current_operator
from app.auth import require_login_or_disabled as require_login
from app.rms.catalogs_tags import list_allergens, list_dietary_tags
from app.rms.charts import sparkline
from app.rms.config import ASUNCION_TZ
from app.rms.dependencies import get_session
from app.rms.errors import (
    AlreadyExists,
    BadRequest,
    Conflict,
    NotFound,
)
from app.rms.ingredient_intel import classify_ingredient
from app.rms.messages import INGREDIENT_DUPLICATE_NAME, INGREDIENT_NAME_REQUIRED
from app.rms.models import (
    Ingredient,
    IngredientPriceEvent,
    IngredientVariant,
    Recipe,
    RecipeLine,
    StockMovement,
)
from app.rms.observability import record_audit
from app.rms.price_history import price_history, price_stats, record_price_event
from app.rms.rate_limit import read_rate_limit_dependency
from app.rms.units import Unit
from app.services.template_render import render

router = APIRouter(prefix="/inventario", dependencies=[Depends(require_login)])


@router.get("/api/packaging", response_class=JSONResponse)
def packaging_api_search(
    request: Request,
    q: str = Query(""),
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """US 4.1 — autocomplete for the sale's packaging picker.

    Returns packaging-flagged ingredients only (is_packaging=True).
    Response shape: [{"id": 12, "name": "Caja torta", "unit": "und",
                       "stock_qty": 5.0, "purchase_price_gs": 1500}, ...]
    """
    like = f"%{q.strip().lower()}%"
    rows = (
        session.execute(
            select(Ingredient)
            .where(Ingredient.is_packaging.is_(True))
            .where(func.lower(Ingredient.name).like(like))
            .order_by(Ingredient.name)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return JSONResponse(
        [
            {
                "id": r.id,
                "name": r.name,
                "unit": r.unit,
                "stock_qty": r.stock_qty,
                "purchase_price_gs": r.purchase_price_gs,
            }
            for r in rows
        ]
    )


@router.post("/{ing_id}/toggle-packaging")
def ingredient_toggle_packaging(
    ing_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """US 4.1 — flag/unflag an Ingredient as a packaging item.

    Operators click "Marcar como empaque" on a regular ingredient (e.g. a
    leftover "Caja torta 30cm" they want to track as packaging). The flag
    controls whether the sale's packaging picker shows this ingredient.
    """
    ing = session.get(Ingredient, ing_id)
    if ing is None:
        raise NotFound("Ingredient", id=ing_id)
    ing.is_packaging = not bool(ing.is_packaging)
    record_audit(
        request,
        session=session,
        action="ingredient.toggle_packaging",
        target_type="ingredient",
        target_id=ing_id,
        detail={"is_packaging": ing.is_packaging},
    )
    session.commit()
    back = request.headers.get("referer") or f"/inventario/{ing_id}"
    return RedirectResponse(url=back, status_code=303)


@router.get(
    "/api/search",
    response_class=JSONResponse,
    dependencies=[Depends(read_rate_limit_dependency(60, route_tag="api.search.ingredients"))],
)
def ingredients_api_search(
    q: str = Query("", description="Search query"),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Search ingredients by name for combobox pickers.

    Used by /merma and /pedidos/nuevo. Returns matching ingredients
    ordered by name, with up to `limit` rows. Empty query returns
    all ingredients up to limit (alphabetical).

    BACKLOG #10: rate-limited at 60 reads/minute/IP via the
    `read_rate_limit_dependency`.
    """
    if not q or q.strip() == "":
        rows = session.scalars(select(Ingredient).order_by(Ingredient.name).limit(limit)).all()
    else:
        like = f"%{q.strip().lower()}%"
        rows = session.scalars(
            select(Ingredient)
            .where(func.lower(Ingredient.name).like(like))
            .order_by(Ingredient.name)
            .limit(limit)
        ).all()
    payload = [
        {
            "id": ing.id,
            "name": ing.name,
            "unit": ing.unit,
            "stock_qty": ing.stock_qty or 0.0,
            "min_stock_qty": ing.min_stock_qty or 0.0,
            "purchase_price_gs": ing.purchase_price_gs or 0,
        }
        for ing in rows
    ]
    return JSONResponse({"results": payload, "count": len(payload)})


@router.get("/export.csv")
def inventory_export_csv(
    request: Request,
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """Export all ingredients as a CSV download (streaming)."""
    from app.rms.streaming_csv import stream_csv_rows

    ingredients = session.scalars(select(Ingredient).order_by(Ingredient.name)).all()

    def _iter():
        for i in ingredients:
            yield [
                i.id,
                i.name,
                i.unit,
                i.category or "",
                i.stock_qty,
                i.min_stock_qty,
                i.purchase_price_gs or "",
                i.opening_stock_qty or "",
                i.opening_stock_date or "",
                i.reorder_point or "",
                i.notes or "",
            ]

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return StreamingResponse(
        stream_csv_rows(
            [
                "id",
                "name",
                "unit",
                "category",
                "stock_qty",
                "min_stock_qty",
                "purchase_price_gs",
                "opening_stock_qty",
                "opening_stock_date",
                "reorder_point",
                "notes",
            ],
            _iter(),
        ),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=rms-inventory-{timestamp}.csv"},
    )


@router.get("", response_class=HTMLResponse)
def inventory_list(
    request: Request,
    sort: str | None = Query(
        None, description="Sort column: name, stock_qty, unit, min_stock_qty, purchase_price_gs"
    ),
    dir: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    expiry: str = Query("all", pattern="^(all|7days|30days|expired)$"),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """List all ingredients with stock badge. Paginated at 50/page.

    Refactored 2026-10-09 to reduce cognitive complexity from 198 to <10.
    """
    PER_PAGE = 50
    from datetime import timedelta

    today = datetime.now(ASUNCION_TZ).date()
    week_from_now = today + timedelta(days=7)
    month_from_now = today + timedelta(days=30)

    all_ings = session.scalars(select(Ingredient)).all()
    loaded_ids = set(session.scalars(select(StockMovement.ingredient_id).distinct()).all())

    # Parse filter selections from query string
    filters = _parse_inventory_filters(request)

    # Compute variant counts for variant-aware KPIs
    _variant_counts = _compute_variant_counts(session, all_ings)

    # Provisional never_loaded / critical counts (will be refined after
    # variant info is available)
    never_loaded_ids = {
        i.id for i in all_ings if (i.stock_qty or 0) == 0 and i.id not in loaded_ids
    }
    kpi_never_loaded = len(never_loaded_ids)
    kpi_critical = sum(
        1
        for i in all_ings
        if i.stock_qty <= (i.min_stock_qty or 0) and i.id not in never_loaded_ids
    )
    kpi_no_cost = sum(1 for i in all_ings if not i.purchase_price_gs)
    kpi_total = len(all_ings)
    kpi_value_gs = _compute_stock_value(session, all_ings)

    # Filter ingredients
    _filtered_all = _filter_ingredients(
        all_ings, filters, never_loaded_ids, today, week_from_now, month_from_now
    )
    total = len(_filtered_all)
    total_all = len(all_ings)
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    page = min(page, total_pages)

    # Sort
    _filtered_all = _sort_ingredients(_filtered_all, sort, dir)

    # Paginate
    ingredients = _filtered_all[(page - 1) * PER_PAGE : page * PER_PAGE]

    # Compute per-ingredient enrichments
    price_info = _build_price_info(session, ingredients)
    effective_stock_qty, variants_by_ing_id = _compute_variant_data(session, ingredients)
    market_refs = _compute_market_refs(session, ingredients)

    # Refine KPIs with variant-aware effective stock
    _has_variant = {ing_id for ing_id, n in _variant_counts.items() if n > 0}
    never_loaded_ids = {
        i.id
        for i in all_ings
        if (i.stock_qty or 0) == 0 and i.id not in loaded_ids and i.id not in _has_variant
    }
    kpi_never_loaded = len(never_loaded_ids)
    kpi_critical = sum(
        1
        for i in all_ings
        if effective_stock_qty.get(i.id, float(i.stock_qty or 0.0)) <= (i.min_stock_qty or 0)
        and i.id not in never_loaded_ids
    )

    # Data quality checks
    duplicates = _find_duplicate_ingredients(all_ings)
    suspicious_prices = _find_suspicious_prices(all_ings)
    expiring_soon = sum(
        1
        for i in all_ings
        if i.expiry_date and i.expiry_date <= week_from_now and i.expiry_date >= today
    )

    # Build filter options for the template
    categories = sorted(
        {(i.category or "").strip() for i in all_ings if (i.category or "").strip()}
    )
    storages = sorted({(i.storage or "").strip() for i in all_ings if (i.storage or "").strip()})

    from app.rms.tagging.vocabulary import CANONICAL_DIETARY_TAGS

    return render(
        request,
        "inventario.html",
        _build_template_context(
            ingredients=ingredients,
            effective_stock_qty=effective_stock_qty,
            variants_by_ing_id=variants_by_ing_id,
            price_info=price_info,
            market_refs=market_refs,
            sort=sort or "",
            dir=dir,
            page=page,
            total_pages=total_pages,
            total=total,
            total_all=total_all,
            per_page=PER_PAGE,
            kpi_total=kpi_total,
            kpi_critical=kpi_critical,
            kpi_never_loaded=kpi_never_loaded,
            kpi_value_gs=kpi_value_gs,
            kpi_no_cost=kpi_no_cost,
            never_loaded_ids=never_loaded_ids,
            expiring_soon=expiring_soon,
            duplicates=duplicates,
            suspicious_prices=suspicious_prices,
            filters=filters,
            categories=categories,
            storages=storages,
            CANONICAL_DIETARY_TAGS=CANONICAL_DIETARY_TAGS,
            session=session,
        ),
    )


def _parse_inventory_filters(request: Request) -> dict[str, Any]:
    """Parse filter selections from query string.

    Extracted from inventory_list to reduce complexity. Returns dict with
    all filter parameters (q, estados_sel, categorias, alergenos, etc.).
    """
    q = (request.query_params.get("q") or "").strip().lower()
    estados_sel = [e for e in request.query_params.getlist("estado") if e]
    categorias = [c for c in request.query_params.getlist("categoria") if c]
    alergenos = [a for a in request.query_params.getlist("alergeno") if a]
    almacenes_sel = [a for a in request.query_params.getlist("almacen") if a]
    expiries_sel = [e for e in request.query_params.getlist("expiry") if e and e != "all"]
    diet_sel = [d.strip().lower() for d in request.query_params.getlist("diet") if d.strip()]

    return {
        "q": q,
        "estados_sel": estados_sel,
        "categorias": categorias,
        "alergenos": alergenos,
        "almacenes_sel": almacenes_sel,
        "expiries_sel": expiries_sel,
        "diet_sel": diet_sel,
    }


def _compute_variant_counts(session: Session, all_ings: list) -> dict[int, int]:
    """Compute variant counts for all ingredients.

    Extracted from inventory_list to reduce complexity. Returns dict
    mapping ingredient_id to variant count.
    """
    _all_ing_ids = [i.id for i in all_ings]
    if not _all_ing_ids:
        return {}
    return dict(
        session.execute(
            select(IngredientVariant.ingredient_id, func.count(IngredientVariant.id))
            .where(IngredientVariant.ingredient_id.in_(_all_ing_ids))
            .group_by(IngredientVariant.ingredient_id)
        ).all()
    )


def _compute_stock_value(session: Session, all_ings: list) -> float:
    """Compute total stock value in guaraníes.

    Extracted from inventory_list to reduce complexity. Falls back to
    manual calculation if the helper function fails.
    """
    from app.rms.inventory_intel import stock_value_gs

    try:
        return stock_value_gs(session)
    except Exception:
        return sum((i.stock_qty or 0) * (i.purchase_price_gs or 0) for i in all_ings)


def _filter_ingredients(
    all_ings: list,
    filters: dict,
    never_loaded_ids: set,
    today: Any,
    week_from_now: Any,
    month_from_now: Any,
) -> list:
    """Filter ingredients based on filter selections.

    Extracted from inventory_list to reduce complexity. Applies all
    filters (text search, estado, category, allergens, diet, storage,
    expiry) and returns filtered list.
    """
    def _match(i: Ingredient) -> bool:
        if not _matches_text_search(i, filters["q"]):
            return False
        if filters["estados_sel"] and not _matches_estado(i, filters["estados_sel"], never_loaded_ids):
            return False
        if filters["categorias"] and not _matches_category(i, filters["categorias"]):
            return False
        if filters["alergenos"] and not _matches_allergens(i, filters["alergenos"]):
            return False
        if not _matches_diet(i, filters["diet_sel"]):
            return False
        if filters["almacenes_sel"] and not _matches_storage(i, filters["almacenes_sel"]):
            return False
        if filters["expiries_sel"] and not _matches_expiry(i, filters["expiries_sel"], today, week_from_now, month_from_now):
            return False
        return True

    return [i for i in all_ings if _match(i)]


def _matches_text_search(i: Ingredient, q: str) -> bool:
    """Check if ingredient matches text search.

    Extracted from _filter_ingredients to reduce complexity.
    """
    if not q:
        return True
    return q in (i.name or "").lower()


def _matches_category(i: Ingredient, categorias: list) -> bool:
    """Check if ingredient matches selected categories.

    Extracted from _filter_ingredients to reduce complexity.
    """
    return (i.category or "") in categorias


def _matches_storage(i: Ingredient, almacenes_sel: list) -> bool:
    """Check if ingredient matches selected storage.

    Extracted from _filter_ingredients to reduce complexity.
    """
    return (i.storage or "") in almacenes_sel


def _matches_allergens(i: Ingredient, alergenos: list) -> bool:
    """Check if ingredient has all selected allergens.

    Extracted from _filter_ingredients to reduce complexity.
    """
    return all(code in (i.allergens or "").lower() for code in alergenos)


def _matches_diet(i: Any, diet_sel: list) -> bool:
    """Check if ingredient matches selected diet restrictions.

    Extracted from _filter_ingredients to reduce complexity. Supports
    both Spanish canonical tags and legacy English codes.
    """
    if not diet_sel:
        return True
    tags = _ingredient_diet_tags(i)
    alias_map = {
        "gluten_free": ("sin gluten", "sin tacc"),
        "vegan": ("vegano",),
        "vegetarian": ("vegetariano",),
        "dairy_free": ("sin lactosa",),
        "egg_free": ("sin huevo",),
        "keto_friendly": ("keto",),
        "nut_free": ("sin frutos secos",),
    }
    for want in diet_sel:
        if want in tags:
            continue
        if any(a in tags for a in alias_map.get(want, ())):
            continue
        return False
    return True


def _ingredient_diet_tags(i: Any) -> set[str]:
    """Get the set of diet tags for an ingredient.

    Extracted from _matches_diet to reduce complexity.
    """
    raw = (i.dietary_tags or "").lower()
    return {t.strip() for t in raw.split(",") if t.strip()}


def _matches_estado(i: Ingredient, estados_sel: list, never_loaded_ids: set) -> bool:
    """Check if ingredient matches any selected estado.

    Extracted from _filter_ingredients to reduce complexity. Uses a
    table-driven approach for clarity.
    """
    for estado in estados_sel:
        if _check_single_estado(i, estado, never_loaded_ids):
            return True
    return False


def _check_single_estado(i: Ingredient, estado: str, never_loaded_ids: set) -> bool:
    """Check if ingredient matches a single estado.

    Extracted from _matches_estado to reduce complexity.
    """
    if estado == "bajo":
        return i.stock_qty <= (i.min_stock_qty or 0)
    if estado == "critico":
        return i.stock_qty <= 0 or (i.min_stock_qty and i.stock_qty < i.min_stock_qty * 0.5)
    if estado == "negativo":
        return i.stock_qty < 0
    if estado == "sincargar":
        return i.id in never_loaded_ids
    if estado == "sinprecio":
        return i.purchase_price_gs is None
    if estado == "ok":
        return i.stock_qty > (i.min_stock_qty or 0)
    if estado == "sobre_stock":
        return i.max_stock_qty is not None and i.stock_qty > i.max_stock_qty
    return False


def _matches_expiry(
    i: Ingredient, expiries_sel: list, today: Any, week_from_now: Any, month_from_now: Any
) -> bool:
    """Check if ingredient matches any selected expiry filter.

    Extracted from _filter_ingredients to reduce complexity.
    """
    for expiry in expiries_sel:
        if expiry == "expired" and i.expiry_date and i.expiry_date < today:
            return True
        if (
            expiry == "7days"
            and i.expiry_date
            and i.expiry_date <= week_from_now
            and i.expiry_date >= today
        ):
            return True
        if (
            expiry == "30days"
            and i.expiry_date
            and i.expiry_date <= month_from_now
            and i.expiry_date >= today
        ):
            return True
    return False


def _sort_ingredients(ingredients: list, sort: str | None, dir: str) -> list:
    """Sort ingredients by the selected column.

    Extracted from inventory_list to reduce complexity. Uses a sort map
    for supported columns; defaults to name.
    """
    _sort_map = {
        "name": lambda i: (i.name or "").lower(),
        "stock_qty": lambda i: i.stock_qty or 0,
        "min_stock_qty": lambda i: i.min_stock_qty or 0,
        "purchase_price_gs": lambda i: i.purchase_price_gs or 0,
        "unit": lambda i: i.unit or "",
        "valor_gs": lambda i: (i.stock_qty or 0) * (i.purchase_price_gs or 0),
        "category": lambda i: (i.category or "").lower(),
        "expiry_date": lambda i: i.expiry_date.isoformat() if i.expiry_date else "",
        "supplier": lambda i: i.supplier.name.lower() if i.supplier and i.supplier.name else "",
    }
    if sort and sort in _sort_map:
        ingredients.sort(key=_sort_map[sort], reverse=(dir == "desc"))
    else:
        ingredients.sort(key=lambda i: (i.name or "").lower())
    return ingredients


def _build_price_info(session: Session, ingredients: list) -> dict[int, dict]:
    """Build price-history enrichment for ingredients on this page.

    Extracted from inventory_list to reduce complexity. Phase D — Q1
    surface: ingredients with >=2 events in the last 90d get a muted
    min/max line; >=3 events also get a sparkline SVG.
    """
    price_info: dict[int, dict] = {}
    ing_ids_with_events = set(
        session.scalars(select(IngredientPriceEvent.ingredient_id).distinct()).all()
    )
    for ing in ingredients:
        if ing.id not in ing_ids_with_events:
            continue
        stats = price_stats(session, ing.id, days=90)
        if stats["count"] >= 2:
            info: dict = {"stats": stats, "sparkline_svg": ""}
            if stats["count"] >= 3:
                history = price_history(session, ing.id, days=90)
                info["sparkline_svg"] = sparkline(
                    [p for _, p in history],
                    label=f"histórico de precio de {ing.name}",
                )
            price_info[ing.id] = info
    return price_info


def _compute_variant_data(
    session: Session, ingredients: list
) -> tuple[dict[int, float], dict[int, list[dict]]]:
    """Compute variant-aware stock and variant details for ingredients.

    Extracted from inventory_list to reduce complexity. Returns
    (effective_stock_qty, variants_by_ing_id).
    """
    from app.rms.variants import rollup_ingredient_stock

    effective_stock_qty: dict[int, float] = {}
    variants_by_ing_id: dict[int, list[dict]] = {}
    for ing in ingredients:
        rollup = rollup_ingredient_stock(session, ing.id)
        if rollup is not None and rollup.variant_count > 0:
            effective_stock_qty[ing.id] = rollup.base_qty
            _sup_ids = {v["supplier_id"] for v in rollup.variants if v.get("supplier_id")}
            _sup_names: dict[int, str] = {}
            if _sup_ids:
                from app.rms.models import Supplier as _Supplier

                _sup_names = {
                    s.id: s.name
                    for s in session.scalars(
                        select(_Supplier).where(_Supplier.id.in_(_sup_ids))
                    ).all()
                }
            variants_by_ing_id[ing.id] = [
                {
                    "id": v["variant_id"],
                    "package_size": v["package_size"],
                    "package_unit": v["package_unit"],
                    "preferred": v["preferred"],
                    "supplier_name": _sup_names.get(v.get("supplier_id")),
                    "stock_qty": v["stock_qty"],
                    "purchase_price_gs": v["purchase_price_gs"],
                    "label": v.get("label"),
                }
                for v in rollup.variants
            ]
        else:
            effective_stock_qty[ing.id] = float(ing.stock_qty or 0.0)
            variants_by_ing_id[ing.id] = []
    return effective_stock_qty, variants_by_ing_id


def _compute_market_refs(session: Session, ingredients: list) -> dict[int, dict]:
    """Compute market reference price comparisons.

    Extracted from inventory_list to reduce complexity. Wave 4 — Market
    reference price (Paraguay baseline). Returns dict mapping ingredient_id
    to market reference data.
    """
    from app.rms.models import MarketPriceReference

    market_refs: dict[int, dict] = {}
    ing_ids = [ing.id for ing in ingredients]
    if not ing_ids:
        return market_refs
    refs = session.scalars(
        select(MarketPriceReference).where(MarketPriceReference.ingredient_id.in_(ing_ids))
    ).all()
    for r in refs:
        ing = next((i for i in ingredients if i.id == r.ingredient_id), None)
        if not ing or ing.purchase_price_gs is None:
            continue
        delta_pct = (
            (ing.purchase_price_gs - r.price_gs) / r.price_gs * 100 if r.price_gs > 0 else 0
        )
        market_refs[ing.id] = {
            "market_price_gs": r.price_gs,
            "market_unit": r.unit,
            "market_source": r.source,
            "market_notes": r.notes,
            "delta_pct": delta_pct,
        }
    return market_refs


def _find_duplicate_ingredients(all_ings: list) -> list[dict]:
    """Find duplicate ingredients (same name, case-insensitive).

    Extracted from inventory_list to reduce complexity. Returns list of
    duplicate groups with name, count, units, and ids.
    """
    _by_norm: dict[str, list] = {}
    for i in all_ings:
        _by_norm.setdefault((i.name or "").strip().lower(), []).append(i)
    return [
        {
            "name": k,
            "count": len(v),
            "units": sorted({x.unit or "" for x in v}),
            "ids": [x.id for x in v],
        }
        for k, v in _by_norm.items()
        if len(v) > 1
    ]


def _find_suspicious_prices(all_ings: list) -> list[dict]:
    """Find ingredients with suspicious prices (per-g/ml above Gs. 5,000).

    Extracted from inventory_list to reduce complexity. Data-quality:
    price per g/ml above Gs. 5.000 is almost certainly a per-kg/l price
    entered on a gram/milliliter row (carrot-cake 11M bug class).
    """
    return [
        {"id": i.id, "name": i.name, "unit": i.unit, "price": i.purchase_price_gs}
        for i in all_ings
        if i.unit in ("g", "ml") and (i.purchase_price_gs or 0) > 5000
    ]


def _build_template_context(
    ingredients: list,
    effective_stock_qty: dict,
    variants_by_ing_id: dict,
    price_info: dict,
    market_refs: dict,
    sort: str,
    dir: str,
    page: int,
    total_pages: int,
    total: int,
    total_all: int,
    per_page: int,
    kpi_total: int,
    kpi_critical: int,
    kpi_never_loaded: int,
    kpi_value_gs: float,
    kpi_no_cost: int,
    never_loaded_ids: set,
    expiring_soon: int,
    duplicates: list,
    suspicious_prices: list,
    filters: dict,
    categories: list,
    storages: list,
    CANONICAL_DIETARY_TAGS: set,
    session: Session,
) -> dict:
    """Build the template context dict.

    Extracted from inventory_list to reduce complexity. Centralizes all
    the template variables in one place.
    """
    return {
        "ingredients": ingredients,
        "effective_stock_qty": effective_stock_qty,
        "variants_by_ing_id": variants_by_ing_id,
        "price_info": price_info,
        "market_refs": market_refs,
        "sort": sort,
        "dir": dir,
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "per_page": per_page,
        "page_start": (page - 1) * per_page + 1,
        "page_end": min(page * per_page, total),
        "kpi_total": kpi_total,
        "kpi_critical": kpi_critical,
        "kpi_never_loaded": kpi_never_loaded,
        "never_loaded_ids": never_loaded_ids,
        "kpi_value_gs": kpi_value_gs,
        "kpi_no_cost": kpi_no_cost,
        "expiring_soon": expiring_soon,
        "q": filters["q"],
        "estados_sel": filters["estados_sel"],
        "categorias": filters["categorias"],
        "alergenos_sel": filters["alergenos"],
        "diet_sel": filters["diet_sel"],
        "diet_options": sorted(CANONICAL_DIETARY_TAGS),
        "almacenes_sel": filters["almacenes_sel"],
        "expiries_sel": filters["expiries_sel"],
        "categories": categories,
        "storages": storages,
        "allergen_codes": [
            ("gluten", "Gluten"),
            ("dairy", "Lácteos"),
            ("eggs", "Huevos"),
            ("nuts", "Frutos secos"),
            ("soy", "Soja"),
            ("sesame", "Sésamo"),
            ("sulfites", "Sulfitos"),
        ],
        "total_filtered": total,
        "duplicates": duplicates,
        "suspicious_prices": suspicious_prices,
        "tag_audit_count": session.scalar(
            select(func.count(Ingredient.id)).where(
                Ingredient.tag_validation_issues.isnot(None),
                Ingredient.tag_validation_issues != "",
            )
        )
        or 0,
        "total_all": total_all,
    }
@router.get("/carga-inicial", response_class=HTMLResponse)
def carga_inicial_view(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    """PRO-INV: asisted initial stock load — list every ingredient that has
    zero movements in the ledger so the operator can load real opening counts
    in one screen (instead of 21 detail-page visits)."""
    loaded_ids = set(session.scalars(select(StockMovement.ingredient_id).distinct()).all())
    pendientes = [
        i
        for i in session.scalars(select(Ingredient).order_by(Ingredient.name)).all()
        if (i.stock_qty or 0) == 0 and i.id not in loaded_ids
    ]
    return render(request, "carga_inicial.html", {"pendientes": pendientes})


@router.post("/carga-inicial")
async def carga_inicial_save(
    request: Request,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Save bulk initial stock. Form fields: qty_<id> per row (blank = skip)."""

    current_operator(request)
    saved = 0
    form = await request.form()
    for key in list(form.keys()):
        if not key.startswith("qty_"):
            continue
        try:
            ing_id = int(key[4:])
        except ValueError:
            continue
        raw_val = (form.get(key) or "").strip()
        if not raw_val:
            continue
        try:
            qty = float(raw_val.replace(",", "."))
        except ValueError:
            continue
        if qty <= 0:
            continue
        ing = session.get(Ingredient, ing_id)
        if ing is None:
            continue
        ing.stock_qty = qty
        session.add(
            StockMovement(
                ingredient_id=ing_id,
                movement_type="initial",
                qty=qty,
                reason="carga inicial de inventario",
                reference_id=None,
                reference_type=None,
                recorded_at=datetime.now(timezone.utc),
            )
        )
        saved += 1
    session.commit()
    from urllib.parse import urlencode

    params = urlencode({"flash": f"ok:Carga inicial guardada: {saved} ingredientes."})
    return RedirectResponse(url=f"/inventario?{params}", status_code=303)


@router.get("/nuevo", response_class=HTMLResponse)
def inventory_new(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    """Show the new-ingredient form."""
    cats = session.scalars(
        select(Ingredient.category)
        .where(Ingredient.category.isnot(None))
        .where(Ingredient.category != "")
        .distinct()
        .order_by(Ingredient.category)
    ).all()
    return render(
        request,
        "inventario_form.html",
        {
            "mode": "new",
            "ingredient": None,
            "action": "Nuevo",
            "units": [u.value for u in Unit],
            "existing_categories": [{"label": c, "value": c} for c in cats],
            "allergens": [{"code": a.code, "label": a.label} for a in list_allergens(session)],
            "dietary_tags": [
                {"code": d.code, "label": d.label} for d in list_dietary_tags(session)
            ],
        },
    )


@router.post("/nuevo")
def inventory_create(
    request: Request,
    name: str = Form(""),
    unit: str = Form(""),
    stock_qty: float = Form(0.0),
    min_stock_qty: float = Form(0.0),
    purchase_price_gs: str = Form(""),
    notes: str = Form(""),
    category: str = Form(""),
    opening_stock_qty: str = Form(""),
    opening_stock_date: str = Form(""),
    reorder_point: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Create new ingredient.

    Refactored 2026-10-09 to reduce cognitive complexity from 16 to <10.
    """
    name_clean = _validate_name(name)
    unit_enum = _validate_unit(unit)
    price = _parse_price(purchase_price_gs)
    _validate_non_negative_stock(stock_qty, min_stock_qty)

    opening_qty, opening_date = _parse_opening_stock(opening_stock_qty, opening_stock_date)
    reorder = _parse_reorder_value(reorder_point)

    classification = classify_ingredient(name_clean, session=session)
    ing = _build_ingredient(
        name=name_clean,
        unit_enum=unit_enum,
        stock_qty=stock_qty,
        min_stock_qty=min_stock_qty,
        price=price,
        notes=notes,
        category=category,
        classification=classification,
        opening_qty=opening_qty,
        opening_date=opening_date,
        reorder=reorder,
    )

    session.add(ing)
    try:
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise AlreadyExists(
            f"Ya existe un ingrediente con nombre {name!r}",
            context={"name": name},
            cause=e,
        ) from e

    _populate_tag_validation(session, ing)
    _log_ingredient_creation(request, session, ing)

    if opening_qty is not None and opening_qty != stock_qty:
        _record_initial_stock_movement(request, session, ing, opening_qty)

    _record_initial_price(session, ing.id, price)

    return RedirectResponse(url="/inventario", status_code=303)


def _validate_name(name: str) -> str:
    """Validate that the ingredient name is non-empty.

    Extracted from inventory_create to reduce complexity.
    """
    name_clean = name.strip() if name else ""
    if not name_clean:
        raise BadRequest(INGREDIENT_NAME_REQUIRED)
    return name_clean


def _validate_unit(unit: str) -> Unit:
    """Parse and validate the unit field.

    Extracted from inventory_create to reduce complexity.
    """
    try:
        return Unit.coerce(unit)
    except ValueError as e:
        raise BadRequest(f"Unidad inválida: {e}", context={"unit": str(unit)}, cause=e) from e


def _validate_non_negative_stock(stock_qty: float, min_stock_qty: float) -> None:
    """Validate that stock quantities are non-negative.

    Extracted from inventory_create to reduce complexity.
    """
    if stock_qty < 0:
        raise BadRequest("El stock no puede ser negativo.", context={"stock_qty": stock_qty})
    if min_stock_qty < 0:
        raise BadRequest(
            "El stock mínimo no puede ser negativo.",
            context={"min_stock_qty": min_stock_qty},
        )


def _parse_opening_stock(
    opening_stock_qty: str, opening_stock_date: str
) -> tuple[float | None, str | None]:
    """Parse opening stock fields.

    Extracted from inventory_create to reduce complexity.
    """
    opening_qty = float(opening_stock_qty) if opening_stock_qty.strip() else None
    opening_date = opening_stock_date.strip() or None
    return opening_qty, opening_date


def _parse_reorder_value(reorder_point: str) -> float | None:
    """Parse the reorder point field.

    Extracted from inventory_create to reduce complexity.
    """
    return float(reorder_point) if reorder_point.strip() else None


def _build_ingredient(
    name: str,
    unit_enum: Unit,
    stock_qty: float,
    min_stock_qty: float,
    price: Any,
    notes: str,
    category: str,
    classification: dict,
    opening_qty: float | None,
    opening_date: str | None,
    reorder: float | None,
) -> Ingredient:
    """Build the Ingredient object with inferred classification.

    Extracted from inventory_create to reduce complexity. Uses inferred
    classification as defaults; operator-provided category overrides.
    """
    inferred_category = classification["category"]
    inferred_subcategory = classification["subcategory"]
    inferred_role = classification["role"]
    inferred_allergens = ",".join(classification["allergens"])
    inferred_dietary_tags = ",".join(classification["dietary_tags"])
    inferred_shelf_life = classification["shelf_life_days"]
    inferred_storage = classification["storage"]

    return Ingredient(
        name=name.strip(),
        unit=unit_enum.value,
        stock_qty=stock_qty,
        min_stock_qty=min_stock_qty,
        purchase_price_gs=price,
        notes=notes.strip() or None,
        category=(category.strip() or inferred_category) or None,
        subcategory=inferred_subcategory,
        role=inferred_role,
        # '' = declared-neutral (no allergen keywords matched). NULL = operator
        # never touched the field → triggers the receta 'Sin alérgenos declarados' banner.
        allergens=inferred_allergens,  # empty string stays empty, never NULL
        dietary_tags=inferred_dietary_tags or None,
        shelf_life_days=inferred_shelf_life,
        storage=inferred_storage,
        opening_stock_qty=opening_qty,
        opening_stock_date=opening_date,
        reorder_point=reorder,
    )


def _populate_tag_validation(session: Session, ing: Ingredient) -> None:
    """Populate tag_validation_issues column on the new ingredient.

    Extracted from inventory_create to reduce complexity. Catches any
    issues immediately (e.g. operator claimed 'vegano' but allergens
    include dairy).
    """
    try:
        from app.rms.tagging.classify import validate_ingredient

        issues = validate_ingredient(ing)
        if issues:
            ing.tag_validation_issues = "\n".join(issues)
            session.commit()
    except Exception:
        logger.warning(
            "tag validation refresh failed for new ingredient ing_id=%s",
            ing.id,
            exc_info=True,
        )
        session.rollback()


def _log_ingredient_creation(request: Request, session: Session, ing: Ingredient) -> None:
    """Log the ingredient creation for audit and info.

    Extracted from inventory_create to reduce complexity.
    """
    logger.info(
        "ingredient_created id={} name={!r} unit={} stock={}",
        ing.id,
        ing.name,
        ing.unit,
        ing.stock_qty,
    )
    record_audit(
        request,
        session=session,
        action="ingredient.create",
        target_type="Ingredient",
        target_id=ing.id,
        detail={"name": ing.name, "unit": ing.unit},
    )


def _record_initial_stock_movement(
    request: Request, session: Session, ing: Ingredient, opening_qty: float
) -> None:
    """Record the initial stock movement if opening stock was set.

    Extracted from inventory_create to reduce complexity.
    """
    user_id = current_operator(request)
    movement = StockMovement(
        ingredient_id=ing.id,
        movement_type="initial",
        qty=opening_qty,
        reason="stock inicial",
        reference_id=None,
        reference_type=None,
        recorded_at=datetime.now(timezone.utc),
        created_by=user_id,
    )
    session.add(movement)
    session.commit()


def _record_initial_price(session: Session, ing_id: int, price: Any) -> None:
    """Record the initial price event if price was provided.

    Extracted from inventory_create to reduce complexity. Phase B — Q1
    core: when an operator creates an ingredient with a price, record
    the first price event so the history starts populated.
    """
    if price is None:
        return
    try:
        record_price_event(session, ing_id, price, source="manual")
        session.commit()
    except Exception:
        # Don't fail the whole request on a price-history write error.
        logger.warning(
            "record_price_event failed for new ingredient ing_id=%s",
            ing_id,
            exc_info=True,
        )


# ─────────────────────────────────────────────────────────────────────────
# Tag audit (2026-09-29 tagging/ refactor)
# ─────────────────────────────────────────────────────────────────────────
# Endpoint: GET /inventario/auditoria-etiquetas
#
# Shows every ingredient that has tag_validation_issues populated, plus a
# fresh run of audit_all_ingredients() to catch anything added since the
# last backfill. Renders as a sortable table with one-click navigation to
# the ingredient edit form so the operator can fix data-entry errors
# surfaced by the tagging system.
#
# Why an explicit page (vs inlining into /inventario):
#   - Some issues are subtle (e.g. "Jengibre fresco" categorized as
#     'carnes'). Easy to miss in a long inventory list.
#   - Operators should fix all issues in one batch, then re-run the audit.
#   - Auditors / external reviewers need a stable URL to verify compliance.
#
# Route ordering: this is registered BEFORE the /{ing_id} routes so it
# matches /inventario/auditoria-etiquetas literally instead of being
# captured as ing_id='auditoria-etiquetas' (which fails int parsing).
# ─────────────────────────────────────────────────────────────────────────


@router.get("/auditoria-etiquetas", response_class=HTMLResponse)
def inventory_tag_audit(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Page listing every ingredient with a tag-validation issue.

    Two-phase audit:
      1. Read the pre-computed Ingredient.tag_validation_issues column
         (populated by migration 061 + audit.backfill_validation_issues).
      2. Run audit_all_ingredients() to catch anything added since.

    The two sources can differ when ingredients were created after the
    last backfill. We display both (tagged 'fresh' vs 'cached') so the
    operator knows which need re-running.
    """
    from app.rms.tagging.audit import audit_all_ingredients

    # Phase 1 — fresh audit
    fresh_issues = audit_all_ingredients(session)

    # Phase 2 — read cached column
    cached_rows = session.execute(
        select(Ingredient.id, Ingredient.name, Ingredient.tag_validation_issues)
        .where(Ingredient.tag_validation_issues.isnot(None))
        .where(Ingredient.tag_validation_issues != "")
    ).all()

    # Merge: by ingredient id
    rows: list[dict] = []
    seen_ids: set[int] = set()

    # First pass: fresh audit (more authoritative)
    for iid, issues in sorted(fresh_issues.items()):
        ing = session.get(Ingredient, iid)
        if ing is None:
            continue
        seen_ids.add(iid)
        rows.append(
            {
                "id": iid,
                "name": ing.name,
                "category": ing.category,
                "allergens": ing.allergens,
                "dietary_tags": ing.dietary_tags,
                "issues": issues,
                "source": "fresh",
            }
        )

    # Second pass: cached only (not in fresh — ingredient changed since
    # the last save that didn't trigger a re-audit)
    for rid, name, cached in cached_rows:
        if rid in seen_ids:
            continue
        ing = session.get(Ingredient, rid)
        if ing is None:
            continue
        seen_ids.add(rid)
        rows.append(
            {
                "id": rid,
                "name": name,
                "category": ing.category,
                "allergens": ing.allergens,
                "dietary_tags": ing.dietary_tags,
                "issues": (cached or "").split("\n") if cached else [],
                "source": "cached",
            }
        )

    # Sort by issue count (most issues first)
    rows.sort(key=lambda r: -len(r["issues"]))

    return render(
        request,
        "inventario_auditoria_etiquetas.html",
        {
            "rows": rows,
            "total": len(rows),
            "fresh_count": len(fresh_issues),
        },
    )


@router.post("/auditoria-etiquetas/rerun", response_class=JSONResponse)
def inventory_tag_audit_rerun(
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Re-run repair + backfill in case data changed since the last
    migration. The repair step (audit_repair) uses the allergens column
    as source of truth and drops contradictory dietary_tags claims —
    that's the one-shot auto-fix the user asked for. Returns:

      { "repaired": N, "tags_removed": M, "validation_issues": K }

    N = ingredients that had at least one tag dropped
    M = total tags dropped
    K = remaining ingredients with validation issues (after the repair)
    """
    from app.rms.tagging.audit import backfill_validation_issues
    from app.rms.tagging.audit_repair import repair_all_ingredients

    changes = repair_all_ingredients(session)
    tags_removed = sum(len(v) for v in changes.values())
    session.flush()

    issues_count = backfill_validation_issues(session)
    session.commit()
    return JSONResponse(
        {
            "repaired": len(changes),
            "tags_removed": tags_removed,
            "validation_issues": issues_count,
        }
    )


@router.get("/api/categories", response_class=JSONResponse)
def ingredients_api_categories(
    q: str = Query("", description="Search query"),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Distinct ingredient categories for the category combobox.

    Returns rows of ``{"label": <category>, "value": <category>}`` so the
    picker shows the existing categories and can filter them by `q`.
    Empty `q` returns every distinct category ordered alphabetically.
    """
    stmt = (
        select(Ingredient.category)
        .where(Ingredient.category.isnot(None))
        .where(Ingredient.category != "")
        .distinct()
        .order_by(Ingredient.category)
    )
    cats = [c for c in session.scalars(stmt).all() if c is not None]
    if q:
        needle = q.strip().lower()
        cats = [c for c in cats if needle in c.lower()]
    cats = cats[:limit]
    return JSONResponse([{"label": c, "value": c} for c in cats])


@router.get("/{ing_id}", response_class=HTMLResponse)
def inventory_detail(
    ing_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Show ingredient detail page with 'used in recipes' list."""
    ing = session.get(Ingredient, ing_id)
    if ing is None:
        raise NotFound("Ingredient", id=ing_id)

    # Find all recipes that use this ingredient
    recipe_lines = session.scalars(
        select(RecipeLine).where(
            RecipeLine.line_kind == "ingredient",
            RecipeLine.line_ref_id == ing_id,
        )
    ).all()

    recipes = []
    for line in recipe_lines:
        recipe = session.get(Recipe, line.recipe_id)
        if recipe:
            recipes.append(
                {
                    "id": recipe.id,
                    "name": recipe.name,
                    "qty": line.qty,
                    "line_unit": line.line_unit,
                }
            )

    # S7 Decision B — forecast horizon computation (per-ingredient or default)
    from app.rms.variants import (
        days_until_short,
        rollup_ingredient_stock,
    )

    rollup = rollup_ingredient_stock(session, ing_id)
    forecast = days_until_short(session, ing_id)

    from app.rms.ingredient_margins import product_margins_for_ingredient

    return render(
        request,
        "ingrediente_detalle.html",
        {
            "ingredient": ing,
            "recipes": recipes,
            "variants_rollup": rollup,
            "forecast": forecast,
            # Price history stats for the detail strip (price_history.py).
            "price_stats": _price_stats_safe(session, ing_id),
            "product_margins": product_margins_for_ingredient(session, ing_id),
        },
    )


def _price_stats_safe(session: Session, ing_id: int) -> object:
    try:
        from app.rms.price_history import price_stats

        return price_stats(session, ing_id, days=90)
    except Exception:
        return None


@router.get("/{ing_id}/editar", response_class=HTMLResponse)
def inventory_edit(
    ing_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Show the edit form for an ingredient."""
    ing = session.get(Ingredient, ing_id)
    if ing is None:
        raise NotFound("Ingredient", id=ing_id)
    cats = session.scalars(
        select(Ingredient.category)
        .where(Ingredient.category.isnot(None))
        .where(Ingredient.category != "")
        .distinct()
        .order_by(Ingredient.category)
    ).all()
    return render(
        request,
        "inventario_form.html",
        {
            "mode": "edit",
            "ingredient": ing,
            "action": "Editar",
            "units": [u.value for u in Unit],
            "existing_categories": [{"label": c, "value": c} for c in cats],
            "allergens": [{"code": a.code, "label": a.label} for a in list_allergens(session)],
            "dietary_tags": [
                {"code": d.code, "label": d.label} for d in list_dietary_tags(session)
            ],
        },
    )


@router.post("/{ing_id}/editar")
def inventory_update(
    ing_id: int,
    request: Request,
    name: str = Form(""),
    unit: str = Form(""),
    stock_qty: str = Form("0"),
    min_stock_qty: str = Form("0"),
    purchase_price_gs: str = Form(""),
    notes: str = Form(""),
    category: str = Form(""),
    opening_stock_qty: str = Form(""),
    opening_stock_date: str = Form(""),
    reorder_point: str = Form(""),
    shelf_life_days: str = Form(""),
    allergens: str = Form("__unset__"),
    dietary_tags: str = Form("__unset__"),
    may_contain_gluten: str = Form(""),
    lead_time_days: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Update an existing ingredient.

    Centralized validation (app.rms.validation) replaces inline checks.

    Refactored 2026-10-09 to reduce cognitive complexity from 33 to <10.
    """
    ing = session.get(Ingredient, ing_id)
    if ing is None:
        raise NotFound("Ingredient", id=ing_id)

    parsed = _parse_ingredient_form(name, unit, stock_qty, min_stock_qty, purchase_price_gs, notes)
    _apply_parsed_fields(ing, parsed)

    _update_optional_metadata(
        ing,
        shelf_life_days=shelf_life_days,
        allergens=allergens,
        dietary_tags=dietary_tags,
        may_contain_gluten=may_contain_gluten,
        lead_time_days=lead_time_days,
    )

    _update_classification(ing, category, name, session)

    _update_opening_stock(ing, opening_stock_qty, opening_stock_date)
    ing.reorder_point = _parse_reorder_point(reorder_point)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise Conflict(
            INGREDIENT_DUPLICATE_NAME,
            context={"name": parsed["name"]},
        ) from None

    if parsed["price"] is not None:
        _record_price_change(session, ing.id, parsed["price"])

    _cascade_tag_refresh(session, ing.id)
    _refresh_tag_validation(session, ing)

    return RedirectResponse(url="/inventario", status_code=303)


def _parse_ingredient_form(
    name: str,
    unit: str,
    stock_qty: str,
    min_stock_qty: str,
    purchase_price_gs: str,
    notes: str,
) -> dict[str, Any]:
    """Parse and validate the form fields.

    Extracted from inventory_update to reduce complexity.
    """
    from app.rms.validation import (
        optional_text,
        parse_money_gs,
        parse_quantity,
        parse_unit,
        require_text,
    )

    return {
        "name": require_text(name, field="nombre", max_len=120),
        "unit": parse_unit(unit).value,
        "stock": parse_quantity(stock_qty, field="stock", allow_zero=True),
        "min_stock": parse_quantity(min_stock_qty, field="stock mínimo", allow_zero=True),
        "price": parse_money_gs(purchase_price_gs, allow_zero=True),
        "notes": optional_text(notes, max_len=2000),
    }


def _apply_parsed_fields(ing: Ingredient, parsed: dict[str, Any]) -> None:
    """Apply parsed form fields to the ingredient.

    Extracted from inventory_update to reduce complexity. The price is
    NOT applied here — it's recorded as a price event later in the
    handler (BACKLOG #31: avoid double-firing record_price_event).
    """
    ing.name = parsed["name"]
    ing.unit = parsed["unit"]
    ing.stock_qty = parsed["stock"]
    ing.min_stock_qty = parsed["min_stock"]
    ing.notes = parsed["notes"]


def _update_optional_metadata(
    ing: Ingredient,
    shelf_life_days: str,
    allergens: str,
    dietary_tags: str,
    may_contain_gluten: str,
    lead_time_days: str,
) -> None:
    """Update optional metadata fields (shelf life, allergens, tags).

    Extracted from inventory_update to reduce complexity. "__unset__"
    means the field was not submitted (older form posts) → keep current
    value.
    """
    ing.shelf_life_days = _parse_optional_int(shelf_life_days, "shelf_life_days")
    if allergens != "__unset__":
        # Empty string = explicitly cleared to "sin declarar" (None).
        ing.allergens = allergens.strip() or ""  # '' = declared-neutral, never NULL
    if dietary_tags != "__unset__":
        ing.dietary_tags = dietary_tags.strip() or None
    ing.may_contain_gluten = may_contain_gluten == "1"
    ing.lead_time_days = _parse_optional_int(lead_time_days, "lead_time_days")


def _parse_optional_int(value: str, field_name: str) -> int | None:
    """Parse an optional integer field, returning None on failure.

    Extracted from _update_optional_metadata to reduce complexity.
    Logs debug on parse failure and returns the previous value (None).
    """
    if not value.strip():
        return None
    try:
        return int(value) or None
    except ValueError:
        try:
            return int(float(value)) or None
        except (TypeError, ValueError) as exc:
            logger.debug("inventory %s parse failed: {}", field_name, exc)
            return None


def _update_classification(
    ing: Ingredient,
    category: str,
    name_clean: str,
    session: Session,
) -> str | None:
    """Update ingredient classification (category, tags, etc.).

    Extracted from inventory_update to reduce complexity. If the operator
    provides an explicit category, use it and re-infer the rest. Otherwise
    re-infer everything from the name.
    """
    from app.rms.validation import optional_text

    explicit_category_raw = optional_text(category, max_len=32)
    if explicit_category_raw:
        ing.category = explicit_category_raw
        # Re-infer the rest of the classification against the new name.
        cls = classify_ingredient(name_clean, session=session)
        ing.subcategory = cls["subcategory"]
        ing.role = cls["role"]
        ing.allergens = ",".join(cls["allergens"]) or ""  # '' = declared-neutral
        ing.dietary_tags = ",".join(cls["dietary_tags"]) or None
        ing.shelf_life_days = cls["shelf_life_days"]
        ing.storage = cls["storage"]
        return explicit_category_raw
    else:
        ing.category = None
        cls = classify_ingredient(name_clean, session=session)
        ing.category = cls["category"]
        ing.subcategory = cls["subcategory"]
        ing.role = cls["role"]
        ing.allergens = ",".join(cls["allergens"]) or None
        ing.dietary_tags = ",".join(cls["dietary_tags"]) or None
        ing.shelf_life_days = cls["shelf_life_days"]
        ing.storage = cls["storage"]
    return explicit_category_raw


def _update_opening_stock(ing: Ingredient, opening_stock_qty: str, opening_stock_date: str) -> None:
    """Update opening stock if both qty and date are provided.

    Extracted from inventory_update to reduce complexity.
    """
    from app.rms.validation import parse_date_iso, parse_quantity

    op_qty_raw = (opening_stock_qty or "").strip()
    op_date_raw = (opening_stock_date or "").strip()
    if op_qty_raw and op_date_raw:
        ing.opening_stock_qty = parse_quantity(op_qty_raw, field="stock inicial")
        ing.opening_stock_date = parse_date_iso(op_date_raw, field="fecha de stock inicial")
    else:
        ing.opening_stock_qty = None
        ing.opening_stock_date = None


def _parse_reorder_point(reorder_point: str) -> float | None:
    """Parse the reorder point field.

    Extracted from inventory_update to reduce complexity.
    """
    from app.rms.validation import parse_quantity

    rp_raw = (reorder_point or "").strip()
    if not rp_raw:
        return None
    return parse_quantity(rp_raw, field="punto de reorden", allow_zero=True)


def _record_price_change(session: Session, ing_id: int, price: Decimal) -> None:
    """Record a price change event for auditability.

    Extracted from inventory_update to reduce complexity. Always records
    when price is non-null (auditability beats optimization).
    """
    try:
        record_price_event(session, ing_id, price, source="manual")
        session.commit()
    except Exception:
        logger.warning(
            "record_price_event failed for ingredient ing_id=%s update",
            ing_id,
            exc_info=True,
        )


def _cascade_tag_refresh(session: Session, ing_id: int) -> None:
    """Cascade tag refresh to recipes and products using this ingredient.

    Extracted from inventory_update to reduce complexity.
    """
    try:
        from app.rms.tag_algebra import _product_inherit_sync, cascade_refresh

        refreshed = cascade_refresh(session, ingredient_id=ing_id)
        for rid in refreshed:
            _product_inherit_sync(session, rid)
        session.commit()
    except Exception:
        logger.warning(
            "tag cascade failed for ingredient ing_id=%s update",
            ing_id,
            exc_info=True,
        )
        session.rollback()


def _refresh_tag_validation(session: Session, ing: Ingredient) -> None:
    """Refresh the ingredient's tag_validation_issues column.

    Extracted from inventory_update to reduce complexity. The audit is
    pure (no DB writes except the column), so it's safe to run inline
    after the save commit.
    """
    try:
        from app.rms.tagging.classify import validate_ingredient

        issues = validate_ingredient(ing)
        # Re-fetch in case the previous session.commit() reset the binding.
        ing_row = session.get(Ingredient, ing.id)
        if ing_row is not None:
            ing_row.tag_validation_issues = "\n".join(issues) if issues else None
            session.commit()
    except Exception:
        logger.warning(
            "tag validation refresh failed for ing_id=%s",
            ing.id,
            exc_info=True,
        )
        session.rollback()


@router.post("/bulk-fill-to-2x-min")
def inventory_bulk_fill_to_2x_min(
    request: Request,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """P34 (2026-10-07, Ivan) — top up every ingredient below 2× its
    minimum stock. Operator action: "make sure all ingredients are
    filled to double the minimum we set".

    Per-ingredient target:
      target = max_stock_qty if set, else 2 × min_stock_qty
    If target is 0 (min_stock_qty is 0), skip — operator must define a
    minimum first via /inventario/{id}/editar.

    Per-ingredient delta:
      delta = max(0, target - stock_qty)
    Only ingredients with delta > 0 get touched. Each touch writes a
    StockMovement with movement_type='reorder' and a free-text reason
    that names the new target, so /merma and the audit trail can
    explain why stock jumped by N units.

    Idempotent: re-running the endpoint after everything is at target
    is a no-op (every delta == 0, no movements written, no stock
    touched). Safe to put behind a "Llenar a 2× mínimo" button on
    /inventario.

    Optional `?force=1` query param: also fills ingredients where
    min_stock_qty==0 (sets to 10.0 default; matches reorder.py
    fallback). Off by default to avoid silently inventing targets.

    Refactored 2026-10-09 to reduce cognitive complexity from 37 to <10.
    """
    force = request.query_params.get("force") == "1"
    user_id = current_operator(request)
    now = datetime.now(timezone.utc)
    ingredients = list(session.scalars(select(Ingredient)).all())

    stats = {"filled": 0, "total_delta": 0.0, "skipped_no_min": 0}
    for ing in ingredients:
        result = _process_bulk_fill_ingredient(session, ing, force, user_id, now)
        if result is None:
            continue
        stats["filled"] += 1
        stats["total_delta"] += result

    session.commit()
    flash_key = _build_bulk_fill_flash_key(
        stats["filled"], stats["total_delta"], stats["skipped_no_min"]
    )
    return RedirectResponse(
        url=f"/inventario?flash={flash_key}",
        status_code=303,
    )


def _process_bulk_fill_ingredient(
    session: Session,
    ing: Ingredient,
    force: bool,
    user_id: Any,
    now: datetime,
) -> float | None:
    """Process a single ingredient for bulk fill.

    Extracted from inventory_bulk_fill_to_2x_min to reduce complexity.
    Returns the delta applied, or None if the ingredient was skipped
    or already at target.
    """
    target = _compute_bulk_fill_target(ing, force)
    if target is None:
        return None

    current = _get_current_stock(session, ing)
    delta = target - current
    if delta <= 0:
        return None

    _apply_bulk_fill_delta(session, ing, delta)
    _record_bulk_fill_movement(session, ing, delta, target, user_id, now)
    return delta


def _compute_bulk_fill_target(ing: Ingredient, force: bool) -> float | None:
    """Compute the target stock for bulk fill.

    Extracted from _process_bulk_fill_ingredient to reduce complexity.
    Returns None if the ingredient should be skipped (no min and not
    forced).
    """
    if ing.min_stock_qty <= 0:
        if not force:
            return None
        return 10.0  # mirror reorder.py fallback for the 0-min case
    # Use explicit max_stock_qty when set, else 2 × min.
    return ing.max_stock_qty if ing.max_stock_qty else ing.min_stock_qty * 2


def _get_current_stock(session: Session, ing: Ingredient) -> float:
    """Get the current stock for an ingredient.

    Extracted from _process_bulk_fill_ingredient to reduce complexity.
    For variant ingredients, uses the rollup (sum across packages in
    base unit). For legacy ingredients, uses Ingredient.stock_qty.
    """
    from app.rms.variants import rollup_ingredient_stock

    rollup = rollup_ingredient_stock(session, ing.id)
    if rollup is not None and getattr(rollup, "variants", None):
        return rollup.base_qty
    return ing.stock_qty or 0.0


def _apply_bulk_fill_delta(session: Session, ing: Ingredient, delta: float) -> None:
    """Apply the bulk fill delta to the ingredient.

    Extracted from _process_bulk_fill_ingredient to reduce complexity.
    Variant-aware: when variants exist, add the delta to the preferred
    variant's stock_qty in package units, then re-sync the parent.
    """
    from app.rms.variants import rollup_ingredient_stock

    rollup = rollup_ingredient_stock(session, ing.id)
    if rollup is not None and getattr(rollup, "variants", None):
        _fill_preferred_variant(session, ing, rollup, delta)
    else:
        # Legacy path: no variants, parent.stock_qty is the only
        # source of truth.
        ing.stock_qty = max(0.0, (ing.stock_qty or 0.0) + delta)


def _fill_preferred_variant(
    session: Session,
    ing: Ingredient,
    rollup: Any,
    delta: float,
) -> None:
    """Fill the preferred variant and sync the parent stock.

    Extracted from _apply_bulk_fill_delta to reduce complexity.
    """
    from app.rms.variants import rollup_ingredient_stock

    preferred = next(
        (v for v in rollup.variants if v.get("preferred")),
        rollup.variants[0],
    )
    size_in_base = float(preferred["size_in_base"])
    packages_to_add = delta / size_in_base if size_in_base > 0 else 0
    preferred_variant = session.get(IngredientVariant, int(preferred["variant_id"]))
    if preferred_variant is not None:
        preferred_variant.stock_qty = max(
            0.0,
            (preferred_variant.stock_qty or 0.0) + packages_to_add,
        )
    # Re-sync the parent from the (now-updated) rollup so any
    # consumer reading the legacy column sees the right number.
    new_rollup = rollup_ingredient_stock(session, ing.id)
    ing.stock_qty = new_rollup.base_qty if new_rollup else ing.stock_qty


def _record_bulk_fill_movement(
    session: Session,
    ing: Ingredient,
    delta: float,
    target: float,
    user_id: Any,
    now: datetime,
) -> None:
    """Record a StockMovement for the bulk fill.

    Extracted from _process_bulk_fill_ingredient to reduce complexity.
    Uses movement_type='reorder' (closest fit in the existing taxonomy)
    and a free-text reason naming the target.
    """
    session.add(
        StockMovement(
            ingredient_id=ing.id,
            movement_type="reorder",
            qty=delta,
            reason=(
                f"Llenado bulk a 2x min (target={target:g} {ing.unit}, min={ing.min_stock_qty:g})"
            ),
            reference_id=None,
            reference_type=None,
            recorded_at=now,
            created_by=user_id,
        )
    )


def _build_bulk_fill_flash_key(filled: int, total_delta: float, skipped_no_min: int) -> str:
    """Build the flash key for the bulk fill operation.

    Extracted from inventory_bulk_fill_to_2x_min to reduce complexity.
    """
    if filled == 0:
        return "inventory_filled_already"
    delta_str = f"{total_delta:g}"
    return f"inventory_filled:{filled}:{delta_str}:{skipped_no_min}"


@router.post("/{ing_id}/eliminar")
def inventory_delete(
    ing_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Delete an ingredient. Blocked if it's used in a recipe."""
    ing = session.get(Ingredient, ing_id)
    if ing is None:
        raise NotFound("Ingredient", id=ing_id)

    # Check if ingredient is on any recipe
    usage = session.scalar(
        select(RecipeLine)
        .where(
            RecipeLine.line_kind == "ingredient",
            RecipeLine.line_ref_id == ing_id,
        )
        .limit(1)
    )
    if usage is not None:
        raise Conflict(
            "No se puede eliminar: el ingrediente está en una receta. Quitá la línea primero.",
            context={"ingredient_id": ing_id, "name": ing.name, "recipe_line_id": usage.id},
        )

    session.delete(ing)
    session.commit()
    return RedirectResponse(url="/inventario", status_code=303)


@router.post("/{ing_id}/ajustar")
def inventory_adjust(
    ing_id: int,
    request: Request,
    adjustment: float = Form(...),
    reason: str = Form(""),
    confirm_negative: str = Form(""),
    variant_id: str = Form(""),  # NEW: multi-package + multi-supplier support
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Record a stock adjustment (wastage, breakage, count correction, RECEIPT).

    Pass positive adjustment to add stock, negative to remove.
    Writes a StockMovement record for auditability.

    Refactored 2026-10-09 to reduce cognitive complexity from 42 to <10.
    """
    ing = session.get(Ingredient, ing_id)
    if ing is None:
        raise NotFound("Ingredient", id=ing_id)

    if adjustment == 0:
        return _redirect_with_flash("no_op:El ajuste fue 0 — no se modificó el stock.", ing_id)

    target_variant, auto_picked = _resolve_target_variant(session, ing_id, variant_id)

    pre = _get_pre_adjustment_stock(ing, target_variant)
    if pre + adjustment < 0 and confirm_negative != "yes":
        return _redirect_with_negative_confirm(ing, target_variant, pre, adjustment, ing_id)

    user_id = current_operator(request)
    _record_stock_movement(session, ing_id, target_variant, adjustment, reason, user_id)
    _apply_stock_adjustment(session, ing, target_variant, adjustment)

    session.commit()
    return _redirect_after_adjustment(ing_id, target_variant, auto_picked)


def _resolve_target_variant(
    session: Session, ing_id: int, variant_id: str
) -> tuple[IngredientVariant | None, bool]:
    """Resolve which variant to adjust.

    Extracted from inventory_adjust to reduce complexity. Returns
    (target_variant, auto_picked) where auto_picked is True if the
    system auto-selected a preferred variant.
    """
    variants = list(
        session.scalars(
            select(IngredientVariant)
            .where(IngredientVariant.ingredient_id == ing_id)
            .order_by(IngredientVariant.preferred.desc(), IngredientVariant.id)
        )
    )
    if not variants:
        return None, False

    if variant_id:
        return _find_specific_variant(variants, variant_id, ing_id), False

    # Auto-pick preferred variant
    target = next((v for v in variants if v.preferred), variants[0])
    return target, True


def _find_specific_variant(variants: list, variant_id: str, ing_id: int) -> IngredientVariant:
    """Find a specific variant by ID, raising BadRequest if not found.

    Extracted from _resolve_target_variant to reduce complexity.
    """
    try:
        vid = int(variant_id)
    except ValueError:
        raise BadRequest(
            f"ID de variante inválido: {variant_id!r}",
            context={"raw": variant_id},
        ) from None
    for v in variants:
        if v.id == vid:
            return v
    raise BadRequest(f"Variante {vid} no pertenece al ingrediente {ing_id}.")


def _get_pre_adjustment_stock(ing: Ingredient, target_variant: IngredientVariant | None) -> float:
    """Get the stock quantity before adjustment.

    Extracted from inventory_adjust to reduce complexity. Uses variant
    stock if variant-aware, otherwise legacy ingredient stock.
    """
    if target_variant is not None:
        return target_variant.stock_qty or 0.0
    return ing.stock_qty or 0.0


def _redirect_with_flash(message: str, ing_id: int) -> RedirectResponse:
    """Redirect to inventory with a flash message.

    Extracted from inventory_adjust to reduce complexity.
    """
    params = urlencode({"flash": message, "ing_id": ing_id})
    return RedirectResponse(url=f"/inventario?{params}", status_code=303)


def _redirect_with_negative_confirm(
    ing: Ingredient,
    target_variant: IngredientVariant | None,
    pre: float,
    adjustment: float,
    ing_id: int,
) -> RedirectResponse:
    """Redirect asking for negative stock confirmation.

    Extracted from inventory_adjust to reduce complexity.
    """
    if target_variant is not None:
        which = f"{target_variant.package_size:g} {target_variant.package_unit}"
    else:
        which = ing.name
    flash_msg = (
        f"no_confirm:La operación llevaría stock de {which} a "
        f"{pre + adjustment:.2f}. Confirmá haciendo click en Ajustar de nuevo."
    )
    return _redirect_with_flash(flash_msg, ing_id)


def _record_stock_movement(
    session: Session,
    ing_id: int,
    target_variant: IngredientVariant | None,
    adjustment: float,
    reason: str,
    user_id: int | None,
) -> None:
    """Create and add the StockMovement audit record.

    Extracted from inventory_adjust to reduce complexity. Sets variant_id
    on the movement if the schema supports it.
    """
    movement_kwargs = dict(
        ingredient_id=ing_id,
        movement_type="adjustment",
        qty=adjustment,
        reason=reason.strip() or None,
        reference_id=None,
        reference_type=None,
        recorded_at=datetime.now(timezone.utc),
        created_by=user_id,
    )
    if target_variant is not None and "variant_id" in StockMovement.__table__.columns:
        movement_kwargs["variant_id"] = target_variant.id

    movement = StockMovement(**movement_kwargs)
    session.add(movement)


def _apply_stock_adjustment(
    session: Session,
    ing: Ingredient,
    target_variant: IngredientVariant | None,
    adjustment: float,
) -> None:
    """Apply the stock adjustment to the variant or legacy ingredient.

    Extracted from inventory_adjust to reduce complexity. Updates variant
    stock if variant-aware, otherwise legacy ingredient stock. Syncs the
    rollup for variant-aware ingredients.
    """
    if target_variant is not None:
        target_variant.stock_qty = max(0.0, (target_variant.stock_qty or 0.0) + adjustment)
        # Sync the legacy Ingredient.stock_qty column with the rollup so
        # any consumer still reading the legacy field sees the correct total.
        from app.rms.variants import rollup_ingredient_stock

        rollup = rollup_ingredient_stock(session, ing.id)
        if rollup is not None:
            ing.stock_qty = rollup.base_qty
    else:
        ing.stock_qty = max(0.0, (ing.stock_qty or 0.0) + adjustment)


def _redirect_after_adjustment(
    ing_id: int,
    target_variant: IngredientVariant | None,
    auto_picked: bool,
) -> RedirectResponse:
    """Redirect after successful adjustment with optional flash message.

    Extracted from inventory_adjust to reduce complexity. Shows a flash
    message if a variant was auto-picked.
    """
    if not auto_picked:
        return RedirectResponse(url="/inventario", status_code=303)
    flash_msg = (
        f"info:Sin variante elegida — se aplicó a la preferida "
        f"({target_variant.package_size:g} {target_variant.package_unit})."
    )
    params = urlencode({"flash": flash_msg, "ing_id": ing_id})
    return RedirectResponse(url=f"/inventario?{params}", status_code=303)


@router.get("/{ing_id}/movimientos", response_class=HTMLResponse)
def inventory_movements(
    ing_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Show the movement history for one ingredient."""
    ing = session.get(Ingredient, ing_id)
    if ing is None:
        raise NotFound("Ingredient", id=ing_id)

    movements = session.scalars(
        select(StockMovement)
        .where(StockMovement.ingredient_id == ing_id)
        .order_by(StockMovement.recorded_at.desc())
        .limit(200)
    ).all()

    # Current stock for display
    current_stock = ing.stock_qty

    # Running balance: start from current stock and walk backwards
    balance = current_stock
    enriched = []
    for m in reversed(movements):
        prev_balance = balance
        balance = balance - m.qty  # reverse the movement to get prior state
        enriched.append(
            {
                "id": m.id,
                "movement_type": m.movement_type,
                "qty": m.qty,
                "reason": m.reason,
                "reference_id": m.reference_id,
                "reference_type": m.reference_type,
                "recorded_at": m.recorded_at,
                "created_by": m.created_by,
                "balance_before": balance,
                "balance_after": prev_balance,
            }
        )

    return render(
        request,
        "inventario_movimientos.html",
        {
            "ingredient": ing,
            "movements": enriched,
            "current_stock": current_stock,
        },
    )


# ---------------------------------------------------------------------------
# S7 — IngredientVariant CRUD (Decision A1)
# ---------------------------------------------------------------------------
#
# the operator's audio reference:
#   "harina 1kg / harina 250g / proveedor X — a single ingredient 'harina'
#    with sub-rows for each package".
#
# A variant is a specific (package_size, package_unit, supplier, price)
# combination for an Ingredient. Each Ingredient has 1+ variants; exactly
# one is marked preferred (the "current price" the dashboard reads).
# Stock rolls up across variants by converting each variant's stock into
# the Ingredient's base unit (unit on ingredient) and summing.
#


@router.get("/{ing_id}/variantes", response_class=HTMLResponse)
def ingredient_variants(
    ing_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Variants live on the ingredient detail page (#variants anchor).

    2026-09-26: the standalone ingrediente_variantes.html template never
    existed (prod 500). Redirect to the detail view instead.
    """
    ing = session.get(Ingredient, ing_id)
    if ing is None:
        raise NotFound("Ingredient", id=ing_id)
    return RedirectResponse(url=f"/inventario/{ing_id}#variants", status_code=303)


@router.post("/{ing_id}/variantes/nuevo")
def ingredient_variant_create(
    ing_id: int,
    request: Request,
    package_size: str = Form(...),
    package_unit: str = Form("und"),
    purchase_price_gs: str = Form(""),
    supplier_id: str = Form(""),
    stock_qty: str = Form("0"),
    notes: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Create a new variant for this Ingredient.

    If ``preferred`` is the only variant for this ingredient, it is marked
    preferred automatically (so the rollup always has one).
    """
    ing = session.get(Ingredient, ing_id)
    if ing is None:
        raise NotFound("Ingredient", id=ing_id)
    try:
        size = float(package_size.replace(",", "."))
        if size <= 0:
            raise ValueError
    except ValueError:
        raise BadRequest(
            f"Tamaño de paquete inválido: {package_size!r}",
            context={"raw": package_size},
        ) from None
    if package_unit not in ("g", "kg", "ml", "l", "und"):
        raise BadRequest(f"Unidad inválida: {package_unit!r}")

    try:
        price = (
            int(purchase_price_gs.replace(".", "").replace(",", "")) if purchase_price_gs else None
        )
    except ValueError:
        raise BadRequest(
            f"Precio inválido: {purchase_price_gs!r}",
            context={"raw": purchase_price_gs},
        ) from None
    if price is not None and price < 0:
        raise BadRequest("El precio no puede ser negativo.")

    sup_id: int | None = None
    if supplier_id:
        try:
            sup_id = int(supplier_id)
        except ValueError:
            raise BadRequest(
                f"ID de proveedor inválido: {supplier_id!r}",
                context={"raw": supplier_id},
            ) from None

    try:
        stock = float(stock_qty.replace(",", "."))
    except ValueError:
        raise BadRequest(f"Stock inválido: {stock_qty!r}", context={"raw": stock_qty}) from None
    if stock < 0:
        raise BadRequest("El stock no puede ser negativo.")

    existing = session.scalars(
        select(IngredientVariant).where(IngredientVariant.ingredient_id == ing_id)
    ).all()
    is_first = len(existing) == 0

    v = IngredientVariant(
        ingredient_id=ing_id,
        package_size=size,
        package_unit=package_unit,
        purchase_price_gs=price,
        supplier_id=sup_id,
        preferred=is_first,  # auto-prefer the first variant; operator can flip
        stock_qty=stock,
        notes=notes.strip() or None,
    )
    session.add(v)
    record_audit(
        request,
        session=session,
        action="ingredient_variant.create",
        target_type="ingredient_variant",
        target_id=None,
        detail={
            "ingredient_id": ing_id,
            "package_size": size,
            "package_unit": package_unit,
            "purchase_price_gs": price,
            "supplier_id": sup_id,
            "preferred": is_first,
        },
    )
    session.commit()
    return RedirectResponse(url=f"/inventario/{ing_id}#variants", status_code=303)


@router.post("/{ing_id}/variantes/{variant_id}/preferir")
def ingredient_variant_prefer(
    ing_id: int,
    variant_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Mark the given variant as preferred. Unset the previous preferred.

    The DB triggers (migration 040) clear the old preferred flag, so we
    just flip the new one to TRUE.
    """
    v = session.get(IngredientVariant, variant_id)
    if v is None or v.ingredient_id != ing_id:
        raise NotFound("IngredientVariant", id=variant_id)
    v.preferred = True
    # Update the parent ingredient's purchase_price_gs so legacy code
    # continues to see the current price.
    ing = session.get(Ingredient, ing_id)
    if ing is not None and v.purchase_price_gs is not None:
        ing.purchase_price_gs = v.purchase_price_gs
    record_audit(
        request,
        session=session,
        action="ingredient_variant.prefer",
        target_type="ingredient_variant",
        target_id=variant_id,
        detail={"ingredient_id": ing_id},
    )
    session.commit()
    return RedirectResponse(url=f"/inventario/{ing_id}#variants", status_code=303)


@router.post("/{ing_id}/variantes/{variant_id}/eliminar")
def ingredient_variant_delete(
    ing_id: int,
    variant_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Delete a variant.

    Refuses to delete if it is the only variant (would orphan the parent
    Ingredient). Preferring another first is the workaround.
    """
    v = session.get(IngredientVariant, variant_id)
    if v is None or v.ingredient_id != ing_id:
        raise NotFound("IngredientVariant", id=variant_id)
    siblings = session.scalars(
        select(IngredientVariant).where(
            IngredientVariant.ingredient_id == ing_id,
            IngredientVariant.id != variant_id,
        )
    ).all()
    if not siblings:
        raise BadRequest(
            "No se puede eliminar la única variante. "
            "Creá otra primero o convertí esta en la preferida con stock 0.",
            context={"ingredient_id": ing_id},
        )
    session.delete(v)
    record_audit(
        request,
        session=session,
        action="ingredient_variant.delete",
        target_type="ingredient_variant",
        target_id=variant_id,
        detail={"ingredient_id": ing_id},
    )
    session.commit()
    return RedirectResponse(url=f"/inventario/{ing_id}#variants", status_code=303)


@router.post("/{ing_id}/variantes/{variant_id}/editar")
def ingredient_variant_edit(
    ing_id: int,
    variant_id: int,
    request: Request,
    package_size: str = Form(...),
    package_unit: str = Form("und"),
    purchase_price_gs: str = Form(""),
    supplier_id: str = Form(""),
    stock_qty: str = Form("0"),
    notes: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Edit an existing variant (price, supplier, size, stock)."""
    v = session.get(IngredientVariant, variant_id)
    if v is None or v.ingredient_id != ing_id:
        raise NotFound("IngredientVariant", id=variant_id)

    try:
        size = float(package_size.replace(",", "."))
        if size <= 0:
            raise ValueError
    except ValueError:
        raise BadRequest(f"Tamaño inválido: {package_size!r}") from None
    if package_unit not in ("g", "kg", "ml", "l", "und"):
        raise BadRequest(f"Unidad inválida: {package_unit!r}")
    try:
        price = (
            int(purchase_price_gs.replace(".", "").replace(",", "")) if purchase_price_gs else None
        )
    except ValueError:
        raise BadRequest(f"Precio inválido: {purchase_price_gs!r}") from None
    sup_id: int | None = None
    if supplier_id:
        try:
            sup_id = int(supplier_id)
        except ValueError:
            raise BadRequest(f"Proveedor inválido: {supplier_id!r}") from None
    try:
        stock = float(stock_qty.replace(",", "."))
    except ValueError:
        raise BadRequest(f"Stock inválido: {stock_qty!r}") from None
    if stock < 0:
        raise BadRequest("El stock no puede ser negativo.")

    v.package_size = size
    v.package_unit = package_unit
    v.purchase_price_gs = price
    v.supplier_id = sup_id
    v.stock_qty = stock
    v.notes = notes.strip() or None

    # If this variant is preferred and the price changed, mirror it onto
    # the parent Ingredient.purchase_price_gs for backwards compatibility.
    if v.preferred:
        ing = session.get(Ingredient, ing_id)
        if ing is not None and ing.purchase_price_gs != price:
            # BACKLOG #31: route through record_price_event so the
            # IngredientPriceEvent row + purchase_price_updated_at both
            # stay in sync. The bare assignment previously bypassed both,
            # leaving /reportes/precios with 0 history rows for variant
            # edits on the preferred variant.
            record_price_event(session, ing.id, price, source="manual")

    record_audit(
        request,
        session=session,
        action="ingredient_variant.edit",
        target_type="ingredient_variant",
        target_id=variant_id,
        detail={"ingredient_id": ing_id, "new_price": price},
    )
    session.commit()
    return RedirectResponse(url=f"/inventario/{ing_id}#variants", status_code=303)


@router.post("/{ing_id}/forecast-horizon")
def ingredient_forecast_horizon_set(
    ing_id: int,
    request: Request,
    forecast_horizon_days: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Set the per-ingredient forecast horizon (Decision B).

    Empty string clears the override (falls back to global default).
    """
    ing = session.get(Ingredient, ing_id)
    if ing is None:
        raise NotFound("Ingredient", id=ing_id)
    val: int | None = None
    if forecast_horizon_days.strip():
        try:
            val = int(forecast_horizon_days)
            if val < 1 or val > 365:
                raise ValueError
        except ValueError:
            raise BadRequest(
                f"Horizonte inválido: {forecast_horizon_days!r}",
                context={"raw": forecast_horizon_days},
            ) from None
    ing.forecast_horizon_days = val
    record_audit(
        request,
        session=session,
        action="ingredient.forecast_horizon",
        target_type="ingredient",
        target_id=ing_id,
        detail={"forecast_horizon_days": val},
    )
    session.commit()
    return RedirectResponse(url=f"/inventario/{ing_id}#forecast", status_code=303)


def _parse_price(raw: str) -> int | None:
    """Parse the purchase_price_gs form field. Empty string → None."""
    raw = raw.strip()
    if not raw:
        return None
    try:
        from app.rms.money import parse_gs

        return parse_gs(raw)
    except (ValueError, TypeError) as e:
        raise BadRequest(f"Precio inválido: {raw!r}", context={"raw": raw}, cause=e) from e


# Additional search endpoints for Phase 2 completion


@router.get("/api/search/by-category", response_class=JSONResponse)
def ingredients_api_search_by_category(
    category: str = Query("", description="Category to search within"),
    q: str = Query("", description="Search query"),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Search ingredients by category and name for improved filtering.

    Returns ingredients matching the category and optionally filtered by search term.
    Useful for category-specific search in combo boxes.
    """
    # Get base query
    stmt = select(Ingredient).where(Ingredient.category == category)

    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(func.lower(Ingredient.name).like(like))

    # Order and limit
    stmt = stmt.order_by(Ingredient.name).limit(limit)
    rows = session.scalars(stmt).all()

    payload = [
        {
            "id": ing.id,
            "name": ing.name,
            "unit": ing.unit,
            "stock_qty": ing.stock_qty or 0.0,
            "min_stock_qty": ing.min_stock_qty or 0.0,
            "purchase_price_gs": ing.purchase_price_gs or 0,
        }
        for ing in rows
    ]
    return JSONResponse({"results": payload, "count": len(payload), "category": category})


@router.get("/api/search/critical", response_class=JSONResponse)
def ingredients_api_search_critical(
    limit: int = Query(20, ge=1, le=50),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Search for ingredients with critical stock levels.

    Returns ingredients that are at or below minimum stock levels,
    prioritized by how critical the situation is.
    """
    # Get ingredients that are critical (stock <= min_stock) and have stock movements
    loaded_ids = set(session.scalars(select(StockMovement.ingredient_id).distinct()).all())

    critical_ingredients = session.scalars(
        select(Ingredient)
        .where(Ingredient.stock_qty <= (Ingredient.min_stock_qty or 0))
        .where(Ingredient.id.in_(loaded_ids))
        .order_by(
            # Most critical first: negative stock, then very low stock.
            # SQLAlchemy func.case() in this env doesn't take `else_=` —
            # use raw SQL case for cross-dialect compatibility.
            sql_case(
                (Ingredient.stock_qty < 0, 1),
                (Ingredient.stock_qty <= (Ingredient.min_stock_qty or 0) * 0.5, 2),
                else_=3,
            ),
            Ingredient.name,
        )
        .limit(limit)
    ).all()

    payload = [
        {
            "id": ing.id,
            "name": ing.name,
            "unit": ing.unit,
            "stock_qty": ing.stock_qty or 0.0,
            "min_stock_qty": ing.min_stock_qty or 0.0,
            "purchase_price_gs": ing.purchase_price_gs or 0,
            "criticality": "negative"
            if ing.stock_qty < 0
            else "very_low"
            if ing.stock_qty <= (ing.min_stock_qty or 0) * 0.5
            else "low",
        }
        for ing in critical_ingredients
    ]
    return JSONResponse({"results": payload, "count": len(payload)})


@router.get("/api/search/reorder", response_class=JSONResponse)
def ingredients_api_search_reorder(
    limit: int = Query(20, ge=1, le=50),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Search for ingredients that need reordering.

    Returns ingredients that are at or below reorder point and have positive reorder points set.
    Useful for reordering workflows.
    """
    reorder_ingredients = session.scalars(
        select(Ingredient)
        .where(Ingredient.reorder_point.isnot(None))
        .where(Ingredient.reorder_point > 0)
        .where(Ingredient.stock_qty <= (Ingredient.reorder_point or 0))
        .order_by(Ingredient.name)
        .limit(limit)
    ).all()

    payload = [
        {
            "id": ing.id,
            "name": ing.name,
            "unit": ing.unit,
            "stock_qty": ing.stock_qty or 0.0,
            "reorder_point": ing.reorder_point or 0.0,
            "purchase_price_gs": ing.purchase_price_gs or 0,
        }
        for ing in reorder_ingredients
    ]
    return JSONResponse({"results": payload, "count": len(payload)})


__all__ = ["router"]
