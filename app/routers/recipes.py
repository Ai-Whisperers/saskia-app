"""app/routers/recipes.py — CRUD endpoints for recipes with polymorphic lines.

Per dev plan §9 Task 3 + v2 §5 (polymorphic recipe_line).

Note: repeated form fields (multiple line_kind / line_target_id / line_qty / line_notes
per row) require async parsing via `await request.form()` because FastAPI's Form()
only handles single values.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
)
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.costing import (
    CostResult,
    batch_recipes_cost,
)
from app.rms.dependencies import get_session
from app.rms.errors import BadRequest, Conflict, NotFound
from app.rms.messages import (
    RECIPE_CYCLE_DETECTED,
    RECIPE_DUPLICATE_NAME,
    RECIPE_INVALID_UNIT,
    RECIPE_LINES_REQUIRED,
    RECIPE_NAME_REQUIRED,
)
from app.rms.models import Ingredient, Product, Recipe, RecipeLine
from app.rms.observability import record_audit
from app.rms.rate_limit import read_rate_limit_dependency
from app.rms.recipe_intel import (
    estimate_cook_minutes,
    estimate_prep_minutes,
    infer_difficulty,
    infer_recipe_dietary,
    infer_recipe_family_from_name,
    recipe_ingredient_count,
)
from app.rms.units import Unit
from app.services.template_render import render

router = APIRouter(prefix="/recetas", dependencies=[Depends(require_login)])


def _format_total_minutes(total_minutes: int | None) -> str:
    """Format total minutes as 'Xh YYm' or 'Sin definir' if None."""
    if total_minutes is None:
        return "Sin definir"
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


def _decorate(
    session: Session, r: Recipe, batch: CostResult, unit: CostResult | None, line_count: int
) -> dict:
    """Compute batch + unit cost for a recipe row (data passed in from batch loader)."""
    total_minutes = (
        (r.prep_minutes or 0) + (r.cook_minutes or 0)
        if (r.prep_minutes or r.cook_minutes)
        else None
    )
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
        "total_minutes": total_minutes,
        "total_minutes_fmt": _format_total_minutes(total_minutes),
        "family": r.family,
        "dietary_tags": r.dietary_tags,
        # 2026-09-23 (US 1.1): recipe-photo button in /recetas list depends on
        # this key. Must be in the dict, not read from `r` directly in the
        # template, because `r` isn't passed to the template — only `recipes`
        # (a list of these dicts) is.
        "image_url": r.image_url,
        # 2026-09-29: template's Dificultad column renders r.difficulty, but
        # `recipes` is a list of these decorated dicts, not Recipe objects.
        # Without this key the cell renders "—" for every row.
        "difficulty": r.difficulty,
    }


@router.get("", response_class=HTMLResponse)
async def recipes_list(
    request: Request,
    q: str = Query("", description="Search by recipe name"),
    familia: str = Query("", description="Filter by recipe family (comma-separated, OR semantics)"),
    dificultad: str = Query(
        "", description="Filter by difficulty 1-5, comma-separated multi (P3 UX batch)"
    ),
    dieteticas: str = Query(
        "", description="Filter by dietary tags (comma-separated, AND semantics)"
    ),
    ingredient_id: str = Query("", description="Filter by single ingredient ID (legacy)"),
    ingredient_ids: str = Query(
        "",
        description="Filter by multiple ingredient IDs (comma-separated). US 3.2: AND semantics — recipe must use ALL selected.",
    ),
    sort: str = Query(
        "name",
        pattern="^(name|yield_qty|batch_cost_gs|unit_cost_gs|prep_minutes|cook_minutes|difficulty|line_count)$",
    ),
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
        except (TypeError, ValueError) as exc:
            # Bad URL param — skip this id but keep parsing the rest.
            logger.debug("recipes filter: bad ingredient_id: {}", exc)
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

    # P3 UX batch: multi-select popover posts repeated ?ingredient_multi=N
    # params — merge into the same AND-semantics id set.
    for raw in request.query_params.getlist("ingredient_multi"):
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
    familias_sel = [x.strip() for x in familia.split(",") if x.strip()]
    # Accept both ?dificultad=1&dificultad=3 (repeated) and ?dificultad=1,3
    dif_sel = [
        d.strip()
        for d in request.query_params.getlist("dificultad")
        for d in d.split(",")
        if d.strip()
    ]
    diet_sel = [x.strip() for x in dieteticas.split(",") if x.strip()]

    count_stmt = select(func.count(Recipe.id))
    if q:
        count_stmt = count_stmt.where(Recipe.name.ilike(f"%{q}%"))
    if familias_sel:
        # UI-V2: match legacy family OR the multi-select menu_tags column.
        from sqlalchemy import or_ as _or

        count_stmt = count_stmt.where(
            _or(
                Recipe.family.in_(familias_sel),
                *[Recipe.menu_tags.ilike(f"%{tag}%") for tag in familias_sel],
            )
        )
    if dif_sel:
        try:
            dif_ints = [int(d) for d in dif_sel]
            count_stmt = count_stmt.where(Recipe.difficulty.in_(dif_ints))
        except ValueError as exc:
            # Bad difficulty query param — just don't filter.
            logger.debug("recipes difficulty filter dropped: {}", exc)
    if diet_sel:
        for tag in diet_sel:
            count_stmt = count_stmt.where(Recipe.dietary_tags.ilike(f"%{tag}%"))
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
    if familias_sel:
        # UI-V2: match legacy family OR the multi-select menu_tags column.
        from sqlalchemy import or_ as _or

        stmt = stmt.where(
            _or(
                Recipe.family.in_(familias_sel),
                *[Recipe.menu_tags.ilike(f"%{tag}%") for tag in familias_sel],
            )
        )
    if dif_sel:
        try:
            stmt = stmt.where(Recipe.difficulty.in_([int(d) for d in dif_sel]))
        except ValueError as exc:
            # Bad difficulty query param — just don't filter.
            logger.debug("recipes difficulty filter dropped: {}", exc)
    if diet_sel:
        for tag in diet_sel:
            stmt = stmt.where(Recipe.dietary_tags.ilike(f"%{tag}%"))

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
    recipes = session.scalars(stmt.distinct().offset(offset).limit(page_size)).all()
    batch_results = batch_recipes_cost(session, list(recipes))
    decorated = [
        _decorate(
            session, r, batch_results[r.id][0], batch_results[r.id][1], batch_results[r.id][2]
        )
        for r in recipes
    ]

    # P3 UX batch: sort EVERY column in-memory after decoration — costs,
    # difficulty, prep/cook are computed values, not plain columns. The
    # SQL order_by above remains for name/yield (deterministic pagination);
    # this final pass re-orders the current page's rows by the chosen key.
    _sort_keys = {
        "name": lambda x: (x["name"] or "").lower(),
        "yield_qty": lambda x: x["yield_qty"] or 0,
        "batch_cost_gs": lambda x: x["batch_cost_gs"] or 0,
        "unit_cost_gs": lambda x: x["unit_cost_gs"] or 0,
        "prep_minutes": lambda x: x["prep_minutes"] or 0,
        "cook_minutes": lambda x: x["cook_minutes"] or 0,
        "difficulty": lambda x: x["difficulty"] or 0,
        "line_count": lambda x: x["line_count"] or 0,
    }
    if sort in _sort_keys:
        decorated.sort(key=_sort_keys[sort], reverse=(dir == "desc"))

    # Ingredient list for filter dropdown
    all_ingredients = session.scalars(select(Ingredient).order_by(Ingredient.name)).all()

    from app.rms.tagging.ensure import (
        list_tags_for_kind,  # canonical home (post-sense-dedup, 2026-10-09)
    )

    all_families = sorted(
        {
            f
            for (f,) in session.execute(
                select(Recipe.family).where(Recipe.family.is_not(None)).distinct()
            )
            if f
        }
    )
    all_tags = [t.name for t in list_tags_for_kind(session, "recipe")]
    total_all = session.scalar(select(func.count(Recipe.id))) or 0
    return render(
        request,
        "recetas.html",
        {
            "recipes": decorated,
            "q": q,
            "familias_sel": familias_sel,
            "dif_sel": dif_sel,
            "ing_multi_sel": [str(i) for i in ing_id_ints],
            "diet_sel": diet_sel,
            "all_families": all_families,
            "all_recipe_tags": all_tags,
            "total_all": total_all,
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
        },
    )


@router.get("/nueva", response_class=HTMLResponse)
async def recipe_new(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    """Show new-recipe form. Passes DB-driven catalogs:
    - recipe_families: rows from `category` WHERE scope='recipe_family'
    - dietary_tags: rows from `tag` WHERE kind='recipe'
    """
    ingredients = session.scalars(select(Ingredient).order_by(Ingredient.name)).all()
    # Variant-aware price so JS live cost matches server-side batch/unit
    # totals. preferred_price_gs is what the costing walk uses via
    # current_variant_price() — see app/rms/variants.py.
    from app.rms.variants import current_variant_price as _cvp_new

    for _ing in ingredients:
        _vp = _cvp_new(session, _ing.id)
        _ing.preferred_price_gs = int(_vp) if _vp else (_ing.purchase_price_gs or 0)
    from app.rms.categories import list_categories as list_cats
    from app.rms.tagging import list_tags_for_kind

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
            "menu_tag_options": sorted(
                {
                    t.strip()
                    for r_row in session.scalars(select(Recipe.menu_tags)).all()
                    if r_row
                    for t in r_row.split(",")
                    if t.strip()
                }
                | {r_row for r_row in session.scalars(select(Recipe.family)).all() if r_row}
            ),
        },
    )


@router.post("/nueva")
async def recipe_create(
    request: Request, session: Session = Depends(get_session)
) -> RedirectResponse:
    """Create recipe + lines from form data."""
    form = await request.form()

    # Parse and validate form fields
    fields = _parse_recipe_form(form)

    # Validate required fields
    if not fields["name"]:
        raise BadRequest(RECIPE_NAME_REQUIRED)

    # Auto-fill family if blank
    if not fields["family"]:
        fields["family"] = infer_recipe_family_from_name(fields["name"])

    # Create the recipe
    recipe = _create_recipe_record(session, fields)

    # Apply lines from form
    skipped = _apply_lines_from_form(session, recipe.id, form)

    # Validate lines
    _validate_recipe_lines(session, form, skipped, recipe)

    # Check for sub-recipe cycles
    _check_recipe_cycles(session, recipe.id)

    # Auto-fill inference (dietary tags, difficulty, prep/cook minutes)
    _apply_recipe_inference(session, recipe, fields)

    # Refresh tag algebra cache
    _refresh_recipe_tag_cache(session, recipe.id)

    # Redirect logic
    also_create = str(form.get("also_create_product", "")).strip() == "1"
    if also_create:
        return RedirectResponse(url=f"/productos/nuevo?recipe_id={recipe.id}", status_code=303)
    return RedirectResponse(url="/recetas", status_code=303)


def _parse_recipe_form(form: dict) -> dict:
    """Parse recipe form data into a structured dict.

    Extracted from recipe_create to reduce complexity.
    """
    name = str(form.get("name", "")).strip()
    yield_qty_raw = str(form.get("yield_qty", "")).strip()
    yield_unit_raw = str(form.get("yield_unit", "und")).strip()
    notes = str(form.get("notes", "")).strip()
    prep_minutes_raw = str(form.get("prep_minutes", "")).strip()
    cook_minutes_raw = str(form.get("cook_minutes", "")).strip()
    difficulty_raw = str(form.get("difficulty", "")).strip()

    # Validate yield unit
    try:
        y_unit = Unit.coerce(yield_unit_raw)
    except ValueError as e:
        raise BadRequest(RECIPE_INVALID_UNIT, context={"original_error": str(e)}) from e

    # Parse difficulty (1-5)
    difficulty_val: int | None = None
    if difficulty_raw:
        try:
            difficulty_val = max(1, min(5, int(difficulty_raw)))
        except ValueError:
            difficulty_val = None

    # Parse menu tags (multi-select)
    menu_tags_vals = list(form.getlist("menu_tag")) + [
        t.strip() for t in str(form.get("menu_tags", "")).split(",") if t.strip()
    ]
    menu_tags = ",".join(dict.fromkeys(menu_tags_vals)) or None

    return {
        "name": name,
        "yield_qty": float(yield_qty_raw) if yield_qty_raw else None,
        "yield_unit": y_unit.value,
        "notes": notes or None,
        "prep_minutes": int(prep_minutes_raw) if prep_minutes_raw else None,
        "cook_minutes": int(cook_minutes_raw) if cook_minutes_raw else None,
        "difficulty_val": difficulty_val,
        "family": str(form.get("family", "")).strip() or None,
        "menu_tags": menu_tags,
        "dietary_tags": str(form.get("dietary_tags", "")).strip() or None,
    }


def _create_recipe_record(session: Session, fields: dict) -> Recipe:
    """Create a Recipe record and commit it.

    Extracted from recipe_create to reduce complexity.
    """
    recipe = Recipe(
        name=fields["name"],
        yield_qty=fields["yield_qty"],
        yield_unit=fields["yield_unit"],
        notes=fields["notes"],
        prep_minutes=fields["prep_minutes"],
        cook_minutes=fields["cook_minutes"],
        family=fields["family"],
        menu_tags=fields["menu_tags"],
        dietary_tags=fields["dietary_tags"],
    )
    session.add(recipe)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise Conflict(
            RECIPE_DUPLICATE_NAME,
            context={"name": fields["name"]},
        ) from None
    return recipe


def _validate_recipe_lines(session: Session, form: dict, skipped: list, recipe: Recipe) -> None:
    """Validate that at least one valid line exists.

    Raises HTTPException if validation fails.
    Extracted from recipe_create to reduce complexity.
    """
    valid_line_count = _count_valid_lines(form)

    if valid_line_count == 0:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail=RECIPE_LINES_REQUIRED,
        )

    if skipped:
        # BUG-00: surface WHY a line was rejected instead of silently dropping it.
        # Roll back so the operator can fix and retry without orphans.
        session.rollback()
        from fastapi import HTTPException as _HTTPExc

        detail = "Algunas líneas no se pudieron guardar. " + "; ".join(skipped[:5])
        if len(skipped) > 5:
            detail += f" (y {len(skipped) - 5} más)"
        raise _HTTPExc(status_code=400, detail=detail)


def _count_valid_lines(form: dict) -> int:
    """Count valid recipe lines from form data.

    Extracted from recipe_create to reduce complexity.
    """
    valid_line_count = 0
    for i, kind in enumerate(form.getlist("line_kind")):
        target = (
            form.getlist("line_target_id")[i] if i < len(form.getlist("line_target_id")) else ""
        )
        qty_raw = form.getlist("line_qty")[i] if i < len(form.getlist("line_qty")) else ""
        try:
            if str(kind).strip() and str(target).strip() and float(str(qty_raw).strip()) > 0:
                valid_line_count += 1
        except (ValueError, IndexError):
            continue
    return valid_line_count


def _check_recipe_cycles(session: Session, recipe_id: int) -> None:
    """Check for sub-recipe cycles and raise if detected.

    Extracted from recipe_create to reduce complexity.
    """
    cycle = _detect_sub_recipe_cycle(session, recipe_id)
    if cycle:
        session.rollback()
        session.execute(select(Recipe.name).where(Recipe.id.in_(cycle))).scalars().all()
        raise HTTPException(
            status_code=400,
            detail=RECIPE_CYCLE_DETECTED,
        )


def _apply_recipe_inference(session: Session, recipe: Recipe, fields: dict) -> None:
    """Apply auto-fill inference: dietary tags, difficulty, prep/cook minutes.

    Extracted from recipe_create to reduce complexity.
    """
    try:
        session.refresh(recipe)
        inferred_tags = sorted(infer_recipe_dietary(session, recipe))
        if not fields["dietary_tags"]:
            recipe.dietary_tags = ",".join(inferred_tags) if inferred_tags else None
        n_ing = recipe_ingredient_count(recipe)
        # Sub-recipe depth requires recursive walk; skip if deep.
        if fields["difficulty_val"] is None:
            # auto-infer only when the operator didn't type one (1-5)
            recipe.difficulty = infer_difficulty(recipe, n_ing, sub_recipe_depth=0)
        else:
            recipe.difficulty = fields["difficulty_val"]
        if not fields["prep_minutes"]:
            recipe.prep_minutes = estimate_prep_minutes(recipe, n_ing)
        if not fields["cook_minutes"]:
            recipe.cook_minutes = estimate_cook_minutes(recipe)
        session.commit()
    except Exception as exc:
        logger.warning("auto-fill inference failed for recipe %s: %s", recipe.id, exc)
        session.rollback()


def _refresh_recipe_tag_cache(session: Session, recipe_id: int) -> None:
    """Refresh tag algebra cache for the recipe and cascade to parents.

    Extracted from recipe_create to reduce complexity.
    """
    try:
        from app.rms.tag_algebra import _product_inherit_sync, cascade_refresh

        cascade_refresh(session, recipe_id=recipe_id)
        _product_inherit_sync(session, recipe_id)
        session.commit()
    except Exception as exc:
        logger.warning("tag algebra refresh failed for recipe %s: %s", recipe_id, exc)
        session.rollback()
    return RedirectResponse(url="/recetas", status_code=303)


@router.get("/{r_id}/set-photo", response_class=HTMLResponse)
async def recipe_set_photo(
    request: Request,
    r_id: int,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Show a picker of all photos in /static/recipes/."""

    from app.rms import static_paths

    photo_dir = static_paths.recipes_dir()
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
) -> RedirectResponse:
    """Persist the recipe's image_url."""
    recipe = session.get(Recipe, r_id)
    if recipe:
        recipe.image_url = f"/static/recipes/{photo}"
        record_audit(
            request,
            session=session,
            action="write.recipe.photo.upload",
            target_type="recipe",
            target_id=r_id,
            detail={"filename": photo},
        )
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
        raise NotFound("receta")

    resolved_lines = _load_resolved_lines(session, r_id)
    batch_cost, unit_cost = _load_costs(session, r_id)
    products_using = _load_products_using(session, r_id)
    tags = _load_recipe_tags(session, r_id)
    aggregated_allergens = _aggregate_allergens(session, r)
    vista, consolidated_lines = _resolve_vista(session, request, r_id)
    recipe_phases = _parse_recipe_phases(r)

    return render(
        request,
        "receta_detalle.html",
        {
            "recipe": r,
            "recipe_phases": recipe_phases,
            "tag_derivation": _derive_recipe_tags(session, r_id),
            "vista": vista,
            "consolidated_lines": consolidated_lines,
            "derived_tags": [t for t in (r.derived_dietary_tags or "").split(",") if t],
            "resolved_lines": resolved_lines,
            "batch_cost": batch_cost,
            "unit_cost": unit_cost,
            "products_using": [{"id": p.id, "name": p.name} for p in products_using],
            "tags": [{"id": t.id, "name": t.name, "color": t.color} for t in tags],
            "aggregated_allergens": aggregated_allergens,
        },
    )


