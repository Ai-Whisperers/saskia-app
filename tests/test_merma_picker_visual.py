"""tests/test_merma_picker_visual.py — Phase 20 merma recipe picker visual.

Tests the visual upgrade to the /merma recipe picker: image, yield,
and "portions today" badge.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


# ── Backend: /recetas/api/search ──────────────────────────────────────────


def test_recipe_search_api_returns_image_url(authed_client, qseed):
    """The recipe search endpoint must return image_url."""
    qseed("basic")
    r = authed_client.get("/recetas/api/search?q=")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "results" in data, "missing 'results' key"
    if data["results"]:
        first = data["results"][0]
        assert "image_url" in first, "missing image_url"
        assert isinstance(first["image_url"], str), "image_url must be str"


def test_recipe_search_api_returns_batches_today(authed_client, qseed):
    """The recipe search endpoint must return batches_today and portions_today."""
    qseed("basic")
    r = authed_client.get("/recetas/api/search?q=")
    data = r.json()
    if data["results"]:
        first = data["results"][0]
        assert "batches_today" in first, "missing batches_today"
        assert "portions_today" in first, "missing portions_today"
        assert isinstance(first["batches_today"], (int, float))
        assert isinstance(first["portions_today"], (int, float))


def test_recipe_search_api_portions_equals_batches_times_yield(
    authed_client, qseed, session_factory
):
    """portions_today = batches_today × yield_qty when yield_qty is set.

    ProductionCompletion is keyed by product_id; we insert via a product
    that points at a recipe, then verify the recipe search picks it up.
    """
    from datetime import datetime, timezone
    from app.rms.models import Product, Recipe
    from sqlalchemy import text as sa_text

    qseed("basic")
    with session_factory() as s:
        recipe = s.query(Recipe).first()
        assert recipe is not None
        # Find or create a product for this recipe
        product = s.query(Product).filter_by(recipe_id=recipe.id).first()
        if product is None:
            product = Product(
                name="Merma Test Product",
                recipe_id=recipe.id,
                sale_price_gs=1000,
            )
            s.add(product)
            s.flush()
        # Inject a ProductionCompletion row via raw SQL (product_id key)
        s.execute(
            sa_text(
                "INSERT INTO production_completion "
                "(product_id, for_date, completed_qty, recorded_at) "
                "VALUES (:pid, :d, :q, :r)"
            ),
            {
                "pid": product.id,
                "d": datetime.now(timezone.utc).date(),
                "q": 3.0,
                "r": datetime.now(timezone.utc),
            },
        )
        s.commit()

    r = authed_client.get("/recetas/api/search?q=")
    data = r.json()
    target = next((x for x in data["results"] if x["id"] == recipe.id), None)
    assert target is not None, "recipe not found in search results"
    assert target["batches_today"] >= 3.0, \
        f"batches_today={target['batches_today']}"
    if recipe.yield_qty:
        assert target["portions_today"] >= 3.0 * recipe.yield_qty - 0.01
        assert target["portions_today"] <= 3.0 * recipe.yield_qty + 0.01


# ── Frontend: recipeRowLabel ──────────────────────────────────────────────


JS_PATH = (
    Path(__file__).resolve().parent.parent
    / "app" / "static" / "combo-rows.js"
)


def _get_function_body(name: str) -> str:
    """Extract the body of a named function inside the IIFE."""
    text = JS_PATH.read_text()
    sig = f"function {name}(row) {{"
    idx = text.find(sig)
    assert idx > 0, f"function {name} not found"
    depth = 0
    i = idx + len(sig)
    start = i
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            if depth == 0:
                return text[start:i]
            depth -= 1
        i += 1
    raise AssertionError(f"could not find end of {name}")


def test_recipe_row_label_function_exists():
    body = _get_function_body("recipeRowLabel")
    assert body, "recipeRowLabel has empty body"


def test_recipe_row_label_renders_image_or_placeholder():
    body = _get_function_body("recipeRowLabel")
    assert "combo-row-img" in body, "missing image class"
    assert "combo-row-img--placeholder" in body, "missing placeholder class"


def test_recipe_row_label_shows_yield():
    body = _get_function_body("recipeRowLabel")
    assert "yield_qty" in body
    assert "yield_unit" in body


def test_recipe_row_label_shows_portions_today_badge():
    body = _get_function_body("recipeRowLabel")
    assert "portions_today" in body
    assert "hoy" in body


def test_recipe_row_label_handles_zero_batches():
    body = _get_function_body("recipeRowLabel")
    assert "sin prod" in body or "is-neutral" in body, \
        "should gracefully handle recipes with 0 batches today"


# ── Template: merma.html uses recipeRowLabel ─────────────────────────────


def test_merma_html_uses_recipe_row_label():
    path = (
        Path(__file__).resolve().parent.parent
        / "app" / "templates" / "merma.html"
    )
    text = path.read_text()
    assert "recipeRowLabel" in text, \
        "merma.html does not wire recipeRowLabel to the recipe combo"
    # Find the recipe_id combo specifically
    combo = re.search(
        r"combo_field\(\s*name='recipe_id'.*?\)", text, re.DOTALL,
    )
    assert combo, "could not find recipe_id combo_field"
    assert "row_label='recipeRowLabel'" in combo.group(0), \
        "recipe_id combo missing row_label='recipeRowLabel'"
