"""P36 — bulk-fill variant-aware top-up regression test.

Background (2026-10-07 audit, Ivan):
The first version of POST /inventario/bulk-fill-to-2x-min only wrote
delta to Ingredient.stock_qty (the legacy parent column) and never
touched the variant. That made parent.stock_qty diverge from the
variant rollup, which produced false "Faltante" badges on
/produccion/prep-recipes (which reads parent.stock_qty directly).

This test pins down the correct behavior: bulk-fill must add the
delta to the preferred variant's stock_qty (in package units) and
re-sync the parent from the new rollup.
"""

import pytest


@pytest.fixture
def seed_variant_ingredient(session_factory):
    """Create a variant-bearing ingredient and a simple ingredient,
    both below 2x min, to exercise the bulk-fill endpoint."""
    from app.rms.models import Ingredient, IngredientVariant

    with session_factory() as s:
        # Variant-bearing ingredient
        ing = s.query(Ingredient).filter_by(name="P36-queso").first()
        if ing is None:
            ing = Ingredient(
                name="P36-queso",
                unit="kg",
                stock_qty=0.0,
                min_stock_qty=1.0,
                max_stock_qty=3.0,
                purchase_price_gs=36000,
            )
            s.add(ing)
            s.flush()
            s.add(
                IngredientVariant(
                    ingredient_id=ing.id,
                    package_size=1.0,
                    package_unit="kg",
                    purchase_price_gs=35000,
                    stock_qty=0.0,
                    preferred=True,
                )
            )
        # Simple ingredient (no variants)
        ing_simple = s.query(Ingredient).filter_by(name="P36-harina").first()
        if ing_simple is None:
            ing_simple = Ingredient(
                name="P36-harina",
                unit="kg",
                stock_qty=0.0,
                min_stock_qty=1.0,
                purchase_price_gs=4500,
            )
            s.add(ing_simple)
        s.commit()
        return {"queso_id": ing.id, "harina_id": ing_simple.id}


def test_bulk_fill_writes_to_variant_and_resyncs_parent(
    authed_client, session_factory, seed_variant_ingredient
):
    """After bulk-fill, parent.stock_qty must equal the rollup
    (sum of variant.stock_qty × package_size) for variant-bearing
    ingredients, and equal the target for simple ingredients.
    """
    from app.rms.models import Ingredient, IngredientVariant

    queso_id = seed_variant_ingredient["queso_id"]
    harina_id = seed_variant_ingredient["harina_id"]

    r = authed_client.post("/inventario/bulk-fill-to-2x-min", follow_redirects=False)
    assert r.status_code in (303, 307), f"bulk-fill should redirect, got {r.status_code}"

    with session_factory() as s:
        ing = s.get(Ingredient, queso_id)
        var = s.query(IngredientVariant).filter_by(ingredient_id=queso_id).first()
        # Variant should have packages added (target=3 kg, package=1 kg → 3 packages)
        assert var.stock_qty >= 3.0, f"variant should have ≥3 packages, got {var.stock_qty}"
        # Parent must equal the rollup
        rollup = var.stock_qty * var.package_size
        assert abs(ing.stock_qty - rollup) < 0.01, (
            f"parent.stock_qty={ing.stock_qty} should equal rollup={rollup}"
        )

        # Simple ingredient parent must be 2.0 (2 × min=1)
        ing_simple = s.get(Ingredient, harina_id)
        assert abs(ing_simple.stock_qty - 2.0) < 0.01, (
            f"simple parent should be 2.0 (2x min), got {ing_simple.stock_qty}"
        )


def test_bulk_fill_is_idempotent(authed_client, session_factory, seed_variant_ingredient):
    """Running bulk-fill twice should be a no-op the second time."""
    authed_client.post("/inventario/bulk-fill-to-2x-min", follow_redirects=False)
    with session_factory() as s:
        from sqlalchemy import text

        before = s.execute(
            text(
                "SELECT COUNT(*) FROM stock_movement "
                "WHERE movement_type='reorder' AND reason LIKE 'Llenado bulk%'"
            )
        ).scalar()
    authed_client.post("/inventario/bulk-fill-to-2x-min", follow_redirects=False)
    with session_factory() as s:
        from sqlalchemy import text

        after = s.execute(
            text(
                "SELECT COUNT(*) FROM stock_movement "
                "WHERE movement_type='reorder' AND reason LIKE 'Llenado bulk%'"
            )
        ).scalar()
    assert after == before, f"idempotent re-run wrote {after - before} new bulk-fill rows"
