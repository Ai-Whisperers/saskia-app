"""tests/test_sale_create_writes_stock_movement.py

REGRESSION TEST for AGENTS.md Hard Rule 8 ("Every sale decrements stock").

This test locks the contract: when a sale is created via the HTTP route
`/ventas/nueva`, the request must:
  1. Decrement the ingredient's `stock_qty` field (covered by
     `test_sale_create_drops_stock` in test_routes.py).
  2. Write a `StockMovement` audit row referencing the sale.

Background: 2026-10-07 review of `app/routers/sales.py` found that
`sale_create` does NOT directly write `StockMovement` rows. It delegates
to `apply_sale()` in `app/rms/costing.py`, which DOES write the rows.

A future refactor that moves the audit-row write responsibility back to
the router (or skips it entirely) would silently break the stock
audit trail. This test catches that.

The test is intentionally narrow: it asserts the existence and shape of
the audit row, not its semantic correctness (that's covered by
test_stock_drop.py). It is also explicit about why it exists so future
agents don't remove it as "covered by test_stock_drop.py".
"""

from __future__ import annotations


def _seed_simple(session_factory):
    """1 product with recipe, 2 ingredients priced. Returns product_id."""
    from app.rms.models import Ingredient, Product, Recipe, RecipeLine

    with session_factory() as s:
        flour = Ingredient(name="Harina", unit="kg", stock_qty=2.0, purchase_price_gs=5000)
        egg = Ingredient(name="Huevo", unit="und", stock_qty=20.0, purchase_price_gs=1500)
        s.add_all([flour, egg])
        s.flush()

        recipe = Recipe(name="Muffin", yield_qty=12.0, yield_unit="und")
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
            name="Muffin",
            portion_label="1 muffin",
            sale_price_gs=8000,
            recipe_id=recipe.id,
        )
        s.add(product)
        s.commit()
        return product.id


def test_sale_create_writes_stock_movement_row(client, session_factory):
    """POST /ventas/nueva → at least one StockMovement row written.

    Verifies:
      - At least one StockMovement row exists for the sale
      - The row's reference_id matches the new sale.id
      - The row's reference_type is "sale"
      - The row's movement_type is "sale"
      - The row's qty is negative (decrement, not increment)
    """
    from app.rms.models import Sale, StockMovement

    product_id = _seed_simple(session_factory)

    # POST the sale via the public route
    r = client.post(
        "/ventas/nueva",
        data={
            "product_id": str(product_id),
            "qty": "1",
            "sold_at": "",
            "notes": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303, f"Expected 303 redirect, got {r.status_code}"

    # Read the sale and the stock_movement rows
    with session_factory() as s:
        # Get the most recent sale (id 1 in fresh fixture)
        sale = s.query(Sale).order_by(Sale.id.desc()).first()
        assert sale is not None, "No sale row was written"
        assert sale.product_id == product_id

        # Now look for the matching StockMovement rows
        moves = (
            s.query(StockMovement)
            .filter_by(
                reference_id=sale.id,
                reference_type="sale",
            )
            .all()
        )

        assert len(moves) >= 1, (
            f"Expected at least 1 StockMovement row for sale.id={sale.id}, "
            f"got {len(moves)}. This is the AGENTS.md Hard Rule 8 contract: "
            f"every sale MUST write a StockMovement audit row. The router "
            f"delegates to apply_sale() in app/rms/costing.py — verify the "
            f"delegation is intact."
        )

        # All matching rows must be decrements (negative qty)
        for m in moves:
            assert m.movement_type == "sale", (
                f"Expected movement_type='sale', got {m.movement_type!r}"
            )
            assert m.qty is not None and m.qty < 0, (
                f"Expected negative qty (decrement), got {m.qty!r}"
            )
            assert m.ingredient_id is not None, (
                "StockMovement.ingredient_id must be set for a sale decrement"
            )


def test_sale_create_writes_one_stock_movement_per_recipe_line(client, session_factory):
    """POST /ventas/nueva for a 2-ingredient recipe → exactly 2 StockMovement rows."""
    from app.rms.models import StockMovement

    product_id = _seed_simple(session_factory)

    r = client.post(
        "/ventas/nueva",
        data={
            "product_id": str(product_id),
            "qty": "1",
            "sold_at": "",
            "notes": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303

    with session_factory() as s:
        moves = (
            s.query(StockMovement)
            .filter_by(
                reference_type="sale",
            )
            .all()
        )
        # The seed has 2 ingredient lines (Harina, Huevo)
        assert len(moves) == 2, (
            f"Expected 2 StockMovement rows (one per recipe line), "
            f"got {len(moves)}: {[(m.ingredient_id, m.qty) for m in moves]}"
        )


def test_sale_create_no_recipe_writes_no_stock_movement(client, session_factory):
    """Product with no recipe: sale is saved, but no StockMovement row written.

    Documents the intentional behavior: a product with `recipe_id=None` is a
    "mystery" item (e.g. variable-weight, custom cake). The sale is recorded
    for revenue tracking, but no stock decrement happens because there's no
    recipe to walk.

    The AGENTS.md Hard Rule 8 says "every sale decrements stock" but this
    case is the documented exception. If you add StockMovement rows here,
    that breaks the contract.
    """
    from app.rms.models import Product, StockMovement

    with session_factory() as s:
        s.add(Product(name="Mystery", portion_label="1", sale_price_gs=5000, recipe_id=None))
        s.commit()

    r = client.post(
        "/ventas/nueva",
        data={
            "product_id": "1",
            "qty": "1",
            "sold_at": "",
            "notes": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303, f"Expected 303, got {r.status_code}"

    with session_factory() as s:
        moves = (
            s.query(StockMovement)
            .filter_by(
                reference_type="sale",
            )
            .all()
        )
        assert len(moves) == 0, (
            f"Expected 0 StockMovement rows for product with no recipe, "
            f"got {len(moves)}: {[(m.ingredient_id, m.qty) for m in moves]}"
        )
