"""P37 — operator-friendly substitution suggestions.

The original _build_substitution_suggestions (T-2026-10-04) was a flat
dump of "Falta X para Y → 3 recetas con similitud 60%/55%/45%". The
suggested recipes were never cross-checked against current stock, so it
often suggested swaps that were themselves unbakeable. The list was
also long, unsorted, and used developer jargon ("similitud ≥0.3").

P37 rewrites both the backend and the template:
- Suggestions are grouped by the short INGREDIENT (not by recipe).
- For each substitute recipe, we verify its own ingredients are
  actually in stock — bakeable ones get a "✓ podés hornearla" badge,
  unbakeable ones get "⚠ falta N más".
- Suggestions are sorted by shortage_qty desc (biggest problem first).
- The lead action is "buy more" (link to /reorder), with substitutes
  as the alternative. The dev jargon is gone.

This test pins down the new shape and the bakeable-verify behavior.
"""
import pytest


def _seed_full_fixture(s):
    """Seed: 1 short ingredient, 1 long ingredient, 2 recipes, 2 products.
    Idempotent — caller is responsible for s.commit() afterwards.
    """
    from app.rms.models import Ingredient, Recipe, RecipeLine, Product
    short = s.query(Ingredient).filter_by(name="P37-short-ing").first()
    if short is None:
        short = Ingredient(
            name="P37-short-ing", unit="kg",
            stock_qty=0.0, min_stock_qty=1.0, max_stock_qty=2.0,
            purchase_price_gs=5000,
        )
        s.add(short)
        s.flush()
    long_ing = s.query(Ingredient).filter_by(name="P37-long-ing").first()
    if long_ing is None:
        long_ing = Ingredient(
            name="P37-long-ing", unit="kg",
            stock_qty=5.0, min_stock_qty=1.0, max_stock_qty=10.0,
            purchase_price_gs=2000,
        )
        s.add(long_ing)
        s.flush()
    rec_orig = s.query(Recipe).filter_by(name="P37-original-recipe").first()
    if rec_orig is None:
        rec_orig = Recipe(name="P37-original-recipe", yield_qty=12, yield_unit="und")
        s.add(rec_orig)
        s.flush()
        s.add(RecipeLine(
            recipe_id=rec_orig.id, line_kind="ingredient",
            line_ref_id=short.id, qty=1.0, line_unit="kg",
        ))
        s.add(RecipeLine(
            recipe_id=rec_orig.id, line_kind="ingredient",
            line_ref_id=long_ing.id, qty=0.5, line_unit="kg",
        ))
        s.flush()
    rec_sub = s.query(Recipe).filter_by(name="P37-substitute-recipe").first()
    if rec_sub is None:
        rec_sub = Recipe(name="P37-substitute-recipe", yield_qty=10, yield_unit="und")
        s.add(rec_sub)
        s.flush()
        s.add(RecipeLine(
            recipe_id=rec_sub.id, line_kind="ingredient",
            line_ref_id=long_ing.id, qty=0.8, line_unit="kg",
        ))
        s.flush()
    orig_prod = s.query(Product).filter_by(name="P37-original-product").first()
    if orig_prod is None:
        orig_prod = Product(
            name="P37-original-product", recipe_id=rec_orig.id, sale_price_gs=5000,
        )
        s.add(orig_prod)
        s.flush()
    sub_prod = s.query(Product).filter_by(name="P37-substitute-product").first()
    if sub_prod is None:
        sub_prod = Product(
            name="P37-substitute-product", recipe_id=rec_sub.id, sale_price_gs=5000,
        )
        s.add(sub_prod)
        s.flush()
    return {
        "short_id": short.id, "long_id": long_ing.id,
        "orig_prod_id": orig_prod.id, "sub_prod_id": sub_prod.id,
        "orig_prod_name": orig_prod.name, "sub_prod_name": sub_prod.name,
    }


@pytest.fixture
def seed_substitution_fixture(session_factory):
    with session_factory() as s:
        data = _seed_full_fixture(s)
        s.commit()
    return data


def test_substitutions_grouped_by_ingredient(session_factory, seed_substitution_fixture):
    """Suggestions must be grouped by short ingredient, with shortage
    qty + affected recipe list per ingredient. (One row per short
    ingredient, NOT one row per recipe.)"""
    from app.routers.produccion.analytics import _build_substitution_suggestions
    from app.rms.production import ProductionLine

    fx = seed_substitution_fixture
    short_lines = [ProductionLine(
        ingredient_id=fx["short_id"], ingredient_name="P37-short-ing",
        unit="kg", qty_required=1.0, stock_on_hand=0.0, qty_to_buy=1.0,
    )]
    plan_rows_view = [
        {"product_id": fx["orig_prod_id"], "product_name": fx["orig_prod_name"]},
    ]

    with session_factory() as s:
        suggestions = _build_substitution_suggestions(s, short_lines, plan_rows_view)

    # ONE suggestion for the short ingredient (not 1 per recipe)
    assert len(suggestions) == 1, f"expected 1 suggestion, got {len(suggestions)}"
    s0 = suggestions[0]
    assert s0["ingredient_name"] == "P37-short-ing"
    assert s0["shortage_qty"] == 1.0
    assert s0["unit"] == "kg"
    assert s0["n_recipes"] == 1
    assert fx["orig_prod_name"] in s0["shortage_recipes"]

    # Substitute marked bakeable (its only ingredient is stocked)
    sub_names = [sub["product_name"] for sub in s0["substitutes"]]
    assert fx["sub_prod_name"] in sub_names, (
        f"expected substitute-product in suggestions, got {sub_names}"
    )
    sub_row = next(sub for sub in s0["substitutes"] if sub["product_name"] == fx["sub_prod_name"])
    assert sub_row["own_ingredients_ok"] is True
    assert sub_row["own_short_ingredients"] == []


