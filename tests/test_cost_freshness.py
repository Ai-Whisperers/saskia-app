"""tests/test_cost_freshness.py — Test app/rms/cost_freshness.py (Phase 4.5).

The module answers "is this product's sale price computed on stale
costs?" — the productos table shows a "Costo actualizado" column.

Main API: product_cost_freshness(session, [products]) →
{product_id: datetime | None} in ~3 queries (products → recipes → lines+events).
The list route uses this to stay N+1-free.

A regression here would either:
  - Show every product as "never costed" (false negatives in UI)
  - Show every product with the same wrong timestamp (false positives)
  - Hit the DB N times instead of 3 (N+1 perf regression)
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.rms.cost_freshness import product_cost_freshness
from app.rms.models import (
    Ingredient,
    IngredientPriceEvent,
    Product,
    Recipe,
    RecipeLine,
)


def _make_ingredient(session, name: str) -> Ingredient:
    ing = Ingredient(name=name, unit="kg", stock_qty=10.0, purchase_price_gs=5000)
    session.add(ing)
    session.commit()
    session.refresh(ing)
    return ing


def _make_recipe(session, name: str, family: str = "test") -> Recipe:
    r = Recipe(name=name, yield_qty=10, yield_unit="und", family=family)
    session.add(r)
    session.commit()
    session.refresh(r)
    return r


def _make_product(session, name: str, recipe: Recipe | None = None, price: int = 1000) -> Product:
    p = Product(name=name, sale_price_gs=price, recipe_id=recipe.id if recipe else None)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def _add_recipe_line(
    session, recipe: Recipe, ingredient: Ingredient, qty: float = 0.1
) -> RecipeLine:
    line = RecipeLine(
        recipe_id=recipe.id,
        line_kind="ingredient",
        line_ref_id=ingredient.id,
        qty=qty,
        line_unit="kg",
    )
    session.add(line)
    session.commit()
    return line


def _add_price_event(
    session, ingredient: Ingredient, price_gs: int, recorded_at: datetime, source: str = "manual"
) -> IngredientPriceEvent:
    ev = IngredientPriceEvent(
        ingredient_id=ingredient.id,
        price_gs=price_gs,
        recorded_at=recorded_at,
        source=source,
    )
    session.add(ev)
    session.commit()
    return ev


class TestProductCostFreshness:
    def test_empty_list_returns_empty_dict(self, session_factory):
        with session_factory() as s:
            assert product_cost_freshness(s, []) == {}

    def test_product_without_recipe_is_none(self, session_factory):
        with session_factory() as s:
            p = _make_product(s, "_smoke_no_recipe")
        with session_factory() as s:
            result = product_cost_freshness(s, [p])
        assert result == {p.id: None}

    def test_recipe_with_no_lines_is_none(self, session_factory):
        # Recipe exists but has zero ingredients — effectively "never costed".
        with session_factory() as s:
            r = _make_recipe(s, "_smoke_empty_recipe")
            p = _make_product(s, "_smoke_p", recipe=r)
        with session_factory() as s:
            result = product_cost_freshness(s, [p])
        assert result == {p.id: None}

    def test_ingredient_without_price_events_is_none(self, session_factory):
        # Recipe references an ingredient that has no IngredientPriceEvent rows.
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_ing")
            r = _make_recipe(s, "_smoke_recipe")
            _add_recipe_line(s, r, ing)
            p = _make_product(s, "_smoke_p", recipe=r)
        with session_factory() as s:
            result = product_cost_freshness(s, [p])
        assert result == {p.id: None}

    def test_returns_event_timestamp_for_single_ingredient(self, session_factory):
        ts = datetime(2026, 9, 15, 10, 30, tzinfo=timezone.utc)
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_ing_1")
            r = _make_recipe(s, "_smoke_recipe_1")
            _add_recipe_line(s, r, ing)
            p = _make_product(s, "_smoke_p_1", recipe=r)
            _add_price_event(s, ing, price_gs=5000, recorded_at=ts)
        with session_factory() as s:
            result = product_cost_freshness(s, [p])
        # SQLite drops tz info on roundtrip; compare naive.
        assert result[p.id].replace(tzinfo=None) == ts.replace(tzinfo=None)

    def test_returns_max_timestamp_across_ingredients(self, session_factory):
        # Recipe with 2 ingredients → freshness is the LATER event.
        old = datetime(2026, 8, 1, tzinfo=timezone.utc)
        new = datetime(2026, 9, 15, tzinfo=timezone.utc)
        with session_factory() as s:
            ing_a = _make_ingredient(s, "_smoke_ing_a")
            ing_b = _make_ingredient(s, "_smoke_ing_b")
            r = _make_recipe(s, "_smoke_recipe_2")
            _add_recipe_line(s, r, ing_a)
            _add_recipe_line(s, r, ing_b)
            p = _make_product(s, "_smoke_p_2", recipe=r)
            _add_price_event(s, ing_a, 4000, old)
            _add_price_event(s, ing_b, 6000, new)
        with session_factory() as s:
            result = product_cost_freshness(s, [p])
        assert result[p.id].replace(tzinfo=None) == new.replace(tzinfo=None)  # max wins

    def test_returns_max_timestamp_across_multiple_events(self, session_factory):
        # One ingredient with multiple events → freshness is the LATEST.
        old = datetime(2026, 7, 1, tzinfo=timezone.utc)
        mid = datetime(2026, 8, 1, tzinfo=timezone.utc)
        new = datetime(2026, 9, 1, tzinfo=timezone.utc)
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_ing_multi")
            r = _make_recipe(s, "_smoke_recipe_3")
            _add_recipe_line(s, r, ing)
            p = _make_product(s, "_smoke_p_3", recipe=r)
            _add_price_event(s, ing, 5000, old)
            _add_price_event(s, ing, 5500, mid)
            _add_price_event(s, ing, 6000, new)
        with session_factory() as s:
            result = product_cost_freshness(s, [p])
        assert result[p.id].replace(tzinfo=None) == new.replace(tzinfo=None)

    def test_sub_recipes_included_in_tree(self, session_factory):
        # Product → Recipe A → Recipe B (sub_recipe) → Ingredient.
        # Freshness should still see the ingredient's event.
        ts = datetime(2026, 9, 15, tzinfo=timezone.utc)
        with session_factory() as s:
            ing = _make_ingredient(s, "_smoke_ing_sub")
            child = _make_recipe(s, "_smoke_recipe_child")
            parent = _make_recipe(s, "_smoke_recipe_parent")
            # child has the ingredient
            _add_recipe_line(s, child, ing)
            # parent has child as a sub_recipe
            sub_line = RecipeLine(
                recipe_id=parent.id,
                line_kind="sub_recipe",
                line_ref_id=child.id,
                qty=1.0,
                line_unit="und",
            )
            s.add(sub_line)
            s.commit()
            p = _make_product(s, "_smoke_p_sub", recipe=parent)
            _add_price_event(s, ing, 5000, ts)
        with session_factory() as s:
            result = product_cost_freshness(s, [p])
        assert result[p.id].replace(tzinfo=None) == ts.replace(tzinfo=None)

    def test_mixed_batch_returns_mixed_results(self, session_factory):
        ts = datetime(2026, 9, 15, tzinfo=timezone.utc)
        with session_factory() as s:
            # Product A: full chain with event
            ing_a = _make_ingredient(s, "_smoke_mix_a")
            r_a = _make_recipe(s, "_smoke_recipe_mix_a")
            _add_recipe_line(s, r_a, ing_a)
            p_a = _make_product(s, "_smoke_p_mix_a", recipe=r_a)
            _add_price_event(s, ing_a, 5000, ts)
            # Product B: no recipe
            p_b = _make_product(s, "_smoke_p_mix_b")
            # Product C: recipe with no priced events
            r_c = _make_recipe(s, "_smoke_recipe_mix_c")
            p_c = _make_product(s, "_smoke_p_mix_c", recipe=r_c)
        with session_factory() as s:
            result = product_cost_freshness(s, [p_a, p_b, p_c])
        assert result[p_a.id].replace(tzinfo=None) == ts.replace(tzinfo=None)
        assert result[p_b.id] is None
        assert result[p_c.id] is None

    def test_returns_dict_for_all_input_products(self, session_factory):
        # Even when result is all None, the keys must match the input.
        with session_factory() as s:
            p1 = _make_product(s, "_smoke_batch_1")
            p2 = _make_product(s, "_smoke_batch_2")
            p3 = _make_product(s, "_smoke_batch_3")
        with session_factory() as s:
            result = product_cost_freshness(s, [p1, p2, p3])
        assert set(result.keys()) == {p1.id, p2.id, p3.id}
        assert all(v is None for v in result.values())
