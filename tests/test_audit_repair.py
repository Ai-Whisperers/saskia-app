"""tests/test_audit_repair.py — Unit tests for the auto-repair module.

These verify the allergens-wins logic and the category repair for the
specific live ingredients that triggered the audit page (#62 Panceta,
#66 Pan rallado, #39 Café espresso, #70 Jengibre fresco).
"""

from __future__ import annotations

from app.rms.tagging.audit_repair import repair_ingredient


class _FakeIng:
    """Minimal Ingredient stand-in: only the columns repair reads."""

    def __init__(
        self,
        id: int,
        name: str,
        allergens: str = "",
        dietary_tags: str = "",
        category: str = "",
        may_contain_gluten: bool = False,
    ) -> None:
        self.id = id
        self.name = name
        self.allergens = allergens
        self.dietary_tags = dietary_tags
        self.category = category
        self.may_contain_gluten = may_contain_gluten


# ── Tag/Allergen contradictions ──────────────────────────────────────


def test_panceta_drops_sin_gluten_when_allergens_gluten():
    """#62 Panceta: declares sin gluten/vegano/vegetariano but allergens=gluten.
    Panceta is also meat, so vegetariano/vegano are flagged by name-keyword
    match. All three are contradictory claims → all dropped. 'keto' is
    NOT flagged (keto just means low-carb; it doesn't conflict with
    gluten allergen directly)."""
    ing = _FakeIng(
        id=62,
        name="Panceta",
        allergens="gluten",
        dietary_tags="sin gluten,keto,vegano,vegetariano",
        category="carnes",
    )
    changes = repair_ingredient(ing)
    # sin gluten + vegetariano + vegano dropped
    assert "sin gluten" not in (ing.dietary_tags or "")
    assert "vegetariano" not in (ing.dietary_tags or "")
    assert "vegano" not in (ing.dietary_tags or "")
    # keto stays (no contradiction flagged)
    assert "keto" in (ing.dietary_tags or "")
    assert any("sin gluten" in c for c in changes)
    assert any("vegano" in c for c in changes)
    assert any("vegetariano" in c for c in changes)


def test_pan_rallado_drops_sin_gluten():
    """#66 Pan rallado: declares sin gluten but allergens=gluten."""
    ing = _FakeIng(
        id=66,
        name="Pan rallado",
        allergens="gluten",
        dietary_tags="sin gluten,keto,vegano,vegetariano",
        category="otros",
    )
    changes = repair_ingredient(ing)
    assert "sin gluten" not in (ing.dietary_tags or "")
    assert any("sin gluten" in c for c in changes)


def test_sin_lactosa_dropped_when_dairy_allergen():
    """Standard contradiction: sin lactosa but allergens include dairy."""
    ing = _FakeIng(
        id=100,
        name="Test cheese",
        allergens="dairy",
        dietary_tags="sin lactosa,vegano",
        category="lácteos",
    )
    repair_ingredient(ing)
    assert "sin lactosa" not in (ing.dietary_tags or "")
    assert "vegano" not in (ing.dietary_tags or "")


def test_sin_huevo_dropped_when_eggs_allergen():
    ing = _FakeIng(
        id=101,
        name="Test eggs",
        allergens="eggs",
        dietary_tags="sin huevo,vegano",
    )
    repair_ingredient(ing)
    assert "sin huevo" not in (ing.dietary_tags or "")
    assert "vegano" not in (ing.dietary_tags or "")


def test_sin_frutos_secos_dropped_when_nuts():
    """sin frutos secos + nuts allergen → drops 'sin frutos secos'.
    Note: vegano is NOT flagged just because of nuts allergen — vegano
    only conflicts with dairy/eggs allergens. To test vegano removal
    with nuts, see test_sin_frutos_secos_plus_dairy_drops_all."""
    ing = _FakeIng(
        id=102,
        name="Almendra",
        allergens="nuts",
        dietary_tags="sin frutos secos,vegano,vegetariano",
        category="frutos-secos",
    )
    repair_ingredient(ing)
    assert "sin frutos secos" not in (ing.dietary_tags or "")
    # vegetariano + vegano stay (no contradiction flagged)
    assert "vegano" in (ing.dietary_tags or "")


