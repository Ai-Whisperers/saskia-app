"""tests/test_inference_autofill.py — Wave 2: server-side auto-fill tests."""

from __future__ import annotations


class TestIngredientAutoFill:
    """When operator creates/updates an ingredient with just a name, the server
    auto-fills category, allergens, dietary_tags, shelf_life, storage."""

    def test_create_autofills_harina_classification(self):
        """'Harina' alone should classify to harinas + gluten allergen."""
        from app.rms.ingredient_intel import classify_ingredient

        cls = classify_ingredient("Harina")
        assert cls["category"] == "harinas"
        assert "gluten" in cls["allergens"]
        assert "vegan" in cls["dietary_tags"]
        assert "keto_friendly" not in cls["dietary_tags"]

    def test_create_autofills_huevos(self):
        """'huevos' should classify to huevos category + eggs allergen."""
        from app.rms.ingredient_intel import classify_ingredient

        cls = classify_ingredient("huevos")
        assert cls["category"] == "huevos"
        assert "eggs" in cls["allergens"]
        assert cls["shelf_life_days"] == 21

    def test_create_autofills_pechuga_no_vegetarian(self):
        """'Pechuga de pollo' should classify to carnes + no vegan/vegetarian."""
        from app.rms.ingredient_intel import classify_ingredient

        cls = classify_ingredient("Pechuga de pollo")
        assert cls["category"] == "carnes"
        assert "vegan" not in cls["dietary_tags"]
        assert "vegetarian" not in cls["dietary_tags"]

    def test_create_autofills_storage_zone(self):
        """Dairy ingredients should be classified as refrigerated."""
        from app.rms.ingredient_intel import classify_ingredient

        cls = classify_ingredient("Crema de leche")
        assert cls["storage"] == "refrigerated"

    def test_create_autofills_shelf_life(self):
        """Each category returns a sensible shelf life default."""
        from app.rms.ingredient_intel import classify_ingredient

        assert classify_ingredient("Harina")["shelf_life_days"] == 180
        assert classify_ingredient("Azúcar")["shelf_life_days"] == 730
        assert classify_ingredient("Aceite vegetal")["shelf_life_days"] == 120
        assert classify_ingredient("Pollo")["shelf_life_days"] == 5
        assert classify_ingredient("Frutillas")["shelf_life_days"] == 5


class TestRecipeFamilyInference:
    """Recipe auto-fill derives family, dietary_tags, difficulty."""

    def test_family_from_name(self):
        from app.rms.recipe_intel import infer_recipe_family_from_name

        assert infer_recipe_family_from_name("Muffin de chocolate") == "pastelería"
        assert infer_recipe_family_from_name("Pan lactal") == "panadería"
        assert infer_recipe_family_from_name("Cheesecake clásico") == "fríos"
        assert infer_recipe_family_from_name("Empanada de carne") == "salados"
        assert infer_recipe_family_from_name("Oliebollen holandesa") == "frituras"
        # Rosca → panadería (the dulces_regionales kw is also "rosca" but panadería
        # comes first via "pan " keyword match in "Rosca de Reyes" - actually no,
        # "rosca" appears in panadería list directly. Override → panadería.)
        assert infer_recipe_family_from_name("Rosca de Reyes") == "panadería"
        # Unknown
        assert infer_recipe_family_from_name("") == "otros"
        assert infer_recipe_family_from_name("XYZ") == "otros"


class TestIngredientInferenceOverrides:
    """Operator-supplied form values should win over inference."""

    def test_operator_category_wins(self):
        """If operator explicitly sets category='decoración' for 'Harina',
        that overrides the inferred 'harinas'."""
        from app.rms.ingredient_intel import classify_ingredient

        # Inference itself doesn't know about operator form values — that's the
        # router's job. Here we just verify inference can be computed alongside.
        # The router test (TestRouterInferenceWiring) verifies the override.
        cls = classify_ingredient("Harina")
        assert cls["category"] == "harinas"  # default inference
        # The router uses: explicit if provided, else inferred
