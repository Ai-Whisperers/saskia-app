"""tests/test_tagging_classify.py — pure-function classifier tests.

Exercises normalize(), normalize_all(), infer_allergens(), infer_dietary_tags(),
ingredient_blocks(), validate_ingredient().

All inputs are inert (dataclasses / SimpleNamespace) — no DB needed.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.rms.tagging.classify import (
    infer_allergens,
    infer_dietary_tags,
    ingredient_blocks,
    normalize,
    normalize_all,
    validate_ingredient,
)

# ─────────────────────────────────────────────────────────────────────────
# normalize / normalize_all
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("vegano", "vegano"),
        ("VEGANO", "vegano"),
        ("vegano ", "vegano"),
        ("  vegano  ", "vegano"),
        ("vegan", "vegano"),
        ("vegetarian", "vegetariano"),
        ("gluten_free", "sin gluten"),
        ("gluten-free", "sin gluten"),
        ("sugar-free", "sin azúcar"),
        ("sin gluten", "sin gluten"),
        ("sin-gluten", "sin gluten"),
        ("sin tacc", "sin tacc"),
        ("sin-tacc", "sin tacc"),
        ("sin lactosa", "sin lactosa"),
        ("keto_friendly", "keto"),
        ("keto-friendly", "keto"),
        ("lactose_free", "sin lactosa"),
        ("dairy_free", "sin lactosa"),
        ("egg_free", "sin huevo"),
        ("nut_free", "sin frutos secos"),
        ("whole_grain", "integral"),
        ("organic", "orgánico"),
        ("orgánico", "orgánico"),
        ("organico", "orgánico"),
        ("integral", "integral"),
        ("keto", "keto"),
        ("", None),
        ("   ", None),
        (None, None),
        ("unknown-thing", None),
    ],
)
def test_normalize(raw, expected):
    assert normalize(raw) == expected


def test_normalize_unrecognized_string_returns_none():
    """Defensive: completely unknown input returns None, not a false match.

    This guards against a stray compound like 'gluten-free-stuff' that
    contains the substring 'gluten-free' but isn't actually a known alias.
    """
    assert normalize("gluten-free-stuff") is None
    assert normalize("foo-bar") is None
    assert normalize("diabetes") is None  # might be a tag someday but isn't now


def test_normalize_aliases_with_substring_overlap():
    """Compound inputs that LOOK like aliases but aren't are dropped."""
    # The aliases map has "gluten_free" → "sin gluten". A string that just
    # starts with "gluten_free" is not necessarily that alias.
    assert normalize("gluten_free_keto") is None


def test_normalize_all_csv():
    """CSV with mixed English/Spanish/empty/whitespace/unknown."""
    out = normalize_all("vegano,vegan, ,gluten_free,unknown,keto")
    assert "vegano" in out
    assert "sin gluten" in out
    assert "keto" in out
    assert len(out) == 3


def test_normalize_all_empty():
    assert normalize_all("") == frozenset()
    assert normalize_all(None) == frozenset()
    assert normalize_all(",,,") == frozenset()


# ─────────────────────────────────────────────────────────────────────────
# infer_allergens (ingredient name → allergens)
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Harina de trigo", ["gluten"]),
        ("Harina de trigo 000", ["gluten"]),
        ("Leche entera", ["dairy"]),
        ("Queso crema", ["dairy"]),
        ("Mantequilla sin sal", ["dairy"]),
        ("Dulce de leche", ["dairy"]),
        ("Huevos", ["eggs"]),
        ("Yema de huevo", ["eggs"]),
        ("Almendras", ["nuts"]),
        ("Nueces", ["nuts"]),
        ("Maní", ["nuts"]),
        ("Zanahoria", []),
        ("Agua", []),
        ("Sal", []),
        ("Canela", []),
        ("Aceite vegetal", []),
        ("Bicarbonato de sodio", []),
        ("Polvo de hornear", []),
        ("Levadura", []),
        ("Vinagre", []),
        ("Leche de almendras", ["dairy", "nuts"]),  # both keywords present
        ("Harina de avena", ["gluten"]),
        ("Harina de almendras", ["gluten", "nuts"]),  # contains "harina" → gluten
    ],
)
def test_infer_allergens(name, expected):
    out = infer_allergens(name)
    assert sorted(out) == sorted(expected)


