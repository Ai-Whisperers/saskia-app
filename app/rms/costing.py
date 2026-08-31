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
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import (
    Ingredient,
    Product,
    Recipe,
    RecipeLine,
    Sale,
    SaleStockMove,
)
from app.rms.money import to_int_gs


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

    pass


class RecipeWithoutYield(Exception):
    """Raised when apply_sale is called with a recipe whose yield_qty is NULL."""

    pass


class ProductWithoutRecipe(Exception):
    """Raised when a sale is attempted on a product with no recipe."""

    pass


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
        line_qty = Decimal(str(line.qty))
        target = resolve_line_target(session, line)
        if line.line_kind == "ingredient":
            ingredient = target  # type: ignore[assignment]
            if ingredient is None:
                missing.append(f"line:{line.id} (ingrediente no existe)")
                return None
            if ingredient.purchase_price_gs is None:
                missing.append(f"ingredient:{ingredient.name} (sin precio)")
                return None
            # ingredient.purchase_price_gs is per the ingredient's *unit*, which
            # matches the recipe line's unit at import time. We trust that.
            # (If units differ, the importer normalizes them via convert_qty.)
            line_cost = line_qty * Decimal(str(ingredient.purchase_price_gs))
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
            ratio = line_qty / Decimal(str(sub_recipe.yield_qty))
            total += ratio * sub_cost

        else:
            raise ValueError(f"Unknown line_kind: {line.line_kind!r}")

    return total


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
    """Compute per-portion cost (Gs.) for a recipe. batch_cost / yield_qty."""
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
    unit = Decimal(str(batch.batch_cost_gs)) / Decimal(str(recipe.yield_qty))
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


# --- Sale application (atomic) ---


@dataclass
class ApplySaleResult:
    """Result of apply_sale()."""

    sale_id: int
    product_id: int
    qty: float
    unit_price_gs: int
    total_price_gs: int
    has_recipe: bool
    stock_moves: list[tuple[int, float]]  # list of (ingredient_id, qty_delta)
    cycle_warning: bool = False


def apply_sale(
    session: Session,
    product_id: int,
    qty: float,
    sold_at: datetime,
    notes: str | None = None,
) -> ApplySaleResult:
    """Record a sale. Atomic. Drops theoretical stock.

    Raises:
        ProductWithoutRecipe: if product has no recipe (sale is still saved,
            but with has_recipe=False and zero stock moves).
        RecipeWithoutYield: if the recipe has yield_qty NULL.
        CycleInRecipeTree: if recipe tree has a cycle.
    """
    if qty <= 0:
        raise ValueError(f"qty must be > 0, got {qty}")

    product = session.get(Product, product_id)
    if product is None:
        raise ValueError(f"Product {product_id} not found")

    # Snapshot price at sale time
    unit_price_gs = product.sale_price_gs
    total_price_gs = to_int_gs(Decimal(str(qty)) * Decimal(str(unit_price_gs)))

    # Create sale row
    sale = Sale(
        sold_at=sold_at,
        product_id=product_id,
        qty=qty,
        unit_price_gs=unit_price_gs,
        notes=notes,
    )
    session.add(sale)
    session.flush()  # assigns sale.id

    has_recipe = product.recipe_id is not None
    stock_moves: list[tuple[int, float]] = []
    cycle_warning = False

    if has_recipe and product.recipe_id is not None:
        recipe = session.get(Recipe, product.recipe_id)
        if recipe is None:
            has_recipe = False
        elif recipe.yield_qty is None or recipe.yield_qty <= 0:
            raise RecipeWithoutYield(
                f"Receta '{recipe.name}' sin rendimiento. Cargá el rendimiento antes de vender."
            )
        else:
            try:
                # Walk tree, collect (ingredient_id, qty_delta)
                moves = _compute_stock_moves(session, recipe, qty, set())
                # Create SaleStockMove rows + update ingredient stock
                for affected_recipe_id, ingredient_id, qty_delta in moves:
                    move = SaleStockMove(
                        sale_id=sale.id,
                        affected_recipe_id=affected_recipe_id,
                        ingredient_id=ingredient_id,
                        qty_delta=-abs(qty_delta),  # negative = stock decrease
                    )
                    session.add(move)
                    ingredient = session.get(Ingredient, ingredient_id)
                    if ingredient is not None:
                        ingredient.stock_qty = (ingredient.stock_qty or 0) - abs(qty_delta)
                    stock_moves.append((ingredient_id, -abs(qty_delta)))
            except CycleInRecipeTree:
                cycle_warning = True
                # Sale is still saved; stock moves are not applied.

    session.commit()

    return ApplySaleResult(
        sale_id=sale.id,
        product_id=product_id,
        qty=qty,
        unit_price_gs=unit_price_gs,
        total_price_gs=total_price_gs,
        has_recipe=has_recipe,
        stock_moves=stock_moves,
        cycle_warning=cycle_warning,
    )


