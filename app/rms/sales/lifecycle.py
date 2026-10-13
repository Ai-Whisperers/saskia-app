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

from app.rms.models import (
    Ingredient,
    Product,
    Recipe,
    RecipeLine,
    Sale,
    StockMovement,
)
from app.rms.models.channels import Channel
from app.rms.money import to_int_gs
from app.rms.profitability.cost import (
    CostResult,
    CycleInRecipeTree,
    RecipeWithoutYield,
    batch_recipes_cost,
    recipe_batch_cost_gs,
    recipe_unit_cost_gs,
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

    Orchestrator: validates input, loads the product, persists the Sale
    row, then dispatches to the packaging- and recipe-stock helpers. The
    two stock-movement branches are single-purpose so each can be graded
    on its own; the orchestrator only carries the control flow and the
    final commit + return shape.

    Raises:
        ProductWithoutRecipe: if product has no recipe (sale is still saved,
            but with has_recipe=False and zero stock moves).
        RecipeWithoutYield: if the recipe has yield_qty NULL.
        CycleInRecipeTree: if recipe tree has a cycle.
        ValueError: if packaging_item_id is not a packaging ingredient, or
            packaging_qty is negative, or both/neither packaging_* params
            are set inconsistently.
    """
    _validate_apply_sale_input(qty, packaging_item_id, packaging_qty)
    packaging_item = _resolve_packaging_ingredient(session, packaging_item_id, packaging_qty)

    product, unit_price_gs, total_price_gs = _build_sale_row_and_price(
        session, product_id, qty, unit_price_gs_override
    )

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
        _apply_packaging_stock_movement(session, packaging_item, packaging_qty, sale, sold_at)

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
            # Returns (stock_moves, cycle_warning) so the orchestrator
            # stays free of the loop body; see _apply_recipe_stock_movements
            # for the per-move decrement + StockMovement audit rows.
            stock_moves, cycle_warning = _apply_recipe_stock_movements(
                session, recipe, qty, sale, sold_at
            )

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


# --- apply_sale helpers (orchestrator pattern — S3 batch-8) ---


def _validate_apply_sale_input(
    qty: float, packaging_item_id: int | None, packaging_qty: float | None
) -> None:
    """Validate apply_sale() top-level args + packaging-parameter consistency.

    Lifted from apply_sale() so the orchestrator stays free of value-shape
    branches. Raises ValueError with the SAME messages the pre-split inline
    code did, character-for-character, so the packaging-focused tests in
    tests/test_saskia_r2_sale_packaging.py (4 rejection cases) keep passing
    without modification.
    """
    if qty <= 0:
        raise ValueError(f"qty must be > 0, got {qty}")

    if packaging_item_id is not None:
        if packaging_qty is None or packaging_qty <= 0:
            raise ValueError(
                f"packaging_qty must be > 0 when packaging_item_id is set, got {packaging_qty!r}"
            )
    elif packaging_qty is not None and packaging_qty > 0:
        raise ValueError(f"packaging_qty={packaging_qty} was set without packaging_item_id")


def _resolve_packaging_ingredient(
    session: Session,
    packaging_item_id: int | None,
    packaging_qty: float | None,
) -> Ingredient | None:
    """Load + validate the packaging Ingredient (or None when not used).

    Returns the Ingredient if both `packaging_item_id` and a positive
    `packaging_qty` were supplied, else None. Raises ValueError with the
    SAME messages the pre-split inline code did when:
      - the ingredient id does not exist;
      - the ingredient exists but `is_packaging` is False on it.

    Split out of apply_sale() so the packaging-classification branches
    (and their long Spanish user-facing error strings) stay together.
    """
    if packaging_item_id is None:
        return None
    # packaging_qty>0 (or None) already guarded by _validate_apply_sale_input
    packaging_item = session.get(Ingredient, packaging_item_id)
    if packaging_item is None:
        raise ValueError(f"Packaging ingredient {packaging_item_id} not found")
    if not packaging_item.is_packaging:
        raise ValueError(
            f"Ingredient {packaging_item_id} ({packaging_item.name!r}) is "
            f"not flagged as packaging. Set is_packaging=True on the "
            f"ingredient first."
        )
    return packaging_item


def _build_sale_row_and_price(
    session: Session,
    product_id: int,
    qty: float,
    unit_price_gs_override: int | None,
) -> tuple[Product, int, int]:
    """Load the Product and snapshot (unit_price_gs, total_price_gs) for this sale.

    Returns (product, unit_price_gs, total_price_gs). The `unit_price_gs`
    snapshot uses `unit_price_gs_override` when provided, otherwise falls
    back to `product.sale_price_gs`. `total_price_gs` is computed via
    `to_int_gs` per the money-math rule (rule 2 — Decimal → int is only
    legal through `to_int_gs`).

    Raises ValueError if the product does not exist (same message as
    before).
    """
    product = session.get(Product, product_id)
    if product is None:
        raise ValueError(f"Product {product_id} not found")

    # Snapshot price at sale time
    unit_price_gs = (
        unit_price_gs_override if unit_price_gs_override is not None else product.sale_price_gs
    )
    total_price_gs = to_int_gs(Decimal(str(qty)) * Decimal(str(unit_price_gs)))
    return product, unit_price_gs, total_price_gs


def _apply_packaging_stock_movement(
    session: Session,
    packaging_item: Ingredient,
    packaging_qty: float,
    sale: Sale,
    sold_at: datetime,
) -> None:
    """Decrement packaging stock_qty and write the packaging StockMovement audit row.

    Mirrors the pre-split inline code character-for-character: absolute
    value on the qty delta (recipe qty may be negative in pathological
    schema states), reason string `f"Venta #{sale.id} (packaging)"`,
    reference_type / reference_id tied to the new sale.
    """
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


def _apply_recipe_stock_movements(
    session: Session,
    recipe: Recipe,
    sale_qty: float,
    sale: Sale,
    sold_at: datetime,
) -> tuple[list[tuple[int, float]], bool]:
    """Walk the recipe tree and write one StockMovement per ingredient consumed.

    Returns (stock_moves, cycle_warning). CycleInRecipeTree is caught and
    turned into the same `cycle_warning=True` signal the pre-split inline
    code emitted — the sale row stays committed; stock_moves is empty in
    that case so the caller can rely on `len(stock_moves) == 0` as the
    downstream "did stock move?" signal.

    The migration-092 ledger note lives here (was inline before): the
    sale_stock_move table is gone; the StockMovement rows below (movement_type
    'sale', reference_type 'sale') ARE the audit ledger. The SaleStockMove
    stub that Phase-14 tried to dual-write to was deleted in migration 092.
    """
    try:
        # Walk tree, collect (affected_recipe_id, ingredient_id, qty_delta)
        moves = _compute_stock_moves(session, recipe, sale_qty, set())
    except CycleInRecipeTree:
        # Sale is still saved; stock moves are not applied.
        return [], True

    stock_moves: list[tuple[int, float]] = []
    for _affected_recipe_id, ingredient_id, qty_delta in moves:
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
    return stock_moves, False


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
            raise ValueError(f"void_after_eod_close:{sale_date.isoformat()}")

    # BACKLOG #1: SaleStockMove table dropped by migration 092. The
    # stock_movement rows written by apply_sale() are the only audit
    # ledger now — query them directly instead of the legacy
    # sale.stock_moves relationship.
    sale_moves = (
        session.execute(
            select(StockMovement).where(
                StockMovement.reference_id == sale.id,
                StockMovement.reference_type == "sale",
            )
        )
        .scalars()
        .all()
    )

    restored: list[tuple[int, float]] = []
    # AGENTS.md hard rule: never use naive datetime.now() — always store UTC
    # so that tz-aware consumers (audit log, /ventas, reports) can convert
    # to Asunción local time correctly. Naive datetimes are interpreted as
    # server-local time (UTC on Render), which is 4 hours off from the
    # Asunción bakery's wall clock and breaks "today's sales" queries.
    now_utc = datetime.now(timezone.utc)
    for move in sale_moves:
        # Reverse: qty was negative for a sale → positive (restored).
        # Skip any positive rows (e.g. a prior voided-restore row) — only
        # the original sale-time rows get reversed again.
        if move.qty >= 0:
            continue
        restored_qty = abs(move.qty)
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

    # Pagos mixtos: the sale ledger (`sale_payment`) must reflect the void,
    # otherwise cash-reconciliation reports show phantom payments. We DELETE
    # rather than soft-mark because (a) the sale itself stays in the table
    # for audit (`voided_at` + `void_reason` + `voided_by` are the audit
    # trail), and (b) reports aggregate by non-voided sales only. A
    # soft-mark here would require a `voided_at` migration and report
    # filtering, which is more code than the current approach.
    from app.rms.models_legacy import SalePayment

    payment_rows = (
        session.execute(select(SalePayment).where(SalePayment.sale_id == sale.id)).scalars().all()
    )
    for p in payment_rows:
        session.delete(p)

    # US 4.1 packaging restore: the canonical StockMovement reversal
    # loop above (which queries StockMovement by reference_id+reference_type)
    # already reversed the packaging move written by apply_sale (it's
    # a `movement_type="sale"`, qty<0 row). The previous legacy block
    # here re-restored it from `sale.packaging_qty` AND added a duplicate
    # StockMovement row, double-counting the packaging stock (the bug
    # in test_saskia_r2_sale_packaging::test_void_sale_restores_packaging_stock).
    # The single canonical path is the StockMovement loop; this block is
    # intentionally not present.

    session.commit()

    return VoidSaleResult(sale_id=sale_id, restored_moves=restored)


__all__ = [
    "ApplySaleResult",
    "CostResult",
    "CycleInRecipeTree",
    "RecipeWithoutYield",
    "VoidSaleResult",
    "apply_sale",
    "batch_recipes_cost",
    "recipe_batch_cost_gs",
    "recipe_unit_cost_gs",
    "resolve_line_target",
    "void_sale",
]