def _load_resolved_lines(session, r_id: int) -> list:
    """Load recipe lines with resolved target info.

    Extracted from recipe_detail to reduce complexity.
    """
    from app.rms.costing import resolve_line_target

    lines = session.scalars(
        select(RecipeLine).where(RecipeLine.recipe_id == r_id).order_by(RecipeLine.id)
    ).all()
    resolved = []
    for ln in lines:
        target = resolve_line_target(session, ln)
        resolved.append(
            {
                "line": ln,
                "target": target,
                "target_name": target.name if target else f"#{ln.line_ref_id}",
                "is_ingredient": ln.line_kind == "ingredient",
            }
        )
    return resolved


def _load_costs(session, r_id: int) -> tuple:
    """Load batch and unit costs for a recipe.

    Extracted from recipe_detail to reduce complexity.
    """
    from app.rms.costing import recipe_batch_cost_gs, recipe_unit_cost_gs

    return recipe_batch_cost_gs(session, r_id), recipe_unit_cost_gs(session, r_id)


def _load_products_using(session, r_id: int) -> list:
    """Load products that use this recipe.

    Extracted from recipe_detail to reduce complexity.
    """
    return list(session.scalars(select(Product).where(Product.recipe_id == r_id)).all())


def _load_recipe_tags(session, r_id: int) -> list:
    """Load tags associated with this recipe.

    Extracted from recipe_detail to reduce complexity.
    """
    from app.rms.models import Tag, TagLink

    tag_links = session.scalars(
        select(TagLink).where(
            TagLink.target_kind == "recipe",
            TagLink.target_id == r_id,
        )
    ).all()
    if not tag_links:
        return []
    tag_ids = [tl.tag_id for tl in tag_links]
    return list(session.scalars(select(Tag).where(Tag.id.in_(tag_ids))))


