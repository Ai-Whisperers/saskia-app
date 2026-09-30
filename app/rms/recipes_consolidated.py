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

from sqlalchemy import select
from sqlalchemy.orm import Session

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
    """
    from app.rms.models import Ingredient, Recipe, RecipeLine

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

    # Accumulate by ingredient id (None unit-key fallback for missing ings).
    acc: dict[int | str, ConsolidatedLine] = {}

    for ln in lines:
        qty_scaled = float(ln.qty) * my_scale

        if ln.line_kind == "ingredient":
            ing = session.get(Ingredient, ln.line_ref_id)
            if ing is None:
                key = f"missing:{ln.line_ref_id}"
                row = acc.get(key)
                if row is None:
                    row = ConsolidatedLine(
                        ingredient_id=None,
                        name=f"#{ln.line_ref_id} (ingrediente no existe)",
                        unit="",
                        qty=0.0,
                    )
                    acc[key] = row
                row.error = row.error or "ingrediente no existe"
                continue

            line_unit = ln.line_unit or ing.unit
            try:
                qty_in_ing_unit = float(
                    normalize_recipe_line_qty(qty_scaled, line_unit, ing.unit)
                )
            except ValueError as exc:
                key = f"err:{ing.id}"
                row = acc.get(key)
                if row is None:
                    row = ConsolidatedLine(
                        ingredient_id=ing.id,
                        name=ing.name,
                        unit=ln.line_unit or ing.unit,
                        qty=qty_scaled,
                    )
                    acc[key] = row
                row.error = f"conversión {line_unit!r}→{ing.unit!r} requiere densidad ({exc})"
                continue

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
                for s in _sources or []:
                    if s not in row.sources:
                        row.sources.append(s)

        elif ln.line_kind == "sub_recipe":
            sub = session.get(Recipe, ln.line_ref_id)
            if sub is None:
                key = f"missing_sub:{ln.line_ref_id}"
                row = acc.get(key)
                if row is None:
                    row = ConsolidatedLine(
                        ingredient_id=None,
                        name=f"#{ln.line_ref_id} (sub-receta no existe)",
                        unit="",
                        qty=0.0,
                    )
                    acc[key] = row
                row.error = row.error or "sub-receta no existe"
                continue

            if sub.yield_qty is None or sub.yield_qty <= 0:
                key = f"noyield:{sub.id}"
                row = acc.get(key)
                if row is None:
                    row = ConsolidatedLine(
                        ingredient_id=None,
                        name=sub.name,
                        unit="",
                        qty=0.0,
                    )
                    acc[key] = row
                row.error = row.error or "sub-receta sin rendimiento"
                continue

            # Cycle guard.
            if sub.id == recipe_id:
                key = f"cycle:{sub.id}"
                row = acc.get(key)
                if row is None:
                    row = ConsolidatedLine(
                        ingredient_id=None,
                        name=sub.name,
                        unit="",
                        qty=0.0,
                    )
                    acc[key] = row
                row.error = row.error or "ciclo detectado"
                continue

            # How many sub-batches does this line need, scaled?
            sub_batches = qty_scaled / float(sub.yield_qty)
            child_sources = list(_sources or [])
            label = sub.name
            if label not in child_sources:
                child_sources.append(label)
            _scale_by_rid[sub.id] = sub_batches  # type: ignore[index]
            child_rows = explode_recipe(
                session,
                recipe_id,
                _rid=sub.id,
                scale=scale,
                _scale_by_rid=_scale_by_rid,
                _sources=child_sources,
            )
            # Merge child rows into our accumulator.
            for cr in child_rows:
                key = cr.ingredient_id if cr.ingredient_id is not None else f"e:{cr.name}"
                existing = acc.get(key)
                if existing is None:
                    acc[key] = cr
                else:
                    existing.qty += cr.qty
                    for s in cr.sources:
                        if s not in existing.sources:
                            existing.sources.append(s)
                    if cr.error:
                        existing.error = existing.error or cr.error

    # Stable order: by name.
    return sorted(acc.values(), key=lambda r: r.name.lower())
