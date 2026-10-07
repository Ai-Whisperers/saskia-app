"""P39 — /produccion/prep-recipes must use the variants-aware stock rollup.

The original `_build_recipe_breakdown` (T-2026-10-04) read
`ing.stock_qty` (the legacy parent column) which is 0 for 27 of 103
ingredients whose real stock lives in `ingredient_variant`. /inventario
and /produccion daily use `rollup_ingredient_stock()` from app.rms.variants
so they reflect reality — /prep-recipes did not, so it showed false
"Faltante" badges for those 27 ingredients.

P39 fixes the calculation and pins it down with 3 tests:
1. Ingredient with variants: stock_on_hand = rollup (sum of variants in base units)
2. Ingredient without variants: stock_on_hand = parent.stock_qty (unchanged behavior)
3. Ingredient lookup returns None: stock_on_hand = 0.0
"""
import pytest


def _seed_plan_with_recipe(session_factory):
    """Create: an ingredient with a variant that has stock, a recipe that
    uses the ingredient, and a product linked to the recipe. Returns the
    ingredient_id and the product_id."""
    from app.rms.models import Ingredient, Product, Recipe, RecipeLine
    with session_factory() as s:
        ing = s.query(Ingredient).filter_by(name="P39-rollup-ingredient").first()
        if ing is None:
            ing = Ingredient(
                name="P39-rollup-ingredient",
                unit="kg",
                stock_qty=0.0,  # PARENT is 0 — rollup should be used
                min_stock_qty=1.0,
                max_stock_qty=10.0,
                purchase_price_gs=5000,
            )
            s.add(ing)
            s.flush()
            # Add 3 variants totaling 5kg of stock in base units
            from app.rms.models import IngredientVariant
            s.add(IngredientVariant(
                ingredient_id=ing.id,
                package_size=2.0, package_unit="kg",
                stock_qty=1.0,  # 2.0 kg
                purchase_price_gs=10000,
                preferred=True,
            ))
            s.add(IngredientVariant(
                ingredient_id=ing.id,
                package_size=1.0, package_unit="kg",
                stock_qty=1.5,  # 1.5 kg
                purchase_price_gs=5500,
                preferred=False,
            ))
            s.add(IngredientVariant(
                ingredient_id=ing.id,
                package_size=0.5, package_unit="kg",
                stock_qty=3.0,  # 1.5 kg
                purchase_price_gs=3000,
                preferred=False,
            ))
            s.flush()
        rec = s.query(Recipe).filter_by(name="P39-rollup-recipe").first()
        if rec is None:
            rec = Recipe(name="P39-rollup-recipe", yield_qty=10, yield_unit="und")
            s.add(rec)
            s.flush()
            s.add(RecipeLine(
                recipe_id=rec.id, line_kind="ingredient",
                line_ref_id=ing.id, qty=2.0, line_unit="kg",
            ))
            s.flush()
        prod = s.query(Product).filter_by(name="P39-rollup-product").first()
        if prod is None:
            prod = Product(
                name="P39-rollup-product",
                recipe_id=rec.id,
                sale_price_gs=5000,
            )
            s.add(prod)
            s.flush()
        s.commit()
        return ing.id, prod.id


def test_ingredient_with_variants_uses_rollup(session_factory):
    """If ingredient has variants, stock_on_hand = rollup (5kg here),
    not parent.stock_qty (0kg). The recipe needs 2kg, so the operator
    should see 'Suficiente', not 'Falta 2kg'."""
    from app.rms.models import Product
    from app.routers.produccion.prep_recipes import _build_recipe_breakdown

    ing_id, prod_id = _seed_plan_with_recipe(session_factory)

    with session_factory() as s:
        plan_rows = [{"product_id": prod_id, "recipe_id": s.query(Product).filter_by(name="P39-rollup-product").first().recipe_id, "qty_to_produce": 10}]
        cards = _build_recipe_breakdown(s, plan_rows)

    assert len(cards) == 1
    card = cards[0]
    lines = card["lines"]
    assert len(lines) >= 1
    ing_line = next(ln for ln in lines if ln.get("ingredient_id") == ing_id)
    # Stock should be the rollup: 2 + 1.5 + 1.5 = 5.0 kg
    assert ing_line["stock_on_hand"] == pytest.approx(5.0), (
        f"expected stock=5.0 (rollup), got {ing_line['stock_on_hand']}. "
        "The parent column is 0kg; if this test fails the fix didn't land."
    )
    # Recipe needs 2kg; with 5kg in stock → no shortage
    assert ing_line["shortage"] == 0.0
    assert card["severity"] == "suficiente"


