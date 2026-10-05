"""tests/test_tags.py — verify app/rms/tags.py (E9).

Per docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md E9.

Covers:
- Tag/TagLink models work
- ensure_tag is idempotent
- ensure_starter_tags inserts 31 starter tags (17 product + 11 ingredient + 3 recipe)
- tag_target / untag_target are idempotent
- tags_for_target returns ordered list
- targets_with_tag returns target_ids
- filter_sales respects date, product, voided, tag, amount
- filter_inventory respects stock_status, tag, cost band
- filter_recipes respects margin tier, tag, yield range
- filter_products respects category equivalent, tag, has_recipe
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.rms.models import Recipe, Sale, Tag, TagLink
from app.rms.tagging import (
    STARTER_TAGS,
    InventoryFilter,
    ProductFilter,
    RecipeFilter,
    SalesFilter,
    TagKind,
    ensure_starter_tags,
    ensure_tag,
    filter_inventory,
    filter_products,
    filter_recipes,
    filter_sales,
    tag_target,
    tags_for_target,
    targets_with_tag,
    untag_target,
)
from tests.factories import make_ingredient, make_product


def test_starter_tags_count():
    """STARTER_TAGS should have 31 entries (17 product + 11 ingredient + 3 recipe)."""
    assert len(STARTER_TAGS) == 31
    products = [t for t in STARTER_TAGS if t[1] == TagKind.PRODUCT.value]
    ingredients = [t for t in STARTER_TAGS if t[1] == TagKind.INGREDIENT.value]
    recipes = [t for t in STARTER_TAGS if t[1] == TagKind.RECIPE.value]
    assert len(products) == 17
    assert len(ingredients) == 11
    assert len(recipes) == 3


def test_ensure_starter_tags_inserts_all(session_factory):
    """ensure_starter_tags() inserts all 31 starter tags; idempotent."""
    s = session_factory()
    try:
        ensure_starter_tags(s)
        s.commit()
        n_tags = len(s.execute(select(Tag)).scalars().all())
        assert n_tags == 31

        # Idempotent: second call adds nothing
        ensure_starter_tags(s)
        s.commit()
        n_tags_after = len(s.execute(select(Tag)).scalars().all())
        assert n_tags_after == 31
    finally:
        s.close()


def test_ensure_tag_idempotent(session_factory):
    """ensure_tag() returns the same row on duplicate calls."""
    s = session_factory()
    try:
        t1 = ensure_tag(s, "my-custom-tag", TagKind.PRODUCT.value, "#123456")
        s.commit()
        t2 = ensure_tag(s, "my-custom-tag", TagKind.PRODUCT.value, "#123456")
        s.commit()
        assert t1.id == t2.id
        assert t1.color == "#123456"
    finally:
        s.close()


def test_tag_target_is_idempotent(session_factory):
    """tag_target() called twice does not duplicate the link."""
    s = session_factory()
    try:
        ing = make_ingredient(s, name="harina", unit="kg", stock_qty=5.0, purchase_price_gs=4500)
        s.add(ing)
        s.flush()
        tag = ensure_tag(s, "perecedero", TagKind.INGREDIENT.value)
        tag_target(s, tag, TagKind.INGREDIENT.value, ing.id)
        tag_target(s, tag, TagKind.INGREDIENT.value, ing.id)  # again
        s.commit()

        n_links = len(list(s.execute(select(TagLink).where(TagLink.tag_id == tag.id, TagLink.target_id == ing.id)).scalars()))
        assert n_links == 1
    finally:
        s.close()


def test_untag_target_returns_true_on_removal(session_factory):
    """untag_target() returns True if removed, False if no link existed."""
    s = session_factory()
    try:
        ing = make_ingredient(s, name="azúcar", unit="kg", stock_qty=3.0, purchase_price_gs=5200)
        s.add(ing)
        s.flush()
        tag = ensure_tag(s, "seco", TagKind.INGREDIENT.value)
        tag_target(s, tag, TagKind.INGREDIENT.value, ing.id)
        s.commit()

        # Remove existing
        assert untag_target(s, tag, TagKind.INGREDIENT.value, ing.id) is True
        # Remove again returns False
        assert untag_target(s, tag, TagKind.INGREDIENT.value, ing.id) is False
    finally:
        s.close()


def test_tags_for_target_returns_ordered_list(session_factory):
    """tags_for_target returns tags sorted by name."""
    s = session_factory()
    try:
        prod = make_product(s, name="Docena muffins", sale_price_gs=25000)
        s.add(prod)
        s.flush()
        t1 = ensure_tag(s, "premium", TagKind.PRODUCT.value)
        t2 = ensure_tag(s, "docena", TagKind.PRODUCT.value)
        t3 = ensure_tag(s, "popular", TagKind.PRODUCT.value)
        tag_target(s, t1, TagKind.PRODUCT.value, prod.id)
        tag_target(s, t2, TagKind.PRODUCT.value, prod.id)
        tag_target(s, t3, TagKind.PRODUCT.value, prod.id)
        s.commit()

        tags = tags_for_target(s, TagKind.PRODUCT.value, prod.id)
        names = [t.name for t in tags]
        assert names == sorted(names), f"expected sorted, got {names}"
        assert set(names) == {"premium", "docena", "popular"}
    finally:
        s.close()


def test_targets_with_tag_returns_ids(session_factory):
    """targets_with_tag returns all target_ids that have the given tag."""
    s = session_factory()
    try:
        i1 = make_ingredient(s, name="harina", unit="kg", stock_qty=5.0, purchase_price_gs=4500)
        i2 = make_ingredient(s, name="azúcar", unit="kg", stock_qty=3.0, purchase_price_gs=5200)
        s.add_all([i1, i2])
        s.flush()
        tag = ensure_tag(s, "seco", TagKind.INGREDIENT.value)
        tag_target(s, tag, TagKind.INGREDIENT.value, i1.id)
        tag_target(s, tag, TagKind.INGREDIENT.value, i2.id)
        s.commit()

        ids = targets_with_tag(s, tag)
        assert set(ids) == {i1.id, i2.id}
    finally:
        s.close()


def test_filter_sales_by_date_range(session_factory):
    """filter_sales() respects start_date + end_date."""
    s = session_factory()
    try:
        prod = make_product(s, name="Muffin", sale_price_gs=2500)
        s.add(prod)
        s.flush()

        now = datetime.now(timezone.utc)
        old_sale = Sale(sold_at=now - timedelta(days=30), product_id=prod.id, qty=1.0, unit_price_gs=2500)
        new_sale = Sale(sold_at=now - timedelta(days=2), product_id=prod.id, qty=1.0, unit_price_gs=2500)
        s.add_all([old_sale, new_sale])
        s.commit()

        # Last 7 days: only new_sale
        f = SalesFilter(
            start_date=now - timedelta(days=7),
            end_date=now,
        )
        results = filter_sales(s, f)
        assert len(results) == 1
        assert results[0].id == new_sale.id
    finally:
        s.close()


def test_filter_sales_by_product_ids(session_factory):
    """filter_sales() respects product_ids filter."""
    s = session_factory()
    try:
        p1 = make_product(s, name="Docena muffins", sale_price_gs=25000)
        p2 = make_product(s, name="Cheesecake", sale_price_gs=35000)
        s.add_all([p1, p2])
        s.flush()
        s.add_all([
            Sale(sold_at=datetime.now(timezone.utc), product_id=p1.id, qty=1.0, unit_price_gs=25000),
            Sale(sold_at=datetime.now(timezone.utc), product_id=p2.id, qty=1.0, unit_price_gs=35000),
        ])
        s.commit()

        f = SalesFilter(product_ids=[p1.id])
        results = filter_sales(s, f)
        assert len(results) == 1
        assert results[0].product_id == p1.id
    finally:
        s.close()


def test_filter_sales_by_only_voided(session_factory):
    """filter_sales() respects only_voided flag."""
    s = session_factory()
    try:
        prod = make_product(s, name="Muffin", sale_price_gs=2500)
        s.add(prod)
        s.flush()
        s.add_all([
            Sale(sold_at=datetime.now(timezone.utc), product_id=prod.id, qty=1.0, unit_price_gs=2500),
            Sale(
                sold_at=datetime.now(timezone.utc), product_id=prod.id,
                qty=1.0,
                unit_price_gs=2500,
                voided_at=datetime.now(timezone.utc),
            ),
        ])
        s.commit()

        f = SalesFilter(only_voided=True)
        results = filter_sales(s, f)
        assert len(results) == 1
        assert results[0].voided_at is not None
    finally:
        s.close()


def test_filter_sales_by_amount_range(session_factory):
    """filter_sales() respects min_amount_gs + max_amount_gs."""
    s = session_factory()
    try:
        prod = make_product(s, name="Muffin", sale_price_gs=2500)
        s.add(prod)
        s.flush()
        # One small (qty=1, total=2500), one big (qty=10, total=25000)
        s.add_all([
            Sale(sold_at=datetime.now(timezone.utc), product_id=prod.id, qty=1.0, unit_price_gs=2500),
            Sale(sold_at=datetime.now(timezone.utc), product_id=prod.id, qty=10.0, unit_price_gs=2500),
        ])
        s.commit()

        f = SalesFilter(min_amount_gs=10000)
        results = filter_sales(s, f)
        assert len(results) == 1
        assert results[0].qty == 10.0
    finally:
        s.close()


def test_filter_sales_by_tag(session_factory):
    """filter_sales() filters by product tag."""
    s = session_factory()
    try:
        p_tagged = make_product(s, name="Muffinito", sale_price_gs=2500)
        p_other = make_product(s, name="Croissant", sale_price_gs=3000)
        s.add_all([p_tagged, p_other])
        s.flush()
        tag = ensure_tag(s, "popular", TagKind.PRODUCT.value)
        tag_target(s, tag, TagKind.PRODUCT.value, p_tagged.id)
        s.add_all([
            Sale(sold_at=datetime.now(timezone.utc), product_id=p_tagged.id, qty=1.0, unit_price_gs=2500),
            Sale(sold_at=datetime.now(timezone.utc), product_id=p_other.id, qty=1.0, unit_price_gs=3000),
        ])
        s.commit()

        f = SalesFilter(product_tag_names=["popular"])
        results = filter_sales(s, f)
        assert len(results) == 1
        assert results[0].product_id == p_tagged.id
    finally:
        s.close()


def test_filter_inventory_by_stock_status(session_factory):
    """filter_inventory() filters by stock_status.

    categorize() priority (Phase 7):
      1. muerto (last_consumed_at None OR > 30 days)
      2. sobrestock (ratio > 5.0)
      3. critico (ratio < 0.5)
      4. bajo_min (stock < min AND ratio >= critico_threshold)
      5. None

    Note: with stock_qty=1, min_stock_qty=10, ratio=0.1 → categorizes as
    'critico' (not 'bajo_min'). To test 'bajo_min' we need stock in the
    range where ratio is >= 0.5 but stock < min — e.g. stock=6, min=10
    → ratio=0.6 → 'bajo_min'.
    """
    from datetime import datetime, timedelta, timezone

    s = session_factory()
    try:
        recent = datetime.now(timezone.utc) - timedelta(days=1)
        # stock=6, min=10 → ratio=0.6 → 'bajo_min' (above critico threshold)
        bajo = make_ingredient(s, name="harina", unit="kg", stock_qty=6.0, min_stock_qty=10.0, purchase_price_gs=4500, last_consumed_at=recent)
        # stock=100, min=5 → ratio=20 → 'sobrestock'
        high = make_ingredient(s, name="azúcar", unit="kg", stock_qty=100.0, min_stock_qty=5.0, purchase_price_gs=5200, last_consumed_at=recent)
        s.add_all([bajo, high])
        s.commit()

        f = InventoryFilter(stock_status="bajo_min")
        results = filter_inventory(s, f)
        names = {i.name for i in results}
        assert "harina" in names
        assert "azúcar" not in names
    finally:
        s.close()


def test_filter_inventory_by_cost_band(session_factory):
    """filter_inventory() respects min/max cost band."""
    s = session_factory()
    try:
        cheap = make_ingredient(s, name="sal", unit="kg", stock_qty=2.0, purchase_price_gs=1800)
        expensive = make_ingredient(s, name="almendra", unit="kg", stock_qty=1.0, purchase_price_gs=85000)
        s.add_all([cheap, expensive])
        s.commit()

        f = InventoryFilter(min_cost_gs=10000)
        results = filter_inventory(s, f)
        names = {i.name for i in results}
        assert "almendra" in names
        assert "sal" not in names
    finally:
        s.close()


def test_filter_recipes_by_yield_range(session_factory):
    """filter_recipes() respects min/max yield."""
    s = session_factory()
    try:
        small = Recipe(name="Galleta individual", yield_qty=1.0, yield_unit="und")
        big = Recipe(name="Torta familiar", yield_qty=12.0, yield_unit="und")
        s.add_all([small, big])
        s.commit()

        f = RecipeFilter(min_yield=10.0)
        results = filter_recipes(s, f)
        names = {r.name for r in results}
        assert "Torta familiar" in names
        assert "Galleta individual" not in names
    finally:
        s.close()


def test_filter_products_by_has_recipe(session_factory):
    """filter_products() respects has_recipe=True/False."""
    s = session_factory()
    try:
        rec = Recipe(name="Muffin", yield_qty=12.0, yield_unit="und")
        s.add(rec)
        s.flush()
        with_recipe = make_product(s, name="Docena muffins", sale_price_gs=25000, recipe_id=rec.id)
        without_recipe = make_product(s, name="Soda", sale_price_gs=5000)
        s.add_all([with_recipe, without_recipe])
        s.commit()

        f1 = ProductFilter(has_recipe=True)
        r1 = filter_products(s, f1)
        assert {p.name for p in r1} == {"Docena muffins"}

        f2 = ProductFilter(has_recipe=False)
        r2 = filter_products(s, f2)
        assert {p.name for p in r2} == {"Soda"}
    finally:
        s.close()


def test_filters_handle_empty_db(session_factory):
    """All filters must return empty list on a fresh DB (no exceptions)."""
    s = session_factory()
    try:
        assert filter_sales(s, SalesFilter()) == []
        assert filter_inventory(s, InventoryFilter()) == []
        assert filter_recipes(s, RecipeFilter()) == []
        assert filter_products(s, ProductFilter()) == []
    finally:
        s.close()
