"""app/routers/inventory.py — CRUD endpoints for ingredients.

Per dev plan §9 Task 3.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Query, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
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
    rows = session.execute(
        select(Ingredient)
        .where(Ingredient.is_packaging.is_(True))
        .where(func.lower(Ingredient.name).like(like))
        .order_by(Ingredient.name)
        .limit(limit)
    ).scalars().all()
    return JSONResponse([
        {
            "id": r.id,
            "name": r.name,
            "unit": r.unit,
            "stock_qty": r.stock_qty,
            "purchase_price_gs": r.purchase_price_gs,
        }
        for r in rows
    ])


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
        rows = session.scalars(
            select(Ingredient).order_by(Ingredient.name).limit(limit)
        ).all()
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
                "id", "name", "unit", "category", "stock_qty", "min_stock_qty",
                "purchase_price_gs", "opening_stock_qty", "opening_stock_date",
                "reorder_point", "notes",
            ],
            _iter(),
        ),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=rms-inventory-{timestamp}.csv"},
    )


@router.get("", response_class=HTMLResponse)
def inventory_list(
    request: Request,
    sort: str | None = Query(None, description="Sort column: name, stock_qty, unit, min_stock_qty, purchase_price_gs"),
    dir: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    expiry: str = Query("all", pattern="^(all|7days|30days|expired)$"),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """List all ingredients with stock badge. Paginated at 50/page."""
    PER_PAGE = 50
    from datetime import timedelta
    today = datetime.now(ASUNCION_TZ).date()
    week_from_now = today + timedelta(days=7)
    month_from_now = today + timedelta(days=30)

    # ── KPI strip + filters (inventory redesign 2026-09-25) ───────────
    from app.rms.inventory_intel import stock_value_gs

    all_ings = session.scalars(select(Ingredient)).all()
    kpi_total = len(all_ings)
    # PRO-INV (2026-09-30): distinguish "never loaded initial stock" (stock 0
    # AND zero movements in the ledger) from genuinely depleted stock. Mixing
    # both made the "critical" KPI scary on day one (65 vs 44 real).
    # Variant-aware: ingredients with variants are NEVER "never_loaded"
    # even if legacy stock_qty is 0 — their stock may live on a variant.
    # The exact variant counts are computed later (after price_info); we
    # use a conservative "ignore legacy-only zero" approach here and
    # re-pin both KPIs after rollup_ingredient_stock() runs.
    loaded_ids = set(
        session.scalars(
            select(StockMovement.ingredient_id).distinct()
        ).all()
    )
    # Provisional never_loaded / critical counts. Both will be recomputed
    # once we know which ingredients actually have variants.
    never_loaded_ids = {
        i.id for i in all_ings
        if (i.stock_qty or 0) == 0 and i.id not in loaded_ids
    }
    kpi_never_loaded = len(never_loaded_ids)
    kpi_critical = sum(
        1 for i in all_ings
        if i.stock_qty <= (i.min_stock_qty or 0) and i.id not in never_loaded_ids
    )
    kpi_no_cost = sum(1 for i in all_ings if not i.purchase_price_gs)
    try:
        kpi_value_gs = stock_value_gs(session)
    except Exception:  # noqa: BLE001 — defensive default
        kpi_value_gs = sum((i.stock_qty or 0) * (i.purchase_price_gs or 0) for i in all_ings)

    q = (request.query_params.get("q") or "").strip().lower()
    # P3 UX batch: estado/almacen/expiry are now MULTI-select (checkboxes).
    # Legacy single values still work — normalize to lists.
    estados_sel = [e for e in request.query_params.getlist("estado") if e]
    categorias = [c for c in request.query_params.getlist("categoria") if c]
    alergenos = [a for a in request.query_params.getlist("alergeno") if a]
    almacenes_sel = [a for a in request.query_params.getlist("almacen") if a]
    expiries_sel = [e for e in request.query_params.getlist("expiry") if e and e != "all"]
    # Diet-restriction filter (P3 UX batch): multi-select over the
    # canonical dietary tags. AND semantics like allergens — an ingredient
    # matches only if it carries EVERY selected tag. Both Spanish canonical
    # ("sin gluten") and legacy English codes ("gluten_free") accepted.
    from app.rms.tagging.vocabulary import CANONICAL_DIETARY_TAGS
    diet_sel = [
        d.strip().lower()
        for d in request.query_params.getlist("diet") if d.strip()
    ]

    def _ingredient_diet_tags(i) -> set[str]:
        raw = (i.dietary_tags or "").lower()
        return {t.strip() for t in raw.split(",") if t.strip()}

    def _matches_diet(i) -> bool:
        if not diet_sel:
            return True
        tags = _ingredient_diet_tags(i)
        for want in diet_sel:
            if want in tags:
                continue
            # legacy English aliases → Spanish
            alias_map = {
                "gluten_free": ("sin gluten", "sin tacc"),
                "vegan": ("vegano",),
                "vegetarian": ("vegetariano",),
                "dairy_free": ("sin lactosa",),
                "egg_free": ("sin huevo",),
                "keto_friendly": ("keto",),
                "nut_free": ("sin frutos secos",),
            }
            if any(a in tags for a in alias_map.get(want, ())):
                continue
            return False
        return True

    def _has_allergen(i: Ingredient, code: str) -> bool:
        return code in (i.allergens or "").lower()

    def _match(i: Ingredient) -> bool:
        if q and q not in (i.name or "").lower():
            return False
        if estados_sel:
            ok = False
            for estado in estados_sel:
                if estado == "bajo" and i.stock_qty <= (i.min_stock_qty or 0):
                    ok = True
                elif estado == "critico" and (i.stock_qty <= 0 or (i.min_stock_qty and i.stock_qty < i.min_stock_qty * 0.5)):
                    ok = True
                elif estado == "negativo" and i.stock_qty < 0:
                    ok = True
                elif estado == "sincargar" and i.id in never_loaded_ids:
                    ok = True
                elif estado == "sinprecio" and i.purchase_price_gs is None:
                    ok = True
                elif estado == "ok" and i.stock_qty > (i.min_stock_qty or 0):
                    ok = True
                if ok:
                    break
            if not ok:
                return False
        if categorias and (i.category or "") not in categorias:
            return False
        if alergenos and not all(_has_allergen(i, a) for a in alergenos):
            return False
        if not _matches_diet(i):
            return False
        if almacenes_sel and (i.storage or "") not in almacenes_sel:
            return False
        if expiries_sel:
            ok = False
            for expiry in expiries_sel:
                if expiry == "expired" and i.expiry_date and i.expiry_date < today:
                    ok = True
                elif expiry == "7days" and i.expiry_date and i.expiry_date <= week_from_now and i.expiry_date >= today:
                    ok = True
                elif expiry == "30days" and i.expiry_date and i.expiry_date <= month_from_now and i.expiry_date >= today:
                    ok = True
                if ok:
                    break
            if not ok:
                return False
        return True

    _filtered_all = [i for i in all_ings if _match(i)]
    total = len(_filtered_all)
    total_all = len(all_ings)
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    page = min(page, total_pages)

    # KPI: count ingredients expiring within 7 days
    expiring_soon = sum(
        1 for i in all_ings
        if i.expiry_date and i.expiry_date <= week_from_now and i.expiry_date >= today
    )

    categories = sorted({(i.category or "").strip() for i in all_ings if (i.category or "").strip()})
    storages = sorted({(i.storage or "").strip() for i in all_ings if (i.storage or "").strip()})

    # Data-quality: duplicate ingredients (same name, case-insensitive)
    _by_norm: dict[str, list] = {}
    for i in all_ings:
        _by_norm.setdefault((i.name or "").strip().lower(), []).append(i)
    duplicates = [
        {"name": k, "count": len(v), "units": sorted({x.unit or "" for x in v}),
         "ids": [x.id for x in v]}
        for k, v in _by_norm.items() if len(v) > 1
    ]

    # Data-quality: price per g/ml above Gs. 5.000 is almost certainly a per-kg/l
    # price entered on a gram/milliliter row (carrot-cake 11M bug class).
    suspicious_prices = [
        {"id": i.id, "name": i.name, "unit": i.unit, "price": i.purchase_price_gs}
        for i in all_ings
        if i.unit in ("g", "ml") and (i.purchase_price_gs or 0) > 5000
    ]

    # Sorting applied to the filtered set (in-Python; catalog sizes are small)
    _sort_map = {
        "name": lambda i: (i.name or "").lower(),
        "stock_qty": lambda i: i.stock_qty or 0,
        "min_stock_qty": lambda i: i.min_stock_qty or 0,
        "purchase_price_gs": lambda i: i.purchase_price_gs or 0,
        "unit": lambda i: i.unit or "",
        "valor_gs": lambda i: (i.stock_qty or 0) * (i.purchase_price_gs or 0),
        "category": lambda i: (i.category or "").lower(),
        "expiry_date": lambda i: i.expiry_date.isoformat() if i.expiry_date else "",
        "supplier": lambda i: (i.supplier.name.lower() if i.supplier and i.supplier.name else ""),
    }
    if sort and sort in _sort_map:
        _filtered_all.sort(key=_sort_map[sort], reverse=(dir == "desc"))
    else:
        _filtered_all.sort(key=lambda i: (i.name or "").lower())

    ingredients = _filtered_all[(page - 1) * PER_PAGE : page * PER_PAGE]

    # Phase D — Q1 surface: price-history enrichment per ingredient.
    # Ingredients with >=2 events in the last 90d get a muted min/max line
    # under the price cell; >=3 events also get a sparkline SVG.
    price_info: dict[int, dict] = {}
    ing_ids_with_events = set(
        session.scalars(
            select(IngredientPriceEvent.ingredient_id).distinct()
        ).all()
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

    # Variant-aware (multi-package + multi-supplier) totals.
    # For each ingredient on this page, compute:
    #   - effective_stock_qty: rollup sum if variants exist, else i.stock_qty
    #   - variants_by_ing_id:  list of {variant_id, package_size, package_unit,
    #                          preferred, supplier_name} for the inline +qty
    #                          form's variant picker.
    # rollup.variants is list[dict] with keys: variant_id, package_size,
    # package_unit, stock_qty, purchase_price_gs, supplier_id, preferred, label.
    from app.rms.variants import rollup_ingredient_stock
    effective_stock_qty: dict[int, float] = {}
    variants_by_ing_id: dict[int, list[dict]] = {}
    for ing in ingredients:
        rollup = rollup_ingredient_stock(session, ing.id)
        if rollup is not None and rollup.variant_count > 0:
            effective_stock_qty[ing.id] = rollup.base_qty
            # Resolve supplier names in one pass.
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
    # Global cache for KPIs (covers ingredients NOT on this page).
    _all_ing_ids = [i.id for i in all_ings]
    if _all_ing_ids:
        _variant_counts: dict[int, int] = dict(
            session.execute(
                select(IngredientVariant.ingredient_id, func.count(IngredientVariant.id))
                .where(IngredientVariant.ingredient_id.in_(_all_ing_ids))
                .group_by(IngredientVariant.ingredient_id)
            ).all()
        )
    else:
        _variant_counts = {}

    # KPI adjustments for variant-aware counts: ingredients with variants
    # should NOT be flagged as "never_loaded" just because legacy stock_qty
    # is 0 — their stock may live entirely on a variant.
    _has_variant = {ing_id for ing_id, n in _variant_counts.items() if n > 0}
    never_loaded_ids = {
        i.id for i in all_ings
        if (i.stock_qty or 0) == 0 and i.id not in loaded_ids and i.id not in _has_variant
    }
    kpi_never_loaded = len(never_loaded_ids)
    # Re-run critical with variant-aware effective stock (for ingredients on
    # this page; ingredients off-page still use legacy stock_qty as before,
    # which is fine — the user only ever sorts/views what they see).
    kpi_critical = sum(
        1 for i in all_ings
        if effective_stock_qty.get(i.id, float(i.stock_qty or 0.0)) <= (i.min_stock_qty or 0)
        and i.id not in never_loaded_ids
    )

    # Wave 4 — Market reference price (Paraguay baseline). One row per
    # ingredient. Compute delta_pct = (our_price - market_price) / market * 100.
    from app.rms.models import MarketPriceReference
    market_refs: dict[int, dict] = {}
    ing_ids = [ing.id for ing in ingredients]
    if ing_ids:
        refs = session.scalars(
            select(MarketPriceReference).where(
                MarketPriceReference.ingredient_id.in_(ing_ids)
            )
        ).all()
        for r in refs:
            ing = next((i for i in ingredients if i.id == r.ingredient_id), None)
            if not ing or ing.purchase_price_gs is None:
                continue
            delta_pct = (
                (ing.purchase_price_gs - r.price_gs) / r.price_gs * 100
                if r.price_gs > 0 else 0
            )
            market_refs[ing.id] = {
                "market_price_gs": r.price_gs,
                "market_unit": r.unit,
                "market_source": r.source,
                "market_notes": r.notes,
                "delta_pct": delta_pct,
            }

    return render(
        request,
        "inventario.html",
        {
            "ingredients": ingredients,
            "effective_stock_qty": effective_stock_qty,
            "variants_by_ing_id": variants_by_ing_id,
            "price_info": price_info,
            "market_refs": market_refs,
            "sort": sort or "",
            "dir": dir,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "per_page": PER_PAGE,
            "page_start": (page - 1) * PER_PAGE + 1,
            "page_end": min(page * PER_PAGE, total),
            # redesign 2026-09-25
            "kpi_total": kpi_total,
            "kpi_critical": kpi_critical,
            "kpi_never_loaded": kpi_never_loaded,
            "never_loaded_ids": never_loaded_ids,
            "kpi_value_gs": kpi_value_gs,
            "kpi_no_cost": kpi_no_cost,
            "expiring_soon": expiring_soon,
            "q": q,
            "estados_sel": estados_sel,
            "categorias": categorias,
            "alergenos_sel": alergenos,
            "diet_sel": diet_sel,
            "diet_options": sorted(CANONICAL_DIETARY_TAGS),
            "almacenes_sel": almacenes_sel,
            "expiries_sel": expiries_sel,
            "categories": categories,
            "storages": storages,
            "allergen_codes": [
                ("gluten", "Gluten"), ("dairy", "Lácteos"), ("eggs", "Huevos"),
                ("nuts", "Frutos secos"), ("soy", "Soja"), ("sesame", "Sésamo"),
                ("sulfites", "Sulfitos"),
            ],
            "total_filtered": total,
            "duplicates": duplicates,
            "suspicious_prices": suspicious_prices,
            # 2026-09-29: tag-validation banner (tagging/ refactor).
            # Count ingredients with cached tag_validation_issues. This
            # is a cheap COUNT(*) — the audit only re-runs when the user
            # clicks "Re-correr auditoría" on the audit page.
            "tag_audit_count": session.scalar(
                select(func.count(Ingredient.id)).where(
                    Ingredient.tag_validation_issues.isnot(None),
                    Ingredient.tag_validation_issues != "",
                )
            ) or 0,
            "total_all": total_all,
        },
    )


@router.get("/carga-inicial", response_class=HTMLResponse)
def carga_inicial_view(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    """PRO-INV: asisted initial stock load — list every ingredient that has
    zero movements in the ledger so the operator can load real opening counts
    in one screen (instead of 21 detail-page visits)."""
    loaded_ids = set(
        session.scalars(select(StockMovement.ingredient_id).distinct()).all()
    )
    pendientes = [
        i for i in session.scalars(select(Ingredient).order_by(Ingredient.name)).all()
        if (i.stock_qty or 0) == 0 and i.id not in loaded_ids
    ]
    return render(request, "carga_inicial.html", {"pendientes": pendientes})


@router.post("/carga-inicial")
async def carga_inicial_save(
    request: Request,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Save bulk initial stock. Form fields: qty_<id> per row (blank = skip)."""
    from app.auth import current_user_id

    user_id = current_user_id(request) or "operator"
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
        session.add(StockMovement(
            ingredient_id=ing_id,
            movement_type="initial",
            qty=qty,
            reason="carga inicial de inventario",
            reference_id=None,
            reference_type=None,
            recorded_at=datetime.now(timezone.utc),
        ))
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
    """Create new ingredient."""
    # BUG-00: empty name must yield a 400 with a Spanish error, not a 500.
    # Use default "" instead of required Form(...) so FastAPI's auto-validation
    # does not produce an English "name es obligatorio" before our handler runs.
    name = name.strip() if name else ""
    if not name:
        raise BadRequest(INGREDIENT_NAME_REQUIRED)
    try:
        unit_enum = Unit.coerce(unit)
    except ValueError as e:
        raise BadRequest(f"Unidad inválida: {e}", context={"unit": str(unit)}, cause=e) from e

    price = _parse_price(purchase_price_gs)
    if stock_qty < 0:
        raise BadRequest("El stock no puede ser negativo.", context={"stock_qty": stock_qty})
    if min_stock_qty < 0:
        raise BadRequest("El stock mínimo no puede ser negativo.", context={"min_stock_qty": min_stock_qty})

    opening_qty = float(opening_stock_qty) if opening_stock_qty.strip() else None
    opening_date = opening_stock_date.strip() or None
    reorder = float(reorder_point) if reorder_point.strip() else None

    # Wave 2 — auto-fill inference on create.
    # If operator left the classification fields empty, fill from `name` keyword match.
    # Operator can always override any field after creation via /editar.
    name_for_inference = name.strip()
    classification = classify_ingredient(name_for_inference, session=session)
    inferred_category = classification["category"]
    inferred_subcategory = classification["subcategory"]
    inferred_role = classification["role"]
    inferred_allergens = ",".join(classification["allergens"])
    inferred_dietary_tags = ",".join(classification["dietary_tags"])
    inferred_shelf_life = classification["shelf_life_days"]
    inferred_storage = classification["storage"]

    ing = Ingredient(
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

    # Tag validation (061): populate tag_validation_issues column on the
    # newly-created ingredient so the audit banner catches any issues
    # immediately (e.g. operator claimed 'vegano' but allergens include dairy).
    try:
        from app.rms.tagging.classify import validate_ingredient
        issues = validate_ingredient(ing)
        if issues:
            ing.tag_validation_issues = "\n".join(issues)
            session.commit()
    except Exception:  # noqa: BLE001 — defensive default
        logger.warning(
            "tag validation refresh failed for new ingredient ing_id=%s", ing.id,
            exc_info=True,
        )
        session.rollback()

    # Audit + info log
    logger.info(
        "ingredient_created id={} name={!r} unit={} stock={}",
        ing.id, ing.name, ing.unit, ing.stock_qty,
    )
    record_audit(
        request, session=session,
        action="ingredient.create", target_type="Ingredient",
        target_id=ing.id, detail={"name": ing.name, "unit": ing.unit},
    )

    # Record an initial stock movement if opening stock was set
    if opening_qty is not None and opening_qty != stock_qty:
        from app.auth import current_user_id
        user_id = current_user_id(request) or "operator"
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

    # Phase B — Q1 core: when an operator creates an ingredient with a price,
    # record the first price event so the history starts populated.
    if price is not None:
        try:
            record_price_event(session, ing.id, price, source="manual")
            session.commit()
        except Exception:  # noqa: BLE001 — defensive default
            # Don't fail the whole request on a price-history write error.
            logger.warning(
                "record_price_event failed for new ingredient ing_id={}",
                ing.id, exc_info=True,
            )

    return RedirectResponse(url="/inventario", status_code=303)


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
    return JSONResponse({
        "repaired": len(changes),
        "tags_removed": tags_removed,
        "validation_issues": issues_count,
    })
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
            recipes.append({
                "id": recipe.id,
                "name": recipe.name,
                "qty": line.qty,
                "line_unit": line.line_unit,
            })

    # S7 Decision B — forecast horizon computation (per-ingredient or default)
    from app.rms.variants import (
        days_until_short,
        rollup_ingredient_stock,
    )
    rollup = rollup_ingredient_stock(session, ing_id)
    forecast = days_until_short(session, ing_id)

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
        },
    )