def _aggregate_allergens(session, r: Recipe) -> list:
    """Aggregate allergens from all ingredient lines.

    Wave 3 — aggregate allergens from all ingredient lines so the recipe
    detail page can show a "CONTIENE: gluten, dairy, eggs" summary required
    by INAN Resolución S.G. N° 614/2023 for any retail food product.

    Extracted from recipe_detail to reduce complexity.
    """
    if not r.lines:
        return []
    ingredient_refs = _load_ingredient_refs(session, r.lines)
    return _collect_aggregated_allergens(r.lines, ingredient_refs)


def _load_ingredient_refs(session, lines) -> dict:
    """Load ingredient references for recipe lines.

    Extracted from _aggregate_allergens to reduce complexity.
    """
    from app.rms.models import Ingredient as _Ingredient

    ingredient_line_ids = [ln.line_ref_id for ln in lines if ln.line_kind == "ingredient"]
    if not ingredient_line_ids:
        return {}
    return {
        ing.id: ing
        for ing in session.scalars(
            select(_Ingredient).where(_Ingredient.id.in_(ingredient_line_ids))
        ).all()
    }


def _collect_aggregated_allergens(lines, ingredient_refs: dict) -> list:
    """Collect aggregated allergens from ingredient lines.

    Extracted from _aggregate_allergens to reduce complexity.
    """
    aggregated: list[str] = []
    seen: set[str] = set()
    for line in lines:
        for allergen in _extract_line_allergens(line, ingredient_refs):
            if allergen not in seen:
                seen.add(allergen)
                aggregated.append(allergen)
    return aggregated


