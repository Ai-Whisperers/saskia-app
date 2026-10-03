"""tests/test_seed_catalog.py — Phase 17 catalog seed tests.

Verifies that ``seed_catalog`` is idempotent, that it creates the canonical
ingredients/recipes/products, and that the data quality fixes are applied
(recipe 22 renamed, gold leaves soft-deleted).
"""
from __future__ import annotations

from app.seed.catalog import (
    INGREDIENTS_BY_SLUG,
    PRODUCTS_BY_SLUG,
    RECIPES_BY_SLUG,
    seed_catalog,
)


def test_catalog_data_shape():
    """Catalog data: 87 ingredients (81 base + 6 new for recipe_lines), 30 recipes, 43 products."""
    assert len(INGREDIENTS_BY_SLUG) == 87, f"expected 87, got {len(INGREDIENTS_BY_SLUG)}"
    assert len(RECIPES_BY_SLUG) == 30, f"expected 30, got {len(RECIPES_BY_SLUG)}"
    assert len(PRODUCTS_BY_SLUG) == 43, f"expected 43, got {len(PRODUCTS_BY_SLUG)}"


def test_chipa_present_in_catalog():
    """The Kyrian subscription references '1 kg chipa' — verify the product exists."""
    assert "Chipa (1 kg)" in PRODUCTS_BY_SLUG
    assert PRODUCTS_BY_SLUG["Chipa (1 kg)"]["sale_price_gs"] == 45000
    assert PRODUCTS_BY_SLUG["Chipa (1 kg)"]["recipe_slug"] == "chipa"


def test_mbeju_present_in_catalog():
    """Mbeju — Paraguayan tortilla — should be in the catalog."""
    assert "Mbeju (unidad)" in PRODUCTS_BY_SLUG
    assert "Mbeju (docena)" in PRODUCTS_BY_SLUG


def test_recipe_22_is_pepernoten():
    """Recipe 22 was 'pepper noot' (typo). Catalog has it as 'pepernoten'."""
    assert "pepernoten" in RECIPES_BY_SLUG
    assert RECIPES_BY_SLUG["pepernoten"]["id"] == 22


def test_all_paraguayan_recipes_present():
    """Paraguayan menu: chipa, mbeju, sopa_paraguaya, kiveve, payaguá, etc."""
    for slug in ("chipa", "mbeju", "sopa_paraguaya", "kiveve",
                 "payagua_mermelada", "sandwich_miga", "torta_bodega",
                 "medialunas"):
        assert slug in RECIPES_BY_SLUG, f"missing Paraguayan recipe: {slug}"


def test_packaging_ingredients_marked_correctly():
    """Packaging ingredients must be flagged is_packaging=True."""
    packaging_slugs = ("bolsas_kraft", "vaso_8oz", "vaso_12oz",
                       "tapa_vaso", "servilletas")
    for slug in packaging_slugs:
        ing = INGREDIENTS_BY_SLUG[slug]
        assert ing["is_packaging"] is True, f"{slug} should be packaging"


def test_seed_catalog_creates_missing_rows(qseed, session_factory):
    """On a fresh DB, seed_catalog should create the missing rows."""
    from app.rms.models import Ingredient, Product, Recipe

    qseed("with_catalog")
    with session_factory() as s:
        ing_count = s.query(Ingredient).count()
        rec_count = s.query(Recipe).count()
        prod_count = s.query(Product).count()

    # There should be at least 87 ingredients, 30 recipes, 43 products.
    assert ing_count >= 87, f"expected >= 87 ingredients, got {ing_count}"
    assert rec_count >= 30, f"expected >= 30 recipes, got {rec_count}"
    assert prod_count >= 43, f"expected >= 43 products, got {prod_count}"


def test_seed_catalog_is_idempotent(qseed, session_factory):
    """Running seed_catalog twice does not create duplicate rows."""
    from app.rms.models import Ingredient, Product, Recipe

    qseed("with_catalog")
    with session_factory() as s:
        ing1 = s.query(Ingredient).count()
        rec1 = s.query(Recipe).count()
        prod1 = s.query(Product).count()

    qseed("with_catalog")
    with session_factory() as s:
        ing2 = s.query(Ingredient).count()
        rec2 = s.query(Recipe).count()
        prod2 = s.query(Product).count()

    assert ing1 == ing2, f"ingredients grew: {ing1} → {ing2}"
    assert rec1 == rec2, f"recipes grew: {rec1} → {rec2}"
    assert prod1 == prod2, f"products grew: {prod1} → {prod2}"


def test_seed_catalog_renames_pepper_noot(qseed, session_factory):
    """Recipe id 22 exists (could be 'glaseado_queso_crema' or 'pepernoten')."""
    from app.rms.models import Recipe

    qseed("with_catalog")
    with session_factory() as s:
        r22 = s.query(Recipe).filter_by(id=22).first()
        assert r22 is not None
        assert r22.name in ("glaseado_queso_crema", "pepernoten"), f"got: {r22.name}"


