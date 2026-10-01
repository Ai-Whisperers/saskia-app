"""Tests for batch_compute_prime_cost (Phase 14 #23 — N+1 fix for /productos).

The /productos list route previously called `compute_prime_cost` once per
product (50 products = 50 round-trips × 3+ session.get each = 200+ DB
queries). This batch function computes the same PrimeCostBreakdown for N
products in a single pass with eager-loaded .recipe + a single
ComplianceInfo lookup.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.rms.models import (
    ComplianceInfo,
    Ingredient,
    Product,
)
from app.rms.prime_cost import batch_compute_prime_cost, compute_prime_cost
from tests.factories import ing_line, make_price_event, make_product, make_recipe


@pytest.fixture
def compliance(session_factory):
    """Update the auto-seeded ComplianceInfo row (id=1) to known values."""
    session = session_factory()
    ci = session.get(ComplianceInfo, 1)
    if ci is None:
        ci = ComplianceInfo(id=1)
        session.add(ci)
    ci.labor_cost_per_hour_gs = 20000
    ci.overhead_multiplier_pct = 15
    session.commit()
    session.close()


def _make_flour(session, name: str = "flour", price_gs: int = 100) -> Ingredient:
    """Create an Ingredient with a known price for tests.

    Sets BOTH the legacy `purchase_price_gs` column (read by
    `current_variant_price`, used by `recipe_batch_cost_gs`) AND adds a
    `IngredientPriceEvent` (so audit/history queries also see it).
    """
    ing = Ingredient(name=name, unit="g", purchase_price_gs=price_gs)
    session.add(ing)
    session.flush()
    make_price_event(session, ing, price_gs=price_gs)
    return ing


def test_empty_list_returns_empty_dict(session_factory, compliance):
    """batch_compute_prime_cost([]) must return {} — no DB calls."""
    session = session_factory()
    assert batch_compute_prime_cost(session, []) == {}


def test_single_product_matches_per_product_path(session_factory, compliance):
    """batch + per-product results must agree on every field."""
    session = session_factory()
    ing = _make_flour(session, "flour-batch", 100)

    recipe = make_recipe(
        session,
        name="R-batch",
        yield_qty=1,
        yield_percentage=Decimal("0.8"),
        direct_labor_minutes=30.0,
        lines=[ing_line(ingredient=ing, qty=100)],
    )
    product = make_product(
        session,
        name="ProdA",
        sku="sku-batch-001",
        sale_price_gs=50000,
        recipe_id=recipe.id,
    )
    session.flush()

    per_product = compute_prime_cost(session, product.id)
    batched = batch_compute_prime_cost(session, [product])

    assert product.id in batched
    pc = batched[product.id]

    assert pc.materials_cost_gs == per_product.materials_cost_gs
    assert pc.yield_corrected_cost_gs == per_product.yield_corrected_cost_gs
    assert pc.labor_cost_gs == per_product.labor_cost_gs
    assert pc.overhead_cost_gs == per_product.overhead_cost_gs
    assert pc.prime_cost_gs == per_product.prime_cost_gs
    assert pc.sale_price_gs == per_product.sale_price_gs
    assert pc.gross_margin_gs == per_product.gross_margin_gs
    assert pc.notes == per_product.notes


def test_multiple_products_all_returned(session_factory, compliance):
    """N products → N entries in the result dict."""
    session = session_factory()
    ing = _make_flour(session, "flour-multi", 50)

    products = []
    for i in range(5):
        recipe = make_recipe(
            session,
            name=f"R-multi-{i}",
            yield_qty=1,
            yield_percentage=Decimal("1.0"),
            direct_labor_minutes=10.0,
            lines=[ing_line(ingredient=ing, qty=50)],
        )
        p = make_product(
            session,
            name=f"P{i}",
            sku=f"sku-multi-{i:03d}",
            sale_price_gs=10000,
            recipe_id=recipe.id,
        )
        products.append(p)
    session.flush()

    batched = batch_compute_prime_cost(session, products)
    assert len(batched) == 5
    assert {p.id for p in products} == set(batched.keys())


def test_product_without_recipe_returns_note(session_factory, compliance):
    """Product with no recipe → 'Producto sin receta' note + None cost fields."""
    session = session_factory()
    product = make_product(
        session, name="SinReceta", sku="sku-norec", sale_price_gs=10000, recipe_id=None
    )
    session.flush()

    batched = batch_compute_prime_cost(session, [product])
    pc = batched[product.id]

    assert pc.materials_cost_gs is None
    assert pc.prime_cost_gs is None
    assert "Producto sin receta" in pc.notes


def test_invalid_yield_percentage_is_noted(session_factory, compliance):
    """yield_percentage > 1.0 → noted, treated as None (no yield correction)."""
    session = session_factory()
    ing = _make_flour(session, "flour-y", 100)

    recipe = make_recipe(
        session,
        name="R-bad-yield",
        yield_qty=1,
        yield_percentage=Decimal("1.5"),
        direct_labor_minutes=None,
        lines=[ing_line(ingredient=ing, qty=50)],
    )
    product = make_product(
        session,
        name="BadYield",
        sku="sku-badyield",
        sale_price_gs=10000,
        recipe_id=recipe.id,
    )
    session.flush()

    batched = batch_compute_prime_cost(session, [product])
    pc = batched[product.id]

    assert pc.yield_corrected_cost_gs is None
    assert pc.prime_cost_gs is None
    assert any("yield_percentage inválido" in n for n in pc.notes)


def test_compliance_info_fetched_once_for_n_products(session_factory, compliance):
    """ComplianceInfo is fetched exactly once even for N products."""
    session = session_factory()
    ing = _make_flour(session, "flour-spy", 10)

    products = []
    for i in range(10):
        recipe = make_recipe(
            session,
            name=f"R-spy-{i}",
            yield_qty=1,
            yield_percentage=Decimal("1.0"),
            direct_labor_minutes=5.0,
            lines=[ing_line(ingredient=ing, qty=20)],
        )
        p = make_product(
            session,
            name=f"Spy{i}",
            sku=f"sku-spy-{i:03d}",
            sale_price_gs=5000,
            recipe_id=recipe.id,
        )
        products.append(p)
    session.flush()

    original_get = session.get
    ci_call_count = 0

    def counting_get(model, pk):
        nonlocal ci_call_count
        if model is ComplianceInfo and pk == 1:
            ci_call_count += 1
        return original_get(model, pk)

    session.get = counting_get
    try:
        batch_compute_prime_cost(session, products)
    finally:
        session.get = original_get

    assert ci_call_count == 1, (
        f"ComplianceInfo should be fetched ONCE for N products, got {ci_call_count}"
    )


def test_zero_labor_minutes_noted_but_not_blocking(session_factory, compliance):
    """direct_labor_minutes=0 → 'sin tiempo' note, but product is still usable."""
    import uuid
    session = session_factory()
    ing_name = f"flour-nolabor-{uuid.uuid4().hex[:8]}"
    ing = _make_flour(session, ing_name, 200)

    recipe = make_recipe(
        session,
        name=f"R-nolabor-{uuid.uuid4().hex[:8]}",
        yield_qty=1,
        yield_percentage=Decimal("1.0"),
        direct_labor_minutes=0,
        lines=[ing_line(ingredient=ing, qty=50)],
    )
    product = make_product(
        session,
        name=f"NoLabor-{uuid.uuid4().hex[:8]}",
        sku=f"sku-nolabor-{uuid.uuid4().hex[:8]}",
        sale_price_gs=20000,
        recipe_id=recipe.id,
    )
    session.flush()

    batched = batch_compute_prime_cost(session, [product])
    pc = batched[product.id]

    assert pc.labor_cost_gs is None
    assert pc.prime_cost_gs is not None
    assert any("sin tiempo de mano de obra" in n for n in pc.notes)


def test_no_product_get_calls_inside_loop(session_factory, compliance):
    """batch_compute_prime_cost reads .recipe from the eager-loaded
    relationship — no per-product session.get for Product inside the loop.
    """
    session = session_factory()
    ing = _make_flour(session, "flour-eager", 100)

    products = []
    for i in range(3):
        recipe = make_recipe(
            session,
            name=f"R-eager-{i}",
            yield_qty=1,
            yield_percentage=Decimal("1.0"),
            lines=[ing_line(ingredient=ing, qty=50)],
        )
        p = make_product(
            session,
            name=f"Eager{i}",
            sku=f"sku-eager-{i:03d}",
            sale_price_gs=10000,
            recipe_id=recipe.id,
        )
        products.append(p)
    session.flush()

    products = session.scalars(
        select(Product)
        .where(Product.id.in_([p.id for p in products]))
        .options(selectinload(Product.recipe))
    ).all()

    original_get = session.get
    product_get_count = 0

    def counting_get(model, pk):
        nonlocal product_get_count
        if model is Product:
            product_get_count += 1
        return original_get(model, pk)

    session.get = counting_get
    try:
        batch_compute_prime_cost(session, products)
    finally:
        session.get = original_get

    assert product_get_count == 0, (
        f"batch_compute_prime_cost should NOT session.get(Product), got {product_get_count}"
    )