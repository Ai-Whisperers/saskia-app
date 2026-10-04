"""app/routers/insights_derived.py — routes for the derived-intel engines.

Endpoints:
  GET /insights/food-cost-variance   — theoretical vs actual COGS report
  GET /insights/demand               — tomorrow's demand forecast + shopping list
  GET /insights/freshness            — use-first flags + cook-today suggestions
  GET /insights/price-impact/{id}    — what a price change cascades into
  GET /api/insights/allergen-check   — POS JSON guard

All read-only; no new writes beyond what engines already do.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.demand_freshness import (
    cook_today_suggestions,
    forecast_demand,
    freshness_flags,
    shopping_list_from_forecast,
    substitutes_for,
)
from app.rms.dependencies import get_session
from app.rms.derived_intel import (
    check_customer_risk,
    price_change_impact,
    theoretical_vs_actual,
)
from app.rms.rate_limit import read_rate_limit_dependency
from app.services.template_render import render

# BACKLOG #10: rate-limit /reportes/* at 30/min/IP (shared with
# app/routers/reportes.py). insights_derived is a separate router
# file but uses the same /reportes prefix, so both share the same
# `reportes` route tag in the audit log.
router = APIRouter(
    prefix="/reportes",
    dependencies=[
        Depends(require_login),
        Depends(read_rate_limit_dependency(30, route_tag="reportes")),
    ],
)


@router.get("/food-cost-variance", response_class=HTMLResponse)
def food_cost_variance(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    v = theoretical_vs_actual(session, days=days)
    return render(
        request,
        "insight_food_cost.html",
        {
            "v": v,
            "days": days,
        },
    )


@router.get("/demand", response_class=HTMLResponse)
def demand_view(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    forecasts = forecast_demand(session)
    shopping = shopping_list_from_forecast(session, forecasts)
    return render(
        request,
        "insight_demand.html",
        {
            "forecasts": forecasts,
            "shopping": shopping,
        },
    )


@router.get("/freshness", response_class=HTMLResponse)
def freshness_view(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    flags = freshness_flags(session)
    cook = cook_today_suggestions(session)
    return render(
        request,
        "insight_freshness.html",
        {
            "flags": flags,
            "cook_today": cook,
        },
    )


@router.get("/price-impact/{ingredient_id}", response_class=HTMLResponse)
def price_impact_view(
    request: Request,
    ingredient_id: int,
    new_price: int = Query(..., ge=0),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    from app.rms.models import Ingredient

    ing = session.get(Ingredient, ingredient_id)
    if ing is None:
        raise HTTPException(404, "Ingrediente no encontrado")
    old = int(ing.purchase_price_gs or 0)
    impact = price_change_impact(session, ingredient_id, old, new_price)
    session.rollback()  # discard the simulation writes
    return render(
        request,
        "insight_price_impact.html",
        {
            "impact": impact,
            "old_price": old,
            "new_price": new_price,
        },
    )


@router.get("/api/allergen-check")
def allergen_check_api(
    customer_id: int,
    product_id: int,
    session: Session = Depends(get_session),
) -> dict:
    risk = check_customer_risk(session, customer_id, product_id)
    return {"safe": risk.safe, "matched": risk.matched}


@router.get("/api/substitutes/{ingredient_id}")
def substitutes_api(
    ingredient_id: int,
    recipe_id: int | None = None,
    session: Session = Depends(get_session),
) -> dict:
    opts = substitutes_for(session, ingredient_id, in_recipe_id=recipe_id)
    return {
        "options": [
            {
                "id": o.ingredient_id,
                "name": o.name,
                "role": o.role,
                "price_delta_gs": o.price_delta_per_unit_gs,
                "keeps_tags": o.keeps_tags,
                "tag_conflicts": o.tag_conflicts,
            }
            for o in opts
        ]
    }