def _price_stats_safe(session: Session, ing_id: int) -> object:
    try:
        from app.rms.price_history import price_stats
        return price_stats(session, ing_id, days=90)
    except Exception:  # noqa: BLE001 — defensive default
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
    """
    from app.rms.validation import (
        optional_text,
        parse_date_iso,
        parse_money_gs,
        parse_quantity,
        parse_unit,
        require_text,
    )

    ing = session.get(Ingredient, ing_id)
    if ing is None:
        raise NotFound("Ingredient", id=ing_id)

    name_clean = require_text(name, field="nombre", max_len=120)
    unit_enum = parse_unit(unit)
    stock = parse_quantity(stock_qty, field="stock", allow_zero=True)
    min_stock = parse_quantity(min_stock_qty, field="stock mínimo", allow_zero=True)
    price = parse_money_gs(purchase_price_gs, allow_zero=True)

    ing.name = name_clean
    ing.unit = unit_enum.value
    ing.stock_qty = stock
    ing.min_stock_qty = min_stock
    # BACKLOG #31: price event recording happens later in this handler
    # (see "Phase B — Q1 core" comment around line 1171). Don't pre-write
    # here — that would double-fire record_price_event and produce two
    # events per save (sibling already wired the canonical path).
    ing.notes = optional_text(notes, max_len=2000)

    # Operator-editable classification (detail page exposes them; form
    # overrides auto-inference). "__unset__" = field not submitted (older
    # form posts) → keep current value.
    if shelf_life_days.strip():
        try:
            ing.shelf_life_days = int(float(shelf_life_days)) or None
        except (TypeError, ValueError) as exc:
            logger.debug("inventory shelf_life_days parse failed: {}", exc)
    if allergens != "__unset__":
        # Empty string = explicitly cleared to "sin declarar" (None).
        ing.allergens = allergens.strip() or ''  # '' = declared-neutral, never NULL
    if dietary_tags != "__unset__":
        ing.dietary_tags = dietary_tags.strip() or None
    ing.may_contain_gluten = may_contain_gluten == "1"
    if lead_time_days.strip():
        try:
            ing.lead_time_days = int(lead_time_days) or None
        except (TypeError, ValueError) as exc:
            logger.debug("inventory lead_time_days parse failed: {}", exc)

    # Wave 2 — auto-fill inference on update too.
    # Operator can override category via the form; if they leave it blank,
    # re-run inference against the (possibly new) name.
    explicit_category = optional_text(category, max_len=32)
    if explicit_category:
        ing.category = explicit_category
        # Re-infer the rest of the classification against the new name so
        # the ingredient's metadata stays coherent after a rename.
        cls = classify_ingredient(name_clean, session=session)
        ing.subcategory = cls["subcategory"]
        ing.role = cls["role"]
        ing.allergens = ",".join(cls["allergens"]) or ''  # '' = declared-neutral, never NULL
        ing.dietary_tags = ",".join(cls["dietary_tags"]) or None
        ing.shelf_life_days = cls["shelf_life_days"]
        ing.storage = cls["storage"]
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

    # Opening stock — only update if both qty and date are provided
    op_qty_raw = (opening_stock_qty or "").strip()
    op_date_raw = (opening_stock_date or "").strip()
    if op_qty_raw and op_date_raw:
        ing.opening_stock_qty = parse_quantity(op_qty_raw, field="stock inicial")
        ing.opening_stock_date = parse_date_iso(op_date_raw, field="fecha de stock inicial")
    else:
        ing.opening_stock_qty = None
        ing.opening_stock_date = None

    rp_raw = (reorder_point or "").strip()
    ing.reorder_point = parse_quantity(rp_raw, field="punto de reorden", allow_zero=True) if rp_raw else None

    # Phase B — Q1 core: record a price event when the operator changes the
    # price. We always record when the new price is non-null — even if it
    # matches the previous value (auditability beats optimization here).
    should_record = price is not None

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise Conflict(
            INGREDIENT_DUPLICATE_NAME,
            context={"name": name_clean},
        ) from None

    if should_record:
        try:
            record_price_event(session, ing.id, price, source="manual")
            session.commit()
        except Exception:  # noqa: BLE001 — defensive default
            logger.warning(
                "record_price_event failed for ingredient ing_id={} update",
                ing.id, exc_info=True,
            )

    # Tag algebra (054): ingredient tags/allergens may have changed —
    # re-derive every recipe using it (transitively) and sync products.
    try:
        from app.rms.tag_algebra import _product_inherit_sync, cascade_refresh
        refreshed = cascade_refresh(session, ingredient_id=ing.id)
        for rid in refreshed:
            _product_inherit_sync(session, rid)
        session.commit()
    except Exception:  # noqa: BLE001 — defensive default
        logger.warning(
            "tag cascade failed for ingredient ing_id=%s update", ing.id,
            exc_info=True,
        )
        session.rollback()

    # Tag validation (061): refresh this ingredient's tag_validation_issues
    # column so the warning banner on the inventory list + ingredient edit
    # form stays current. The audit is pure (no DB writes except the
    # column), so it's safe to run inline after the save commit.
    try:
        from app.rms.tagging.classify import validate_ingredient
        issues = validate_ingredient(ing)
        # Re-fetch in case the previous session.commit() reset the binding.
        ing_row = session.get(Ingredient, ing.id)
        if ing_row is not None:
            ing_row.tag_validation_issues = "\n".join(issues) if issues else None
            session.commit()
    except Exception:  # noqa: BLE001 — defensive default
        logger.warning(
            "tag validation refresh failed for ing_id=%s", ing.id,
            exc_info=True,
        )
        session.rollback()

    return RedirectResponse(url="/inventario", status_code=303)


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

    **Variant-aware (multi-package / multi-supplier)**:
    If the ingredient has IngredientVariant rows and ``variant_id`` is
    provided, the adjustment is applied to that variant's stock AND to a
    StockMovement with a ``variant_id`` column when the schema supports it.
    If the ingredient has variants but no variant_id is provided, the
    preferred variant is auto-selected (operator sees a flash notice).
    If the ingredient has NO variants, falls back to the legacy
    Ingredient.stock_qty column (unchanged behavior).

    If the adjustment would drive stock negative and confirm_negative is not
    'yes', the request is rejected — the caller must show a confirmation
    modal first.
    """
    ing = session.get(Ingredient, ing_id)
    if ing is None:
        raise NotFound("Ingredient", id=ing_id)

    if adjustment == 0:
        # Don't silently accept a no-op. Tell the operator what happened.
        params = urlencode({
            "flash": "no_op:El ajuste fue 0 — no se modificó el stock.",
            "ing_id": ing_id,
        })
        return RedirectResponse(url=f"/inventario?{params}", status_code=303)

    # Resolve variant: if the ingredient has variants and none specified,
    # auto-pick the preferred one. The list-view form sends variant_id
    # explicitly so this branch mainly affects the detail-page modal.
    variants = list(session.scalars(
        select(IngredientVariant)
        .where(IngredientVariant.ingredient_id == ing_id)
        .order_by(IngredientVariant.preferred.desc(), IngredientVariant.id)
    ))
    target_variant: IngredientVariant | None = None
    auto_picked = False
    if variants:
        if variant_id:
            try:
                vid = int(variant_id)
            except ValueError:
                raise BadRequest(
                    f"ID de variante inválido: {variant_id!r}",
                    context={"raw": variant_id},
                ) from None
            for v in variants:
                if v.id == vid:
                    target_variant = v
                    break
            if target_variant is None:
                raise BadRequest(
                    f"Variante {vid} no pertenece al ingrediente {ing_id}.",
                )
        else:
            # Prefer the explicitly preferred variant, else the first.
            target_variant = next(
                (v for v in variants if v.preferred), variants[0]
            )
            auto_picked = True
    else:
        target_variant = None  # legacy path

    # Reject negative resulting stock without explicit confirmation.
    # When variants are in play, check the variant's own stock_qty (not
    # the legacy Ingredient.stock_qty column) so the guard matches
    # what's actually being mutated.
    if target_variant is not None:
        pre = target_variant.stock_qty or 0.0
    else:
        pre = ing.stock_qty or 0.0
    if pre + adjustment < 0 and confirm_negative != "yes":
        if target_variant is not None:
            which = f"{target_variant.package_size:g} {target_variant.package_unit}"
        else:
            which = ing.name
        params = urlencode({
            "flash": (
                f"no_confirm:La operación llevaría stock de {which} a "
                f"{pre + adjustment:.2f}. Confirmá haciendo click en Ajustar de nuevo."
            ),
            "ing_id": ing_id,
        })
        return RedirectResponse(url=f"/inventario?{params}", status_code=303)

    from app.auth import current_user_id

    user_id = current_user_id(request) or "operator"

    # StockMovement: positive qty = stock in, negative = stock out.
    # Reference the variant_id when applicable so the audit trail can
    # reconstruct "which bag did this receipt come from?".
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

    if target_variant is not None:
        # Variant model: stock lives on the variant, not the parent.
        target_variant.stock_qty = max(0.0, (target_variant.stock_qty or 0.0) + adjustment)
        # Sync the legacy Ingredient.stock_qty column with the rollup so
        # any consumer still reading the legacy field sees the correct total.
        from app.rms.variants import rollup_ingredient_stock
        rollup = rollup_ingredient_stock(session, ing_id)
        if rollup is not None:
            ing.stock_qty = rollup.base_qty
    else:
        # Legacy path: ingredient has no variants.
        ing.stock_qty = max(0.0, (ing.stock_qty or 0.0) + adjustment)

    session.commit()
    flash_msg = None
    if auto_picked:
        flash_msg = (
            f"info:Sin variante elegida — se aplicó a la preferida "
            f"({target_variant.package_size:g} {target_variant.package_unit})."
        )
    params = urlencode(
        {"flash": flash_msg, "ing_id": ing_id}
    ) if flash_msg else ""
    target_url = f"/inventario?{params}" if params else "/inventario"
    return RedirectResponse(url=target_url, status_code=303)


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
        enriched.append({
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
        })

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
# Saskia's audio reference:
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
        price = int(purchase_price_gs.replace(".", "").replace(",", "")) if purchase_price_gs else None
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
        price = int(purchase_price_gs.replace(".", "").replace(",", "")) if purchase_price_gs else None
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


__all__ = ["router"]
