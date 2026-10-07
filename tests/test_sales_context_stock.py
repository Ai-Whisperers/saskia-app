"""tests/test_sales_context_stock.py — _build_sales_context stock fields.

M-FLO-001: when /ventas is loaded, the context must include
stock_ceilings, stock_sold_out, and stock_low dicts keyed by
product id. The Jinja template uses these to render data-* attributes
on the quick-sell buttons and the stock badges.

The quick-sell grid only renders products that have sales history
OR are favorites (Sazon behavior — see _build_sales_context and the
{% if quick_sell %} guard in ventas.html). To exercise the wire-up,
tests mark products as favorites so they always appear in the grid.
"""
from __future__ import annotations

import re

from app.rms.models import (
    Ingredient, Product, Recipe, RecipeLine,
)


def _make_recipe_product(
    session_factory,
    *,
    name: str,
    ing_stock: float,
    recipe_yield: float = 10.0,
    line_qty: float = 100.0,
    favorite: bool = True,
    no_recipe: bool = False,
) -> int:
    """Build a product with one ingredient. Returns the product id."""
    with session_factory() as session:
        with session.begin():
            ing = Ingredient(name=f"Ing-{name}", stock_qty=ing_stock, unit="g")
            session.add(ing)
            session.flush()
            if no_recipe:
                p = Product(
                    name=name, sku=f"SKU-{name}",
                    sale_price_gs=5000,
                    is_available=True, is_favorite=favorite,
                )
                session.add(p)
                session.flush()
                return p.id
            r = Recipe(name=f"Receta-{name}", yield_qty=recipe_yield, yield_unit="g")
            session.add(r)
            session.flush()
            session.add(RecipeLine(
                recipe_id=r.id, line_kind="ingredient",
                line_ref_id=ing.id, qty=line_qty, line_unit="g",
            ))
            session.flush()
            p = Product(
                name=name, sku=f"SKU-{name}", sale_price_gs=5000,
                recipe_id=r.id, is_available=True, is_favorite=favorite,
            )
            session.add(p)
            session.flush()
            return p.id


def test_sales_context_renders_ok(client, qseed, session_factory):
    """/ventas must render without crashing with stock_ceilings/sold_out/low."""
    qseed("basic")
    _make_recipe_product(session_factory, name="RenderOK", ing_stock=1000.0)
    r = client.get("/ventas")
    assert r.status_code == 200


def test_favorite_product_has_stock_attributes(client, qseed, session_factory):
    """A product marked as favorite gets data-stock-ceiling on its button.

    Even without sales history, favorites always show in the quick-sell
    grid (see _build_sales_context Phase 3 UX comment from 2026-09-30).
    """
    pid = _make_recipe_product(session_factory, name="Favorite-StockAttr",
                               ing_stock=1000.0)
    r = client.get("/ventas")
    assert r.status_code == 200
    html = r.text
    assert "data-stock-ceiling" in html, (
        "data-stock-ceiling missing from quick-sell buttons"
    )
    assert "data-low-stock" in html, "data-low-stock missing"
    assert f'data-product-id="{pid}"' in html


def test_no_recipe_product_has_no_ceiling(client, qseed, session_factory):
    """A product without a recipe renders with empty data-stock-ceiling.

    The FloCafe port must NOT show a sold-out badge for products with
    no recipe — pre_sale_check (sale-time) decides those.
    """
    pid = _make_recipe_product(session_factory, name="SinReceta-StockTest",
                               ing_stock=0.0, no_recipe=True)
    r = client.get("/ventas")
    assert r.status_code == 200
    html = r.text
    pid_marker = f'data-product-id="{pid}"'
    idx = html.find(pid_marker)
    assert idx > 0, "Favorite product not in /ventas response"
    btn_match = re.search(r'<button[^>]*data-product-id="' + str(pid) + r'"[^>]*>', html, re.DOTALL)
    assert btn_match, "Button not found"
    btn_html = btn_match.group(0)
    assert "data-stock-ceiling=\"\"" in btn_html, (
        f"Empty ceiling expected: {btn_html[:200]}"
    )
    # No badge for this one (no recipe → no low-stock concept)
    assert "Agotado" not in btn_html
    assert "Quedan" not in btn_html


def test_low_stock_button_gets_badge_class(client, qseed, session_factory):
    """When ceiling < threshold, the button has is-low-stock class.

    Default pct=0.20: ceiling must be <= 20% of max to show low badge.
    With ing_stock=15 (per_unit=10), ceiling=1.5 units. Threshold
    (20% of ceiling) = 0.3 units. So 1.5 > 0.3 → NOT low-stock.
    To force low-stock we use ing_stock=1 → ceiling=0.1 units.
    """
    pid = _make_recipe_product(session_factory, name="Bizcocho-LowBadge",
                               ing_stock=1.0)  # ceiling = 0.1, very low
    r = client.get("/ventas")
    assert r.status_code == 200
    html = r.text
    pid_marker = f'data-product-id="{pid}"'
    idx = html.find(pid_marker)
    assert idx > 0, "Low-stock product not in /ventas response"
    # The button tag spans multiple lines; use regex to grab the whole opening tag.
    btn_match = re.search(r'<button[^>]*data-product-id="' + str(pid) + r'"[^>]*>', html, re.DOTALL)
    assert btn_match, "Button not found"
    btn_html = btn_match.group(0)
    assert "is-low-stock" in btn_html, (
        f"is-low-stock class missing: {btn_html[:200]}"
    )
    assert "Quedan" in html, "low-stock badge text missing"


def test_sold_out_button_is_disabled(client, qseed, session_factory):
    """A product with 0 stock ceiling is rendered as disabled."""
    pid = _make_recipe_product(session_factory, name="Bizcocho-Out",
                               ing_stock=0.0)
    r = client.get("/ventas")
    assert r.status_code == 200
    html = r.text
    pid_marker = f'data-product-id="{pid}"'
    idx = html.find(pid_marker)
    assert idx > 0
    btn_end = html.find(">", idx)
    btn_html = html[idx:btn_end]
    assert "is-sold-out" in btn_html or "disabled" in btn_html, (
        f"Sold-out button not disabled: {btn_html[:200]}"
    )
    assert "Agotado" in html, "Sold-out badge text missing"
