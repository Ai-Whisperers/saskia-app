"""Tests for SASKIA-220: 5 new packs (Food Truck, Quiosco, Chipería, Pastelería Industrial, Cervecería)."""

from __future__ import annotations

from app.rms.seed.packs import PACKS, PackData, seed_pack

# ---- 1. Total pack count ----


def test_packs_count_16():
    """11 + 5 = 16 packs in the registry."""
    assert len(PACKS) == 16


# ---- 2. New packs present ----


def test_packs_include_food_truck():
    assert "Food Truck" in PACKS


def test_packs_include_quiosco():
    assert "Quiosco/Minimarket" in PACKS


def test_packs_include_chiperia():
    assert "Chiper\u00eda" in PACKS


def test_packs_include_pasteleria_industrial():
    assert "Pasteler\u00eda Industrial" in PACKS


def test_packs_include_cerveceria():
    assert "Cervecer\u00eda" in PACKS


# ---- 3. Each new pack has the required PackData fields populated ----


def test_food_truck_has_summer_relevance():
    """Food truck is a spring-summer vertical (open-air events)."""
    pack = PACKS["Food Truck"]
    assert isinstance(pack, PackData)
    # production templates include weekend days (5, 6) which is summer-pico
    weekday_slots = {t[0] for t in pack.production_templates}
    assert 5 in weekday_slots  # S\u00e1bado
    assert 6 in weekday_slots  # Domingo


def test_quiosco_24_7():
    """Quiosco/Minimarket runs 24/7."""
    pack = PACKS["Quiosco/Minimarket"]
    # All 7 weekdays have a 24-hour template
    for weekday in range(7):
        assert any(t[0] == weekday and t[2] == 24 for t in pack.production_templates), (
            f"Quiosco missing weekday {weekday} 24h template"
        )


def test_chiperia_san_juan_peak():
    """Chiper\u00eda peaks on weekends (San Juan \u00c1ra = chip\u00e1 peak demand in PY)."""
    pack = PACKS["Chiper\u00eda"]
    weekday_slots = {t[0]: t[2] for t in pack.production_templates}
    # Saturday (5) and Sunday (6) should be higher than weekdays
    assert weekday_slots[5] > weekday_slots[0]
    assert weekday_slots[6] > weekday_slots[0]


def test_pasteleria_industrial_uses_corporate_volume():
    """Pasteler\u00eda Industrial uses corporate-scale ingredients (Bizcocho pre-horneado, etc.)."""
    pack = PACKS["Pasteler\u00eda Industrial"]
    ingredient_names = {ing[0] for ing in pack.ingredients}
    # Should include industrial-pack ingredients
    assert "Bizcocho pre-horneado" in ingredient_names
    assert "Crema chantilly" in ingredient_names
    assert "Cobertura chocolate" in ingredient_names


def test_cerveceria_has_brew_malts():
    """Cervecer\u00eda pack includes brewing malts and hops (signature craft-brew ingredients)."""
    pack = PACKS["Cervecer\u00eda"]
    ingredient_names = {ing[0] for ing in pack.ingredients}
    assert any("Malta" in n for n in ingredient_names)
    assert any("L\u00fapulo" in n for n in ingredient_names)
    assert "Levadura cervecera" in ingredient_names


# ---- 4. Currency safety: all Gs as int, no float (AGENTS.md money rule) ----


def test_pack_prices_are_integers_gs():
    """AGENTS.md hard rule 1: money is always integer Gs, never float."""
    for pack_name, pack in PACKS.items():
        for ing in pack.ingredients:
            cost = ing[2]
            assert isinstance(cost, int), (
                f"{pack_name} ingredient {ing[0]!r} cost_gs is {type(cost).__name__}={cost}, must be int"
            )
        for prod in pack.products:
            price = prod[3]
            assert isinstance(price, int), (
                f"{pack_name} product {prod[0]!r} price_gs is {type(price).__name__}={price}, must be int"
            )


# ---- 5. Idempotency: seeding a new pack twice is a no-op ----


def test_seed_new_pack_idempotent(session_factory):
    """Run seed_pack() twice for Chiper\u00eda. The second run is a no-op."""
    s1 = session_factory()
    try:
        r1 = seed_pack(s1, "Chiper\u00eda", tenant_name="Idempotency Same")
        s1.commit()
        # First-run counters should be > 0
        assert r1.ingredients > 0
        assert r1.recipes > 0
        assert r1.products > 0
    finally:
        s1.close()

    s2 = session_factory()
    try:
        r2 = seed_pack(s2, "Chiper\u00eda", tenant_name="Idempotency Same")
        s2.commit()
        # Second-run: the 0-arg new rows should be 0 (everything already exists)
        # Idempotency = second run is a complete no-op (all new-row counters = 0).
        # Note: skipped_existing is a placeholder field on PackReport; the
        # real signal is the per-counter totals (ingredients, recipes, etc).
        assert r2.ingredients == 0
        assert r2.recipes == 0
        assert r2.products == 0
        assert r2.recipe_lines == 0
        assert r2.suppliers == 0
        # Tenant row was created on the first run, so the second run
        # doesn't create a new one.
        assert r2.tenant == 0
    finally:
        s2.close()


# ---- 6. Schema sanity: every new pack has suppliers, ingredients, recipes, products ----


def test_new_packs_are_fully_populated():
    """Each new pack must have all 5 lists non-empty."""
    for name in [
        "Food Truck",
        "Quiosco/Minimarket",
        "Chiper\u00eda",
        "Pasteler\u00eda Industrial",
        "Cervecer\u00eda",
    ]:
        pack = PACKS[name]
        assert pack.suppliers, f"{name} has no suppliers"
        assert pack.ingredients, f"{name} has no ingredients"
        assert pack.recipes, f"{name} has no recipes"
        assert pack.recipe_lines, f"{name} has no recipe_lines"
        assert pack.products, f"{name} has no products"
        assert pack.categories, f"{name} has no categories"
        assert pack.production_templates, f"{name} has no production_templates"


# ---- 7. Recipe lines reference real ingredients (no broken refs) ----


def test_chiperia_recipe_lines_resolve_to_real_ingredients():
    """Every recipe_line in Chiper\u00eda points to an ingredient that exists in the same pack."""
    pack = PACKS["Chiper\u00eda"]
    ing_names = {ing[0] for ing in pack.ingredients}
    for line in pack.recipe_lines:
        # line = (recipe_slug, ingredient_name, qty, unit)
        assert line[1] in ing_names, (
            f"Chiper\u00eda recipe {line[0]!r} references unknown ingredient {line[1]!r}"
        )


def test_cerveceria_recipe_lines_resolve_to_real_ingredients():
    """SASKIA-220: every Cervecería recipe_line must point to an ingredient in the same pack.

    Note: Cervecería intentionally does NOT include almidón/chipa ingredients
    (cross-pack ingredient sharing is a SASKIA-210 design violation:
    per-client INSTANCES, not shared DB). The chipa_cervecera recipe was
    removed in favor of operator buying chipería chipa wholesale.
    """
    pack = PACKS["Cervecer\u00eda"]
    ing_names = {ing[0] for ing in pack.ingredients}
    for line in pack.recipe_lines:
        assert line[1] in ing_names, (
            f"Cervecer\u00eda recipe {line[0]!r} references unknown ingredient {line[1]!r}"
        )
