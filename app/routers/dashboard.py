"""app/routers/dashboard.py — Inicio: ventas/COGS/margen/ranking/avisos.

Per dev plan §9 Task 7 + v2 §11 (timezone).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.analytics import (
    day_of_week_heatmap,
    ingredient_concentration,
    margin_erosion_alerts,
    recipe_complexity,
    stock_turnover,
    top_margin_products,
)
from app.rms.config import ASUNCION_TZ
from app.rms.costing import batch_products_cost_margin, batch_recipes_cost
from app.rms.insights import build_insights
from app.rms.models import Ingredient, Recipe, Sale
from app.services.template_render import render

router = APIRouter(dependencies=[Depends(require_login)])


def get_session(request: Request) -> Session:
    return request.app.state.session_factory()


def _period_window(period: str) -> tuple[datetime, datetime]:
    """Return [start, end) of the current period in Asunción local time.

    today: 00:00:00 → 23:59:59.999 (Asunción)
    week: Monday 00:00 → now (current ISO week)
    month: 1st of month 00:00 → now (current calendar month)
    """
    now_local = datetime.now(ASUNCION_TZ)
    if period == "today":
        start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    elif period == "week":
        iso_weekday = now_local.isoweekday()  # 1=Mon, 7=Sun
        monday_date = now_local.date() - timedelta(days=iso_weekday - 1)
        start = datetime.combine(monday_date, datetime.min.time()).replace(tzinfo=ASUNCION_TZ)
        end = now_local + timedelta(microseconds=1)
    elif period == "month":
        start = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now_local + timedelta(microseconds=1)
    else:
        raise ValueError(f"Unknown period: {period}")
    return start, end


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    period: str = Query("today", pattern="^(today|week|month)$"),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    start, end = _period_window(period)

    # Sales are stored naive-UTC (per the data layer convention). The
    # period_window is computed in Asunción local TZ, so we convert both
    # endpoints to UTC and drop tzinfo for the DB comparison.
    start_utc_naive = start.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc_naive = end.astimezone(timezone.utc).replace(tzinfo=None)

    sales = session.scalars(
        select(Sale).where(
            Sale.sold_at >= start_utc_naive,
            Sale.sold_at < end_utc_naive,
        )
    ).all()
    # The above filter is approximate since we store naive UTC; for v1 this is OK.
    # A more correct implementation would store tz-aware datetime in DB.

    ventas_gs = sum(int(round(s.qty * s.unit_price_gs)) for s in sales)

    # Batch-load all product costs in ~3-4 queries (replaces N+1 loop).
    # The batch helper caches recipes + lines + ingredients in the
    # session identity map, so subsequent session.get() calls hit memory.
    products_in_period = sorted(
        {s.product for s in sales if s.product is not None},
        key=lambda p: p.id,
    )
    batch_costs = batch_products_cost_margin(session, products_in_period)

    cogs_gs = 0
    sales_no_recipe = []
    for s in sales:
        if s.product is None or s.product.recipe_id is None:
            sales_no_recipe.append(s)
            continue
        cost, _margin = batch_costs.get(s.product_id, (None, (None, None)))
        if cost is None or cost.batch_cost_gs is None:
            sales_no_recipe.append(s)
            continue
        cogs_gs += int(round(s.qty * cost.batch_cost_gs))

    margen_gs = ventas_gs - cogs_gs
    margen_pct_fmt = f"{(margen_gs / ventas_gs * 100):.1f}%" if ventas_gs > 0 else "—"

    # Ranking: aggregate margin by product (reuse batch_costs — no extra queries)
    ranking_dict: dict[int, dict] = {}
    for s in sales:
        if s.product is None:
            continue
        rid = s.product_id
        if rid not in ranking_dict:
            ranking_dict[rid] = {
                "name": s.product.name,
                "ventas_gs": 0,
                "margen_gs": 0,
                "qty": 0.0,
                "margen_ratio": None,
            }
        ranking_dict[rid]["ventas_gs"] += int(round(s.qty * s.unit_price_gs))
        ranking_dict[rid]["qty"] += s.qty
        if s.product.recipe_id is not None:
            cost, _margin = batch_costs.get(rid, (None, (None, None)))
            if cost is not None and cost.batch_cost_gs is not None:
                line_margin = int(round(s.qty * (s.unit_price_gs - cost.batch_cost_gs)))
                ranking_dict[rid]["margen_gs"] += line_margin

    ranking = sorted(
        ranking_dict.values(),
        key=lambda r: r["margen_gs"],
        reverse=True,
    )
    # Compute ratios
    for r in ranking:
        if r["ventas_gs"] > 0:
            r["margen_ratio"] = r["margen_gs"] / r["ventas_gs"]

    # Alerts
    stock_low = session.scalars(
        select(Ingredient).where(
            Ingredient.min_stock_qty > 0,
            Ingredient.stock_qty < Ingredient.min_stock_qty,
        )
    ).all()

    # Batch-load all recipe costs (replaces per-recipe N+1).
    all_recipes = list(session.scalars(select(Recipe)).all())
    batch_recipe_results = batch_recipes_cost(session, all_recipes)
    recipes_no_cost = [
        r for r in all_recipes
        if batch_recipe_results[r.id][0].batch_cost_gs is None and len(r.lines) > 0
    ]

    sales_no_recipe_decor = [
        {
            "id": s.id,
            "product_name": s.product.name if s.product else "(deleted)",
            "sold_at_str": s.sold_at.strftime("%d/%m/%Y %H:%M") if s.sold_at else "",
        }
        for s in sales_no_recipe[:10]
    ]

    return render(
        request,
        "inicio.html",
        {
            "period": period,
            "ventas_gs": ventas_gs,
            "cogs_gs": cogs_gs,
            "margen_gs": margen_gs,
            "margen_pct_fmt": margen_pct_fmt,
            "ranking": ranking,
            "stock_low": [
                {
                    "name": i.name,
                    "stock_qty": i.stock_qty,
                    "min_stock_qty": i.min_stock_qty,
                    "unit": i.unit,
                }
                for i in stock_low
            ],
            "recipes_no_cost": recipes_no_cost,
            "sales_no_recipe": sales_no_recipe_decor,
            # E8: operational analytics surfaces
            "dow_buckets": day_of_week_heatmap(session, days=90),
            "turnover": [
                stock_turnover(session, ing.id, days=30)
                for ing in session.scalars(
                    select(Ingredient).where(Ingredient.stock_qty > 0).limit(8)
                )
            ],
            "top_margin": top_margin_products(session, days=30, limit=5),
            "concentration": ingredient_concentration(session, days=90)[:5],
            "erosion_alerts": margin_erosion_alerts(session, threshold_pct=5.0),
            "complexity": recipe_complexity(session),
            # E34: consolidated insights panel
            "insights": build_insights(session),
        },
    )


__all__ = ["router"]
