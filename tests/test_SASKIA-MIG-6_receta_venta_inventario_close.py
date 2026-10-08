"""tests/test_SASKIA-MIG-6_receta_venta_inventario_close.py — SASKIA-MIG-6.

End-to-end chain verification: receta → venta → inventario.

This is a VERIFY-ONLY item from the migration plan (RestoPOS pattern).
The chain is already locked by:

  - test_sale_create_writes_stock_movement.py (StockMovement rows written)
  - test_stock_drop.py (apply_sale drops ingredient stock)
  - test_sale_payments.py (sale_payment rows mirror the cash side)
  - tests/test_cash_sessions.py (cash_session.expected_gs = opening + efectivo)

This module adds ONE end-to-end test that exercises the full chain in
a single transaction: seed a recipe → POST a sale → confirm the
StockMovement audit row exists, the ingredient.stock_qty dropped, and
the sale appears in the expected-amount arithmetic of an open cash
session.

If this test ever fails, AGENTS.md Rule 8 ("Every sale decrements
stock") has been broken and the inventory + cash-side close cannot
trust the receta chain.
"""

from __future__ import annotations

from sqlalchemy.orm import sessionmaker


def _svc_session(session_factory):
    return sessionmaker(bind=session_factory.kw["bind"])()


def _seed_flour_egg_muffin(session_factory):
    """1 product with recipe, 2 ingredients priced. Returns ids."""
    from app.rms.models import Ingredient, Product, Recipe, RecipeLine

    with session_factory() as s:
        flour = Ingredient(name="Harina-Mig6", unit="kg", stock_qty=5.0, purchase_price_gs=5000)
        egg = Ingredient(name="Huevo-Mig6", unit="und", stock_qty=30.0, purchase_price_gs=1500)
        s.add_all([flour, egg])
        s.flush()

        recipe = Recipe(name="Muffin-Mig6", yield_qty=12.0, yield_unit="und")
        s.add(recipe)
        s.flush()
        s.add_all(
            [
                RecipeLine(
                    recipe_id=recipe.id,
                    line_kind="ingredient",
                    line_ref_id=flour.id,
                    qty=0.3,
                ),
                RecipeLine(
                    recipe_id=recipe.id,
                    line_kind="ingredient",
                    line_ref_id=egg.id,
                    qty=2.0,
                ),
            ]
        )
        s.flush()

        product = Product(
            name="Muffin-Mig6",
            portion_label="1 muffin",
            sale_price_gs=8000,
            recipe_id=recipe.id,
        )
        s.add(product)
        s.commit()
        return flour.id, egg.id, product.id


def test_full_receta_venta_inventario_chain(client_with_caja, session_factory):
    """Single end-to-end transaction: seed recipe → POST sale → confirm
    the chain closes on the inventario and the cash side.

    Step 1: seed a recipe + product + ingredients with known stock.
    Step 2: POST /ventas/nueva (default cash payment, abierto caja).
    Step 3: confirm
        a) the StockMovement audit row was written
        b) the ingredient.stock_qty dropped by the expected per-unit qty
        c) the sale's amount_gs landed in sale_payment (efectivo)
        d) the cash session's expected_gs now reflects the sale.
    """
    from app.rms import cash
    from app.rms.models import Ingredient, Sale, SalePayment, StockMovement

    flour_id, egg_id, product_id = _seed_flour_egg_muffin(session_factory)

    # Step 2: POST the sale via the multi-item public route (which
    # also writes the SalePayment row — sale_create single-item does
    # not, per app/routers/sales.py:1669).
    r = client_with_caja.post(
        "/ventas/nueva/multi",
        json={"items": [{"product_id": product_id, "qty": 1}], "payment_method": "efectivo"},
        follow_redirects=False,
    )
    assert r.status_code == 303, f"Expected 303 redirect, got {r.status_code}: {r.text[:200]}"

    # Step 3a: StockMovement audit row exists and references the sale.
    s = _svc_session(session_factory)
    try:
        sale = s.query(Sale).order_by(Sale.id.desc()).first()
        assert sale is not None, "No sale was created"
        moves = (
            s.query(StockMovement)
            .filter_by(reference_type="sale", reference_id=sale.id)
            .all()
        )
        assert len(moves) == 2, (
            f"Expected 2 StockMovement rows (one per recipe line), "
            f"got {len(moves)}: {[(m.ingredient_id, m.qty) for m in moves]}"
        )
        # Both movements must be decrements (negative qty).
        assert all(m.qty < 0 for m in moves), "All movements must be decrements"
        # Per-unit qty = (line.qty / recipe.yield_qty) * sale.qty
        # flour: 0.3/12 * 1 = 0.025, egg: 2.0/12 * 1 = 0.1666...
        ingredient_ids = {m.ingredient_id: m.qty for m in moves}
        assert abs(ingredient_ids[flour_id] - (-0.025)) < 1e-6, (
            f"flour qty {ingredient_ids[flour_id]} != -0.025"
        )
        assert abs(ingredient_ids[egg_id] - (-2.0 / 12)) < 1e-6, (
            f"egg qty {ingredient_ids[egg_id]} != -2/12"
        )

        # Step 3b: ingredient.stock_qty actually dropped.
        flour = s.get(Ingredient, flour_id)
        egg = s.get(Ingredient, egg_id)
        # 5.0 - 0.025 = 4.975
        assert abs(flour.stock_qty - 4.975) < 1e-6, f"flour stock {flour.stock_qty} != 4.975"
        # 30.0 - 2/12 = 29.833...
        assert abs(egg.stock_qty - (30.0 - 2.0 / 12)) < 1e-6, (
            f"egg stock {egg.stock_qty} != 29.833..."
        )

        # Step 3c: sale_payment rows mirror the cash side.
        payments = s.query(SalePayment).filter_by(sale_id=sale.id).all()
        assert len(payments) == 1, f"Expected 1 payment row, got {len(payments)}"
        assert payments[0].method == "efectivo", f"method={payments[0].method} != efectivo"
        assert payments[0].amount_gs == 8000, f"amount={payments[0].amount_gs} != 8000"

        # Step 3d: cash session expected_gs now reflects the sale.
        open_sess = cash.get_open_session(s)
        assert open_sess is not None, "No open cash session"
        # opening was 0, plus one 8000 sale = 8000
        exp = cash.expected_gs(s, open_sess)
        assert exp == 8000, f"expected_gs {exp} != 8000"
    finally:
        s.close()
