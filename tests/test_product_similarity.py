"""tests/test_product_similarity.py — E31 product similarity tests."""

from __future__ import annotations

from app.rms.models import Ingredient, Product, Recipe, RecipeLine
from app.rms.product_similarity import (
    find_clones,
    ingredient_overlap_count,
    jaccard_similarity,
    most_similar_products,
    product_ingredient_set,
    similarity_matrix,
    suggest_substitute,
)


def _setup_three_products(session):
    """Three products with known ingredient overlap.

    P1: {A, B, C, D}
    P2: {A, B, C, E}   → sim(P1,P2) = 3/5 = 0.6
    P3: {X, Y, Z}       → sim(P1,P3) = 0/7 = 0.0, sim(P2,P3) = 0/7
    """
    ings = {}
    for name in "ABCDEXYZ":
        ing = Ingredient(name=f"sim_{name}_xyz", unit="kg", purchase_price_gs=1000)
        session.add(ing)
        session.flush()
        ings[name] = ing.id

    recipes = {}
    products = {}
    for name, ing_ids in [
        ("P1", ["A", "B", "C", "D"]),
        ("P2", ["A", "B", "C", "E"]),
        ("P3", ["X", "Y", "Z"]),
    ]:
        r = Recipe(name=f"sim_r_{name}_xyz", yield_qty=10, yield_unit="und")
        session.add(r)
        session.flush()
        for iid in ing_ids:
            session.add(
                RecipeLine(recipe_id=r.id, line_kind="ingredient", line_ref_id=ings[iid], qty=0.1)
            )
        p = Product(
            name=f"sim_p_{name}_xyz", portion_label="und", sale_price_gs=5000, recipe_id=r.id
        )
        session.add(p)
        session.flush()
        recipes[name] = r
        products[name] = p
    session.commit()
    return products, recipes


# ---------------------------------------------------------------------------
# Jaccard
# ---------------------------------------------------------------------------


def test_jaccard_identical():
    s = {1, 2, 3}
    assert jaccard_similarity(s, s) == 1.0


def test_jaccard_disjoint():
    s1 = {1, 2, 3}
    s2 = {4, 5, 6}
    assert jaccard_similarity(s1, s2) == 0.0


def test_jaccard_partial_overlap():
    # {1,2,3} ∩ {2,3,4} = {2,3} → 2
    # {1,2,3} ∪ {2,3,4} = {1,2,3,4} → 4
    # 2/4 = 0.5
    assert jaccard_similarity({1, 2, 3}, {2, 3, 4}) == 0.5


def test_jaccard_both_empty():
    assert jaccard_similarity(set(), set()) == 0.0


def test_ingredient_overlap_count():
    assert ingredient_overlap_count({1, 2, 3}, {2, 3, 4}) == 2
    assert ingredient_overlap_count({1, 2}, {3, 4}) == 0


# ---------------------------------------------------------------------------
# product_ingredient_set
# ---------------------------------------------------------------------------


def test_product_ingredient_set_basic(session_factory):
    with session_factory() as s:
        products, _recipes = _setup_three_products(s)
        p1 = products["P1"]
        ing_set = product_ingredient_set(s, p1)
        assert len(ing_set) == 4


def test_product_ingredient_set_no_recipe_returns_empty(session_factory):
    with session_factory() as s:
        p = Product(name="sim_no_recipe_xyz", portion_label="und", sale_price_gs=1000)
        s.add(p)
        s.commit()
        assert product_ingredient_set(s, p) == set()


# ---------------------------------------------------------------------------
# Sub-recipe recursion
# ---------------------------------------------------------------------------


def test_product_ingredient_set_with_sub_recipe(session_factory):
    """Product → Recipe A → SubRecipe B → ingredients."""
    with session_factory() as s:
        ing = Ingredient(name="sim_sub_xyz", unit="kg", purchase_price_gs=1000)
        s.add(ing)
        s.flush()

        # Sub-recipe B → ingredient
        sub = Recipe(name="sim_sub_r_xyz", yield_qty=10, yield_unit="und")
        s.add(sub)
        s.flush()
        s.add(RecipeLine(recipe_id=sub.id, line_kind="ingredient", line_ref_id=ing.id, qty=0.1))

        # Main recipe A → ingredient + sub-recipe
        main = Recipe(name="sim_main_r_xyz", yield_qty=10, yield_unit="und")
        s.add(main)
        s.flush()
        ing2 = Ingredient(name="sim_main_xyz", unit="kg", purchase_price_gs=1000)
        s.add(ing2)
        s.flush()
        s.add(RecipeLine(recipe_id=main.id, line_kind="ingredient", line_ref_id=ing2.id, qty=0.1))
        s.add(RecipeLine(recipe_id=main.id, line_kind="sub_recipe", line_ref_id=sub.id, qty=1))

        p = Product(
            name="sim_p_sub_xyz", portion_label="und", sale_price_gs=1000, recipe_id=main.id
        )
        s.add(p)
        s.commit()

        ing_set = product_ingredient_set(s, p)
        # Should include both ing (from sub-recipe) and ing2 (direct).
        assert len(ing_set) == 2


