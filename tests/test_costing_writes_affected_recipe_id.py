"""Tests that costing.py populates affected_recipe_id on StockMovement rows.

This is the write-side bridge for BACKLOG #1 (partial). When costing
records the dual-write for a sale, BOTH SaleStockMove AND the new
StockMovement row must carry the affected_recipe_id, so the read
path can serve from stock_movement alone (after migration 091
backfills historical rows).
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.rms.models import (
    Ingredient,
    Product,
    Recipe,
    RecipeLine,
    StockMovement,
)


def test_complete_sale_writes_affected_recipe_id_on_stock_movement(session_factory):
    """costing.complete_sale() must populate affected_recipe_id on
    the new StockMovement row it inserts (not just on SaleStockMove)."""
    from app.rms.costing import apply_sale

    session = session_factory()
    try:
        ing = Ingredient(
            name="CostingAffected", unit="kg", stock_qty=10, purchase_price_gs=1000
        )
        prod = None  # set after Recipe is created
        rec = Recipe(name="r_costing_affected", yield_qty=1, yield_unit="und")
        prod = Product(
            name="costing_affected_prod",
            sale_price_gs=5000,
            recipe_id=None,  # set after Recipe is flushed
        )
        session.add_all([ing, prod, rec])
        session.flush()
        prod.recipe_id = rec.id
        session.add(
            RecipeLine(
                recipe_id=rec.id,
                line_kind="ingredient",
                line_ref_id=ing.id,
                qty=1.0,
                line_unit="kg",
            )
        )
        session.commit()

        result = apply_sale(
            session=session,
            product_id=prod.id,
            qty=1,
            sold_at=datetime.now(timezone.utc),
            payment_method="efectivo",
            channel="mostrador",
        )
        session.commit()

        # Inspect the StockMovement rows created by the dual-write.
        sm_rows = session.query(StockMovement).filter_by(reference_id=result.sale_id).all()
        assert sm_rows, "complete_sale did not create any StockMovement rows"
        for row in sm_rows:
            assert row.affected_recipe_id == rec.id, (
                f"StockMovement row {row.id} has "
                f"affected_recipe_id={row.affected_recipe_id}, expected {rec.id}. "
                "costing.py must populate this field (BACKLOG #1 complete)."
            )

        # BACKLOG #1 (complete): SaleStockMove table is gone — the
        # test only verifies it is NOT being written to. On fresh
        # test DBs (post-092), the table doesn't even exist, which is
        # the strongest possible assertion that it's not being used.
        # We don't probe by name (cross-engine); instead we verify
        # the SaleStockMove class is the abstract stub that raises
        # on instantiation (the intended runtime guard).
        from app.rms.models import SaleStockMove
        import pytest
        with pytest.raises(TypeError):
            SaleStockMove(
                sale_id=result.sale_id,
                affected_recipe_id=1,
                ingredient_id=1,
                qty_delta=-1.0,
            )
    finally:
        session.close()