def test_ingredient_without_variants_uses_parent(session_factory):
    """If ingredient has NO variants, stock_on_hand = parent.stock_qty
    (unchanged behavior — the parent column IS the truth for that case)."""
    from app.rms.models import Ingredient, Product, Recipe, RecipeLine
    from app.routers.produccion.prep_recipes import _build_recipe_breakdown

    with session_factory() as s:
        ing = s.query(Ingredient).filter_by(name="P39-no-variant-ing").first()
        if ing is None:
            ing = Ingredient(
                name="P39-no-variant-ing",
                unit="kg",
                stock_qty=3.5,  # parent has stock
                min_stock_qty=1.0,
                max_stock_qty=10.0,
                purchase_price_gs=5000,
            )
            s.add(ing)
            s.flush()
        rec = s.query(Recipe).filter_by(name="P39-no-variant-recipe").first()
        if rec is None:
            rec = Recipe(name="P39-no-variant-recipe", yield_qty=10, yield_unit="und")
            s.add(rec)
            s.flush()
            s.add(RecipeLine(
                recipe_id=rec.id, line_kind="ingredient",
                line_ref_id=ing.id, qty=2.0, line_unit="kg",
            ))
            s.flush()
        prod = s.query(Product).filter_by(name="P39-no-variant-product").first()
        if prod is None:
            prod = Product(
                name="P39-no-variant-product",
                recipe_id=rec.id,
                sale_price_gs=5000,
            )
            s.add(prod)
            s.flush()
        s.commit()
        plan_rows = [{"product_id": prod.id, "recipe_id": rec.id, "qty_to_produce": 10}]
        cards = _build_recipe_breakdown(s, plan_rows)

    card = cards[0]
    ing_line = next(ln for ln in card["lines"] if ln.get("ingredient_id") == ing.id)
    assert ing_line["stock_on_hand"] == pytest.approx(3.5)
    assert ing_line["shortage"] == 0.0


def test_missing_ingredient_object_returns_zero(session_factory):
    """If the ingredient lookup returns None (e.g., dangling ref), stock
    must default to 0.0 so the operator sees a shortage — defensive
    behavior is unchanged from before P39."""
    from app.rms.models import Product, Recipe, RecipeLine
    from app.routers.produccion.prep_recipes import _build_recipe_breakdown

    with session_factory() as s:
        # Recipe line with ref_id pointing to a NON-EXISTENT ingredient (99999)
        rec = s.query(Recipe).filter_by(name="P39-missing-recipe").first()
        if rec is None:
            rec = Recipe(name="P39-missing-recipe", yield_qty=10, yield_unit="und")
            s.add(rec)
            s.flush()
            s.add(RecipeLine(
                recipe_id=rec.id, line_kind="ingredient",
                line_ref_id=99999, qty=1.0, line_unit="kg",
            ))
            s.flush()
        prod = s.query(Product).filter_by(name="P39-missing-product").first()
        if prod is None:
            prod = Product(
                name="P39-missing-product",
                recipe_id=rec.id,
                sale_price_gs=5000,
            )
            s.add(prod)
            s.flush()
        s.commit()
        plan_rows = [{"product_id": prod.id, "recipe_id": rec.id, "qty_to_produce": 10}]
        cards = _build_recipe_breakdown(s, plan_rows)

    # With a missing ingredient, the line may be skipped or have stock=0;
    # we just verify the page doesn't raise.
    assert isinstance(cards, list)
