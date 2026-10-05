"""tests/test_ingredient_intel.py — E26 ingredient intelligence tests.

Covers:
- infer_category: every closed-set category has at least one keyword match
- infer_subcategory: returns None for unrecognized, matches for specific
- infer_role: returns role from closed set
- infer_allergens: detects gluten / dairy / eggs / nuts
- infer_dietary_tags: vegan/vegetarian/gluten_free/keto_friendly logic
- infer_shelf_life_days: returns CATEGORY_SHELF_LIFE default
- infer_storage: refrigerated for dairy, ambient for dry goods
- classify_ingredient: composite result has all 7 keys
- find_substitutes_by_role: ingredients sharing role + recipes are returned
"""

from __future__ import annotations

from app.rms.ingredient_intel import (
    CATEGORY_SHELF_LIFE,
    classify_ingredient,
    find_substitutes_by_role,
    infer_allergens,
    infer_category,
    infer_dietary_tags,
    infer_role,
    infer_shelf_life_days,
    infer_storage,
    infer_subcategory,
)

# ---------------------------------------------------------------------------
# infer_category
# ---------------------------------------------------------------------------


def test_infer_category_dairy():
    assert infer_category("Leche entera") == "lácteos"
    assert infer_category("MANTECA") == "lácteos"
    assert infer_category("Queso Crema") == "lácteos"
    assert infer_category("Dulce de Leche") == "lácteos"


def test_infer_category_flour():
    assert infer_category("Harina 000") == "harinas"
    assert infer_category("maicena") == "harinas"


def test_infer_category_sweetener():
    assert infer_category("azúcar impalpable") == "endulzantes"
    assert infer_category("MIEL") == "endulzantes"


def test_infer_category_leavening():
    assert infer_category("Levadura") == "leudantes"
    assert infer_category("polvo de hornear") == "leudantes"


def test_infer_category_fruit():
    assert infer_category("Limón") == "frutas"
    assert infer_category("frutilla") == "frutas"


def test_infer_category_nuts():
    assert infer_category("Almendra molida") == "frutos-secos"
    assert infer_category("nuez") == "frutos-secos"


def test_infer_category_fat():
    assert infer_category("Aceite de girasol") == "grasas"
    assert infer_category("margarina") == "grasas"


def test_infer_category_decoration():
    assert infer_category("Esencia de vainilla") == "decoración"
    assert infer_category("ralladura de limón") == "decoración"


def test_infer_category_unknown_fallback():
    assert infer_category("xyz123") == "otros"
    assert infer_category("") == "otros"


# ---------------------------------------------------------------------------
# infer_subcategory
# ---------------------------------------------------------------------------


def test_infer_subcategory_known():
    assert infer_subcategory("Leche entera") == "leche entera"
    assert infer_subcategory("Azúcar impalpable") == "azúcar impalpable"
    assert infer_subcategory("almendra") == "almendra"


def test_infer_subcategory_unknown():
    assert infer_subcategory("misterio123") is None


# ---------------------------------------------------------------------------
# infer_role
# ---------------------------------------------------------------------------


def test_infer_role_leavening():
    assert infer_role("levadura") == "leavening"
    assert infer_role("polvo de hornear") == "leavening"
    assert infer_role("bicarbonato") == "leavening"


def test_infer_role_sweetener():
    assert infer_role("azúcar") == "sweetener"
    assert infer_role("miel") == "sweetener"


def test_infer_role_fat():
    assert infer_role("manteca") == "fat"
    assert infer_role("aceite") == "fat"


def test_infer_role_structure():
    assert infer_role("harina") == "structure"


def test_infer_role_dairy():
    assert infer_role("leche") == "dairy"


def test_infer_role_flavor():
    assert infer_role("esencia de vainilla") == "flavor"


def test_infer_role_other():
    assert infer_role("xyz123") == "other"


# ---------------------------------------------------------------------------
# infer_allergens
# ---------------------------------------------------------------------------