# ---------------------------------------------------------------------------
# most_similar_products
# ---------------------------------------------------------------------------


def test_most_similar_products(session_factory):
    with session_factory() as s:
        products, _ = _setup_three_products(s)
        p1 = products["P1"]
        sim = most_similar_products(s, p1.id, top_n=5)
        # P1 most similar to P2 (3/5=0.6).
        assert len(sim) == 1
        assert sim[0][0].id == products["P2"].id
        assert abs(sim[0][1] - 0.6) < 1e-6


def test_most_similar_products_unknown_returns_empty(session_factory):
    with session_factory() as s:
        assert most_similar_products(s, 99999) == []


def test_most_similar_products_excludes_self(session_factory):
    with session_factory() as s:
        products, _ = _setup_three_products(s)
        p1 = products["P1"]
        sim = most_similar_products(s, p1.id, top_n=10)
        # No self in results.
        assert not any(p.id == p1.id for p, _ in sim)


# ---------------------------------------------------------------------------
# suggest_substitute
# ---------------------------------------------------------------------------


def test_suggest_substitute_basic(session_factory):
    with session_factory() as s:
        products, _ = _setup_three_products(s)
        p1 = products["P1"]
        subs = suggest_substitute(s, p1.id, similarity_threshold=0.5, price_band_pct=0.5)
        # P2 has 0.6 sim and same price → substitute.
        assert len(subs) >= 1
        assert any(sub.id == products["P2"].id for sub in subs)


def test_suggest_substitute_price_band_excludes(session_factory):
    with session_factory() as s:
        products, _ = _setup_three_products(s)
        # Bump P2's price to 10x to break the 20% band.
        products["P2"].sale_price_gs = 50000
        s.commit()
        subs = suggest_substitute(
            s, products["P1"].id, similarity_threshold=0.5, price_band_pct=0.2
        )
        assert not any(sub.id == products["P2"].id for sub in subs)


def test_suggest_substitute_unknown_product_returns_empty(session_factory):
    with session_factory() as s:
        assert suggest_substitute(s, 99999) == []


# ---------------------------------------------------------------------------
# similarity_matrix
# ---------------------------------------------------------------------------


def test_similarity_matrix_shape(session_factory):
    with session_factory() as s:
        products, _ = _setup_three_products(s)
        mat = similarity_matrix(s)
        # Only P1-P2 has sim>0 (0.6). P1-P3 and P2-P3 are excluded.
        assert len(mat) == 1
        # Verify P1-P2 entry exists with correct sim.
        p1_id, p2_id = products["P1"].id, products["P2"].id
        key = (min(p1_id, p2_id), max(p1_id, p2_id))
        assert key in mat
        assert abs(mat[key] - 0.6) < 1e-6


def test_similarity_matrix_zero_sim_excluded(session_factory):
    """Pair with no overlap should not appear in matrix."""
    with session_factory() as s:
        products, _ = _setup_three_products(s)
        mat = similarity_matrix(s)
        # P1-P3 and P2-P3 should be 0, excluded.
        p1_id, p3_id = products["P1"].id, products["P3"].id
        key = (min(p1_id, p3_id), max(p1_id, p3_id))
        assert key not in mat


# ---------------------------------------------------------------------------
# find_clones
# ---------------------------------------------------------------------------


def test_find_clones_detects_high_sim(session_factory):
    with session_factory() as s:
        products, _ = _setup_three_products(s)
        clones = find_clones(s, threshold=0.5)
        # P1-P2 sim=0.6 → above threshold.
        assert any(c[0].id == products["P1"].id and c[1].id == products["P2"].id for c in clones)


def test_find_clones_high_threshold_excludes_partial(session_factory):
    with session_factory() as s:
        _products, _ = _setup_three_products(s)
        clones = find_clones(s, threshold=0.9)
        # 0.6 < 0.9 → no clones detected.
        assert clones == []


def test_find_clones_includes_similarity_score(session_factory):
    with session_factory() as s:
        _products, _ = _setup_three_products(s)
        clones = find_clones(s, threshold=0.5)
        # Each tuple has (product_a, product_b, similarity).
        assert len(clones) >= 1
        sim = clones[0][2]
        assert 0.0 < sim <= 1.0