def test_sin_frutos_secos_plus_dairy_drops_all():
    """sin frutos secos + nuts allergen AND vegano + dairy allergen →
    drops both sin frutos secos AND vegano."""
    ing = _FakeIng(
        id=104,
        name="Almendra con queso",
        allergens="nuts,dairy",
        dietary_tags="sin frutos secos,vegano",
        category="frutos-secos",
    )
    repair_ingredient(ing)
    assert "sin frutos secos" not in (ing.dietary_tags or "")
    assert "vegano" not in (ing.dietary_tags or "")


def test_sin_tacc_dropped_when_gluten_allergen():
    """sin tacc and sin gluten are equivalent (INAN terminology)."""
    ing = _FakeIng(
        id=103,
        name="Bread crumbs",
        allergens="gluten",
        dietary_tags="sin tacc,sin gluten,keto",
    )
    repair_ingredient(ing)
    assert "sin tacc" not in (ing.dietary_tags or "")
    assert "sin gluten" not in (ing.dietary_tags or "")


def test_consistent_ingredient_unchanged():
    """A clean ingredient should produce no changes."""
    ing = _FakeIng(
        id=200,
        name="Aceite vegetal",
        allergens="",
        dietary_tags="vegano,keto",
        category="grasas",
    )
    changes = repair_ingredient(ing)
    assert changes == []
    assert ing.dietary_tags == "vegano,keto"
    assert ing.category == "grasas"


# ── Category repair ───────────────────────────────────────────────────


def test_jengibre_fresco_category_was_wrong():
    """#70 Jengibre fresco: category='carnes' is wrong; should be 'especias'."""
    ing = _FakeIng(
        id=70,
        name="Jengibre fresco",
        allergens="",
        dietary_tags="vegano,vegetariano,keto",
        category="carnes",
    )
    # First the tag repair should be a no-op (no contradictions)
    changes = repair_ingredient(ing)
    # Now category should be fixed
    assert ing.category == "especias", f"got category={ing.category!r}"
    assert any("category" in c and "especias" in c for c in changes)


def test_cafe_espresso_category_was_wrong():
    """#39 Café espresso (polvo): category='carnes' is wrong; should be 'líquidos'."""
    ing = _FakeIng(
        id=39,
        name="Café espresso (polvo)",
        allergens="",
        dietary_tags="vegano,vegetariano,keto",
        category="carnes",
    )
    changes = repair_ingredient(ing)
    assert ing.category == "líquidos", f"got category={ing.category!r}"
    assert any("líquidos" in c for c in changes)


def test_panceta_category_correct_not_changed():
    """#62 Panceta: category='carnes' is CORRECT (bacon). Don't change."""
    ing = _FakeIng(
        id=62,
        name="Panceta",
        allergens="gluten",
        dietary_tags="sin gluten,keto,vegano,vegetariano",
        category="carnes",
    )
    repair_ingredient(ing)
    # Tag changes are made, so category is NOT touched (operator should
    # review). The category was correct anyway.
    assert ing.category == "carnes"


def test_carne_molida_category_correct_not_changed():
    """A real meat ingredient must stay 'carnes'."""
    ing = _FakeIng(
        id=300,
        name="Carne molida",
        allergens="",
        dietary_tags="keto",
        category="carnes",
    )
    changes = repair_ingredient(ing)
    assert ing.category == "carnes"
    assert changes == []


def test_word_boundary_fix_no_longer_falsely_matches_res_in_fresco():
    """Regression test: substring 'res' inside 'fresco' used to classify
    Jengibre fresco as 'carnes' (it inherits from infer_category).
    After word-boundary fix, 'res' should NOT match in 'jengibre fresco'.
    """
    from app.rms.ingredient_intel import _keyword_in
    # 'res' is in carnes keywords but should NOT match inside 'fresco'
    assert not _keyword_in("res", "jengibre fresco")
    # But it should match standalone 'res' (for carne de res)
    assert _keyword_in("res", "carne de res")
    # 'pescado' should match 'pescado fresco'
    assert _keyword_in("pescado", "pescado fresco")
    # 'cafe' should match 'cafe espresso'
    assert _keyword_in("café", "café espresso")
