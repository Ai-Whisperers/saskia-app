"""app/routers/recipes.py — CRUD endpoints for recipes with polymorphic lines.

Per dev plan §9 Task 3 + v2 §5 (polymorphic recipe_line).

Note: repeated form fields (multiple line_kind / line_target_id / line_qty / line_notes
per row) require async parsing via `await request.form()` because FastAPI's Form()
only handles single values.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
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
    }


@router.get("", response_class=HTMLResponse)
async def recipes_list(
    request: Request,
    q: str = Query("", description="Search by recipe name"),
    ingredient_id: int | None = Query(None, description="Filter by ingredient"),
    sort: str = Query("name", pattern="^(name|yield_qty|batch_cost_gs)$"),
    dir: str = Query("asc", pattern="^(asc|desc)$"),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """List recipes with batch + unit cost, search, filter by ingredient, and column sort.

    Batch-loaded to avoid N+1 on Neon.
    """
    # Base query
    stmt = select(Recipe)

    # Search filter
    if q:
        stmt = stmt.where(Recipe.name.ilike(f"%{q}%"))

    # Ingredient filter: find recipes that use this ingredient
    if ingredient_id is not None:
        stmt = stmt.join(RecipeLine).where(
            RecipeLine.line_kind == "ingredient",
            RecipeLine.line_ref_id == ingredient_id,
        )

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

    recipes = session.scalars(stmt.distinct()).all()
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
        "ingredient_id": ingredient_id,
        "sort": sort,
        "dir": dir,
        "ingredients": all_ingredients,
        "total": len(decorated),
    })


@router.get("/nueva", response_class=HTMLResponse)
async def recipe_new(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
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
    return RedirectResponse(url="/recetas", status_code=303)


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

    return render(request, "receta_detalle.html", {
        "recipe": r,
        "resolved_lines": resolved_lines,
        "batch_cost": batch_cost,
        "unit_cost": unit_cost,
        "products_using": [{"id": p.id, "name": p.name} for p in products_using],
        "tags": [{"id": t.id, "name": t.name, "color": t.color} for t in tags],
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


__all__ = ["router"]
