"""app/routers/recipes.py — CRUD endpoints for recipes with polymorphic lines.

Per dev plan §9 Task 3 + v2 §5 (polymorphic recipe_line).

Note: repeated form fields (multiple line_kind / line_target_id / line_qty / line_notes
per row) require async parsing via `await request.form()` because FastAPI's Form()
only handles single values.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.costing import (
    CostResult,
    batch_recipes_cost,
)
from app.rms.dependencies import get_session
from app.rms.models import Ingredient, Product, Recipe, RecipeLine
from app.rms.units import Unit
from app.rms.recipe_intel import (
    infer_recipe_dietary,
    infer_recipe_family_from_name,
    infer_difficulty,
    estimate_prep_minutes,
    estimate_cook_minutes,
    recipe_ingredient_count,
)
from app.services.template_render import render

router = APIRouter(prefix="/recetas", dependencies=[Depends(require_login)])


def _decorate(session: Session, r: Recipe, batch: CostResult, unit: CostResult | None, line_count: int) -> dict:
    """Compute batch + unit cost for a recipe row (data passed in from batch loader)."""
    return {
        "id": r.id,
        "name": r.name,
        "yield_qty": r.yield_qty,
        "yield_unit": r.yield_unit,
        "line_count": line_count,
        "batch_cost_gs": batch.batch_cost_gs,
        "unit_cost_gs": unit.batch_cost_gs if unit else None,
        "notes": r.notes,
        "prep_minutes": r.prep_minutes,
        "cook_minutes": r.cook_minutes,
        "family": r.family,
        "dietary_tags": r.dietary_tags,
        # 2026-09-23 (US 1.1): recipe-photo button in /recetas list depends on
        # this key. Must be in the dict, not read from `r` directly in the
        # template, because `r` isn't passed to the template — only `recipes`
        # (a list of these dicts) is.
        "image_url": r.image_url,
    }


@router.get("", response_class=HTMLResponse)
async def recipes_list(
    request: Request,
    q: str = Query("", description="Search by recipe name"),
    ingredient_id: str = Query("", description="Filter by single ingredient ID (legacy)"),
    ingredient_ids: str = Query("", description="Filter by multiple ingredient IDs (comma-separated). US 3.2: AND semantics — recipe must use ALL selected."),
    sort: str = Query("name", pattern="^(name|yield_qty|batch_cost_gs)$"),
    dir: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """List recipes with batch + unit cost, search, filter by ingredient, and column sort.

    ingredient_id comes from a form hidden field that may be empty (when the user
    hasn't picked an ingredient from the combo). Empty string → no filter.

    ingredient_ids (US 3.2) accepts a comma-separated list. A recipe matches if
    it uses ALL listed ingredients. The single-id legacy parameter still works.

    Batch-loaded to avoid N+1 on Neon.
    """
    # Coerce single-id (legacy) into the multi-id list for unified handling.
    ing_id_ints: list[int] = []
    if ingredient_id and ingredient_id.strip():
        try:
            ing_id_ints.append(int(ingredient_id))
        except (TypeError, ValueError):
            pass
    # Parse multi-id list. Strip whitespace, ignore empties, validate as int, dedupe.
    if ingredient_ids and ingredient_ids.strip():
        for raw in ingredient_ids.split(","):
            raw = raw.strip()
            if not raw:
                continue
            try:
                val = int(raw)
            except ValueError:
                continue
            if val not in ing_id_ints:
                ing_id_ints.append(val)

    # Base query — first count for pagination
    count_stmt = select(func.count(Recipe.id))
    if q:
        count_stmt = count_stmt.where(Recipe.name.ilike(f"%{q}%"))
    if ing_id_ints:
        # AND semantics: recipe must use ALL of these ingredients.
        # Subquery: pick recipe_ids that have N distinct line_ref_id matches.
        from sqlalchemy import func as _func
        match_subq = (
            select(RecipeLine.recipe_id)
            .where(
                RecipeLine.line_kind == "ingredient",
                RecipeLine.line_ref_id.in_(ing_id_ints),
            )
            .group_by(RecipeLine.recipe_id)
            .having(_func.count(_func.distinct(RecipeLine.line_ref_id)) == len(ing_id_ints))
            .subquery()
        )
        count_stmt = count_stmt.where(Recipe.id.in_(select(match_subq.c.recipe_id)))
    total_count = session.scalar(count_stmt) or 0

    # Building data stmt
    stmt = select(Recipe)

    # Search filter
    if q:
        stmt = stmt.where(Recipe.name.ilike(f"%{q}%"))

    # Ingredient filter: find recipes that use ALL of these ingredients
    if ing_id_ints:
        from sqlalchemy import func as _func
        match_subq = (
            select(RecipeLine.recipe_id)
            .where(
                RecipeLine.line_kind == "ingredient",
                RecipeLine.line_ref_id.in_(ing_id_ints),
            )
            .group_by(RecipeLine.recipe_id)
            .having(_func.count(_func.distinct(RecipeLine.line_ref_id)) == len(ing_id_ints))
            .subquery()
        )
        stmt = stmt.where(Recipe.id.in_(select(match_subq.c.recipe_id)))

    # Sorting
    sort_col = {
        "name": Recipe.name,
        "yield_qty": Recipe.yield_qty,
        "batch_cost_gs": Recipe.id,  # Will override after cost calc
    }.get(sort, Recipe.name)
    if dir == "desc":
        stmt = stmt.order_by(sort_col.desc())
    else:
        stmt = stmt.order_by(sort_col.asc())

    # Pagination
    offset = (page - 1) * page_size
    recipes = session.scalars(
        stmt.distinct().offset(offset).limit(page_size)
    ).all()
    batch_results = batch_recipes_cost(session, list(recipes))
    decorated = [
        _decorate(session, r, batch_results[r.id][0], batch_results[r.id][1], batch_results[r.id][2])
        for r in recipes
    ]

    # Sort by cost after decoration if needed
    if sort == "batch_cost_gs":
        decorated.sort(key=lambda x: x["batch_cost_gs"] or 0, reverse=(dir == "desc"))

    # Ingredient list for filter dropdown
    all_ingredients = session.scalars(select(Ingredient).order_by(Ingredient.name)).all()

    return render(request, "recetas.html", {
        "recipes": decorated,
        "q": q,
        "ingredient_id": ing_id_ints[0] if ing_id_ints else "",
        "ingredient_ids": ",".join(str(i) for i in ing_id_ints),
        "sort": sort,
        "dir": dir,
        "ingredients": all_ingredients,
        "total": len(decorated),
        "pagination": {
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total_count + page_size - 1) // page_size),
        },
        "page_start": offset + 1 if decorated else 0,
        "page_end": offset + len(decorated),
    })


@router.get("/nueva", response_class=HTMLResponse)
async def recipe_new(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    """Show new-recipe form. Passes DB-driven catalogs:
      - recipe_families: rows from `category` WHERE scope='recipe_family'
      - dietary_tags: rows from `tag` WHERE kind='recipe'
    """
    from app.rms.categories import list_categories as list_cats
    from app.rms.tags import list_tags_for_kind

    ingredients = session.scalars(select(Ingredient).order_by(Ingredient.name)).all()
    other_recipes = session.scalars(select(Recipe).order_by(Recipe.name)).all()
    return render(
        request,
        "receta_form.html",
        {
            "mode": "new",
            "recipe": None,
            "action": "Nueva",
            "lines": [],
            "units": [u.value for u in Unit],
            "ingredients": ingredients,
            "other_recipes": other_recipes,
            "recipe_families": list_cats(session, "recipe_family"),
            "dietary_tags": list_tags_for_kind(session, "recipe"),
        },
    )


@router.post("/nueva")
async def recipe_create(
    request: Request, session: Session = Depends(get_session)
) -> RedirectResponse:
    """Create recipe + lines from form data."""
    form = await request.form()
    name = str(form.get("name", "")).strip()
    yield_qty_raw = str(form.get("yield_qty", "")).strip()
    yield_unit_raw = str(form.get("yield_unit", "und")).strip()
    notes = str(form.get("notes", "")).strip()
    prep_minutes_raw = str(form.get("prep_minutes", "")).strip()
    cook_minutes_raw = str(form.get("cook_minutes", "")).strip()
    family = str(form.get("family", "")).strip() or None
    dietary_tags = str(form.get("dietary_tags", "")).strip() or None

    if not name:
        raise HTTPException(status_code=400, detail="Nombre es obligatorio")

    try:
        y_unit = Unit.coerce(yield_unit_raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Unidad inválida: {e}") from e

    y_qty = float(yield_qty_raw) if yield_qty_raw else None
    prep_min = int(prep_minutes_raw) if prep_minutes_raw else None
    cook_min = int(cook_minutes_raw) if cook_minutes_raw else None

    # Wave 2 — auto-fill inference on recipe create.
    # Auto-fill family if operator left it blank.
    if not family:
        family = infer_recipe_family_from_name(name)

    recipe = Recipe(
        name=name,
        yield_qty=y_qty,
        yield_unit=y_unit.value,
        notes=notes or None,
        prep_minutes=prep_min,
        cook_minutes=cook_min,
        family=family,
        dietary_tags=dietary_tags,
    )
    session.add(recipe)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409, detail=f"Ya existe una receta con nombre {name!r}"
        ) from None

    skipped = _apply_lines_from_form(session, recipe.id, form)
    if skipped:
        # BUG-00: surface WHY a line was rejected instead of silently dropping it.
        # Roll back so the operator can fix and retry without orphans.
        session.rollback()
        from fastapi import HTTPException as _HTTPExc
        detail = "Algunas líneas no se pudieron guardar. " + "; ".join(skipped[:5])
        if len(skipped) > 5:
            detail += f" (y {len(skipped) - 5} más)"
        raise _HTTPExc(status_code=400, detail=detail)

    # If the user checked "create product from this recipe", redirect
    # to the crear-producto helper instead of /recetas.
    also_create = str(form.get("also_create_product", "")).strip() == "1"

    # Wave 2 — auto-fill dietary_tags from ingredient set + difficulty from
    # line count / sub_recipe depth. Operator can override on subsequent edits.
    try:
        session.refresh(recipe)
        inferred_tags = sorted(infer_recipe_dietary(session, recipe))
        if not dietary_tags:
            recipe.dietary_tags = ",".join(inferred_tags) if inferred_tags else None
        n_ing = recipe_ingredient_count(recipe)
        # Sub-recipe depth requires recursive walk; skip if deep.
        recipe.difficulty = infer_difficulty(recipe, n_ing, sub_recipe_depth=0)
        if not prep_min:
            recipe.prep_minutes = estimate_prep_minutes(recipe, n_ing)
        if not cook_min:
            recipe.cook_minutes = estimate_cook_minutes(recipe)
        session.commit()
    except Exception as exc:
        logger.warning("auto-fill inference failed for recipe %s: %s", recipe.id, exc)
        session.rollback()

    if also_create:
        return RedirectResponse(url=f"/recetas/{recipe.id}/crear-producto", status_code=303)
    return RedirectResponse(url="/recetas", status_code=303)


@router.get("/{r_id}/set-photo", response_class=HTMLResponse)
async def recipe_set_photo(
    request: Request,
    r_id: int,
    session: Session = Depends(get_session),
):
    """Show a picker of all photos in /static/recipes/."""
    from pathlib import Path
    photo_dir = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app/static/recipes")
    photos = sorted([p.name for p in photo_dir.glob("*.jpg")]) if photo_dir.is_dir() else []
    recipe = session.get(Recipe, r_id)
    return render(
        request,
        "recipe_photos.html",
        {"recipe": recipe, "photos": photos, "saved": False},
    )


@router.post("/{r_id}/set-photo")
async def recipe_save_photo(
    request: Request,
    r_id: int,
    photo: str = Form(...),
    session: Session = Depends(get_session),
):
    """Persist the recipe's image_url."""
    recipe = session.get(Recipe, r_id)
    if recipe:
        recipe.image_url = f"/static/recipes/{photo}"
        session.commit()
    return RedirectResponse(
        url=f"/recetas/{r_id}/set-photo?saved=1",
        status_code=303,
    )


@router.get("/{r_id}", response_class=HTMLResponse)
async def recipe_detail(
    r_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Read-only recipe detail with cost breakdown and used-by products."""
    r = session.get(Recipe, r_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    lines = session.scalars(
        select(RecipeLine).where(RecipeLine.recipe_id == r_id).order_by(RecipeLine.id)
    ).all()

    # Resolve line targets for display
    from app.rms.costing import resolve_line_target
    resolved_lines = []
    for ln in lines:
        target = resolve_line_target(session, ln)
        resolved_lines.append({
            "line": ln,
            "target": target,
            "target_name": target.name if target else f"#{ln.line_ref_id}",
            "is_ingredient": ln.line_kind == "ingredient",
        })

    # Cost breakdown
    from app.rms.costing import recipe_batch_cost_gs, recipe_unit_cost_gs
    batch_cost = recipe_batch_cost_gs(session, r_id)
    unit_cost = recipe_unit_cost_gs(session, r_id)

    # Used by products
    products_using = session.scalars(
        select(Product).where(Product.recipe_id == r_id)
    ).all()

    # Tags for this recipe
    from app.rms.models import TagLink
    tag_links = session.scalars(
        select(TagLink).where(
            TagLink.target_kind == "recipe",
            TagLink.target_id == r_id,
        )
    ).all()
    tag_ids = [tl.tag_id for tl in tag_links]
    tags = []
    if tag_ids:
        from app.rms.models import Tag
        tags = list(session.scalars(select(Tag).where(Tag.id.in_(tag_ids))))

    # Wave 3 — aggregate allergens from all ingredient lines so the recipe
    # detail page can show a "CONTIENE: gluten, dairy, eggs" summary required
    # by INAN Resolución S.G. N° 614/2023 for any retail food product.
    from app.rms.models import Ingredient as _Ingredient
    ingredient_refs = {
        ing.id: ing
        for ing in session.scalars(
            select(_Ingredient).where(
                _Ingredient.id.in_([
                    l.line_ref_id for l in r.lines if l.line_kind == "ingredient"
                ])
            )
        ).all()
    } if r.lines else {}
    aggregated_allergens: list[str] = []
    seen: set[str] = set()
    for line in r.lines:
        # Skip sub-recipe lines (need recursion) for v1 — fall back to direct
        # ingredient allergens. Future: walk RecipeLine.line_kind == "recipe".
        if line.line_kind != "ingredient":
            continue
        ing = ingredient_refs.get(line.line_ref_id)
        if not ing or not ing.allergens:
            continue
        for a in ing.allergens.split(","):
            a_clean = a.strip()
            if a_clean and a_clean not in seen:
                seen.add(a_clean)
                aggregated_allergens.append(a_clean)

    return render(request, "receta_detalle.html", {
        "recipe": r,
        "resolved_lines": resolved_lines,
        "batch_cost": batch_cost,
        "unit_cost": unit_cost,
        "products_using": [{"id": p.id, "name": p.name} for p in products_using],
        "tags": [{"id": t.id, "name": t.name, "color": t.color} for t in tags],
        "aggregated_allergens": aggregated_allergens,
    })


@router.get("/{r_id}/editar", response_class=HTMLResponse)
async def recipe_edit(
    r_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    r = session.get(Recipe, r_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    lines = session.scalars(
        select(RecipeLine).where(RecipeLine.recipe_id == r_id).order_by(RecipeLine.id)
    ).all()
    ingredients = session.scalars(select(Ingredient).order_by(Ingredient.name)).all()
    other_recipes = session.scalars(
        select(Recipe).where(Recipe.id != r_id).order_by(Recipe.name)
    ).all()

    # Cost breakdown for the recipe detail
    from app.rms.costing import recipe_batch_cost_gs, recipe_unit_cost_gs
    batch_cost = recipe_batch_cost_gs(session, r_id)
    unit_cost = recipe_unit_cost_gs(session, r_id)

    # Used by products
    products_using = session.scalars(
        select(Product).where(Product.recipe_id == r_id)
    ).all()

    # Yield scaling: if scale param is passed, compute scaled quantities
    scale = request.query_params.get("scale", "1")
    try:
        scale_factor = max(0.25, min(10.0, float(scale)))
    except ValueError:
        scale_factor = 1.0

    from app.rms.categories import list_categories as list_cats
    from app.rms.tags import list_tags_for_kind

    return render(
        request,
        "receta_form.html",
        {
            "mode": "edit",
            "recipe": r,
            "action": "Editar",
            "lines": lines,
            "units": [u.value for u in Unit],
            "ingredients": ingredients,
            "other_recipes": other_recipes,
            "batch_cost_gs": batch_cost.batch_cost_gs,
            "unit_cost_gs": unit_cost.batch_cost_gs if unit_cost else None,
            "products_using": [{"id": p.id, "name": p.name} for p in products_using],
            "scale_factor": scale_factor,
            "recipe_families": list_cats(session, "recipe_family"),
            "dietary_tags": list_tags_for_kind(session, "recipe"),
        },
    )


@router.post("/{r_id}/editar")
async def recipe_update(
    r_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    r = session.get(Recipe, r_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Receta no encontrada")

    form = await request.form()
    name = str(form.get("name", "")).strip()
    yield_qty_raw = str(form.get("yield_qty", "")).strip()
    yield_unit_raw = str(form.get("yield_unit", "und")).strip()
    notes = str(form.get("notes", "")).strip()
    prep_minutes_raw = str(form.get("prep_minutes", "")).strip()
    cook_minutes_raw = str(form.get("cook_minutes", "")).strip()
    family = str(form.get("family", "")).strip() or None
    dietary_tags = str(form.get("dietary_tags", "")).strip() or None

    if not name:
        raise HTTPException(status_code=400, detail="Nombre es obligatorio")
    try:
        y_unit = Unit.coerce(yield_unit_raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Unidad inválida: {e}") from e

    r.name = name
    r.yield_qty = float(yield_qty_raw) if yield_qty_raw else None
    r.yield_unit = y_unit.value
    r.notes = notes or None
    r.prep_minutes = int(prep_minutes_raw) if prep_minutes_raw else None
    r.cook_minutes = int(cook_minutes_raw) if cook_minutes_raw else None
    r.family = family
    r.dietary_tags = dietary_tags

    # Replace lines
    for old in list(r.lines):
        session.delete(old)
    session.flush()
    skipped = _apply_lines_from_form(session, r.id, form)
    if skipped:
        session.rollback()
        from fastapi import HTTPException as _HTTPExc
        detail = "Algunas líneas no se pudieron guardar. " + "; ".join(skipped[:5])
        if len(skipped) > 5:
            detail += f" (y {len(skipped) - 5} más)"
        raise _HTTPExc(status_code=400, detail=detail)
    session.commit()
    return RedirectResponse(url="/recetas", status_code=303)


@router.get("/{r_id}/crear-producto")
async def recipe_create_product_redirect(
    r_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Redirect to /productos/nuevo with query params pre-filled from this recipe.

    The product form reads these params on load and auto-fills:
      - name, recipe_id, category (from recipe.family), tags (from dietary_tags)
      - portion_label (from recipe yield_qty + yield_unit)
      - sale_price_gs (estimated from unit cost * 3 markup)
    """
    r = session.get(Recipe, r_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Receta no encontrada")

    # Compute suggested price: cost × SettingsKV-configured markup (default 3.0)
    from app.rms.costing import recipe_unit_cost_gs
    from app.rms.settings_runtime import get_pricing_markup, compute_suggested_price
    unit = recipe_unit_cost_gs(session, r_id)
    suggested_price = ""
    if unit.batch_cost_gs:
        markup_cfg = get_pricing_markup(session)
        suggested_price = str(compute_suggested_price(unit.batch_cost_gs, markup_cfg))

    # Suggested portion label
    portion_label = "1 unidad"
    if r.yield_qty:
        portion_label = f"1 {r.yield_unit or 'und'}"

    # Build query params (only include non-empty)
    params = {
        "recipe_id": str(r.id),
        "name": r.name,
        "category": r.family or "",
        "tags": r.dietary_tags or "",
        "portion_label": portion_label,
        "sale_price_gs": suggested_price,
    }
    qs = "&".join(f"{k}={v}" for k, v in params.items() if v)
    return RedirectResponse(url=f"/productos/nuevo?{qs}", status_code=303)


def _apply_lines_from_form(session: Session, recipe_id: int, form) -> list[str]:
    """Parse repeated form fields for recipe lines and persist them.

    Expected form keys (each repeated for N lines):
      line_kind (str: 'ingredient' or 'sub_recipe')
      line_target_id (str: integer ID as string)
      line_qty (str: float as string)
      line_unit (str: optional unit override)
      line_notes (str, optional)

    Lines with empty kind or target_id or qty <= 0 return their reason in the
    skipped list. The caller can choose to surface these as a Spanish 400 (so
    the operator knows WHY a line was ignored instead of silently dropping it).
    """
    skipped: list[str] = []
    kinds = form.getlist("line_kind")
    target_ids = form.getlist("line_target_id")
    qtys = form.getlist("line_qty")
    line_units = form.getlist("line_unit")
    notes_list = form.getlist("line_notes")

    n = max(len(kinds), len(target_ids), len(qtys), len(line_units))
    for i in range(n):
        kind = str(kinds[i]).strip() if i < len(kinds) else ""
        target = str(target_ids[i]).strip() if i < len(target_ids) else ""
        qty_raw = str(qtys[i]).strip() if i < len(qtys) else ""
        ln_unit_raw = str(line_units[i]).strip() if i < len(line_units) else ""
        ln_notes = str(notes_list[i]).strip() if i < len(notes_list) else ""

        if not kind or not target or not qty_raw:
            skipped.append(f"Línea {i + 1}: tipo, ingrediente o cantidad vacíos")
            continue
        try:
            qty = float(qty_raw)
            target_id = int(target)
        except ValueError:
            skipped.append(
                f"Línea {i + 1}: cantidad '{qty_raw}' o id '{target}' inválidos"
            )
            continue
        if qty <= 0:
            skipped.append(f"Línea {i + 1}: cantidad debe ser mayor a 0")
            continue
        if target_id <= 0:
            skipped.append(f"Línea {i + 1}: id de ingrediente inválido")
            continue

        # Validate the unit (if supplied) against the canonical enum.
        # On invalid value, fall back to empty string — the costing walk will
        # then default to the linked ingredient's unit (back-compat).
        line_unit_value = ""
        if ln_unit_raw:
            try:
                line_unit_value = Unit.coerce(ln_unit_raw).value
            except ValueError:
                line_unit_value = ""

        session.add(
            RecipeLine(
                recipe_id=recipe_id,
                line_kind=kind,
                line_ref_id=target_id,
                qty=qty,
                line_unit=line_unit_value,
                notes=ln_notes or None,
            )
        )

    return skipped


@router.get("/api/search", response_class=JSONResponse)
def recipe_search_api(
    q: str = Query("", description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Search recipes by name/description (case-insensitive).
    
    Used by the combo system on /merma form for recipe selection.
    """
    # Basic search by name
    query = (
        select(Recipe)
        .where(Recipe.name.ilike(f"%{q}%"))
        .order_by(Recipe.name)
        .limit(limit)
    )
    
    recipes = session.scalars(query).all()
    
    if not recipes:
        return JSONResponse({"results": [], "count": 0})
    
    # Format results for combo
    payload = []
    for r in recipes:
        payload.append({
            "id": r.id,
            "name": r.name,
            "yield_qty": r.yield_qty,
            "yield_unit": r.yield_unit,
        })
    
    return JSONResponse({
        "results": payload,
        "count": len(payload)
    })


@router.get("/api/units", response_class=JSONResponse)
def units_api() -> JSONResponse:
    """List all available units.
    
    Used by the combo system on /merma form for unit selection.
    """
    from app.rms.units import Unit
    
    payload = []
    for unit in Unit:
        payload.append({
            "value": unit.value,
            "display": unit.display,
        })
    
    return JSONResponse({
        "results": payload,
        "count": len(payload)
    })


__all__ = ["router"]
