"""app/routers/produccion/prep_recipes.py — /produccion/prep-recipes route.

Recipe-organized ingredient view. Where /produccion/prep shows ingredients
aggregated across the week (operator asks "how much flour do I need?"),
/produccion/prep-recipes shows the same data organized by recipe
(operator asks "for 6 batches of Sopa Paraguaya, how much flour,
manteca, and cheese do I need to weigh out?").

Each card has:
  - Recipe name + link to /recetas/{id}
  - Number of batches (= qty_to_produce / recipe.yield_qty)
  - Ingredient list with scaled quantities and current stock
  - Cumulative totals per ingredient across all recipes (cross-recipe
    shopping list)
  - Severity flag per recipe (Falta / Justo / Suficiente)
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.rms.dependencies import get_session
from app.rms.models import Ingredient, Recipe
from app.rms.production import plan_production
from app.rms.recipes_consolidated import explode_recipe
from app.rms.variants import rollup_ingredient_stock
from app.routers.produccion._helpers import _asuncion_today
from app.routers.produccion._router import router
from app.services.template_render import render


def _build_recipe_breakdown(
    session: Session,
    plan_rows: list[dict],
) -> list[dict[str, Any]]:
    """For each plan row that has a recipe, return a recipe-card with the
    exploded ingredient lines (sub-recipes included).

    Output shape:
      [
        {
          "recipe_id": int,
          "recipe_name": str,
          "product_id": int,
          "product_name": str,
          "batches": float,
          "yield_qty": float,
          "qty_to_produce": float,
          "unit": str,
          "lines": [
            {"ingredient_id": int|None, "name": str, "unit": str,
             "qty": float, "stock_on_hand": float, "shortage": float},
            ...
          ],
          "shortage_count": int,
          "total_shortage": float,
          "severity": "falta" | "justo" | "suficiente",
        },
        ...
      ]
    Sorted: severity - "alerta" recipes (Falta) first, then Justo, then
    Suficiente.
    """
    cards: list[dict[str, Any]] = []
    for row in plan_rows:
        recipe_id = row.get("recipe_id")
        if not recipe_id:
            # Products without a recipe can't be broken down; skip.
            continue
        recipe = session.get(Recipe, recipe_id)
        if recipe is None:
            continue
        qty = float(row.get("qty_to_produce", 0.0))
        yield_qty = float(recipe.yield_qty or 1.0)
        batches = qty / yield_qty if yield_qty > 0 else 1.0

        exploded = explode_recipe(session, recipe_id, scale=batches)
        ing_lines: list[dict[str, Any]] = []
        total_shortage = 0.0
        shortage_count = 0
        for cl in exploded:
            if cl.error:
                ing_lines.append(
                    {
                        "ingredient_id": cl.ingredient_id,
                        "name": cl.name,
                        "unit": cl.unit,
                        "qty": cl.qty,
                        "stock_on_hand": None,
                        "shortage": 0.0,
                        "error": cl.error,
                        "sources": cl.sources,
                    }
                )
                continue
            if cl.ingredient_id is None:
                continue
            ing = session.get(Ingredient, cl.ingredient_id)
            # P39 (2026-10-07, Ivan): variants-aware stock. Before this fix the page
            # read ing.stock_qty (the legacy parent column) which is 0 for 27
            # of 103 ingredients that only have variants. /inventario and
            # /produccion daily use rollup_ingredient_stock() — /prep-recipes
            # now does too so the Faltante badges match reality.
            if ing is None:
                stock = 0.0
            else:
                rollup = rollup_ingredient_stock(session, ing.id)
                stock = float(rollup.base_qty) if rollup else float(ing.stock_qty or 0.0)
            shortage = max(0.0, cl.qty - stock)
            if shortage > 0:
                shortage_count += 1
                total_shortage += shortage
            ing_lines.append(
                {
                    "ingredient_id": cl.ingredient_id,
                    "name": cl.name,
                    "unit": cl.unit,
                    "qty": cl.qty,
                    "stock_on_hand": stock,
                    "shortage": shortage,
                    "error": "",
                    "sources": cl.sources,
                }
            )

        # Severity: any line short → "falta". All lines >= 80% → "suficiente". Else "justo".
        if shortage_count > 0:
            severity = "falta"
        else:
            pct_ok = 0
            pct_total = 0
            for ln in ing_lines:
                if ln["error"]:
                    continue
                pct_total += 1
                if ln["stock_on_hand"] >= ln["qty"]:
                    pct_ok += 1
            if pct_total == 0 or pct_ok / pct_total >= 0.8:
                severity = "suficiente"
            else:
                severity = "justo"

        cards.append(
            {
                "recipe_id": recipe_id,
                "recipe_name": recipe.name or f"Receta #{recipe_id}",
                "product_id": row.get("product_id"),
                "product_name": row.get("product_name", ""),
                "batches": batches,
                "yield_qty": yield_qty,
                "qty_to_produce": qty,
                "unit": "lotes",
                "lines": ing_lines,
                "shortage_count": shortage_count,
                "total_shortage": total_shortage,
                "severity": severity,
            }
        )

    # Sort by severity (falta first, justo, suficiente), then by total
    # shortage desc.
    severity_order = {"falta": 0, "justo": 1, "suficiente": 2}
    cards.sort(
        key=lambda c: (
            severity_order.get(c["severity"], 9),
            -c["total_shortage"],
            c["recipe_name"],
        )
    )
    return cards


def _build_cumulative_totals(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sum each ingredient across all recipe cards. Operator uses this
    as a cross-check against /shopping-list.
    """
    acc: dict[int, dict[str, Any]] = {}
    for card in cards:
        for ln in card["lines"]:
            if ln["ingredient_id"] is None:
                continue
            iid = ln["ingredient_id"]
            entry = acc.setdefault(
                iid,
                {
                    "ingredient_id": iid,
                    "name": ln["name"],
                    "unit": ln["unit"],
                    "qty": 0.0,
                    "stock_on_hand": ln["stock_on_hand"] or 0.0,
                    "shortage": 0.0,
                    "in_recipes": 0,
                },
            )
            entry["qty"] += ln["qty"]
            if ln["shortage"] > 0:
                entry["shortage"] += ln["shortage"]
            entry["in_recipes"] += 1
    out = sorted(
        acc.values(),
        key=lambda r: (r["shortage"] <= 0, -r["qty"], r["name"]),
    )
    return out


