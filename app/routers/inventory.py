"""app/routers/inventory.py — CRUD endpoints for ingredients.

Per dev plan §9 Task 3.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Query, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.charts import sparkline
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
        .where(Ingredient.is_packaging == True)
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


@router.get("/api/search", response_class=JSONResponse)
def ingredients_api_search(
    q: str = Query("", description="Search query"),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Search ingredients by name for combobox pickers.

    Used by /merma and /pedidos/nuevo. Returns matching ingredients
    ordered by name, with up to `limit` rows. Empty query returns
    all ingredients up to limit (alphabetical).
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
) -> Response:
    """Export all ingredients as a CSV download."""
    ingredients = session.scalars(select(Ingredient).order_by(Ingredient.name)).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "name", "unit", "category", "stock_qty", "min_stock_qty",
        "purchase_price_gs", "opening_stock_qty", "opening_stock_date",
        "reorder_point", "notes",
    ])
    for i in ingredients:
        writer.writerow([
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
        ])

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
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
    from datetime import date, timedelta
    today = datetime.now(ASUNCION_TZ).date()
    week_from_now = today + timedelta(days=7)
    month_from_now = today + timedelta(days=30)

    # ── KPI strip + filters (inventory redesign 2026-09-25) ───────────
    from app.rms.inventory_intel import stock_value_gs

    all_ings = session.scalars(select(Ingredient)).all()
    kpi_total = len(all_ings)
    kpi_critical = sum(1 for i in all_ings if i.stock_qty <= (i.min_stock_qty or 0))
    kpi_no_cost = sum(1 for i in all_ings if not i.purchase_price_gs)
    try:
        kpi_value_gs = stock_value_gs(session)
    except Exception:  # noqa: BLE001 — defensive default
        kpi_value_gs = sum((i.stock_qty or 0) * (i.purchase_price_gs or 0) for i in all_ings)

    q = (request.query_params.get("q") or "").strip().lower()
    estado = request.query_params.get("estado") or ""
    categorias = [c for c in request.query_params.getlist("categoria") if c]
    alergenos = [a for a in request.query_params.getlist("alergeno") if a]
    almacen = request.query_params.get("almacen") or ""

    def _has_allergen(i: Ingredient, code: str) -> bool:
        return code in (i.allergens or "").lower()

    def _match(i: Ingredient) -> bool:
        if q and q not in (i.name or "").lower():
            return False
        if estado == "bajo" and not (i.stock_qty <= (i.min_stock_qty or 0)):
            return False
        if estado == "critico" and not (i.stock_qty <= 0 or (i.min_stock_qty and i.stock_qty < i.min_stock_qty * 0.5)):
            return False
        if estado == "negativo" and not (i.stock_qty < 0):
            return False
        if estado == "sinprecio" and i.purchase_price_gs is not None:
            return False
        if estado == "ok" and (i.stock_qty <= (i.min_stock_qty or 0)):
            return False
        if categorias and (i.category or "") not in categorias:
            return False
        if alergenos and not all(_has_allergen(i, a) for a in alergenos):
            return False
        if almacen and (i.storage or "") != almacen:
            return False
        if expiry == "expired" and not (i.expiry_date and i.expiry_date < today):
            return False
        if expiry == "7days" and not (i.expiry_date and i.expiry_date <= week_from_now and i.expiry_date >= today):
            return False
        if expiry == "30days" and not (i.expiry_date and i.expiry_date <= month_from_now and i.expiry_date >= today):
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
            "kpi_value_gs": kpi_value_gs,
            "kpi_no_cost": kpi_no_cost,
            "expiring_soon": expiring_soon,
            "q": q,
            "estado": estado,
            "categorias": categorias,
            "alergenos_sel": alergenos,
            "almacen": almacen,
            "expiry": expiry,
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
            "total_all": total_all,
        },
    )


@router.get("/nuevo", response_class=HTMLResponse)
def inventory_new(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    """Show the new-ingredient form."""
    return render(
        request,
        "inventario_form.html",
        {"mode": "new", "ingredient": None, "action": "Nuevo", "units": [u.value for u in Unit]},
    )


@router.post("/nuevo")
def inventory_create(
    request: Request,
    name: str = Form(...),
    unit: str = Form(...),
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
        allergens=inferred_allergens or None,
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
    return render(
        request,
        "inventario_form.html",
        {"mode": "edit", "ingredient": ing, "action": "Editar", "units": [u.value for u in Unit]},
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
    ing.purchase_price_gs = price
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
        ing.allergens = allergens.strip() or None
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
        ing.allergens = ",".join(cls["allergens"]) or None
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
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Record a stock adjustment (wastage, breakage, count correction).
    Pass positive adjustment to add stock, negative to remove.
    Writes a StockMovement record for auditability.

    If the adjustment would drive stock negative and confirm_negative is not
    'yes', the request is rejected — the caller must show a confirmation
    modal first.
    """
    ing = session.get(Ingredient, ing_id)
    if ing is None:
        raise NotFound("Ingredient", id=ing_id)

    if adjustment == 0:
        # Don't silently accept a no-op. Tell the operator what happened.
        from urllib.parse import urlencode
        params = urlencode({
            "flash": "no_op:El ajuste fue 0 — no se modificó el stock.",
            "ing_id": ing_id,
        })
        return RedirectResponse(url=f"/inventario?{params}", status_code=303)

    # Reject negative resulting stock without explicit confirmation
    if ing.stock_qty + adjustment < 0 and confirm_negative != "yes":
        from urllib.parse import urlencode
        params = urlencode({
            "flash": f"no_confirm:La operación llevaría stock de {ing.name} a {ing.stock_qty + adjustment:.2f} {ing.unit}. Confirmá haciendo click en Ajustar de nuevo.",
            "ing_id": ing_id,
        })
        return RedirectResponse(url=f"/inventario?{params}", status_code=303)

    from app.auth import current_user_id

    user_id = current_user_id(request) or "operator"

    # StockMovement: positive qty = stock in, negative = stock out
    movement = StockMovement(
        ingredient_id=ing_id,
        movement_type="adjustment",
        qty=adjustment,
        reason=reason.strip() or None,
        reference_id=None,
        reference_type=None,
        recorded_at=datetime.now(timezone.utc),
        created_by=user_id,
    )
    session.add(movement)

    ing.stock_qty = max(0.0, ing.stock_qty + adjustment)
    session.commit()
    return RedirectResponse(url="/inventario", status_code=303)


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
        if ing is not None:
            ing.purchase_price_gs = price

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
