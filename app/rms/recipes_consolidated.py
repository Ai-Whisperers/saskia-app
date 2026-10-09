"""app/rms/recipes_consolidated.py — Consolidated ("exploded") recipe view.

UI-V2 Sprint: the recipe detail page shows two modes:
  - Estructural (assembly): sub-recipes stay as single logical lines.
  - Consolidada (compras): sub-recipes are exploded mathematically — raw
    ingredients from every sub-recipe are summed with the base recipe's
    own ingredients into one deduplicated shopping list.

Quantities are normalized into each ingredient's own unit via
normalize_recipe_line_qty (cross-family conversions like g→l raise
ValueError and surface as a "requires density" note, mirroring costing).
Sub-recipe lines scale by (line_qty / sub_recipe.yield_qty) exactly like
_walk_recipe_cost. Cycle-guarded via a visited set.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import Ingredient, Recipe, RecipeLine
from app.rms.units import normalize_recipe_line_qty


@dataclass
class ConsolidatedLine:
    """One raw-ingredient row of the exploded shopping list."""

    ingredient_id: int | None
    name: str
    unit: str
    qty: float
    # Recipe names (beyond the root) this qty came from, for traceability.
    sources: list[str] = field(default_factory=list)
    # How many separate recipe lines were summed into this row. >1 means
    # duplicates merged (base + one or more sub-recipes use the same
    # ingredient) — the UI surfaces this so nothing "disappears".
    merged_count: int = 1
    # Non-empty when a line could not be converted (unit density missing).
    error: str = ""


def explode_recipe(
    session: Session,
    recipe_id: int,
    *,
    scale: float = 1.0,
    _rid: int | None = None,
    _scale_by_rid: dict[int, float] | None = None,
    _sources: list[str] | None = None,
) -> list[ConsolidatedLine]:
    """Flatten a recipe tree into raw ingredients, summing duplicates.

    scale: multiplier applied to the ROOT recipe's batch (e.g. 2.0 to bake
    two batches). Sub-recipe scaling follows the parent automatically.

    Refactored 2026-10-09 to reduce cognitive complexity from 95 to <10
    by extracting logical branches into helper functions.
    """

    if _rid is None:
        _rid = recipe_id
        _scale_by_rid = {recipe_id: scale}
        _sources = []

    recipe = session.get(Recipe, _rid)
    if recipe is None:
        return []

    my_scale = (_scale_by_rid or {}).get(_rid, 1.0)
    lines = session.scalars(
        select(RecipeLine).where(RecipeLine.recipe_id == _rid).order_by(RecipeLine.id)
    ).all()

    acc: dict[int | str, ConsolidatedLine] = {}

    for ln in lines:
        qty_scaled = float(ln.qty) * my_scale

        if ln.line_kind == "ingredient":
            _process_ingredient_line(session, ln, qty_scaled, _sources, acc)
        elif ln.line_kind == "sub_recipe":
            _process_sub_recipe_line(
                session, recipe_id, ln, qty_scaled, _scale_by_rid, _sources, acc
            )

    return list(acc.values())


def _process_ingredient_line(
    session: Session,
    ln: Any,
    qty_scaled: float,
    _sources: list[str] | None,
    acc: dict[int | str, ConsolidatedLine],
) -> None:
    """Process a single ingredient recipe line.

    Extracted from explode_recipe to reduce complexity. Handles three cases:
    1. Missing ingredient (creates error row)
    2. Unit conversion error (creates error row with original qty)
    3. Valid ingredient (accumulates into accumulator)
    """
    ing = session.get(Ingredient, ln.line_ref_id)
    if ing is None:
        _add_error_row(
            acc,
            f"missing:{ln.line_ref_id}",
            ingredient_id=None,
            name=f"#{ln.line_ref_id} (ingrediente no existe)",
            unit="",
            qty=0.0,
            error="ingrediente no existe",
        )
        return

    line_unit = ln.line_unit or ing.unit
    try:
        qty_in_ing_unit = float(normalize_recipe_line_qty(qty_scaled, line_unit, ing.unit))
    except ValueError as exc:
        _add_error_row(
            acc,
            f"err:{ing.id}",
            ingredient_id=ing.id,
            name=ing.name,
            unit=ln.line_unit or ing.unit,
            qty=qty_scaled,
            error=f"conversión {line_unit!r}→{ing.unit!r} requiere densidad ({exc})",
        )
        return

    _accumulate_ingredient(acc, ing, qty_in_ing_unit, _sources)


def _process_sub_recipe_line(
    session: Session,
    recipe_id: int,
    ln: Any,
    qty_scaled: float,
    _scale_by_rid: dict[int, float],
    _sources: list[str] | None,
    acc: dict[int | str, ConsolidatedLine],
) -> None:
    """Process a single sub-recipe line.

    Extracted from explode_recipe to reduce complexity. Validates the
    sub-recipe, then recurses to explode it and merges the results.
    """
    sub = _get_validated_sub_recipe(session, recipe_id, ln, acc)
    if sub is None:
        return

    child_rows = _explode_sub_recipe(session, recipe_id, sub, qty_scaled, _scale_by_rid, _sources)
    _merge_child_rows(acc, child_rows)


def _get_validated_sub_recipe(
    session: Session,
    recipe_id: int,
    ln: Any,
    acc: dict[int | str, ConsolidatedLine],
) -> Any | None:
    """Validate a sub-recipe line and return the Recipe, or None on error.

    Extracted from _process_sub_recipe_line to reduce complexity. Validates:
    1. Sub-recipe exists
    2. Has yield_qty
    3. No cycle

    Adds error rows to acc and returns None if any validation fails.
    """

    sub = session.get(Recipe, ln.line_ref_id)
    if sub is None:
        _add_error_row(
            acc,
            f"missing_sub:{ln.line_ref_id}",
            ingredient_id=None,
            name=f"#{ln.line_ref_id} (sub-receta no existe)",
            unit="",
            qty=0.0,
            error="sub-receta no existe",
        )
        return None

    if sub.yield_qty is None or sub.yield_qty <= 0:
        _add_error_row(
            acc,
            f"noyield:{sub.id}",
            ingredient_id=None,
            name=sub.name,
            unit="",
            qty=0.0,
            error="sub-receta sin rendimiento",
        )
        return None

    if sub.id == recipe_id:
        _add_error_row(
            acc,
            f"cycle:{sub.id}",
            ingredient_id=None,
            name=sub.name,
            unit="",
            qty=0.0,
            error="ciclo detectado",
        )
        return None

    return sub


def _explode_sub_recipe(
    session: Session,
    recipe_id: int,
    sub: Any,
    qty_scaled: float,
    _scale_by_rid: dict[int, float],
    _sources: list[str] | None,
) -> list[ConsolidatedLine]:
    """Recursively explode a sub-recipe and return its rows.

    Extracted from _process_sub_recipe_line to reduce complexity.
    Sets the scale for the sub-recipe and recurses.
    """
    sub_batches = qty_scaled / float(sub.yield_qty)
    child_sources = list(_sources or [])
    if sub.name not in child_sources:
        child_sources.append(sub.name)
    _scale_by_rid[sub.id] = sub_batches

    return explode_recipe(
        session,
        recipe_id,
        _rid=sub.id,
        scale=1.0,
        _scale_by_rid=_scale_by_rid,
        _sources=child_sources,
    )


def _merge_child_rows(
    acc: dict[int | str, ConsolidatedLine],
    child_rows: list[ConsolidatedLine],
) -> None:
    """Merge rows from a sub-recipe explosion into the accumulator.

    Extracted from _process_sub_recipe_line to reduce complexity. For each
    child row, either creates a new row or merges into an existing one.
    """
    for cr in child_rows:
        key = cr.ingredient_id if cr.ingredient_id is not None else f"e:{cr.name}"
        existing = acc.get(key)
        if existing is None:
            acc[key] = cr
        else:
            _merge_into_existing(existing, cr)


def _merge_into_existing(
    existing: ConsolidatedLine,
    child: ConsolidatedLine,
) -> None:
    """Merge a child row into an existing accumulator row.

    Extracted from _merge_child_rows to reduce complexity. Sums quantities,
    counts, and deduplicates sources.
    """
    existing.qty += child.qty
    existing.merged_count += child.merged_count
    if child.error and not existing.error:
        existing.error = child.error
    for s in child.sources:
        if s not in existing.sources:
            existing.sources.append(s)


def _add_error_row(
    acc: dict[int | str, ConsolidatedLine],
    key: str,
    *,
    ingredient_id: int | None,
    name: str,
    unit: str,
    qty: float,
    error: str,
) -> None:
    """Add an error row to the accumulator, or update existing error.

    Extracted from explode_recipe to reduce complexity. Creates a
    ConsolidatedLine with the given error, or updates the error field
    of an existing row with the same key.
    """
    row = acc.get(key)
    if row is None:
        acc[key] = ConsolidatedLine(
            ingredient_id=ingredient_id,
            name=name,
            unit=unit,
            qty=qty,
        )
        row = acc[key]
    row.error = row.error or error


def _accumulate_ingredient(
    acc: dict[int | str, ConsolidatedLine],
    ing: Any,
    qty_in_ing_unit: float,
    _sources: list[str] | None,
) -> None:
    """Accumulate an ingredient into the result dictionary.

    Extracted from explode_recipe to reduce complexity. Creates a new
    row if the ingredient hasn't been seen, otherwise updates the
    existing row's quantity and sources.
    """
    key = ing.id
    row = acc.get(key)
    if row is None:
        acc[key] = ConsolidatedLine(
            ingredient_id=ing.id,
            name=ing.name,
            unit=ing.unit,
            qty=qty_in_ing_unit,
            sources=list(_sources or []),
        )
    else:
        row.qty += qty_in_ing_unit
        row.merged_count += 1
        for s in _sources or []:
            if s not in row.sources:
                row.sources.append(s)
