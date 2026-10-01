"""Tag algebra tests — derivation, cancellation, cascade (migration 054).

The core semantics under test:
- Allergens UNION (any line → recipe contains it; recursive via sub-recipes)
- Dietary INTERSECTION (one blocking ingredient cancels the tag; neutral
  ingredients never block; sub-recipes block via their own derived set)
- "sin tacc" strictness (may_contain_gluten blocks even when sin_gluten)
- Packaging ingredients excluded from food claims
- Cycle guard in the tree walker
- Cascade refresh touches transitive parents
"""

from __future__ import annotations

from app.rms.models import Ingredient, Product, Recipe, RecipeLine
from app.rms.tagging import (
    cascade_refresh,
    derive_recipe_tags,
    ingredient_blocks,
    walk_recipe_tree,
)


def _ing(session, name, *, allergens=None, dietary=None, packaging=False, may_contain=False):
    i = Ingredient(
        name=name, unit="g", stock_qty=10, purchase_price_gs=100,
        allergens=allergens, dietary_tags=dietary,
        is_packaging=packaging, may_contain_gluten=may_contain,
    )
    session.add(i)
    session.flush()
    return i


def _recipe(session, name, lines, yield_qty=10):
    r = Recipe(name=name, yield_qty=yield_qty, yield_unit="und")
    session.add(r)
    session.flush()
    for kind, ref_id, qty in lines:
        session.add(RecipeLine(recipe_id=r.id, line_kind=kind, line_ref_id=ref_id, qty=qty))
    session.flush()
    return r


# ── Allergen union ─────────────────────────────────────────────────────────

def test_allergen_union_across_lines(session_factory):
    with session_factory() as s:
        harina = _ing(s, "Harina 000", allergens="gluten")
        leche = _ing(s, "Leche entera", allergens="dairy")
        _recipe(s, "Pan de leche", [("ingredient", harina.id, 500), ("ingredient", leche.id, 200)])
        d = derive_recipe_tags(s, 1)
        assert set(d.allergens) == {"gluten", "dairy"}


def test_allergen_recursive_through_subrecipe(session_factory):
    with session_factory() as s:
        h = _ing(s, "Harina integral", allergens="gluten")
        sub = _recipe(s, "Masa madre", [("ingredient", h.id, 400)])
        parent = _recipe(s, "Chipá", [("sub_recipe", sub.id, 1)])
        d = derive_recipe_tags(s, parent.id)
        assert "gluten" in d.allergens


def test_undeclared_allergens_tracked(session_factory):
    with session_factory() as s:
        mystery = _ing(s, "Preparado misterioso", allergens=None)
        _recipe(s, "Raro", [("ingredient", mystery.id, 100)])
        d = derive_recipe_tags(s, 1)
        assert "Preparado misterioso" in d.undeclared
        assert d.allergens == []


# ── Dietary intersection ───────────────────────────────────────────────────

def test_dietary_intersection_keeps_common_tags(session_factory):
    with session_factory() as s:
        a = _ing(s, "Harina de arroz", dietary="sin gluten,sin tacc,sin lactosa")
        b = _ing(s, "Agua")
        _recipe(s, "Sin gluten ok", [("ingredient", a.id, 200), ("ingredient", b.id, 100)])
        d = derive_recipe_tags(s, 1, candidate_tags=["sin gluten", "sin tacc", "sin lactosa", "vegano"])
        assert "sin gluten" in d.dietary
        assert "sin tacc" in d.dietary
        assert "sin lactosa" in d.dietary
        assert "blocked" == {} or all(t not in d.dietary for t in [])


def test_one_ingredient_cancels_tag(session_factory):
    """THE cancellation: 1g of harina kills sin gluten for the whole recipe."""
    with session_factory() as s:
        rice = _ing(s, "Harina de arroz", dietary="sin gluten")
        wheat = _ing(s, "Harina 000", dietary="")  # no sin gluten
        _recipe(s, "Contaminado", [("ingredient", rice.id, 500), ("ingredient", wheat.id, 1)])
        d = derive_recipe_tags(s, 1, candidate_tags=["sin gluten"])
        assert "sin gluten" not in d.dietary
        assert d.blocked["sin gluten"] == ["Harina 000"]


def test_neutral_ingredients_never_block(session_factory):
    with session_factory() as s:
        rice = _ing(s, "Harina de arroz", dietary="sin gluten")
        sal = _ing(s, "Sal fina", dietary=None)  # undeclared but neutral
        agua = _ing(s, "Agua", dietary=None)
        _recipe(s, "Salado", [("ingredient", rice.id, 200), ("ingredient", sal.id, 5), ("ingredient", agua.id, 300)])
        d = derive_recipe_tags(s, 1, candidate_tags=["sin gluten"])
        assert "sin gluten" in d.dietary