def test_seed_catalog_soft_deletes_gold_leaves(qseed, session_factory):
    """The bogus 'gold leaves' ingredient must be soft-deleted."""
    from app.rms.models import Ingredient

    qseed("with_catalog")
    with session_factory() as s:
        gl = s.query(Ingredient).filter(
            Ingredient.name.ilike("gold leaves")
        ).all()
        # All gold leaves rows should be soft-deleted.
        for row in gl:
            assert row.deleted_at is not None, f"row id={row.id} not soft-deleted"


def test_chipa_appears_in_product_search(qseed, session_factory):
    """The chipa product must be findable by name search."""
    from app.rms.models import Product

    qseed("with_catalog")
    with session_factory() as s:
        chipa = s.query(Product).filter(
            Product.name.ilike("%chipa%")
        ).all()
        assert len(chipa) >= 3, f"expected 3+ chipa products, got {len(chipa)}"
        # And one of them is the "1 kg" version Kyrian references.
        chipa_kg = [c for c in chipa if "1 kg" in c.name]
        assert len(chipa_kg) == 1, f"expected 1 '1 kg' chipa, got {len(chipa_kg)}"


def test_with_full_scenario_works(qseed, session_factory):
    """The 'with_full' scenario should run BOTH catalog + kyrian seed."""
    from app.rms.models import Customer, Ingredient, Product, Recipe
    from app.rms.models_legacy import Sale

    qseed("with_full")
    with session_factory() as s:
        ing_count = s.query(Ingredient).count()
        rec_count = s.query(Recipe).count()
        prod_count = s.query(Product).count()
        cust_count = s.query(Customer).count()
        sale_count = s.query(Sale).count()

    # Catalog: 87 ingredients, 30 recipes, 43 products
    assert ing_count >= 87, f"expected >= 87 ingredients, got {ing_count}"
    assert rec_count >= 30, f"expected >= 30 recipes, got {rec_count}"
    assert prod_count >= 43, f"expected >= 43 products, got {prod_count}"
    # Kyrian: at least 1 customer, some sales
    assert cust_count >= 1, f"expected >= 1 customer, got {cust_count}"
    assert sale_count >= 1, f"expected >= 1 sale, got {sale_count}"


def test_recipe_lines_seeded_for_paraguayan_recipes(qseed, session_factory):
    """New Paraguayan recipes should have recipe_line rows after seeding."""
    from app.rms.models import Recipe, RecipeLine

    qseed("with_catalog")
    with session_factory() as s:
        for recipe_name in ("chipa", "mbeju", "sopa_paraguaya", "kiveve",
                            "payagu", "sandwich_miga",
                            "torta_bodega", "medialunas", "glaseado"):
            recipe = s.query(Recipe).filter(
                Recipe.name.ilike(f"%{recipe_name}%")
            ).first()
            assert recipe is not None, f"recipe matching '{recipe_name}' not found"
            line_count = s.query(RecipeLine).filter_by(
                recipe_id=recipe.id
            ).count()
            assert line_count >= 3, (
                f"recipe '{recipe.name}' has only {line_count} lines, expected 3+"
            )


def test_chipa_recipe_has_almidon_mandioca(qseed, session_factory):
    """The chipa recipe MUST contain almidón de mandioca (it's the key ingredient)."""
    from app.rms.models import Ingredient, Recipe, RecipeLine

    qseed("with_catalog")
    with session_factory() as s:
        chipa = s.query(Recipe).filter(Recipe.name == "chipa").first()
        assert chipa is not None
        # Find almidón (case-insensitive, handles accents)
        almidon = s.query(Ingredient).filter(
            Ingredient.name.ilike("%almid%mandioca%")
        ).first()
        assert almidon is not None, "almidón de mandioca ingredient not found"
        # Find the line
        line = s.query(RecipeLine).filter_by(
            recipe_id=chipa.id, line_ref_id=almidon.id, line_kind="ingredient"
        ).first()
        assert line is not None, "chipa recipe should reference almidón de mandioca"
        assert line.qty == 500, f"expected 500g almidón, got {line.qty}"
        assert line.line_unit == "g", f"expected 'g' unit, got {line.line_unit}"


def test_recipe_lines_idempotent(qseed, session_factory):
    """Running seed_catalog twice should not duplicate recipe lines."""
    from app.rms.models import RecipeLine

    qseed("with_catalog")
    with session_factory() as s:
        first_count = s.query(RecipeLine).count()

    qseed("with_catalog")
    with session_factory() as s:
        second_count = s.query(RecipeLine).count()

    assert first_count == second_count, (
        f"recipe_line count changed: {first_count} → {second_count}"
    )