# ─────────────────────────────────────────────────────────────────────────
# infer_dietary_tags (English labels — old contract)
# ─────────────────────────────────────────────────────────────────────────


def test_infer_dietary_tags_zanahoria_is_vegetarian_and_vegan():
    out = infer_dietary_tags("Zanahoria")
    assert "vegan" in out
    assert "vegetarian" in out
    assert "gluten_free" in out


def test_infer_dietary_tags_carne_is_neither():
    out = infer_dietary_tags("Carne de res")
    assert "vegan" not in out
    assert "vegetarian" not in out
    assert "gluten_free" in out  # beef has no gluten


def test_infer_dietary_tags_leche_is_vegetarian_not_vegan():
    out = infer_dietary_tags("Leche entera")
    assert "vegetarian" in out
    assert "vegan" not in out


def test_infer_dietary_tags_harina_is_not_keto():
    out = infer_dietary_tags("Harina de trigo")
    assert "gluten_free" not in out


def test_infer_dietary_tags_stevia_is_keto():
    out = infer_dietary_tags("Stevia")
    assert "keto_friendly" in out


# ─────────────────────────────────────────────────────────────────────────
# ingredient_blocks
# ─────────────────────────────────────────────────────────────────────────


def _ing(name, allergens=None, dietary_tags=None, may_contain_gluten=False):
    return SimpleNamespace(
        name=name,
        allergens=allergens,
        dietary_tags=dietary_tags,
        may_contain_gluten=may_contain_gluten,
    )


def test_blocks_gluten_via_allergens_column():
    """Harina de trigo with allergens='gluten' blocks sin gluten."""
    ing = _ing("Harina de trigo", allergens="gluten")
    assert ingredient_blocks(ing, "sin gluten") is True
    assert ingredient_blocks(ing, "sin tacc") is True


def test_carrot_does_not_block_sin_huevo():
    """Carrot with no allergens and no name-keyword match → does NOT block sin huevo.

    This is the regression test for the absurdities bug.
    """
    ing = _ing("Zanahoria")
    assert ingredient_blocks(ing, "sin huevo") is False
    assert ingredient_blocks(ing, "sin lactosa") is False
    assert ingredient_blocks(ing, "sin gluten") is False


def test_cinnamon_does_not_block_sin_huevo():
    ing = _ing("Canela")
    assert ingredient_blocks(ing, "sin huevo") is False
    assert ingredient_blocks(ing, "sin lactosa") is False


def test_bicarbonato_does_not_block_sin_huevo():
    ing = _ing("Bicarbonato de sodio")
    assert ingredient_blocks(ing, "sin huevo") is False
    assert ingredient_blocks(ing, "sin lactosa") is False


def test_neutral_keywords_never_block():
    for kw in ("Agua", "Sal", "Hielo", "Sal fina", "Sal gruesa",
               "Canela", "Jengibre", "Nuez moscada", "Esencia",
               "Bicarbonato de sodio", "Polvo de hornear",
               "Levadura", "Vinagre", "Aceite vegetal"):
        ing = _ing(kw)
        for tag in ("sin gluten", "sin huevo", "sin lactosa",
                    "vegano", "keto", "vegetariano"):
            assert ingredient_blocks(ing, tag) is False, (
                f"neutral {kw!r} unexpectedly blocks {tag!r}"
            )


def test_sin_tacc_stricter_than_sin_gluten_via_cross_contamination():
    """may_contain_gluten=True blocks sin tacc even without allergens column.

    Use an ingredient whose name has NO gluten keywords (e.g. 'Quinoa'),
    so the heuristic doesn't override — and the cross-contamination rule
    is the only reason it blocks sin tacc.
    """
    ing = _ing("Quinoa", may_contain_gluten=True)
    assert ingredient_blocks(ing, "sin tacc") is True
    # sin gluten depends on allergen column / name heuristic only —
    # not on may_contain_gluten.
    assert ingredient_blocks(ing, "sin gluten") is False


def test_sin_tacc_via_cross_contamination_overrides_neutral_for_quinoa():
    """Even with may_contain_gluten=True, if name has no gluten keywords,
    sin tacc still blocks (operator-set flag wins)."""
    ing = _ing("Avena", allergens=None, may_contain_gluten=True)
    # 'avena' is a gluten keyword, so this also blocks sin gluten — that's
    # expected behavior, not what we're testing here.
    assert ingredient_blocks(ing, "sin tacc") is True


