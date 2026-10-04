"""tests/e2e/test_dark_engines_wired.py — the 4 dark engines surfaced.

Covers:
  - /reportes/stock-intel (all_stock_turnover + dead_stock)
  - /reportes/afinidades (top_pairs)
  - /reportes/margenes (margin_drift_all + product_price_history)
  - variants.current_variant_price as costing basis (preferred variant
    overrides parent ingredient price)

Uses factories only; Spanish copy asserted (AGENTS.md rule 5).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.rms.models import IngredientVariant
from tests.factories import (
    ing_line,
    make_catalog,
    make_ingredient,
    make_product,
    make_recipe,
    make_sale,
)

pytestmark = [pytest.mark.smoke]


def test_stock_intel_page_renders_with_dead_stock(client, session_factory):
    with session_factory() as s:
        # an ingredient with stock but never consumed → dead stock
        make_ingredient(s, name="Colorante", stock_qty=3.0, purchase_price_gs=8000)
        s.commit()
    r = client.get("/reportes/stock-intel")
    assert r.status_code == 200
    assert "stock muerto" in r.text.lower()
    assert "Colorante" in r.text


def test_afinidades_page_shows_top_pair(client, session_factory):
    with session_factory() as s:
        a = make_product(s, name="Chipa")
        b = make_product(s, name="Cafe")
        t = datetime.now(timezone.utc).replace(tzinfo=None)
        for i in range(3):  # same basket window
            make_sale(s, product=a, qty=1, at=t + timedelta(minutes=i))
            make_sale(s, product=b, qty=1, at=t + timedelta(minutes=i))
        s.commit()
    r = client.get("/reportes/afinidades")
    assert r.status_code == 200
    body = r.text
    assert "Chipa" in body and "Cafe" in body


def test_margenes_page_and_product_history(client, session_factory):
    with session_factory() as s:
        cat = make_catalog(s, price_gs=10_000)
        t0 = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=10)
        make_sale(s, product=cat["product"], qty=1, at=t0, unit_price_gs=10_000)
        make_sale(s, product=cat["product"], qty=1, at=t0 + timedelta(days=5), unit_price_gs=12_000)
        s.commit()
        pid = cat["product"].id

    r = client.get("/reportes/margenes")
    assert r.status_code == 200
    assert cat["product"].name in r.text

    r2 = client.get(f"/reportes/margenes/{pid}")
    assert r2.status_code == 200
    assert "12.000" in r2.text or "12000" in r2.text  # observed price present


def test_margenes_404_for_unknown_product(client):
    r = client.get("/reportes/margenes/999999")
    assert r.status_code == 404


def test_preferred_variant_price_drives_costing(session_factory):
    """current_variant_price: preferred variant overrides parent price in
    recipe costing (the wiring change in costing.py)."""
    from app.rms.costing import recipe_unit_cost_gs

    with session_factory() as s:
        ing = make_ingredient(s, name="Harina V", purchase_price_gs=5_000)
        # preferred variant cheaper than parent
        s.add(
            IngredientVariant(
                ingredient_id=ing.id,
                package_size=1.0,
                package_unit="kg",
                purchase_price_gs=3_000,
                preferred=True,
            )
        )
        rec = make_recipe(s, lines=[ing_line(ing, qty=1.0)])  # 1 kg per batch
        rec.yield_qty = 1.0
        s.commit()
        cost = recipe_unit_cost_gs(s, rec.id)
        assert cost is not None
        assert cost.batch_cost_gs == 3_000, (
            f"costing should use variant price 3000, got {cost.batch_cost_gs}"
        )


def test_reportes_index_lists_new_cards(client):
    r = client.get("/reportes")
    assert r.status_code == 200
    for term in ("stock-intel", "afinidades", "margenes"):
        assert term in r.text, f"reportes index missing card {term}"