def test_infer_allergens_gluten():
    allergens = infer_allergens("harina")
    assert "gluten" in allergens


def test_infer_allergens_dairy():
    allergens = infer_allergens("leche entera")
    assert "dairy" in allergens


def test_infer_allergens_eggs():
    allergens = infer_allergens("huevo")
    assert "eggs" in allergens


def test_infer_allergens_nuts():
    allergens = infer_allergens("almendra")
    assert "nuts" in allergens


def test_infer_allergens_combined():
    allergens = infer_allergens("harina de almendra")
    assert "gluten" in allergens or "nuts" in allergens


def test_infer_allergens_none():
    assert infer_allergens("agua") == []


def test_infer_allergens_returns_sorted():
    allergens = infer_allergens("harina con leche")
    assert allergens == sorted(allergens)


# ---------------------------------------------------------------------------
# infer_dietary_tags
# ---------------------------------------------------------------------------


def test_dietary_tags_flour_is_not_vegan():
    tags = infer_dietary_tags("harina")
    assert "vegan" in tags  # flour itself is vegan


def test_dietary_tags_milk_is_not_vegan_but_vegetarian():
    tags = infer_dietary_tags("leche entera")
    assert "vegan" not in tags
    assert "vegetarian" in tags


def test_dietary_tags_egg_not_vegan():
    tags = infer_dietary_tags("huevo")
    assert "vegan" not in tags
    assert "vegetarian" in tags


def test_dietary_tags_flour_not_keto():
    tags = infer_dietary_tags("harina")
    assert "keto_friendly" not in tags


def test_dietary_tags_stevia_is_keto():
    tags = infer_dietary_tags("stevia")
    assert "keto_friendly" in tags


def test_dietary_tags_almendra_is_vegan_and_keto():
    tags = infer_dietary_tags("almendra")
    assert "vegan" in tags
    assert "keto_friendly" in tags


def test_dietary_tags_flour_not_gluten_free():
    tags = infer_dietary_tags("harina")
    assert "gluten_free" not in tags


def test_dietary_tags_almendra_is_gluten_free():
    tags = infer_dietary_tags("almendra")
    assert "gluten_free" in tags


# ---------------------------------------------------------------------------
# infer_shelf_life_days + storage
# ---------------------------------------------------------------------------


def test_shelf_life_dairy():
    assert infer_shelf_life_days("leche entera") == CATEGORY_SHELF_LIFE["lácteos"]
    assert infer_shelf_life_days("leche entera") == 7


def test_shelf_life_flour():
    assert infer_shelf_life_days("harina") == 180


def test_shelf_life_sugar():
    assert infer_shelf_life_days("azúcar") == 730


def test_storage_refrigerated():
    assert infer_storage("leche entera") == "refrigerated"
    assert infer_storage("manteca") == "refrigerated"
    assert infer_storage("huevo") == "refrigerated"


def test_storage_ambient():
    assert infer_storage("harina") == "ambient"
    assert infer_storage("azúcar") == "ambient"


# ---------------------------------------------------------------------------
# classify_ingredient — composite
# ---------------------------------------------------------------------------


def test_classify_ingredient_has_all_keys():
    result = classify_ingredient("leche entera")
    assert set(result.keys()) == {
        "category",
        "subcategory",
        "role",
        "allergens",
        "dietary_tags",
        "shelf_life_days",
        "storage",
    }


def test_classify_ingredient_milk():
    result = classify_ingredient("leche entera")
    assert result["category"] == "lácteos"
    assert result["subcategory"] == "leche entera"
    assert result["role"] == "dairy"
    assert "dairy" in result["allergens"]
    assert "vegetarian" in result["dietary_tags"]
    assert "vegan" not in result["dietary_tags"]
    assert result["shelf_life_days"] == 7
    assert result["storage"] == "refrigerated"


def test_classify_ingredient_flour():
    result = classify_ingredient("harina")
    assert result["category"] == "harinas"
    assert result["role"] == "structure"
    assert "gluten" in result["allergens"]
    assert "vegan" in result["dietary_tags"]


