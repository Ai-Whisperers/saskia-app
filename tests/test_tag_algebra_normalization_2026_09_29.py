"""Regression: tag-algebra must accept English/snake_case dietary tags on
ingredients AND sub-recipes, normalising them to the canonical Spanish
vocabulary before intersecting.

Symptom (2026-09-29 live VPS):
  /recetas/18 showed "Canceladas (14)" with every canonical Spanish tag
  blocked by every ingredient. Root cause: ingredient_intel emits
  'vegan', 'vegetarian', 'gluten_free', 'keto_friendly'; tag_algebra
  compared 'vegano'/'vegetariano'/'sin gluten' against that column and
  found nothing matching. Fix: normalize on read in
  app/rms/tag_algebra.py via _TAG_NORMALIZE.
"""

from __future__ import annotations

from app.rms.tag_algebra import (
    _normalize_tag,
    ingredient_blocks,
    ingredient_dietary_set,
)

# _normalize_tag -------------------------------------------------------------


class TestNormalizeTag:
    def test_english_vegan_to_vegano(self):
        assert _normalize_tag("vegan") == "vegano"

    def test_english_vegetarian_to_vegetariano(self):
        assert _normalize_tag("vegetarian") == "vegetariano"

    def test_snake_gluten_free_to_sin_gluten(self):
        assert _normalize_tag("gluten_free") == "sin gluten"

    def test_keto_friendly_normalizes_to_keto(self):
        assert _normalize_tag("keto_friendly") == "keto"

    def test_sugar_free_to_sin_azucar(self):
        assert _normalize_tag("sugar_free") == "sin azúcar"

    def test_already_spanish_passes_through(self):
        assert _normalize_tag("vegano") == "vegano"
        assert _normalize_tag("sin gluten") == "sin gluten"
        assert _normalize_tag("sin tacc") == "sin tacc"

    def test_organic_to_organico(self):
        assert _normalize_tag("organic") == "orgánico"
        assert _normalize_tag("organico") == "orgánico"

    def test_unknown_returns_none(self):
        assert _normalize_tag("made-up-tag") is None
        assert _normalize_tag("") is None

    def test_case_insensitive(self):
        assert _normalize_tag("VEGAN") == "vegano"
        assert _normalize_tag("Gluten_Free") == "sin gluten"


# ingredient_dietary_set ------------------------------------------------------
# Use a tiny stub object so we don't need the SQLAlchemy model here.


class _StubIng:
    def __init__(self, name: str, dietary_tags: str | None):
        self.name = name
        self.dietary_tags = dietary_tags


class TestIngredientDietarySet:
    def test_empty_yields_empty(self):
        ing = _StubIng("sal", None)
        assert ingredient_dietary_set(ing) == frozenset()

    def test_normalizes_mixed_language_csv(self):
        ing = _StubIng(
            "harina de almendras",
            "vegan,vegetarian,gluten_free,keto_friendly",
        )
        assert ingredient_dietary_set(ing) == frozenset(
            {
                "vegano",
                "vegetariano",
                "sin gluten",
                "keto",
            }
        )

    def test_already_spanish_unchanged(self):
        ing = _StubIng("manteca", "sin gluten,keto,vegetariano")
        assert ingredient_dietary_set(ing) == frozenset(
            {
                "sin gluten",
                "keto",
                "vegetariano",
            }
        )

    def test_unknown_tags_dropped_silently(self):
        ing = _StubIng("sal", "vegano,unknown-tag,sin gluten")
        assert ingredient_dietary_set(ing) == frozenset({"vegano", "sin gluten"})


# ingredient_blocks ----------------------------------------------------------


class TestIngredientBlocks:
    """The function that drives the 'CANCELADAS (N) — ver por qué' UI."""

    def test_flour_blocks_sin_gluten_via_normalized_tag(self):
        # harina de trigo declared 'vegan' (English) — must still NOT
        # satisfy 'sin gluten' (which is what the operator means by the
        # Spanish canonical tag) because flour is not in any gluten-free set.
        ing = _StubIng("Harina de trigo", "vegan")
        assert "sin gluten" not in ingredient_dietary_set(ing)
        assert ingredient_blocks(ing, "sin gluten") is True

    def test_manteca_blocks_sin_lactosa_dairy(self):
        # manteca has allergens='dairy' — dietary_tags 'sin gluten, vegetariano'
        # (Spanish) is fine; the canonical 'sin lactosa' is NOT in manteca's
        # declared set, so manteca blocks it.
        ing = _StubIng("manteca", "sin gluten,keto,vegetariano")
        assert ingredient_blocks(ing, "sin lactosa") is True

    def test_almendra_blocks_sin_frutos_secos(self):
        # almonds ARE nuts; sin frutos secos claim is "no nuts anywhere",
        # so almonds block.
        ing = _StubIng("almendra molida", "vegano,vegetariano,sin gluten,keto")
        assert ingredient_blocks(ing, "sin frutos secos") is True

    def test_keto_canonical_works_end_to_end(self):
        # 'keto' in canonical is new; ingredient_intel still emits
        # 'keto_friendly'. Both must agree.
        ing_a = _StubIng("almendra", "vegan,keto_friendly")
        ing_b = _StubIng("almendra", "vegano,keto")
        assert ingredient_dietary_set(ing_a) == ingredient_dietary_set(ing_b)

    def test_neutral_salt_never_blocks(self):
        ing = _StubIng("sal", None)
        for tag in (
            "sin gluten",
            "vegano",
            "vegetariano",
            "keto",
            "sin lactosa",
            "sin azúcar",
            "orgánico",
            "integral",
            "sin tacc",
        ):
            assert ingredient_blocks(ing, tag) is False, f"sal should not block {tag}"