def _extract_line_allergens(line, ingredient_refs: dict) -> list:
    """Extract allergens from a single recipe line.

    Extracted from _collect_aggregated_allergens to reduce complexity.
    """
    if line.line_kind != "ingredient":
        return []
    ing = ingredient_refs.get(line.line_ref_id)
    if not ing or not ing.allergens:
        return []
    return [a.strip() for a in ing.allergens.split(",") if a.strip()]


def _resolve_vista(session, request: Request, r_id: int) -> tuple:
    """Resolve the vista (estructural/consolidada) and load consolidated lines.

    UI-V2 dual view: ?vista=estructural (default, assembly) vs
    ?vista=consolidada (exploded purchase list). Both computed here;
    the template toggles which table renders.
    Extracted from recipe_detail to reduce complexity.
    """
    from app.rms.recipes_consolidated import explode_recipe

    vista = (request.query_params.get("vista") or "estructural").lower()
    if vista not in ("estructural", "consolidada"):
        vista = "estructural"
    consolidated_lines = explode_recipe(session, r_id) if vista == "consolidada" else []
    return vista, consolidated_lines


def _parse_recipe_phases(r: Recipe):
    """Parse instructions JSON for template.

    Extracted from recipe_detail to reduce complexity.
    """
    if not r.instructions:
        return None
    import json as _json
    try:
        return _json.loads(r.instructions)
    except Exception:
        return None