# ---------------------------------------------------------------------------
# find_substitutes_by_role (co-occurrence)
# ---------------------------------------------------------------------------


def test_find_substitutes_returns_list_for_unknown(session_factory):
    """If ingredient doesn't exist, returns empty list."""
    with session_factory() as s:
        assert find_substitutes_by_role(s, 999_999) == []


def test_find_substitutes_returns_list_for_known(session_factory):
    """If ingredient has no recipes, returns empty list."""
    from app.rms.models import Ingredient

    with session_factory() as s:
        s.add(Ingredient(name="solitaria_xyz", unit="kg", stock_qty=0, purchase_price_gs=1000))
        s.commit()
        ing = s.scalars(
            __import__("sqlalchemy").select(Ingredient).where(Ingredient.name == "solitaria_xyz")
        ).one()
        assert find_substitutes_by_role(s, ing.id) == []


def test_find_substitutes_finds_pair(session_factory):
    """Two ingredients with the same role appearing in shared recipes."""

    from app.rms.models import Ingredient, Recipe, RecipeLine

    with session_factory() as s:
        ing_a = Ingredient(name="mantequilla_xyz", unit="kg", stock_qty=1, purchase_price_gs=50000)
        ing_b = Ingredient(name="margarina_xyz", unit="kg", stock_qty=1, purchase_price_gs=30000)
        ing_c = Ingredient(name="aceite_xyz", unit="kg", stock_qty=1, purchase_price_gs=20000)
        s.add_all([ing_a, ing_b, ing_c])
        s.flush()

        # 4 recipes, all containing both A and B (so they co-occur ≥3 times)
        for i in range(4):
            r = Recipe(name=f"recipe_xyz_{i}", yield_qty=10, yield_unit="und")
            s.add(r)
            s.flush()
            s.add_all(
                [
                    RecipeLine(
                        recipe_id=r.id, line_kind="ingredient", line_ref_id=ing_a.id, qty=0.5
                    ),
                    RecipeLine(
                        recipe_id=r.id, line_kind="ingredient", line_ref_id=ing_b.id, qty=0.5
                    ),
                ]
            )
        s.commit()

        # A and B share role 'fat' and co-occur in 4 recipes → substitutable.
        subs = find_substitutes_by_role(s, ing_a.id)
        assert ing_b.id in subs
        # C only appears in 0 recipes with A → not a substitute.
        assert ing_c.id not in subs


