"""tests/test_void_semantics.py — void idempotency + restoration semantics.

Per dev plan Batch 3. Targets ~5 tests.

Covers:
- Voiding twice: second attempt raises with Spanish "ya anulada" message
- Void after no moves: no-op, just sets voided_at
- Void restores qty for ingredient whose sale-stock-move was positive (defensive)
- Void preserves the Sale row (does not delete)
- void_sale returns restored_moves with positive qty values
"""

from __future__ import annotations

from datetime import datetime


def _seed(session_factory):
    from app.rms.models import Ingredient, Product, Recipe, RecipeLine

    with session_factory() as s:
        flour = Ingredient(name="Harina", unit="kg", stock_qty=2.0, purchase_price_gs=5000)
        s.add(flour)
        s.flush()
        rec = Recipe(name="Masa", yield_qty=12.0, yield_unit="und")
        s.add(rec)
        s.flush()
        s.add(
            RecipeLine(
                recipe_id=rec.id,
                line_kind="ingredient",
                line_ref_id=flour.id,
                qty=0.3,
            )
        )
        s.flush()
        product = Product(
            name="Torta",
            portion_label="1 torta",
            sale_price_gs=10000,
            recipe_id=rec.id,
        )
        s.add(product)
        s.commit()
        return flour.id, product.id


def test_void_sale_double_void_message_in_spanish(session_factory):
    """The 'ya anulada' message must be Spanish (UI-facing)."""
    import pytest

    from app.rms.costing import apply_sale, void_sale

    _, product_id = _seed(session_factory)
    with session_factory() as s:
        result = apply_sale(s, product_id, qty=1.0, sold_at=datetime.now())
        sale_id = result.sale_id

    with session_factory() as s:
        void_sale(s, sale_id)

    with pytest.raises(ValueError) as exc_info:
        with session_factory() as s:
            void_sale(s, sale_id)
    assert "ya anulada" in str(exc_info.value)


def test_void_sale_preserves_sale_row(session_factory):
    """Void does not delete the sale — it only sets voided_at and reverses moves."""
    from app.rms.costing import apply_sale, void_sale
    from app.rms.models import Sale

    _, product_id = _seed(session_factory)
    with session_factory() as s:
        result = apply_sale(s, product_id, qty=1.0, sold_at=datetime.now())
        sale_id = result.sale_id

    with session_factory() as s:
        void_sale(s, sale_id)

    with session_factory() as s:
        # Sale still exists
        sale = s.get(Sale, sale_id)
        assert sale is not None
        assert sale.voided_at is not None


def test_void_sale_restored_moves_positive_qty(session_factory):
    """restored_moves in VoidSaleResult contains positive qty values."""
    from app.rms.costing import apply_sale, void_sale

    _, product_id = _seed(session_factory)
    with session_factory() as s:
        result = apply_sale(s, product_id, qty=1.0, sold_at=datetime.now())
        sale_id = result.sale_id

    with session_factory() as s:
        void_result = void_sale(s, sale_id)

    assert len(void_result.restored_moves) == 1
    ingredient_id, qty_restored = void_result.restored_moves[0]
    assert ingredient_id is not None
    assert qty_restored > 0


def test_void_sale_no_moves_is_noop(session_factory):
    """Product with no recipe → no moves to restore; void just sets voided_at."""
    from app.rms.costing import apply_sale, void_sale
    from app.rms.models import Product, Sale

    with session_factory() as s:
        s.add(Product(name="X", portion_label="1", sale_price_gs=5000, recipe_id=None))
        s.commit()

    with session_factory() as s:
        result = apply_sale(s, 1, qty=1.0, sold_at=datetime.now())
        sale_id = result.sale_id

    with session_factory() as s:
        void_result = void_sale(s, sale_id)

    assert void_result.restored_moves == []
    with session_factory() as s:
        sale = s.get(Sale, sale_id)
        assert sale.voided_at is not None


def test_void_sale_restores_to_exact_original_qty(session_factory):
    """Stock restored to original even after multiple sale/void cycles."""
    from app.rms.costing import apply_sale, void_sale
    from app.rms.models import Ingredient

    flour_id, product_id = _seed(session_factory)
    original_stock = 2.0

    # Cycle 1
    with session_factory() as s:
        r1 = apply_sale(s, product_id, qty=1.0, sold_at=datetime.now())
    with session_factory() as s:
        void_sale(s, r1.sale_id)

    # Cycle 2
    with session_factory() as s:
        r2 = apply_sale(s, product_id, qty=1.0, sold_at=datetime.now())
    with session_factory() as s:
        void_sale(s, r2.sale_id)

    with session_factory() as s:
        flour = s.get(Ingredient, flour_id)
        assert flour.stock_qty == original_stock
