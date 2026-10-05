"""app/rms/costing.py — recipe cost, product margin, apply_sale, void_sale.

Per dev plan §9 Task 2 + v2 §5 (data model + stock-drop logic).

Pure functions where possible. Functions that touch the DB take a SQLAlchemy
Session as first arg.

Money discipline (enforced by tests):
- All intermediate calculations use Decimal
- Only `app.rms.money.to_int_gs()` is allowed to round money to integer
- All DB money columns are INTEGER (no Decimal in DB)

Polymorphic recipe_line: walks sub-recipe tree recursively. Cycle detection via
visited-set raises `CycleInRecipeTree`.

Stock drop (apply_sale):
- Atomic transaction with sale + sale_stock_move rows
- Walks recipe tree depth-first
- Negative stock allowed (kitchen reality > accounting purity)
- NULL yield_qty blocks the sale explicitly

Void: reverses all stock_moves for the sale, atomically.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import Ingredient, Product, Recipe, RecipeLine
from app.rms.money import to_int_gs
from app.rms.units import normalize_recipe_line_qty


def resolve_line_target(session: Session, line: RecipeLine) -> Ingredient | Recipe | None:
    """Resolve a polymorphic recipe_line to its actual target (Ingredient or Recipe).

    Returns None if the target doesn't exist (referential integrity failure).
    """
    if line.line_kind == "ingredient":
        return session.get(Ingredient, line.line_ref_id)
    elif line.line_kind == "sub_recipe":
        return session.get(Recipe, line.line_ref_id)
    else:
        raise ValueError(f"Unknown line_kind: {line.line_kind!r}")


# --- Custom exceptions ---


class CycleInRecipeTree(Exception):
    """Raised when a recipe tree has a cycle (A uses B uses A)."""



class RecipeWithoutYield(Exception):
    """Raised when apply_sale is called with a recipe whose yield_qty is NULL."""



class ProductWithoutRecipe(Exception):
    """Raised when a sale is attempted on a product with no recipe."""



# --- Recipe cost computation (polymorphic tree walk) ---


@dataclass(frozen=True)
class CostResult:
    """Result of a recipe cost computation.

    batch_cost_gs: int | None. None means at least one ingredient/sub-recipe is
        missing purchase_price_gs (or one of them transitively is).
    missing_ingredient_names: list of names (for UI alert).
    visited: internal; used by recursive walker to detect cycles.
    """

    batch_cost_gs: int | None
    missing_ingredient_names: list[str]
    cycle_detected: bool = False

    @property
    def has_missing(self) -> bool:
        return self.batch_cost_gs is None and not self.cycle_detected


def _walk_recipe_cost(
    session: Session,
    recipe: Recipe,
    visited: set[int],
    missing: list[str],
) -> Decimal | None:
    """Recursive walker. Returns Decimal batch cost (None if any line is incomplete).

    Walks sub-recipes recursively. Cycle detection via `visited` set.
    """
    if recipe.id in visited:
        # Cycle. Raise so the caller knows.
        raise CycleInRecipeTree(
            f"Cycle detected in recipe tree at recipe id={recipe.id} name={recipe.name!r}"
        )
    visited = visited | {recipe.id}

    if recipe.yield_qty is None or recipe.yield_qty <= 0:
        # Recipe with no yield cannot be costed.
        missing.append(f"recipe:{recipe.name} (sin rendimiento)")
        return None

    total = Decimal("0")

    # Refresh lines (caller may have passed a stale Recipe)
    lines = session.scalars(select(RecipeLine).where(RecipeLine.recipe_id == recipe.id)).all()

    for line in lines:
        # Phase B — T1: line_unit is the unit Saskia typed the qty in.
        # Default to the linked ingredient's unit (backward compat for
        # legacy rows with line_unit=''). normalize_recipe_line_qty raises
        # ValueError on cross-family conversion (g→l, etc.) — the costing
        # walk surfaces this via missing[] so the UI can show "unidades
        # incompatibles" instead of crashing.
        line_qty_raw = Decimal(str(line.qty))
        target = resolve_line_target(session, line)
        if line.line_kind == "ingredient":
            ingredient = target  # type: ignore[assignment]
            if ingredient is None:
                missing.append(f"line:{line.id} (ingrediente no existe)")
                return None
            # variants.current_variant_price: preferred variant price if
            # any, else the parent Ingredient price (backward compatible).
            from app.rms.variants import current_variant_price

            effective_price = current_variant_price(session, ingredient.id)
            if effective_price is None:
                missing.append(f"ingredient:{ingredient.name} (sin precio)")
                return None
            # Resolve which unit to normalize qty INTO: prefer line_unit when
            # set, else fall back to ingredient.unit (legacy/back-compat).
            line_unit = line.line_unit if line.line_unit else ingredient.unit
            try:
                line_qty_in_ingredient_unit = normalize_recipe_line_qty(
                    line_qty_raw, line_unit, ingredient.unit
                )
            except ValueError as exc:
                missing.append(
                    f"line:{line.id} ({line_unit!r}→{ingredient.unit!r} requiere densidad: {exc})"
                )
                return None
            # Multiply the normalized qty against the ingredient's per-unit price.
            line_cost = line_qty_in_ingredient_unit * Decimal(
                str(effective_price)
            )
            total += line_cost

        elif line.line_kind == "sub_recipe":
            sub_recipe = target  # type: ignore[assignment]
            if sub_recipe is None:
                missing.append(f"line:{line.id} (sub-receta no existe)")
                return None
            sub_cost = _walk_recipe_cost(session, sub_recipe, visited, missing)
            if sub_cost is None:
                return None
            # sub_cost is per sub_recipe.yield_qty. We need sub_qty in same units.
            if sub_recipe.yield_qty is None or sub_recipe.yield_qty <= 0:
                missing.append(f"sub-recipe:{sub_recipe.name} (sin rendimiento)")
                return None
            # Scale: line_qty is in (sub_recipe's yield unit). Convert:
            # line_cost = line_qty × (sub_cost / sub_recipe.yield_qty)
            ratio = line_qty_raw / Decimal(str(sub_recipe.yield_qty))
            total += ratio * sub_cost

        else:
            raise ValueError(f"Unknown line_kind: {line.line_kind!r}")

    return total


def batch_products_cost_margin(
    session: Session,
    products: list[Product],
) -> dict[int, tuple["CostResult", tuple[int | None, float | None]]]:
    """Batch-compute cost + margin for many products in ~3 queries.

    Replaces the N+1 pattern of calling product_unit_cost_gs per product.
    Pre-loads all referenced recipes + recipe_lines + ingredients in a
    single pass, then computes costs in Python using the identity map.

    Returns {product_id: (CostResult, (margin_gs, margin_ratio))}.
    """
    if not products:
        return {}

    recipe_ids = {p.recipe_id for p in products if p.recipe_id is not None}

    no_recipe_result: tuple[CostResult, tuple[int | None, float | None]] = (
        CostResult(batch_cost_gs=None, missing_ingredient_names=["product sin receta"]),
        (None, None),
    )
    if not recipe_ids:
        return {p.id: no_recipe_result for p in products}

    # Pre-load Recipe + RecipeLine + Ingredient + sub-recipe rows in 3-4 queries.
    # After this, session.get() / line walks are identity-map hits (zero cost).
    session.scalars(select(Recipe).where(Recipe.id.in_(recipe_ids))).all()
    all_lines = session.scalars(
        select(RecipeLine).where(RecipeLine.recipe_id.in_(recipe_ids))
    ).all()
    ingredient_ids = {
        ln.line_ref_id for ln in all_lines if ln.line_kind == "ingredient"
    }
    sub_recipe_ids = {
        ln.line_ref_id for ln in all_lines if ln.line_kind == "sub_recipe"
    }
    if ingredient_ids:
        session.scalars(
            select(Ingredient).where(Ingredient.id.in_(ingredient_ids))
        ).all()
    if sub_recipe_ids:
        sub_recipes = session.scalars(
            select(Recipe).where(Recipe.id.in_(sub_recipe_ids))
        ).all()
        new_recipe_ids = {sr.id for sr in sub_recipes}
        session.scalars(
            select(RecipeLine).where(RecipeLine.recipe_id.in_(new_recipe_ids))
        ).all()

    # Compute in memory using the cached identity map.
    out: dict[int, tuple[CostResult, tuple[int | None, float | None]]] = {}
    for p in products:
        if p.recipe_id is None:
            out[p.id] = no_recipe_result
            continue
        # UNIT cost (per-portion), not batch cost: sale prices are per-unit,
        # so margin = sale_price - unit_cost. Batch cost here made every
        # multi-portion recipe look money-losing (2026-09-27 audit).
        cost = recipe_unit_cost_gs(session, p.recipe_id)
        if cost.batch_cost_gs is None:
            out[p.id] = (cost, (None, None))
            continue
        margin_gs = p.sale_price_gs - cost.batch_cost_gs
        ratio = margin_gs / p.sale_price_gs if p.sale_price_gs > 0 else None
        out[p.id] = (cost, (margin_gs, ratio))

    return out


def recipe_batch_cost_gs(session: Session, recipe_id: int) -> CostResult:
    """Compute batch cost (Gs.) for a recipe. Walks sub-recipes. Detects cycles.

    Returns CostResult with batch_cost_gs = None if any ingredient/sub-recipe is
    missing a purchase price, or if yield_qty is NULL.
    """
    recipe = session.get(Recipe, recipe_id)
    if recipe is None:
        return CostResult(
            batch_cost_gs=None,
            missing_ingredient_names=[f"recipe_id={recipe_id} (no existe)"],
            cycle_detected=False,
        )

    missing: list[str] = []
    try:
        total = _walk_recipe_cost(session, recipe, set(), missing)
    except CycleInRecipeTree as exc:
        return CostResult(
            batch_cost_gs=None,
            missing_ingredient_names=[str(exc)],
            cycle_detected=True,
        )

    if total is None:
        return CostResult(batch_cost_gs=None, missing_ingredient_names=missing)

    return CostResult(batch_cost_gs=to_int_gs(total), missing_ingredient_names=missing)


def recipe_unit_cost_gs(session: Session, recipe_id: int) -> CostResult:
    """Per-portion cost (Gs.) with yield-loss + labor (2026-09-24 costing fix).

    unit = (batch_cost + labor_cost) / (yield_qty × yield_percentage)

    - yield_percentage (Phase 1.D): 1.0 = no loss; 0.85 = 15% baking/trim
      loss. NULL → 1.0. A bakery that ignores yield loss understates cost
      by exactly the loss fraction.
    - direct_labor_minutes × ComplianceInfo.labor_cost_per_hour_gs
      (Phase 1.D). NULL rate or minutes → no labor component.
    """
    batch = recipe_batch_cost_gs(session, recipe_id)
    if batch.batch_cost_gs is None:
        return batch
    recipe = session.get(Recipe, recipe_id)
    if recipe is None or recipe.yield_qty is None or recipe.yield_qty <= 0:
        return CostResult(
            batch_cost_gs=None,
            missing_ingredient_names=["yield_qty missing"],
            cycle_detected=False,
        )
    batch_dec = Decimal(str(batch.batch_cost_gs))

    # Yield loss: effective output = yield_qty × yield_percentage
    yld = recipe.yield_percentage if recipe.yield_percentage else None
    if yld is not None and not (Decimal("0.3") <= Decimal(str(yld)) <= Decimal("1.0")):
        # Out-of-range yield % is data noise, not a 400% batch. Clamp to no-loss
        # and keep costing sane; the form validates on input.
        yld = None
    eff_yield = Decimal(str(recipe.yield_qty)) * (Decimal(str(yld)) if yld else Decimal("1"))

    # Labor: minutes × hourly rate from compliance costing config
    labor_gs = Decimal("0")
    if recipe.direct_labor_minutes:
        try:
            from app.rms.models import ComplianceInfo
            ci = session.get(ComplianceInfo, 1)
            rate = getattr(ci, "labor_cost_per_hour_gs", None) if ci else None
            if rate:
                labor_gs = (
                    Decimal(str(recipe.direct_labor_minutes))
                    * Decimal(str(rate))
                    / Decimal("60")
                )
        except Exception:  # noqa: BLE001 — defensive default
            labor_gs = Decimal("0")  # costing must never crash on config gaps

    unit = (batch_dec + labor_gs) / eff_yield
    return CostResult(
        batch_cost_gs=to_int_gs(unit), missing_ingredient_names=batch.missing_ingredient_names
    )


def product_unit_cost_gs(session: Session, product_id: int) -> CostResult:
    """Compute per-portion cost (Gs.) for a product. Uses its recipe."""
    product = session.get(Product, product_id)
    if product is None:
        return CostResult(
            batch_cost_gs=None,
            missing_ingredient_names=[f"product_id={product_id} (no existe)"],
            cycle_detected=False,
        )
    if product.recipe_id is None:
        return CostResult(
            batch_cost_gs=None,
            missing_ingredient_names=["product sin receta"],
            cycle_detected=False,
        )
    return recipe_unit_cost_gs(session, product.recipe_id)


def product_margin(session: Session, product_id: int) -> tuple[int | None, float | None]:
    """Compute margin in Gs. and as a ratio (0..1).

    Returns (margin_gs, margin_ratio). Both None if cost cannot be computed.
    """
    product = session.get(Product, product_id)
    if product is None:
        return (None, None)
    cost = product_unit_cost_gs(session, product_id)
    if cost.batch_cost_gs is None:
        return (None, None)
    margin_gs = product.sale_price_gs - cost.batch_cost_gs
    if product.sale_price_gs <= 0:
        return (margin_gs, None)
    ratio = margin_gs / product.sale_price_gs
    return (margin_gs, ratio)

def batch_recipes_cost(
    session: Session,
    recipes: list[Recipe],
) -> dict[int, tuple["CostResult", "CostResult | None", int]]:
    """Batch-compute batch + unit cost + line_count for many recipes.

    Replaces the N+1 pattern of calling recipe_batch_cost_gs per recipe.
    Pre-loads all referenced lines + ingredients in 2-3 queries, then
    computes cost in Python using the identity map.

    Returns {recipe_id: (CostResult, unit CostResult | None, line_count)}.
    """
    if not recipes:
        return {}

    recipe_ids = {r.id for r in recipes if r is not None}
    if not recipe_ids:
        return {r.id: (CostResult(batch_cost_gs=None, missing_ingredient_names=[]), None, 0) for r in recipes}

    # Pre-load Recipe + lines + ingredients in 3 queries.
    session.scalars(select(Recipe).where(Recipe.id.in_(recipe_ids))).all()
    all_lines = session.scalars(
        select(RecipeLine).where(RecipeLine.recipe_id.in_(recipe_ids))
    ).all()
    line_counts: dict[int, int] = {rid: 0 for rid in recipe_ids}
    for ln in all_lines:
        line_counts[ln.recipe_id] = line_counts.get(ln.recipe_id, 0) + 1

    ingredient_ids = {
        ln.line_ref_id for ln in all_lines if ln.line_kind == "ingredient"
    }
    sub_recipe_ids = {
        ln.line_ref_id for ln in all_lines if ln.line_kind == "sub_recipe"
    }
    if ingredient_ids:
        session.scalars(
            select(Ingredient).where(Ingredient.id.in_(ingredient_ids))
        ).all()
    if sub_recipe_ids:
        sub_recipes = session.scalars(
            select(Recipe).where(Recipe.id.in_(sub_recipe_ids))
        ).all()
        new_recipe_ids = {sr.id for sr in sub_recipes}
        session.scalars(
            select(RecipeLine).where(RecipeLine.recipe_id.in_(new_recipe_ids))
        ).all()

    out: dict[int, tuple[CostResult, CostResult | None, int]] = {}
    for r in recipes:
        if r is None:
            continue
        batch = recipe_batch_cost_gs(session, r.id)
        unit = recipe_unit_cost_gs(session, r.id) if batch.batch_cost_gs is not None else None
        out[r.id] = (batch, unit, line_counts.get(r.id, 0))
    return out

