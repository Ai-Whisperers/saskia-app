"""Margins a product still has, read from the ingredient that Inventario opens.

Sale price stays on the product and is not edited here. The two numbers are
the margin against the latest purchase price, and the margin if that same
recipe line had been bought at the highest price in the price-history window.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.costing import product_unit_cost_gs
from app.rms.models import Ingredient, Product, Recipe, RecipeLine
from app.rms.money import to_int_gs
from app.rms.price_history import price_stats
from app.rms.units import normalize_recipe_line_qty


def product_margins_for_ingredient(session: Session, ingredient_id: int) -> list[dict]:
    """One row per product whose recipe uses this ingredient directly.

    margin_last_gs uses the cost the recipe has today (latest purchase price).
    margin_high_gs swaps only this ingredient's line to the period maximum.
    Either value is None when the recipe cost cannot be computed.
    """
    ingredient = session.get(Ingredient, ingredient_id)
    if ingredient is None:
        return []

    lines = session.scalars(
        select(RecipeLine).where(
            RecipeLine.line_kind == "ingredient",
            RecipeLine.line_ref_id == ingredient_id,
        )
    ).all()
    stats = price_stats(session, ingredient_id, days=90)
    last_price = ingredient.purchase_price_gs
    high_price = stats.get("max") if stats else None
    if high_price is None:
        high_price = last_price

    rows: list[dict] = []
    seen: set[int] = set()
    for line in lines:
        recipe = session.get(Recipe, line.recipe_id)
        products = session.scalars(select(Product).where(Product.recipe_id == line.recipe_id)).all()
        for product in products:
            if product.id in seen:
                continue
            seen.add(product.id)
            sale = int(product.sale_price_gs or 0)
            cost = product_unit_cost_gs(session, product.id).batch_cost_gs
            margin_last = None if cost is None else sale - cost
            margin_high = margin_last
            if (
                cost is not None
                and margin_last is not None
                and last_price is not None
                and high_price is not None
                and recipe is not None
                and recipe.yield_qty
            ):
                margin_high = sale - (
                    cost + _line_delta_gs(line, ingredient, recipe, last_price, high_price)
                )
            rows.append(
                {
                    "product_name": product.name,
                    "sale_price_gs": sale,
                    "margin_last_gs": margin_last,
                    "margin_high_gs": margin_high,
                }
            )
    rows.sort(key=lambda row: row["product_name"].lower())
    return rows


def _line_delta_gs(
    line: RecipeLine,
    ingredient: Ingredient,
    recipe: Recipe,
    last_price: int,
    high_price: int,
) -> int:
    """Extra guaraníes per portion when this line is priced at the period max."""
    unit = line.line_unit or ingredient.unit
    try:
        qty = normalize_recipe_line_qty(line.qty, unit, ingredient.unit)
    except ValueError:
        return 0
    per_portion = Decimal(qty) / Decimal(str(recipe.yield_qty))
    return to_int_gs(per_portion * (Decimal(int(high_price)) - Decimal(int(last_price))))