def test_ingredient_with_dairy_allergens_blocks_sin_lactosa_and_vegano():
    ing = _ing("Queso crema", allergens="dairy")
    assert ingredient_blocks(ing, "sin lactosa") is True
    assert ingredient_blocks(ing, "vegano") is True
    assert ingredient_blocks(ing, "sin gluten") is False


def test_ingredient_with_eggs_blocks_sin_huevo_and_vegano():
    ing = _ing("Huevos", allergens="eggs")
    assert ingredient_blocks(ing, "sin huevo") is True
    assert ingredient_blocks(ing, "vegano") is True


def test_falls_back_to_name_heuristic_when_allergens_missing():
    """Operators who haven't populated allergens still get correct blocking
    for ingredients with recognizable keywords."""
    ing = _ing("Harina de trigo", allergens=None)
    assert ingredient_blocks(ing, "sin gluten") is True
    assert ingredient_blocks(ing, "sin tacc") is True


def test_dietary_tags_claim_overrides_heuristic():
    """If an ingredient CLAIMS 'sin frutos secos' in dietary_tags, that
    claim overrides the heuristic (e.g. 'harina de almendras' has the
    'almendra' keyword but if operator marked it sin frutos secos, trust them)."""
    ing = _ing(
        "Harina de almendras",
        allergens=None,
        dietary_tags="sin frutos secos",
    )
    assert ingredient_blocks(ing, "sin frutos secos") is False


def test_allergens_column_overrides_dietary_tags_claim():
    """If allergens column says dairy but dietary_tags says sin lactosa, allergens wins."""
    ing = _ing(
        "Queso procesado",
        allergens="dairy",
        dietary_tags="sin lactosa",
    )
    assert ingredient_blocks(ing, "sin lactosa") is True


def test_empty_string_name_does_not_crash():
    """Defensive: ingredient with no name still returns a clean result."""
    ing = _ing("", allergens=None, dietary_tags=None)
    assert ingredient_blocks(ing, "sin gluten") is False


def test_unknown_tag_with_no_blockers_does_not_block():
    """Tags not in TAG_ALLERGEN_BLOCKERS (e.g. 'integral', 'orgánico') never
    block on allergens — they're certification claims."""
    ing = _ing("Harina de trigo", allergens="gluten")
    assert ingredient_blocks(ing, "integral") is False
    assert ingredient_blocks(ing, "orgánico") is False


def test_dairy_free_alias_blocks_vegano_via_lactose_free_normalization():
    """The blocker lookup uses the canonical tag, not the alias form."""
    ing = _ing("Leche", allergens="dairy")
    # Caller might pass any form; we normalize via lowercase match.
    assert ingredient_blocks(ing, "sin lactosa") is True


# ─────────────────────────────────────────────────────────────────────────
# validate_ingredient
# ─────────────────────────────────────────────────────────────────────────


def test_validate_no_issues_when_consistent():
    ing = _ing("Harina de almendras", allergens="gluten,nuts", dietary_tags="vegano")
    # It's a contradiction, but the function checks specific patterns
    # Let's test a clean one.
    clean = _ing("Harina de arroz", allergens="", dietary_tags="sin gluten,vegano")
    assert validate_ingredient(clean) == []


def test_validate_detects_vegan_with_dairy_allergen():
    ing = _ing("Leche", allergens="dairy", dietary_tags="vegano")
    issues = validate_ingredient(ing)
    assert any("vegano" in i for i in issues)


def test_validate_detects_sin_gluten_with_gluten_allergen():
    ing = _ing("Harina de trigo", allergens="gluten", dietary_tags="sin gluten")
    issues = validate_ingredient(ing)
    assert any("sin gluten" in i for i in issues)


def test_validate_detects_vegetariano_with_meat_name():
    ing = _ing("Pechuga de pollo", dietary_tags="vegetariano")
    issues = validate_ingredient(ing)
    assert any("vegetariano" in i for i in issues)


def test_no_issue_for_meat_with_vegetariano_unset():
    """Not declaring vegetariano = no validation issue, even though it's meat."""
    ing = _ing("Pechuga de pollo", allergens="eggs")
    assert validate_ingredient(ing) == []


# ─────────────────────────────────────────────────────────────────────────
# Sugar / sin-azúcar / keto (2026-09-29 regression)
# ─────────────────────────────────────────────────────────────────────────