@router.get("/prep-recipes", response_class=HTMLResponse)
def produccion_prep_recipes(
    request: Request,
    for_date: date | None = Query(
        None, description="Plan date (defaults to today, Asunción-local)"
    ),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Recipe-organized ingredient view for the bench printout.

    For each product in the plan, shows the exploded ingredient list
    scaled to the day's qty_to_produce. The cook uses this to weigh out
    each recipe's ingredients in one place.

    Args:
      for_date: defaults to today (Asunción-local). Operator clicks the
        day-nav control above to switch.
    """
    today = _asuncion_today()
    target = for_date or today
    plan = plan_production(session, for_date=target)
    # plan.rows are ProductionRow dataclasses; convert to dict for the
    # template. ProductionRow has product_id, product_name, recipe_id,
    # qty_to_produce — enough for the breakdown.
    plan_rows_dict = [
        {
            "product_id": r.product_id,
            "product_name": r.product_name,
            "recipe_id": r.recipe_id,
            "qty_to_produce": r.qty_to_produce,
        }
        for r in plan.rows
    ]
    cards = _build_recipe_breakdown(session, plan_rows_dict)
    cumulative = _build_cumulative_totals(cards)
    severity_counts = {
        "falta": sum(1 for c in cards if c["severity"] == "falta"),
        "justo": sum(1 for c in cards if c["severity"] == "justo"),
        "suficiente": sum(1 for c in cards if c["severity"] == "suficiente"),
    }
    return render(
        request,
        "produccion_prep_recipes.html",
        {
            "for_date": target.isoformat(),
            "for_date_display": target.strftime("%d %b %Y"),
            "today_for_date": today.isoformat(),
            "prev_for_date": (target - timedelta(days=1)).isoformat(),
            "next_for_date": (target + timedelta(days=1)).isoformat(),
            "cards": cards,
            "cumulative": cumulative,
            "severity_counts": severity_counts,
            "total_recipes": len(cards),
            "total_lines": sum(len(c["lines"]) for c in cards),
        },
    )