def test_substitute_marked_unbakeable_when_its_own_ingredient_is_short(session_factory, seed_substitution_fixture):
    """If a candidate substitute recipe needs an ingredient that is
    ALSO out of stock, mark it as not-bakeable so the operator
    doesn't pick it."""
    from app.routers.produccion.analytics import _build_substitution_suggestions
    from app.rms.production import ProductionLine
    from app.rms.models import Ingredient

    fx = seed_substitution_fixture
    # Empty the long ingredient's stock
    with session_factory() as s:
        long_ing = s.get(Ingredient, fx["long_id"])
        long_ing.stock_qty = 0.0
        s.commit()

    short_lines = [ProductionLine(
        ingredient_id=fx["short_id"], ingredient_name="P37-short-ing",
        unit="kg", qty_required=1.0, stock_on_hand=0.0, qty_to_buy=1.0,
    )]
    plan_rows_view = [
        {"product_id": fx["orig_prod_id"], "product_name": fx["orig_prod_name"]},
    ]

    with session_factory() as s:
        suggestions = _build_substitution_suggestions(s, short_lines, plan_rows_view)

    s0 = suggestions[0]
    sub_row = next(sub for sub in s0["substitutes"] if sub["product_name"] == fx["sub_prod_name"])
    assert sub_row["own_ingredients_ok"] is False
    assert "P37-long-ing" in sub_row["own_short_ingredients"]


def test_no_substitute_recipe_that_also_needs_short_ingredient(session_factory, seed_substitution_fixture):
    """Substitute candidates that need the SAME short ingredient
    must be excluded — they're not actual substitutes, they're
    parallel problems (and would still be unbakeable)."""
    from app.routers.produccion.analytics import _build_substitution_suggestions
    from app.rms.production import ProductionLine
    from app.rms.models import Recipe, RecipeLine, Product

    fx = seed_substitution_fixture

    # Create a "fake substitute" recipe that ALSO uses the short ingredient
    with session_factory() as s:
        rec_fake = Recipe(name="P37-fake-substitute", yield_qty=10, yield_unit="und")
        s.add(rec_fake)
        s.flush()
        s.add(RecipeLine(
            recipe_id=rec_fake.id, line_kind="ingredient",
            line_ref_id=fx["short_id"], qty=0.5, line_unit="kg",
        ))
        s.add(RecipeLine(
            recipe_id=rec_fake.id, line_kind="ingredient",
            line_ref_id=fx["long_id"], qty=0.3, line_unit="kg",
        ))
        s.flush()
        fake_prod = Product(
            name="P37-fake-substitute-product",
            recipe_id=rec_fake.id, sale_price_gs=5000,
        )
        s.add(fake_prod)
        s.commit()

    short_lines = [ProductionLine(
        ingredient_id=fx["short_id"], ingredient_name="P37-short-ing",
        unit="kg", qty_required=1.0, stock_on_hand=0.0, qty_to_buy=1.0,
    )]
    plan_rows_view = [
        {"product_id": fx["orig_prod_id"], "product_name": fx["orig_prod_name"]},
    ]

    with session_factory() as s:
        suggestions = _build_substitution_suggestions(s, short_lines, plan_rows_view)

    s0 = suggestions[0]
    sub_names = [sub["product_name"] for sub in s0["substitutes"]]
    assert "P37-fake-substitute-product" not in sub_names, (
        f"fake substitute (which also needs the short ingredient) must not appear: {sub_names}"
    )


def test_suggestions_sorted_by_shortage_qty_desc(session_factory, seed_substitution_fixture):
    """When multiple ingredients are short, the biggest shortage
    must come first so the operator attacks the biggest problem first."""
    from app.routers.produccion.analytics import _build_substitution_suggestions
    from app.rms.production import ProductionLine
    from app.rms.models import Ingredient

    fx = seed_substitution_fixture

    # Add a SECOND short ingredient so we can compare sort order
    with session_factory() as s:
        ing2 = s.query(Ingredient).filter_by(name="P37-short-2").first()
        if ing2 is None:
            ing2 = Ingredient(
                name="P37-short-2", unit="kg",
                stock_qty=0.0, min_stock_qty=1.0, max_stock_qty=2.0,
                purchase_price_gs=4000,
            )
            s.add(ing2)
            s.commit()

    short_lines = [
        ProductionLine(
            ingredient_id=fx["short_id"], ingredient_name="P37-short-ing",
            unit="kg", qty_required=1.0, stock_on_hand=0.0, qty_to_buy=1.0,
        ),
        ProductionLine(
            ingredient_id=ing2.id, ingredient_name="P37-short-2",
            unit="kg", qty_required=5.0, stock_on_hand=0.0, qty_to_buy=5.0,
        ),
    ]
    plan_rows_view = [
        {"product_id": fx["orig_prod_id"], "product_name": fx["orig_prod_name"]},
    ]

    with session_factory() as s:
        suggestions = _build_substitution_suggestions(s, short_lines, plan_rows_view)

    # Two suggestions, biggest shortage first
    assert len(suggestions) == 2
    assert suggestions[0]["shortage_qty"] >= suggestions[1]["shortage_qty"]
    assert suggestions[0]["ingredient_name"] == "P37-short-2"  # 5.0 kg vs 1.0 kg