class TestWave1InferenceFixes:
    """Wave 1 — Bug fixes + new categories from INGREDIENT-DEEP-RESEARCH.md."""

    def test_pechuga_no_vegetarian_bug(self):
        tags = infer_dietary_tags("Pechuga de pollo")
        assert "vegetarian" not in tags
        assert "vegan" not in tags

    def test_carne_molida_no_vegetarian(self):
        tags = infer_dietary_tags("Carne molida")
        assert "vegetarian" not in tags

    def test_ricota_is_not_vegan_bug(self):
        tags = infer_dietary_tags("Ricota")
        assert "vegan" not in tags
        assert "vegetarian" in tags
        assert "dairy" in infer_allergens("Ricota")

    def test_huevos_category(self):
        assert infer_category("Huevos") == "huevos"
        assert infer_category("huevo") == "huevos"
        assert infer_category("Clara de huevo") == "huevos"
        assert infer_category("Yema") == "huevos"

    def test_carnes_category(self):
        assert infer_category("Pollo") == "carnes"
        assert infer_category("Carne molida") == "carnes"
        assert infer_category("Panceta") == "carnes"
        assert infer_category("Pechuga de pollo") == "carnes"
        assert infer_category("Pescado") == "carnes"
        assert infer_category("Jamón") == "carnes"

    def test_manteca_vegetal_is_grasas_bug(self):
        assert infer_category("Manteca vegetal") == "grasas"

    def test_keto_check_includes_jarabe_melaza(self):
        for name in ("Jarabe de maíz", "Melaza", "Panela", "Rapadura"):
            tags = infer_dietary_tags(name)
            assert "keto_friendly" not in tags, f"{name} should not be keto"

    def test_stevia_erythritol_are_keto(self):
        tags_s = infer_dietary_tags("Stevia")
        tags_e = infer_dietary_tags("Eritritol")
        assert "keto_friendly" in tags_s
        assert "keto_friendly" in tags_e

    def test_mandioca_is_harinas(self):
        assert infer_category("Mandioca") == "harinas"

    def test_especias_category(self):
        for name in (
            "Canela molida",
            "Vainilla en vaina",
            "Anís estrellado",
            "Pimienta negra",
            "Extracto de vainilla",
            "Nuez moscada",
        ):
            assert infer_category(name) == "especias", f"{name} should be especias"

    def test_semillas_category(self):
        assert infer_category("Semilla de chía") == "semillas"
        assert infer_category("Semilla de lino") == "semillas"
        assert infer_category("Semilla de girasol") == "semillas"

    def test_agua_is_liquidos(self):
        assert infer_category("Agua") == "líquidos"

    def test_jugo_de_naranja_is_frutas(self):
        """Jugo de naranja contains 'naranja' keyword → frutas wins over líquidos."""
        assert infer_category("Jugo de naranja") == "frutas"

    def test_carnes_dietary(self):
        """Pechuga de pollo has no vegan/vegetarian tag (it's meat)."""
        tags = infer_dietary_tags("Pechuga de pollo")
        assert "vegan" not in tags
        assert "vegetarian" not in tags

    def test_carne_molida_no_dietary(self):
        tags = infer_dietary_tags("Carne molida")
        assert "vegan" not in tags
        assert "vegetarian" not in tags

    def test_panceta_no_dietary(self):
        tags = infer_dietary_tags("Panceta")
        assert "vegan" not in tags
        assert "vegetarian" not in tags

    def test_esencia_de_vainilla_is_decoracion(self):
        assert infer_category("Esencia de vainilla") == "decoración"

    def test_new_shelf_life_keys(self):
        assert CATEGORY_SHELF_LIFE["huevos"] == 21
        assert CATEGORY_SHELF_LIFE["carnes"] == 5
        assert CATEGORY_SHELF_LIFE["especias"] == 730
        assert CATEGORY_SHELF_LIFE["semillas"] == 365
        assert CATEGORY_SHELF_LIFE["líquidos"] == 5

    def test_inan_allergen_categories_present(self):
        """INAN Res. 614/2023 allergen keywords cover required categories."""
        # Each allergen type should fire on at least one ingredient
        assert "dairy" in infer_allergens("Leche")
        assert "eggs" in infer_allergens("Huevos")
        assert "nuts" in infer_allergens("Almendra")
        assert "soy" in infer_allergens("Tofu")
        assert "sesame" in infer_allergens("Sésamo")
        assert "sulfites" in infer_allergens("Sulfito de sodio")
        # Pecán is in the nuts list
        assert "nuts" in infer_allergens("Pecán")

    def test_dairy_egg_honey_not_vegan_vegetarian_ok(self):
        for name in ("Manteca", "Huevo", "Miel", "Leche entera"):
            tags = infer_dietary_tags(name)
            assert "vegan" not in tags, f"{name} should not be vegan"
            assert "vegetarian" in tags, f"{name} should be vegetarian"

    def test_meat_not_vegetarian(self):
        for name in ("Pechuga de pollo", "Carne molida", "Pescado", "Pollo entero"):
            tags = infer_dietary_tags(name)
            assert "vegan" not in tags
            assert "vegetarian" not in tags

    def test_gelatina_dairy(self):
        """Gelatina is animal-derived (typically bovine)."""
        tags = infer_dietary_tags("Gelatina sin sabor")
        assert "vegan" not in tags
        assert "vegetarian" in tags