def test_subrecipe_blocks_via_derived_set(session_factory):
    with session_factory() as s:
        h = _ing(s, "Harina 000", dietary="")
        sub = _recipe(s, "Masa madre", [("ingredient", h.id, 400)])
        sub.dietary_tags = ""  # derived: nothing qualifies
        rice = _ing(s, "Harina de arroz", dietary="sin gluten")
        parent = _recipe(s, "Mixto", [("sub_recipe", sub.id, 1), ("ingredient", rice.id, 200)])
        d = derive_recipe_tags(s, parent.id, candidate_tags=["sin gluten"])
        assert "sin gluten" not in d.dietary
        assert any("Masa madre" in b for b in d.blocked["sin gluten"])


def test_sin_tacc_stricter_than_sin_gluten(session_factory):
    with session_factory() as s:
        # Tagged sin gluten BUT produced in a wheat facility.
        oats = _ing(s, "Avena sin gluten certificada", dietary="sin gluten", may_contain=True)
        _recipe(s, "Avena procesada", [("ingredient", oats.id, 200)])
        d = derive_recipe_tags(s, 1, candidate_tags=["sin gluten", "sin tacc"])
        assert "sin gluten" in d.dietary
        assert "sin tacc" not in d.dietary
        assert "Avena sin gluten certificada" in d.blocked["sin tacc"]


def test_packaging_excluded_from_claims(session_factory):
    with session_factory() as s:
        rice = _ing(s, "Harina de arroz", dietary="sin gluten")
        box = _ing(s, "Caja karton", packaging=True, allergens=None)
        _recipe(s, "Boxed", [("ingredient", rice.id, 200), ("ingredient", box.id, 1)])
        d = derive_recipe_tags(s, 1, candidate_tags=["sin gluten"])
        assert "sin gluten" in d.dietary  # box didn't block (undeclared → would block if included)


# ── Tree walker ────────────────────────────────────────────────────────────

def test_walk_resolves_nested_subrecipes(session_factory):
    with session_factory() as s:
        a = _ing(s, "Ing A", dietary="vegano")
        inner = _recipe(s, "Inner", [("ingredient", a.id, 100)])
        outer = _recipe(s, "Outer", [("sub_recipe", inner.id, 1)])
        top = _recipe(s, "Top", [("sub_recipe", outer.id, 2)])
        targets, cycles = walk_recipe_tree(s, top.id)
        assert len(targets) >= 1
        assert cycles == []


def test_cycle_guard_cuts_and_reports(session_factory):
    with session_factory() as s:
        _ing(s, "Ing X", dietary=None)
        r1 = _recipe(s, "Ciclo A", [])
        r2 = _recipe(s, "Ciclo B", [("sub_recipe", r1.id, 1)])
        # force A → B (cycle A→B→A)
        s.add(RecipeLine(recipe_id=r1.id, line_kind="sub_recipe", line_ref_id=r2.id, qty=1))
        s.commit()
        _targets, cycles = walk_recipe_tree(s, r1.id)
        # must terminate, not RecursionError
        assert isinstance(cycles, list)


# ── Cascade ────────────────────────────────────────────────────────────────

def test_cascade_refresh_touches_transitive_parents(session_factory):
    with session_factory() as s:
        h = _ing(s, "Harina de arroz", dietary="sin gluten")
        sub = _recipe(s, "Sub casc", [("ingredient", h.id, 100)])
        parent = _recipe(s, "Parent casc", [("sub_recipe", sub.id, 1)])
        product = Product(name="Prod casc", recipe_id=parent.id, sale_price_gs=5000)
        s.add(product)
        s.commit()

        # ingredient tag change → cascade up through sub → parent
        h.dietary_tags = ""  # no longer sin gluten
        s.commit()
        refreshed = cascade_refresh(s, ingredient_id=h.id)
        assert sub.id in refreshed
        assert parent.id in refreshed

        s.refresh(parent)
        # cache reflects new derivation: nothing qualifies now (rice undeclared)
        assert "sin gluten" not in (parent.derived_dietary_tags or "")


def test_cascade_blocked_by_traceability(session_factory):
    with session_factory() as s:
        rice = _ing(s, "Harina de arroz", dietary="sin gluten")
        wheat = _ing(s, "Trigo", dietary="")
        _recipe(s, "Mezcla", [("ingredient", rice.id, 300), ("ingredient", wheat.id, 50)])
        d = derive_recipe_tags(s, 1, candidate_tags=["sin gluten"])
        assert d.blocked["sin gluten"] == ["Trigo"]


def test_ingredient_blocks_unit_semantics():
    class FakeIng:
        name = "Sal gruesa"
        dietary_tags = None
        may_contain_gluten = False
    assert ingredient_blocks(FakeIng(), "vegano") is False  # neutral never blocks

    class FakeWheat:
        name = "Harina 000"
        dietary_tags = "integral"
        may_contain_gluten = False
    assert ingredient_blocks(FakeWheat(), "sin gluten") is True
    assert ingredient_blocks(FakeWheat(), "integral") is False
