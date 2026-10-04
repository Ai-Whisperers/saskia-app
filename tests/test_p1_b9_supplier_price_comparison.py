"""P1-B9 — Supplier price comparison page (Gs. 4.3M/year savings opportunity).

These tests exercise:
  * GET /suppliers/{id}/precios — endpoint contract
  * app/rms/supplier_prices.get_price_comparison — domain logic
  * The HTML template renders is-cheapest / is-overpriced classes

NOTE on the schema: the original task spec referenced IngredientPriceEvent.
That model only stores ingredient-level price history with no supplier_id, so
it cannot answer "who charges what". The actual schema (Sprint 7 Decision A1)
stores per-supplier prices on ``IngredientVariant``. Tests use that model.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.crud


@pytest.fixture
def make_variant_prices(session_factory):
    """Build N ingredients × N suppliers, each ingredient with multiple variants.

    Returns a callable ``make(ingredient_specs)`` where ingredient_specs is a
    list of dicts::

        [
            {"name": "harina QA", "variants": {"Molino A": 4500, "Molino B": 5000}},
            {"name": "azúcar QA", "variants": {"Distribuidora X": 3000}},
        ]

    Returns a dict {ingredient_name: {"supplier_name": {"supplier_id": ..,
    "variant_id": .., "price_gs": ..}}} so tests can look up IDs by name.
    """
    from app.rms.models import Ingredient, IngredientVariant, Supplier

    def _make(ingredient_specs):
        out: dict[str, dict[str, dict]] = {}
        with session_factory() as s:
            for spec in ingredient_specs:
                ing_name = spec["name"]
                ing = s.scalar(
                    __import__("sqlalchemy").select(Ingredient).where(Ingredient.name == ing_name)
                )
                if ing is None:
                    ing = Ingredient(
                        name=ing_name,
                        unit="kg",
                        stock_qty=10.0,
                        min_stock_qty=1.0,
                    )
                    s.add(ing)
                    s.flush()

                ing_map: dict[str, dict] = {}
                for sup_name, price_gs in spec["variants"].items():
                    sup = s.scalar(
                        __import__("sqlalchemy").select(Supplier).where(Supplier.name == sup_name)
                    )
                    if sup is None:
                        sup = Supplier(name=sup_name, is_active=True)
                        s.add(sup)
                        s.flush()
                    variant = IngredientVariant(
                        ingredient_id=ing.id,
                        supplier_id=sup.id,
                        package_size=1.0,
                        package_unit="kg",
                        purchase_price_gs=price_gs,
                        preferred=(price_gs == min(spec["variants"].values())),
                    )
                    s.add(variant)
                    s.flush()
                    ing_map[sup_name] = {
                        "supplier_id": sup.id,
                        "variant_id": variant.id,
                        "price_gs": price_gs,
                    }
                out[ing_name] = ing_map
            s.commit()
        return out

    return _make


def test_endpoint_returns_200(authed_client, session_factory, make_variant_prices):
    """GET /suppliers/{id}/precios must return 200 for a real supplier."""
    from app.rms.models import Supplier

    make_variant_prices([{"name": "harina 200", "variants": {"S200 A": 4500}}])
    with session_factory() as s:
        sup = s.scalar(__import__("sqlalchemy").select(Supplier).where(Supplier.name == "S200 A"))
        sup_id = sup.id

    r = authed_client.get(f"/suppliers/{sup_id}/precios")
    assert r.status_code == 200, r.text[:200]
    assert "Comparación de precios" in r.text


def test_endpoint_returns_404_for_missing_supplier(authed_client):
    """GET /suppliers/99999/precios must return 404."""
    r = authed_client.get("/suppliers/99999/precios")
    assert r.status_code == 404


def test_comparison_sorts_suppliers_by_price_ascending(session_factory, make_variant_prices):
    """For one ingredient with two suppliers, the cheapest comes first."""
    from app.rms.supplier_prices import get_price_comparison

    make_variant_prices(
        [
            {"name": "harina sort", "variants": {"Caro S.A.": 5000, "Barato S.R.L.": 4500}},
        ]
    )
    with session_factory() as s:
        comparison = get_price_comparison(s)

    assert len(comparison) == 1
    group = comparison[0]
    assert group.ingredient_name == "harina sort"
    prices = [sp.price_gs for sp in group.suppliers]
    assert prices == sorted(prices), f"Suppliers not sorted ASC: {prices}"
    assert prices[0] == 4500
    assert prices[1] == 5000


def test_comparison_calculates_delta_vs_cheapest(session_factory, make_variant_prices):
    """5000 vs 4500 → delta 500 = 11.1%."""
    from app.rms.supplier_prices import get_price_comparison

    make_variant_prices(
        [
            {"name": "harina delta", "variants": {"Caro": 5000, "Barato": 4500}},
        ]
    )
    with session_factory() as s:
        comparison = get_price_comparison(s)

    group = comparison[0]
    cheapest = group.suppliers[0]
    expensive = group.suppliers[1]
    assert cheapest.is_cheapest is True
    assert cheapest.delta_gs == 0
    assert cheapest.delta_pct == 0.0

    assert expensive.is_cheapest is False
    assert expensive.delta_gs == 500
    assert expensive.delta_pct == pytest.approx(11.1, abs=0.05)


def test_comparison_groups_by_ingredient(session_factory, make_variant_prices):
    """3 ingredients × 2 suppliers each → 3 groups, each with 2 suppliers."""
    from app.rms.supplier_prices import get_price_comparison

    make_variant_prices(
        [
            {"name": "ing-A", "variants": {"Sup-1": 1000, "Sup-2": 1100}},
            {"name": "ing-B", "variants": {"Sup-1": 2000, "Sup-2": 2200}},
            {"name": "ing-C", "variants": {"Sup-1": 3000, "Sup-2": 3300}},
        ]
    )
    with session_factory() as s:
        comparison = get_price_comparison(s)

    assert len(comparison) == 3
    for g in comparison:
        assert len(g.suppliers) == 2, g.ingredient_name


def test_comparison_handles_single_supplier_ingredient(session_factory, make_variant_prices):
    """1 ingredient with only 1 supplier → no delta, savings = 0, is_cheapest=True."""
    from app.rms.supplier_prices import get_price_comparison, total_potential_savings

    make_variant_prices(
        [
            {"name": "lonely ing", "variants": {"Only-Supplier": 7777}},
        ]
    )
    with session_factory() as s:
        comparison = get_price_comparison(s)

    assert len(comparison) == 1
    g = comparison[0]
    assert len(g.suppliers) == 1
    assert g.suppliers[0].is_cheapest is True
    assert g.suppliers[0].delta_gs == 0
    assert g.suppliers[0].delta_pct == 0.0
    assert g.savings_gs_per_unit == 0
    assert total_potential_savings(comparison) == 0


def test_total_savings_only_counts_multi_supplier_ingredients(session_factory, make_variant_prices):
    """Savings = sum of (max - min) per ingredient, but ONLY when ≥2 suppliers.

    Multi: 5000 vs 4500 → 500. Single: 7777 → 0. Total = 500.
    """
    from app.rms.supplier_prices import get_price_comparison, total_potential_savings

    make_variant_prices(
        [
            {"name": "multi ing", "variants": {"A": 5000, "B": 4500}},
            {"name": "single ing", "variants": {"Solo": 7777}},
        ]
    )
    with session_factory() as s:
        comparison = get_price_comparison(s)
        total = total_potential_savings(comparison)

    assert total == 500, f"Expected 500 Gs savings, got {total}"


def test_supplier_link_visible_on_suppliers_list(
    authed_client, session_factory, make_variant_prices
):
    """GET /suppliers must show the 'Ver precios' link in each row."""
    from app.rms.models import Supplier

    make_variant_prices([{"name": "ing-link", "variants": {"Sup-Link": 1000}}])
    with session_factory() as s:
        sup = s.scalar(__import__("sqlalchemy").select(Supplier).where(Supplier.name == "Sup-Link"))
        sup_id = sup.id

    r = authed_client.get("/suppliers")
    assert r.status_code == 200
    assert f"/suppliers/{sup_id}/precios" in r.text, "Ver precios link missing"
    assert "Ver precios" in r.text


def test_template_highlights_cheapest_supplier(authed_client, session_factory, make_variant_prices):
    """Cheapest supplier row must carry the is-cheapest class."""
    from app.rms.models import Supplier

    make_variant_prices(
        [
            {"name": "ing-cheap", "variants": {"Barato": 4500, "Caro": 5000}},
        ]
    )
    with session_factory() as s:
        sup_caro = s.scalar(
            __import__("sqlalchemy").select(Supplier).where(Supplier.name == "Caro")
        )
        sup_id = sup_caro.id

    r = authed_client.get(f"/suppliers/{sup_id}/precios")
    assert r.status_code == 200
    assert "is-cheapest" in r.text, "is-cheapest class missing from rendered HTML"


def test_template_highlights_expensive_supplier(
    authed_client, session_factory, make_variant_prices
):
    """Most expensive supplier row must carry the is-overpriced class."""
    from app.rms.models import Supplier

    make_variant_prices(
        [
            {"name": "ing-overpriced", "variants": {"Barato": 4500, "Caro": 5000}},
        ]
    )
    with session_factory() as s:
        sup_caro = s.scalar(
            __import__("sqlalchemy").select(Supplier).where(Supplier.name == "Caro")
        )
        sup_id = sup_caro.id

    r = authed_client.get(f"/suppliers/{sup_id}/precios")
    assert r.status_code == 200
    assert "is-overpriced" in r.text, "is-overpriced class missing from rendered HTML"


def test_supplier_filter_only_shows_their_ingredients(session_factory, make_variant_prices):
    """With supplier_id filter, the result excludes ingredients where they don't appear."""
    from app.rms.models import Supplier
    from app.rms.supplier_prices import get_price_comparison

    make_variant_prices(
        [
            {"name": "ing-X", "variants": {"Sup-X": 1000, "Sup-Y": 1200}},
            {"name": "ing-Y", "variants": {"Sup-Y": 2000, "Sup-Z": 2200}},
            {"name": "ing-Z", "variants": {"Sup-Z": 3000}},  # Sup-X not present
        ]
    )
    with session_factory() as s:
        sup_x = s.scalar(__import__("sqlalchemy").select(Supplier).where(Supplier.name == "Sup-X"))
        sup_x_id = sup_x.id
        comparison = get_price_comparison(s, supplier_id=sup_x_id)

    # Sup-X appears in ing-X only (1000 + 1200). Should not see ing-Y or ing-Z.
    names = [g.ingredient_name for g in comparison]
    assert names == ["ing-X"], f"Filter leaked: {names}"