def _compute_stock_moves(
    session: Session,
    recipe: Recipe,
    sale_qty: float,
    visited: set[int],
) -> list[tuple[int, int, float]]:
    """Walk recipe tree, return list of (affected_recipe_id, ingredient_id, qty_delta).

    Internal helper for apply_sale(). Cycle detection raises CycleInRecipeTree.
    """
    if recipe.id in visited:
        raise CycleInRecipeTree(f"Cycle at recipe {recipe.id} {recipe.name!r}")
    visited = visited | {recipe.id}

    if recipe.yield_qty is None or recipe.yield_qty <= 0:
        raise RecipeWithoutYield(
            f"Receta '{recipe.name}' sin rendimiento. Cargá el rendimiento antes de vender."
        )

    moves: list[tuple[int, int, float]] = []
    yield_qty = Decimal(str(recipe.yield_qty))
    sale_qty_d = Decimal(str(sale_qty))

    lines = session.scalars(select(RecipeLine).where(RecipeLine.recipe_id == recipe.id)).all()

    for line in lines:
        line_qty = Decimal(str(line.qty))
        if line.line_kind == "ingredient":
            # Per-sale qty of this ingredient = (line.qty / recipe.yield_qty) × sale.qty
            per_sale = (line_qty / yield_qty) * sale_qty_d
            moves.append((recipe.id, line.line_ref_id, float(per_sale)))
        elif line.line_kind == "sub_recipe":
            sub_recipe = resolve_line_target(session, line)
            if sub_recipe is None:
                continue
            # Per-sale qty of sub-recipe = (line.qty / recipe.yield_qty) × sale.qty
            sub_sale_qty = (line_qty / yield_qty) * sale_qty_d
            # Recurse into sub_recipe; its moves are tagged with sub_recipe.id
            sub_moves = _compute_stock_moves(session, sub_recipe, float(sub_sale_qty), visited)
            moves.extend(sub_moves)

    return moves


# --- Void ---


@dataclass
class VoidSaleResult:
    """Result of void_sale()."""

    sale_id: int
    restored_moves: list[tuple[int, float]]  # (ingredient_id, qty_restored)


def void_sale(session: Session, sale_id: int) -> VoidSaleResult:
    """Reverse a sale's stock moves. Atomic.

    If the sale was already voided, raises ValueError (idempotency via state check).
    """
    sale = session.get(Sale, sale_id)
    if sale is None:
        raise ValueError(f"Sale {sale_id} not found")
    if sale.voided_at is not None:
        raise ValueError(f"Sale {sale_id} ya anulada")

    restored: list[tuple[int, float]] = []
    for move in list(sale.stock_moves):  # copy to avoid mutating during iter
        # Reverse: qty_delta becomes positive (restored)
        restored_qty = abs(move.qty_delta)
        move.qty_delta = restored_qty
        ingredient = session.get(Ingredient, move.ingredient_id)
        if ingredient is not None:
            ingredient.stock_qty = (ingredient.stock_qty or 0) + restored_qty
        restored.append((move.ingredient_id, restored_qty))

    sale.voided_at = datetime.now()
    session.commit()

    return VoidSaleResult(sale_id=sale_id, restored_moves=restored)


__all__ = [
    "resolve_line_target",
    "CycleInRecipeTree",
    "RecipeWithoutYield",
    "ProductWithoutRecipe",
    "CostResult",
    "ApplySaleResult",
    "VoidSaleResult",
    "recipe_batch_cost_gs",
    "recipe_unit_cost_gs",
    "product_unit_cost_gs",
    "product_margin",
    "apply_sale",
    "void_sale",
]