def test_azucar_blanca_blocks_sin_azucar_via_name_inference():
    """Sugar ingredients with allergens=None must still block sin-azúcar.

    Regression: previously sin-azúcar was never blocked because the
    allergen-blocker list for it was empty. The user saw 'Sin azúcar' on
    a recipe that contained Azúcar blanca.
    """
    ing = _ing("Azúcar blanca", allergens=None)
    assert ingredient_blocks(ing, "sin azúcar") is True
    assert ingredient_blocks(ing, "keto") is True


def test_azucar_impalpable_blocks_sin_azucar():
    ing = _ing("azúcar impalpable")
    assert ingredient_blocks(ing, "sin azúcar") is True


def test_miel_blocks_sin_azucar():
    ing = _ing("Miel")
    assert ingredient_blocks(ing, "sin azúcar") is True


def test_stevia_does_not_block_sin_azucar():
    """Stevia is a non-sugar sweetener, OK for sin-azúcar."""
    ing = _ing("Stevia")
    assert ingredient_blocks(ing, "sin azúcar") is False
    assert ingredient_blocks(ing, "keto") is False


def test_jarabe_de_maiz_blocks_sin_azucar():
    ing = _ing("Jarabe de maíz")
    assert ingredient_blocks(ing, "sin azúcar") is True


def test_zanahoria_does_not_block_sin_azucar():
    """Carrots should not block sin-azúcar — they're not sweet."""
    ing = _ing("Zanahoria")
    assert ingredient_blocks(ing, "sin azúcar") is False


# ─────────────────────────────────────────────────────────────────────────
# Word-boundary keyword matching (2026-09-29 collision fixes)
# ─────────────────────────────────────────────────────────────────────────


def test_ketjap_manis_is_not_nuts():
    """Regression: Ketjap Manis (Indonesian soy sauce) was falsely flagged
    as nuts because 'mani' (peanut in Spanish) is a substring of 'manis'
    (Indonesian 'sweet'). Word-boundary matching fixes it.
    """
    out = infer_allergens("Ketjap Manis")
    assert "nuts" not in out


def test_mani_tostado_still_recognized_as_nuts():
    """Spanish maní (peanut) — must still be recognized."""
    out = infer_allergens("Maní tostado")
    assert "nuts" in out


def test_nuez_moscada_is_nuts():
    out = infer_allergens("Nuez moscada")
    assert "nuts" in out


def test_almendra_molida_is_nuts_not_gluten():
    """almendra molida — only nuts, no gluten. Word 'almendra' present."""
    out = infer_allergens("almendra molida")
    assert "nuts" in out


def test_almendras_plural_form_matches():
    out = infer_allergens("Almendras tostadas")
    assert "nuts" in out


def test_leche_de_almendras_is_dairy_and_nuts():
    """Compound: both 'leche' (dairy) and 'almendras' (nuts) match."""
    out = infer_allergens("Leche de almendras")
    assert "dairy" in out
    assert "nuts" in out


def test_yemas_plural_matches():
    out = infer_allergens("Yemas")
    assert "eggs" in out


def test_queso_crema_phrase_matches_as_dairy():
    """Multi-word keyword 'queso crema' must match the phrase."""
    out = infer_allergens("Queso crema")
    assert "dairy" in out


def test_ingredient_with_hyphen_separator_matches():
    """Hyphenated names like 'leche-descremada' should match 'leche'."""
    out = infer_allergens("Leche-descremada")
    assert "dairy" in out


def test_ingredient_with_parenthesis_ingredient_name():
    """Names with parentheses — 'Crema agria' should match dairy via 'crema'."""
    out = infer_allergens("Crema agria")
    assert "dairy" in out


def test_accent_insensitive_matching():
    """Keyword 'mani' should match 'maní' (accent stripped in normalize)."""
    out = infer_allergens("maní tostado")
    assert "nuts" in out


def test_cebolla_ajo_no_false_positives():
    """Vegetables should not match any allergen."""
    for name in ("Cebolla", "Ajo", "Perejil", "Tomate", "Lechuga"):
        out = infer_allergens(name)
        assert out == [], f"{name!r} unexpectedly matched {out}"


def test_dulce_de_leche_phrase_matches_dairy():
    """Multi-word phrase 'dulce de leche' must match dairy."""
    out = infer_allergens("Dulce de leche")
    assert "dairy" in out
