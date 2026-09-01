"""app/routers/recipes.py — CRUD endpoints for recipes with polymorphic lines.

Per dev plan §9 Task 3 + v2 §5 (polymorphic recipe_line).

Note: repeated form fields (multiple line_kind / line_target_id / line_qty / line_notes
per row) require async parsing via `await request.form()` because FastAPI's Form()
only handles single values.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.costing import recipe_batch_cost_gs, recipe_unit_cost_gs
from app.rms.models import Ingredient, Recipe, RecipeLine
from app.rms.units import Unit
from app.services.template_render import render

router = APIRouter(prefix="/recetas", dependencies=[Depends(require_login)])


def get_session(request: Request) -> Session:
    return request.app.state.session_factory()


def _decorate(session: Session, r: Recipe) -> dict:
    """Compute batch + unit cost for a recipe row."""
    batch = recipe_batch_cost_gs(session, r.id)
    unit = recipe_unit_cost_gs(session, r.id)
    from sqlalchemy import func

    line_count = (
        session.scalar(select(func.count(RecipeLine.id)).where(RecipeLine.recipe_id == r.id)) or 0
    )
    return {
        "id": r.id,
        "name": r.name,
        "yield_qty": r.yield_qty,
        "yield_unit": r.yield_unit,
        "line_count": line_count,
        "batch_cost_gs": batch.batch_cost_gs,
        "unit_cost_gs": unit.batch_cost_gs,
        "notes": r.notes,
    }


@router.get("", response_class=HTMLResponse)
async def recipes_list(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    recipes = session.scalars(select(Recipe).order_by(Recipe.name)).all()
    decorated = [_decorate(session, r) for r in recipes]
    return render(request, "recetas.html", {"recipes": decorated})


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

    if not name:
        raise HTTPException(status_code=400, detail="Nombre es obligatorio")

    try:
        y_unit = Unit.coerce(yield_unit_raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Unidad inválida: {e}") from e

    y_qty = float(yield_qty_raw) if yield_qty_raw else None

    recipe = Recipe(
        name=name,
        yield_qty=y_qty,
        yield_unit=y_unit.value,
        notes=notes or None,
    )
    session.add(recipe)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409, detail=f"Ya existe una receta con nombre {name!r}"
        ) from None

    _apply_lines_from_form(session, recipe.id, form)
    return RedirectResponse(url="/recetas", status_code=303)


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

    # Replace lines
    for old in list(r.lines):
        session.delete(old)
    session.flush()
    _apply_lines_from_form(session, r.id, form)
    session.commit()
    return RedirectResponse(url="/recetas", status_code=303)


def _apply_lines_from_form(session: Session, recipe_id: int, form) -> None:
    """Parse repeated form fields for recipe lines and persist them.

    Expected form keys (each repeated for N lines):
      line_kind (str: 'ingredient' or 'sub_recipe')
      line_target_id (str: integer ID as string)
      line_qty (str: float as string)
      line_notes (str, optional)

    Lines with empty kind or target_id or qty <= 0 are skipped silently.
    """
    kinds = form.getlist("line_kind")
    target_ids = form.getlist("line_target_id")
    qtys = form.getlist("line_qty")
    notes_list = form.getlist("line_notes")

    n = max(len(kinds), len(target_ids), len(qtys))
    for i in range(n):
        kind = str(kinds[i]).strip() if i < len(kinds) else ""
        target = str(target_ids[i]).strip() if i < len(target_ids) else ""
        qty_raw = str(qtys[i]).strip() if i < len(qtys) else ""
        ln_notes = str(notes_list[i]).strip() if i < len(notes_list) else ""

        if not kind or not target or not qty_raw:
            continue
        try:
            qty = float(qty_raw)
            target_id = int(target)
        except ValueError:
            continue
        if qty <= 0 or target_id <= 0:
            continue

        session.add(
            RecipeLine(
                recipe_id=recipe_id,
                line_kind=kind,
                line_ref_id=target_id,
                qty=qty,
                notes=ln_notes or None,
            )
        )


__all__ = ["router"]
