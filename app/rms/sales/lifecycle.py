"""app/rms/sales/lifecycle.py — Sale apply/void + stock-move computation.

Sprint 2.3 of the 2026-10-02 backend overhaul: split out of
``app/rms/costing.py``. Owns the transactional sale path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models.channels import Channel
from app.rms.models import Ingredient, Product, Recipe, RecipeLine, Sale, SaleStockMove, StockMovement
from app.rms.money import to_int_gs
from app.rms.profitability.cost import (
    CycleInRecipeTree,
    RecipeWithoutYield,
    resolve_line_target,
)


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
    *,
    customer_id: int | None = None,
    payment_method: str | None = None,
    discount_gs: int = 0,
    channel: str | None = None,
    packaging_item_id: int | None = None,
    packaging_qty: float | None = None,
    unit_price_gs_override: int | None = None,
    # Migration 076 — back-pointer to the Pedido that produced this Sale.
    # Set when apply_sale() is called from the /pedidos/{id}/fulfill flow
    # so pedido.sales and sale.linked_pedido_id both populate symmetrically.
    linked_pedido_id: int | None = None,
) -> ApplySaleResult:
    """Record a sale. Atomic. Drops theoretical stock.

    US 4.1 — per-sale packaging. ``packaging_item_id`` must reference an
    Ingredient with ``is_packaging=True``. ``packaging_qty`` defaults to
    1 when packaging_item_id is set but qty is None. The packaging
    ingredient's stock_qty is decremented by packaging_qty, and a
    StockMovement audit row is written.

    Raises:
        ProductWithoutRecipe: if product has no recipe (sale is still saved,
            but with has_recipe=False and zero stock moves).
        RecipeWithoutYield: if the recipe has yield_qty NULL.
        CycleInRecipeTree: if recipe tree has a cycle.
        ValueError: if packaging_item_id is not a packaging ingredient, or
            packaging_qty is negative, or both/neither packaging_* params
            are set inconsistently.
    """
    if qty <= 0:
        raise ValueError(f"qty must be > 0, got {qty}")

    # US 4.1 packaging validation
    packaging_item: Ingredient | None = None
    if packaging_item_id is not None:
        if packaging_qty is None or packaging_qty <= 0:
            raise ValueError(
                f"packaging_qty must be > 0 when packaging_item_id is set, "
                f"got {packaging_qty!r}"
            )
        packaging_item = session.get(Ingredient, packaging_item_id)
        if packaging_item is None:
            raise ValueError(
                f"Packaging ingredient {packaging_item_id} not found"
            )
        if not packaging_item.is_packaging:
            raise ValueError(
                f"Ingredient {packaging_item_id} ({packaging_item.name!r}) is "
                f"not flagged as packaging. Set is_packaging=True on the "
                f"ingredient first."
            )
    elif packaging_qty is not None and packaging_qty > 0:
        raise ValueError(
            f"packaging_qty={packaging_qty} was set without packaging_item_id"
        )

    product = session.get(Product, product_id)
    if product is None:
        raise ValueError(f"Product {product_id} not found")

    # Snapshot price at sale time
    unit_price_gs = unit_price_gs_override if unit_price_gs_override is not None else product.sale_price_gs
    total_price_gs = to_int_gs(Decimal(str(qty)) * Decimal(str(unit_price_gs)))

    # Create sale row
    sale = Sale(
        sold_at=sold_at,
        product_id=product_id,
        qty=qty,
        unit_price_gs=unit_price_gs,
        notes=notes,
        customer_id=customer_id,
        payment_method=payment_method,
        discount_gs=discount_gs,
        channel=channel or Channel.MOSTRADOR.value,
        # US 4.1 — per-sale packaging. Persisted on the sale so the
        # cost report can attribute packaging consumption to the sale.
        packaging_item_id=packaging_item_id,
        packaging_qty=packaging_qty,
        # Migration 076 — link sale back to its source pedido.
        linked_pedido_id=linked_pedido_id,
    )
    session.add(sale)
    session.flush()  # assigns sale.id

    # US 4.1 — decrement packaging stock + audit row.
    if packaging_item is not None and packaging_qty is not None and packaging_qty > 0:
        packaging_item.stock_qty = (packaging_item.stock_qty or 0) - packaging_qty
        stock_movement = StockMovement(
            ingredient_id=packaging_item.id,
            movement_type="sale",
            qty=-abs(packaging_qty),
            reason=f"Venta #{sale.id} (packaging)",
            reference_id=sale.id,
            reference_type="sale",
            recorded_at=sold_at,
            created_by=None,
        )
        session.add(stock_movement)

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
                # KNOWN DUAL-WRITE (Phase 14 #1 — partially addressed):
                # We write BOTH SaleStockMove and StockMovement for the same
                # sale. The reasons SaleStockMove is still written:
                #   - 157 references in app/+ tests/ (accounting COGS,
                #     export_csv, backup, demo_reset, seed/kyrian, etc.).
                #   - SaleStockMove.affected_recipe_id records WHICH recipe
                #     the ingredient came from (sub-recipe traceability),
                #     which StockMovement does not capture.
                # Full consolidation = add affected_recipe_id nullable on
                # StockMovement + migrate SaleStockMove rows + drop the
                # old table. Estimated scope: ~50 files touched. See
                # IMPROVEMENT_BACKLOG.md #1 for the full plan.
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
                    # Write StockMovement audit record (negative qty = stock out)
                    stock_movement = StockMovement(
                        ingredient_id=ingredient_id,
                        movement_type="sale",
                        qty=-abs(qty_delta),
                        reason=f"Venta #{sale.id}",
                        reference_id=sale.id,
                        reference_type="sale",
                        recorded_at=sold_at,
                        created_by=None,
                    )
                    session.add(stock_movement)
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


def void_sale(
    session: Session,
    sale_id: int,
    reason: str | None = None,
    voided_by: str | None = None,
) -> VoidSaleResult:
    """Reverse a sale's stock moves. Atomic.

    If the sale was already voided, raises ValueError (idempotency via state check).

    CIE-01: ``reason`` and ``voided_by`` are persisted on the Sale row so
    operators can audit who voided what and why — critical for accountability
    in a small bakery where every cancelled sale matters.
    """
    sale = session.get(Sale, sale_id)
    if sale is None:
        raise ValueError(f"Sale {sale_id} not found")
    if sale.voided_at is not None:
        raise ValueError(f"Sale {sale_id} ya anulada")

    # P0 cerrar-puertas: block void after EOD close (accounting violation).
    # The roadmap (saskia-only-roadmap.md, 2026-09-29) flagged this as a
    # critical gap: Saskia could void a Monday sale on Wednesday AFTER
    # closing Monday's books. The router translates this to a clean
    # Spanish user-facing message via the Conflict exception.
    sale_date = sale.sold_at.date() if sale.sold_at else None
    if sale_date is not None:
        from app.rms.eod_closed import eod_is_day_closed

        if eod_is_day_closed(session, sale_date):
            raise ValueError(
                f"void_after_eod_close:{sale_date.isoformat()}"
            )

    restored: list[tuple[int, float]] = []
    # AGENTS.md hard rule: never use naive datetime.now() — always store UTC
    # so that tz-aware consumers (audit log, /ventas, reports) can convert
    # to Asunción local time correctly. Naive datetimes are interpreted as
    # server-local time (UTC on Render), which is 4 hours off from the
    # Asunción bakery's wall clock and breaks "today's sales" queries.
    now_utc = datetime.now(timezone.utc)
    for move in list(sale.stock_moves):  # copy to avoid mutating during iter
        # Reverse: qty_delta becomes positive (restored)
        restored_qty = abs(move.qty_delta)
        move.qty_delta = restored_qty
        ingredient = session.get(Ingredient, move.ingredient_id)
        if ingredient is not None:
            ingredient.stock_qty = (ingredient.stock_qty or 0) + restored_qty
        restored.append((move.ingredient_id, restored_qty))
        # StockMovement: positive = stock in (restored)
        stock_movement = StockMovement(
            ingredient_id=move.ingredient_id,
            movement_type="sale",
            qty=restored_qty,
            reason=f"Anulación venta #{sale.id}" + (f" — {reason}" if reason else ""),
            reference_id=sale.id,
            reference_type="sale",
            recorded_at=now_utc,
            created_by=voided_by,
        )
        session.add(stock_movement)

    sale.voided_at = now_utc
    if reason:
        sale.void_reason = reason
    if voided_by:
        sale.voided_by = voided_by

    # US 4.1 — restore packaging ingredient stock + audit row.
    if sale.packaging_item_id is not None and sale.packaging_qty:
        pkg = session.get(Ingredient, sale.packaging_item_id)
        if pkg is not None:
            restored_qty = float(sale.packaging_qty)
            pkg.stock_qty = (pkg.stock_qty or 0) + restored_qty
            restored.append((pkg.id, restored_qty))
            stock_movement = StockMovement(
                ingredient_id=pkg.id,
                movement_type="sale",
                qty=restored_qty,
                reason=f"Anulación venta #{sale.id} (packaging)"
                       + (f" — {reason}" if reason else ""),
                reference_id=sale.id,
                reference_type="sale",
                recorded_at=now_utc,
                created_by=voided_by,
            )
            session.add(stock_movement)

    session.commit()

    return VoidSaleResult(sale_id=sale_id, restored_moves=restored)


__all__ = [
    "ApplySaleResult",
    "CostResult",
    "CycleInRecipeTree",
    "ProductWithoutRecipe",
    "RecipeWithoutYield",
    "VoidSaleResult",
    "apply_sale",
    "product_margin",
    "product_unit_cost_gs",
    "recipe_batch_cost_gs",
    "recipe_unit_cost_gs",
    "resolve_line_target",
    "void_sale",
]


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