def _derive_recipe_tags(session, r_id: int):
    """Derive tags for a recipe.

    Extracted from recipe_detail to reduce complexity.
    """
    from app.rms.tag_algebra import derive_recipe_tags as _derive_tags
    return _derive_tags(session, r_id)


@router.get("/{r_id}/editar", response_class=HTMLResponse)
async def recipe_edit(
    r_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    r = session.get(Recipe, r_id)
    if r is None:
        raise NotFound("receta")

    # Load and decorate recipe lines
    lines = _load_recipe_lines_with_costs(session, r_id)

    # Load ingredients with variant-aware prices
    ingredients = _load_ingredients_with_prices(session)

    # Load other recipes (for sub-recipe dropdown)
    other_recipes = _load_other_recipes(session, r_id)

    # Load cost breakdown
    from app.rms.costing import recipe_batch_cost_gs, recipe_unit_cost_gs

    batch_cost = recipe_batch_cost_gs(session, r_id)
    unit_cost = recipe_unit_cost_gs(session, r_id)

    # Load products using this recipe
    products_using = session.scalars(select(Product).where(Product.recipe_id == r_id)).all()

    # Parse scale factor from query params
    scale_factor = _parse_scale_factor(request)

    return render(
        request,
        "receta_form.html",
        _build_recipe_edit_context(
            r,
            lines,
            ingredients,
            other_recipes,
            batch_cost,
            unit_cost,
            products_using,
            scale_factor,
        ),
    )


def _load_recipe_lines_with_costs(session: Session, r_id: int) -> list[dict]:
    """Load recipe lines with variant-aware costs and target names.

    Extracted from recipe_edit to reduce complexity.
    """
    raw_lines = session.scalars(
        select(RecipeLine).where(RecipeLine.recipe_id == r_id).order_by(RecipeLine.id)
    ).all()

    from app.rms.costing import resolve_line_target
    from app.rms.variants import current_variant_price

    # Unit conversion factors for same-family normalization
    _UF = {"g": 1, "kg": 1000, "ml": 1, "l": 1000, "und": 1, "u": 1, "porcion": 1}

    lines = []
    for ln in raw_lines:
        target = resolve_line_target(session, ln)
        lines.append(
            {
                "id": ln.id,
                "line_kind": ln.line_kind,
                "line_ref_id": ln.line_ref_id,
                "qty": ln.qty,
                "line_unit": ln.line_unit,
                "note": ln.notes,
                "target_name": target.name if target else f"#{ln.line_ref_id}",
                "target_unit": target.unit if target and hasattr(target, "unit") else ln.line_unit,
                # cost_per_kg_gs: the ingredient's variant-aware purchase price per kg — what JS multiplies by qty_norm
                # Use current_variant_price so it matches the line cost above AND the
                # recipe_batch_cost_gs() walk in app/rms/costing.py.
                "price_per_kg_gs": _variant_price_for_line(
                    session, target, ln, current_variant_price
                ),
                # unit_cost_gs: the normalized line total cost = qty_in_kg × price_per_kg_gs
                "unit_cost_gs": _line_cost(ln, target, session, current_variant_price, _UF),
            }
        )
    return lines


def _variant_price_for_line(
    sess: Session, tgt: object, ln: RecipeLine, current_variant_price: int
) -> int:
    """Variant-aware ingredient price for a recipe line. Falls back to
    parent purchase_price_gs when no variants exist (backward compat).
    Returns 0 for sub-recipe lines or missing targets.

    Extracted from recipe_edit to reduce complexity.
    """
    if tgt is None or ln.line_kind != "ingredient":
        return 0
    price = current_variant_price(sess, tgt.id)
    return int(price) if price else 0


def _line_cost(
    ln: RecipeLine, target: object, session: Session, current_variant_price: int, _UF: dict
) -> int:
    """Compute Gs. cost for a recipe line, or 0 if price unavailable.

    Uses current_variant_price() so the displayed cost matches what
    recipe_batch_cost_gs() computes server-side.

    Extracted from recipe_edit to reduce complexity.
    """
    if target is None or ln.line_kind != "ingredient":
        return 0
    # Look up the variant-aware price; falls back to parent
    # purchase_price_gs when no variants exist (backward compatible).
    price = current_variant_price(session, target.id) or 0
    if price == 0:
        return 0
    lu = ln.line_unit or "und"
    tu = getattr(target, "unit", "und")
    lf = _UF.get(lu, 1)
    tf = _UF.get(tu, 1)
    # Same family: weight (g/kg) or volume (ml/l) — normalize
    if lf != 1 and tf != 1 and (lu in ("und", "u", "porcion")) == (tu in ("und", "u", "porcion")):
        qty_norm = ln.qty * lf / tf
    else:
        qty_norm = ln.qty
    return int(qty_norm * price)


def _load_ingredients_with_prices(session: Session) -> list[Ingredient]:
    """Load all ingredients with variant-aware preferred prices attached.

    Extracted from recipe_edit to reduce complexity.
    """
    from app.rms.variants import current_variant_price as _cvp

    ingredients = session.scalars(select(Ingredient).order_by(Ingredient.name)).all()
    for _ing in ingredients:
        _vp = _cvp(session, _ing.id)
        _ing.preferred_price_gs = int(_vp) if _vp else (_ing.purchase_price_gs or 0)
    return ingredients


def _load_other_recipes(session: Session, r_id: int) -> list[Recipe]:
    """Load all recipes except the current one (for sub-recipe dropdown).

    Extracted from recipe_edit to reduce complexity.
    """
    return session.scalars(select(Recipe).where(Recipe.id != r_id).order_by(Recipe.name)).all()


def _parse_scale_factor(request: Request) -> float:
    """Parse scale factor from query params, clamped to [0.25, 10.0].

    Extracted from recipe_edit to reduce complexity.
    """
    scale = request.query_params.get("scale", "1")
    try:
        return max(0.25, min(10.0, float(scale)))
    except ValueError:
        return 1.0


def _build_recipe_edit_context(
    r: Recipe,
    lines: list[dict],
    ingredients: list[Ingredient],
    other_recipes: list[Recipe],
    batch_cost: object,
    unit_cost: object,
    products_using: list[Product],
    scale_factor: float,
) -> dict:
    """Build the template context for the recipe edit form.

    Extracted from recipe_edit to reduce complexity.
    """
    from app.rms.categories import list_categories as list_cats
    from app.rms.tagging import list_tags_for_kind

    return {
        "mode": "edit",
        "recipe": r,
        "action": f"/recetas/{r.id}",
        "lines": lines,
        "ingredients": ingredients,
        "other_recipes": other_recipes,
        "batch_cost": batch_cost,
        "unit_cost": unit_cost,
        "products_using": products_using,
        "scale_factor": scale_factor,
        "categories": list_cats(),
        "all_tags": list_tags_for_kind("recipe"),
    }


@router.post("/{r_id}/editar")
async def recipe_update(
    r_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    r = session.get(Recipe, r_id)
    if r is None:
        raise NotFound("receta")

    form = await request.form()

    # Parse and validate form fields
    fields = _parse_recipe_form(form)

    if not fields["name"]:
        raise BadRequest(RECIPE_NAME_REQUIRED)

    # Update recipe fields
    _update_recipe_fields(r, fields)

    # Replace lines
    for old in list(r.lines):
        session.delete(old)
    session.flush()

    # Apply new lines from form
    skipped = _apply_lines_from_form(session, r.id, form)

    # Validate lines
    _validate_recipe_lines(session, form, skipped, r)

    # Check for sub-recipe cycles
    _check_recipe_cycles(session, r.id)

    # Refresh tag algebra cache
    _refresh_recipe_tag_cache_update(session, r.id)

    # Record audit log
    _record_recipe_update_audit(request, session, r, fields["name"])

    return RedirectResponse(url="/recetas", status_code=303)


def _update_recipe_fields(r: Recipe, fields: dict) -> None:
    """Update recipe fields from parsed form data.

    Extracted from recipe_update to reduce complexity.
    """
    r.name = fields["name"]
    r.yield_qty = fields["yield_qty"]
    r.yield_unit = fields["yield_unit"]
    r.notes = fields["notes"]
    r.prep_minutes = fields["prep_minutes"]
    r.cook_minutes = fields["cook_minutes"]
    r.difficulty = fields["difficulty_val"]
    r.family = fields["family"]
    r.menu_tags = fields["menu_tags"]
    r.dietary_tags = fields["dietary_tags"]


def _refresh_recipe_tag_cache_update(session: Session, recipe_id: int) -> None:
    """Refresh tag algebra cache for the recipe and cascade to parents.

    Extracted from recipe_update to reduce complexity.
    """
    try:
        from app.rms.tag_algebra import _product_inherit_sync, cascade_refresh

        refreshed = cascade_refresh(session, recipe_id=recipe_id)
        for rid in refreshed:
            _product_inherit_sync(session, rid)
        session.commit()
    except Exception as exc:
        logger.warning("tag cascade failed for recipe %s: %s", recipe_id, exc)
        session.rollback()


def _record_recipe_update_audit(
    request: Request,
    session: Session,
    r: Recipe,
    name: str,
) -> None:
    """Record audit log entry for recipe update.

    Extracted from recipe_update to reduce complexity.
    """
    line_count = (
        session.scalar(select(func.count(RecipeLine.id)).where(RecipeLine.recipe_id == r.id)) or 0
    )
    record_audit(
        request,
        session=session,
        action="write.recipe.update",
        target_type="recipe",
        target_id=r.id,
        detail={"name": name, "lines_count": int(line_count)},
    )
    session.commit()


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
        raise NotFound("receta")

    # Compute suggested price: cost × SettingsKV-configured markup (default 3.0)
    from app.rms.costing import recipe_unit_cost_gs
    from app.rms.settings_runtime import compute_suggested_price, get_pricing_markup

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


def _apply_lines_from_form(session: Session, recipe_id: int, form: "object") -> list[str]:
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
    form_fields = _extract_line_form_fields(form)
    n = _max_line_count(form_fields)
    skipped: list[str] = []
    for i in range(n):
        line_data = _extract_line_data(form_fields, i)
        skip_reason = _validate_line_data(line_data, i)
        if skip_reason:
            skipped.append(skip_reason)
            continue
        _add_recipe_line(session, recipe_id, line_data)
    return skipped


def _extract_line_form_fields(form) -> dict:
    """Extract repeated form fields for recipe lines.
    
    Extracted from _apply_lines_from_form to reduce complexity.
    """
    return {
        "kinds": form.getlist("line_kind"),
        "target_ids": form.getlist("line_target_id"),
        "qtys": form.getlist("line_qty"),
        "line_units": form.getlist("line_unit"),
        "notes_list": form.getlist("line_notes"),
    }


def _max_line_count(form_fields: dict) -> int:
    """Get the maximum count of any form field.
    
    Extracted from _apply_lines_from_form to reduce complexity.
    """
    return max(
        len(form_fields["kinds"]),
        len(form_fields["target_ids"]),
        len(form_fields["qtys"]),
        len(form_fields["line_units"]),
    )


def _extract_line_data(form_fields: dict, i: int) -> dict:
    """Extract data for a single line from the form fields.
    
    Extracted from _apply_lines_from_form to reduce complexity.
    """
    return {
        "kind": _get_field(form_fields["kinds"], i),
        "target": _get_field(form_fields["target_ids"], i),
        "qty_raw": _get_field(form_fields["qtys"], i),
        "ln_unit_raw": _get_field(form_fields["line_units"], i),
        "ln_notes": _get_field(form_fields["notes_list"], i),
    }


def _get_field(field_list: list, i: int) -> str:
    """Get a field value at index i, or empty string if not present.
    
    Extracted from _extract_line_data to reduce complexity.
    """
    if i < len(field_list):
        return str(field_list[i]).strip()
    return ""


def _validate_line_data(line_data: dict, i: int) -> str | None:
    """Validate line data and return a skip reason if invalid.
    
    Extracted from _apply_lines_from_form to reduce complexity.
    """
    kind = line_data["kind"]
    target = line_data["target"]
    qty_raw = line_data["qty_raw"]

    if not kind or not target or not qty_raw:
        return f"Línea {i + 1}: tipo, ingrediente o cantidad vacíos"
    try:
        qty = float(qty_raw)
        target_id = int(target)
    except ValueError:
        return f"Línea {i + 1}: cantidad '{qty_raw}' o id '{target}' inválidos"
    if qty <= 0:
        return f"Línea {i + 1}: cantidad debe ser mayor a 0"
    if target_id <= 0:
        return f"Línea {i + 1}: id de ingrediente inválido"

    # Store parsed values for later use
    line_data["qty"] = qty
    line_data["target_id"] = target_id
    return None


def _add_recipe_line(session: Session, recipe_id: int, line_data: dict) -> None:
    """Add a RecipeLine to the session.
    
    Extracted from _apply_lines_from_form to reduce complexity.
    """
    line_unit_value = _coerce_line_unit(line_data["ln_unit_raw"])
    session.add(
        RecipeLine(
            recipe_id=recipe_id,
            line_kind=line_data["kind"],
            line_ref_id=line_data["target_id"],
            qty=line_data["qty"],
            line_unit=line_unit_value,
            notes=line_data["ln_notes"] or None,
        )
    )


def _coerce_line_unit(ln_unit_raw: str) -> str:
    """Coerce a line unit string to its canonical enum value.
    
    On invalid value, fall back to empty string — the costing walk will
    then default to the linked ingredient's unit (back-compat).
    Extracted from _add_recipe_line to reduce complexity.
    """
    if not ln_unit_raw:
        return ""
    try:
        return Unit.coerce(ln_unit_raw).value
    except ValueError:
        return ""


def _detect_sub_recipe_cycle(
    session: Session,
    recipe_id: int,
    visited: set[int] | None = None,
) -> list[int]:
    """Return list of recipe IDs that participate in a cycle starting from recipe_id.

    Walks sub_recipe lines recursively.  If a sub-recipe transitively references
    back to `recipe_id` (or any ancestor in `visited`), a cycle exists.

    Returns the cycle path as a list of recipe IDs, or [] if no cycle.
    """
    if visited is None:
        visited = set()
    if recipe_id in visited:
        return list(visited)
    visited.add(recipe_id)

    # Get all sub-recipe lines for this recipe
    sub_lines = session.scalars(
        select(RecipeLine).where(
            RecipeLine.recipe_id == recipe_id,
            RecipeLine.line_kind == "sub_recipe",
        )
    ).all()

    for line in sub_lines:
        sub_recipe_id = line.line_ref_id
        # Direct self-reference
        if sub_recipe_id == recipe_id:
            return [recipe_id]
        # Check recursively
        cycle = _detect_sub_recipe_cycle(session, sub_recipe_id, visited.copy())
        if cycle:
            return cycle

    return []


@router.get("/api/{recipe_id}/effective-ingredients", response_class=JSONResponse)
def recipe_effective_ingredients(
    recipe_id: int,
    session: Session = Depends(get_session),
) -> JSONResponse:
    """P3: exploded raw-ingredient list for the recipe FORM.

    The form shows each sub-recipe's contributed ingredients as gray,
    read-only rows beneath the line table so the operator sees the
    COMPLETE ingredient list without leaving the editor. Duplicates that
    got merged arrive as one row with merged_count > 1.
    """
    from app.rms.recipes_consolidated import explode_recipe

    lines = explode_recipe(session, recipe_id)
    return JSONResponse(
        {
            "lines": [
                {
                    "ingredient_id": ln.ingredient_id,
                    "name": ln.name,
                    "unit": ln.unit,
                    "qty": round(ln.qty, 3),
                    "sources": ln.sources,
                    "merged_count": ln.merged_count,
                    "error": ln.error,
                }
                for ln in lines
            ]
        }
    )


@router.get(
    "/api/search",
    response_class=JSONResponse,
    dependencies=[Depends(read_rate_limit_dependency(60, route_tag="api.search.recipes"))],
)
def recipe_search_api(
    q: str = Query("", description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Search recipes by name/description (case-insensitive).

    Used by the combo system on /merma form for recipe selection.

    BACKLOG #10: rate-limited at 60 reads/minute/IP via the
    `read_rate_limit_dependency`.

    Phase 20: returns `image_url` + `batches_today` (count of completed
    batches today) + `portions_today` (batches × yield_qty) so the
    cashier can see the merma impact in the picker dropdown.
    """
    from datetime import datetime, timezone

    from sqlalchemy import bindparam as sa_bindparam
    from sqlalchemy import text as sa_text

    # Basic search by name
    query = select(Recipe).where(Recipe.name.ilike(f"%{q}%")).order_by(Recipe.name).limit(limit)

    recipes = session.scalars(query).all()

    if not recipes:
        return JSONResponse({"results": [], "count": 0})

    # Bulk-fetch today's completed batches per recipe.
    # ProductionCompletion is keyed by product_id, not recipe_id —
    # join via product.recipe_id to aggregate per recipe.
    # Use raw SQL to avoid the broken ProductionCompletion<->Recipe mapper.
    recipe_ids = [r.id for r in recipes]
    batches_today_map: dict[int, float] = {}
    try:
        today_start = datetime.now(timezone.utc).date()
        rows = session.execute(
            sa_text(
                "SELECT p.recipe_id, SUM(pc.completed_qty) AS total "
                "FROM production_completion pc "
                "JOIN product p ON p.id = pc.product_id "
                "WHERE p.recipe_id IN :ids AND pc.for_date = :today "
                "GROUP BY p.recipe_id"
            ).bindparams(sa_bindparam("ids", expanding=True)),
            {"ids": recipe_ids, "today": today_start},
        ).fetchall()
        batches_today_map = {rid: float(total or 0) for rid, total in rows}
    except Exception as exc:  # Table may not exist in some test DBs; default to empty
        logger.warning("batches_today lookup failed, defaulting to empty: {!r}", exc)
        batches_today_map = {}

    # Format results for combo
    payload = [
        {
            "id": r.id,
            "name": r.name,
            "yield_qty": r.yield_qty,
            "yield_unit": r.yield_unit,
            "image_url": r.image_url or "",
            "batches_today": batches_today_map.get(r.id, 0.0),
            "portions_today": ((batches_today_map.get(r.id, 0.0) or 0.0) * (r.yield_qty or 0.0)),
        }
        for r in recipes
    ]

    return JSONResponse({"results": payload, "count": len(payload)})


@router.get("/api/units", response_class=JSONResponse)
def units_api() -> JSONResponse:
    """List all available units.

    Used by the combo system on /merma form for unit selection.
    """
    from app.rms.units import Unit

    payload = [
        {
            "value": unit.value,
            "display": unit.display,
        }
        for unit in Unit
    ]

    return JSONResponse({"results": payload, "count": len(payload)})


@router.get("/api/families", response_class=JSONResponse)
def recipe_families_api(
    q: str = Query("", description="Search query"),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Distinct recipe families for the recipe form category combobox.

    Returns ``[{"label": family, "value": family}]`` ordered alphabetically.
    Empty `q` returns every distinct family. The combo `allow-create` flag
    lets users type a brand-new family on the fly.
    """
    stmt = (
        select(Recipe.family)
        .where(Recipe.family.isnot(None))
        .where(Recipe.family != "")
        .distinct()
        .order_by(Recipe.family)
    )
    fams = [f for f in session.scalars(stmt).all() if f]
    if q:
        needle = q.strip().lower()
        fams = [f for f in fams if needle in f.lower()]
    fams = fams[:limit]
    return JSONResponse([{"label": f, "value": f} for f in fams])


@router.get("/export")
def recipes_export_csv(
    request: Request,
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """Export all recipes as a CSV download (streaming)."""
    from datetime import datetime, timezone

    from starlette.responses import StreamingResponse

    from app.rms.streaming_csv import stream_csv_rows

    recipes = session.scalars(select(Recipe).order_by(Recipe.name)).all()

    def _iter():
        from app.rms.costing import recipe_batch_cost_gs, recipe_unit_cost_gs
        from app.rms.models_legacy import RecipeLine

        for r in recipes:
            batch = recipe_batch_cost_gs(session, r.id)
            unit = recipe_unit_cost_gs(session, r.id)
            line_count = (
                session.scalar(
                    select(func.count(RecipeLine.id)).where(RecipeLine.recipe_id == r.id)
                )
                or 0
            )
            yield [
                r.id,
                r.name,
                r.family or "",
                r.difficulty or "",
                r.yield_qty or "",
                r.yield_unit,
                r.prep_minutes or "",
                r.cook_minutes or "",
                line_count,
                batch.batch_cost_gs if batch.batch_cost_gs is not None else "",
                unit.batch_cost_gs if unit.batch_cost_gs is not None else "",
                r.dietary_tags or "",
                r.notes or "",
            ]

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return StreamingResponse(
        stream_csv_rows(
            [
                "id",
                "name",
                "family",
                "difficulty",
                "yield_qty",
                "yield_unit",
                "prep_minutes",
                "cook_minutes",
                "line_count",
                "batch_cost_gs",
                "unit_cost_gs",
                "tags",
                "notes",
            ],
            _iter(),
        ),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=rms-recetas-{timestamp}.csv"},
    )


__all__ = ["router"]
