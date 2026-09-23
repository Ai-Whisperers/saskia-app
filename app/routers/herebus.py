"""app/routers/herebus.py — HEREBUS business modules.

Routes:
  - /wishlist      — kitchen equipment wishlist (28 items seeded)
  - /riesgos       — risk register (12 risks seeded)
  - /pricing       — per-channel recipe pricing (7 recipes)
  - /bank          — bank transactions (Dutch EUR TAB imported)
  - /benchmarks    — vs competitor pricing
  - /dashboard     — KPI dashboard (revenue, food cost %, etc.)
  - /produccion-planner — recipe × batches → ingredient shortfall calc

All routes are read-only by default. Mutations guarded by require_login.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.dependencies import get_session
from app.rms.models import (
    BankTransaction,
    Customer,
    DeliveryZone,
    Ingredient,
    MarketBenchmark,
    Recipe,
    RecipeLine,
    RecipePricing,
    RiskItem,
    Sale,
    SettingsKV,
    Supplier,
    WasteLog,
    WishlistItem,
)
from app.services.template_render import render

# Stub routers; each is a real prefix-based router for its module
wishlist_router = APIRouter(prefix="/wishlist", dependencies=[Depends(require_login)])
risks_router = APIRouter(prefix="/riesgos", dependencies=[Depends(require_login)])
pricing_router = APIRouter(prefix="/pricing", dependencies=[Depends(require_login)])
bank_router = APIRouter(prefix="/bank", dependencies=[Depends(require_login)])
benchmarks_router = APIRouter(prefix="/benchmarks", dependencies=[Depends(require_login)])
dashboard_router = APIRouter(prefix="/dashboard", dependencies=[Depends(require_login)])
planner_router = APIRouter(prefix="/produccion-planner", dependencies=[Depends(require_login)])
delivery_router = APIRouter(prefix="/delivery-zones", dependencies=[Depends(require_login)])

# ──────────────────────────────────────────────────────────────────
# Wishlist
# ──────────────────────────────────────────────────────────────────


@wishlist_router.get("", response_class=HTMLResponse)
def wishlist_list(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    items = session.execute(
        select(WishlistItem).order_by(WishlistItem.purchased, WishlistItem.priority)
    ).scalars().all()

    by_priority = defaultdict(list)
    for item in items:
        by_priority[item.priority].append(item)

    total_pending = sum(
        item.unit_price_gs * item.quantity
        for item in items
        if not item.purchased
    )
    total_all = sum(item.unit_price_gs * item.quantity for item in items)

    return render(
        request,
        "wishlist.html",
        {
            "items": items,
            "by_priority": dict(by_priority),
            "total_pending_gs": total_pending,
            "total_all_gs": total_all,
            "purchased_count": sum(1 for i in items if i.purchased),
            "pending_count": sum(1 for i in items if not i.purchased),
        },
    )


@wishlist_router.post("/mark-purchased")
async def wishlist_mark_purchased(
    request: Request,
    item_id: int = Form(...),
    session: Session = Depends(get_session),
):
    item = session.get(WishlistItem, item_id)
    if not item:
        return RedirectResponse(url="/wishlist", status_code=303)
    item.purchased = True
    item.purchased_at = datetime.now(timezone.utc)
    session.commit()
    return RedirectResponse(url="/wishlist", status_code=303)


# ──────────────────────────────────────────────────────────────────
# Risk register
# ──────────────────────────────────────────────────────────────────


PRIORITY_LABELS = {
    "must_have": "🟢 Must",
    "nice_to_have": "🟡 Nice",
    "optional": "⚪ Optional",
}

RISK_CATEGORIES = [
    "Operacional",
    "Externo",
    "Reputacional",
    "Comercial",
    "Legal",
    "Personal",
]


@risks_router.get("", response_class=HTMLResponse)
def risk_list(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    items = session.execute(
        select(RiskItem).order_by(RiskItem.status, RiskItem.probability.desc())
    ).scalars().all()

    # Compute severity = probability × impact for risk heat
    for item in items:
        item.severity = item.probability * item.impact_gs

    severity_total = sum(
        (item.probability * item.impact_gs) for item in items if item.status == "activo"
    )

    by_category = defaultdict(list)
    for item in items:
        by_category[item.category or "Otros"].append(item)

    return render(
        request,
        "riesgos.html",
        {
            "items": items,
            "by_category": dict(by_category),
            "severity_total_gs": severity_total,
            "active_count": sum(1 for i in items if i.status == "activo"),
            "mitigated_count": sum(1 for i in items if i.status == "mitigated"),
            "closed_count": sum(1 for i in items if i.status == "cerrado"),
        },
    )


# ──────────────────────────────────────────────────────────────────
# Pricing (per-channel)
# ──────────────────────────────────────────────────────────────────


@pricing_router.get("", response_class=HTMLResponse)
def pricing_list(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    pricings = session.execute(
        select(RecipePricing, Recipe)
        .join(Recipe, Recipe.id == RecipePricing.recipe_id)
        .order_by(Recipe.name)
    ).all()

    # Inject recipe object for template convenience
    rows = []
    for p, recipe in pricings:
        p.recipe = recipe
        rows.append(p)

    # Load channel margin from settings
    margins_json = session.get(SettingsKV, "channels_margins")
    margins = json.loads(margins_json.value_json) if margins_json else {}

    total_cost = sum(p.cost_total_gs for p, _ in pricings)
    total_retail = sum(p.retail_gs for p, _ in pricings)

    return render(
        request,
        "pricing.html",
        {
            "rows": rows,
            "channels_margins": margins,
            "total_cost_gs": total_cost,
            "total_retail_gs": total_retail,
        },
    )


# ──────────────────────────────────────────────────────────────────
# Bank Transactions
# ──────────────────────────────────────────────────────────────────


@bank_router.get("", response_class=HTMLResponse)
def bank_list(
    request: Request,
    category: str = Query(None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    query = select(BankTransaction).order_by(BankTransaction.posted_at.desc()).limit(50)
    if category:
        query = query.where(BankTransaction.category == category)
    transactions = session.execute(query).scalars().all()

    # Compute aggregates
    stats = session.execute(
        select(
            BankTransaction.currency,
            BankTransaction.count,
        ).group_by(BankTransaction.currency)
    ).all() if False else None  # Avoid complex aggregate for speed

    # Simpler aggregates
    eur_total = session.execute(
        select(BankTransaction.amount)
        .where(BankTransaction.currency == "EUR")
    ).scalars().all()

    pyg_total = session.execute(
        select(BankTransaction.amount)
        .where(BankTransaction.currency == "PYG")
    ).scalars().all()

    income = sum(a for a in eur_total if a > 0)
    spent = abs(sum(a for a in eur_total if a < 0))
    pyg_balance = sum(pyg_total) if pyg_total else 0

    # Get all categories
    categories = list({tx.category for tx in transactions if tx.category})

    return render(
        request,
        "bank.html",
        {
            "transactions": transactions,
            "eur_income": income,
            "eur_spent": spent,
            "eur_net": income - spent,
            "pyg_balance_gs": pyg_balance,
            "categories": sorted(categories),
            "active_category": category,
        },
    )


# ──────────────────────────────────────────────────────────────────
# Market Benchmarks
# ──────────────────────────────────────────────────────────────────


@benchmarks_router.get("", response_class=HTMLResponse)
def benchmarks_list(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    benchmarks = session.execute(
        select(MarketBenchmark).order_by(MarketBenchmark.product_label)
    ).scalars().all()

    # Compute position (above / below market)
    for b in benchmarks:
        if not b.market_avg_gs:
            b.position_label = "—"
            continue
        if b.our_retail_gs and b.our_retail_gs > b.market_avg_gs:
            b.pct = round((b.our_retail_gs - b.market_avg_gs) / b.market_avg_gs * 100)
            b.position_label = f"+{b.pct}%"
        elif b.our_retail_gs and b.our_retail_gs < b.market_avg_gs:
            b.pct = round((b.market_avg_gs - b.our_retail_gs) / b.market_avg_gs * 100)
            b.position_label = f"-{b.pct}%"
        else:
            b.position_label = "iguales"

    return render(
        request,
        "benchmarks.html",
        {
            "benchmarks": benchmarks,
        },
    )


# ──────────────────────────────────────────────────────────────────
# KPI Dashboard — derived live from existing data
# ──────────────────────────────────────────────────────────────────


@dashboard_router.get("", response_class=HTMLResponse)
def dashboard_index(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    """HEREBUS KPI dashboard.

    Computes the 12 KPIs from the ANALISIS sheet live from the database.
    No data entry required — the dashboard is purely a query view.
    """
    # Revenue this month
    from datetime import datetime, timedelta
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    sales_this_month = session.execute(
        select(Sale).where(Sale.sold_at >= month_start)
    ).scalars().all()

    revenue_gs = sum(int(s.qty * s.unit_price_gs) for s in sales_this_month)
    portions = sum(s.qty for s in sales_this_month)
    unique_customers = len({s.customer_id for s in sales_this_month if s.customer_id})
    repeat = sum(
        1 for s in sales_this_month
        if s.customer_id and sum(1 for s2 in sales_this_month if s2.customer_id == s.customer_id) > 1
    )

    # Cost of ingredients sold (approximate via recipe pricing)
    total_food_cost_gs = 0
    for s in sales_this_month:
        pricing = session.execute(
            select(RecipePricing).where(
                RecipePricing.recipe_id == s.product.recipe_id if s.product else None
            )
        ).scalars().first()
        if pricing:
            total_food_cost_gs += int(pricing.cost_per_unit_gs * s.qty)

    food_cost_pct = (total_food_cost_gs / revenue_gs * 100) if revenue_gs > 0 else 0
    gross_margin_pct = 100 - food_cost_pct if revenue_gs > 0 else 0

    # Waste this month
    waste_gs = session.execute(
        select(WasteLog.cost_gs).where(WasteLog.recorded_at >= month_start)
    ).scalars().all()
    waste_total_gs = sum(waste_gs)
    waste_pct = (waste_total_gs / revenue_gs * 100) if revenue_gs > 0 else 0

    # Recipe count
    recipe_count = session.execute(select(Recipe)).scalars().all()
    recipes_cooked = len({s.product.recipe_id for s in sales_this_month if s.product})

    # Avg order value
    avg_order = revenue_gs / len(sales_this_month) if sales_this_month else 0

    # Channels breakdown
    by_channel = defaultdict(int)
    for s in sales_this_month:
        ch = s.channel or "mostrador"
        by_channel[ch] += int(s.qty * s.unit_price_gs)

    # Top recipe by revenue (approximate)
    by_recipe = defaultdict(int)
    for s in sales_this_month:
        if s.product:
            by_recipe[s.product.name] += int(s.qty * s.unit_price_gs)
    top_recipe = max(by_recipe.items(), key=lambda kv: kv[1], default=("—", 0))

    return render(
        request,
        "dashboard.html",
        {
            "revenue_gs": revenue_gs,
            "portions": portions,
            "unique_customers": unique_customers,
            "repeat_customers": repeat,
            "repeat_pct": (
                int(repeat / unique_customers * 100)
                if unique_customers > 0
                else 0
            ),
            "food_cost_pct": round(food_cost_pct, 1),
            "gross_margin_pct": round(gross_margin_pct, 1),
            "waste_gs": waste_total_gs,
            "waste_pct": round(waste_pct, 1),
            "recipe_count": len(recipe_count),
            "recipes_cooked": recipes_cooked,
            "avg_order_gs": int(avg_order),
            "by_channel": dict(by_channel),
            "top_recipe_name": top_recipe[0],
            "top_recipe_revenue_gs": top_recipe[1],
            "month_label": month_start.strftime("%B %Y"),
            "tx_count_this_month": len(sales_this_month),
        },
    )


# ──────────────────────────────────────────────────────────────────
# Production Planner — recipe × batches → ingredient need
# ──────────────────────────────────────────────────────────────────


@planner_router.get("", response_class=HTMLResponse)
def planner_form(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    """Production planner form. Empty on GET."""
    recipes = session.execute(select(Recipe).order_by(Recipe.name)).scalars().all()
    return render(
        request,
        "planner.html",
        {
            "recipes": recipes,
            "results": None,
        },
    )


@planner_router.post("/compute")
def planner_compute(
    request: Request,
    recipe_id: int = Form(...),
    batches: int = Form(...),
    session: Session = Depends(get_session),
):
    """Compute ingredient needs vs current stock for the given recipe × batches.

    Output: list of {ingredient_name, qty_needed, qty_available, shortage,
    unit, line_unit_price_gs, total_shortage_gs}.
    """
    recipe = session.get(Recipe, recipe_id)
    if not recipe or batches <= 0:
        return RedirectResponse(url="/produccion-planner", status_code=303)

    lines = session.execute(
        select(RecipeLine).where(
            RecipeLine.recipe_id == recipe_id,
            RecipeLine.line_kind == "ingredient",
        )
    ).scalars().all()

    # Build ingredient lookup
    ing_ids = [l.line_ref_id for l in lines]
    ings = {
        i.id: i
        for i in session.execute(
            select(Ingredient).where(Ingredient.id.in_(ing_ids))
        ).scalars().all()
    }

    results = []
    total_needed_gs = 0
    total_shortage_gs = 0

    for line in lines:
        ing = ings.get(line.line_ref_id)
        if not ing:
            continue
        qty_needed = (line.qty or 0) * batches
        qty_available = ing.stock_qty
        shortage = qty_needed - qty_available
        shortage = max(0, shortage)
        unit_price = ing.purchase_price_gs or 0
        total_shortage_gs += shortage * (unit_price / 1.0)  # todo: unit normalization
        results.append(
            {
                "ingredient_id": ing.id,
                "ingredient_name": ing.name,
                "unit": line.line_unit or ing.unit,
                "qty_needed": qty_needed,
                "qty_available": qty_available,
                "shortage": shortage,
                "unit_price_gs": int(unit_price),
                "line_shortage_gs": int(shortage * unit_price),
                "sufficient": shortage <= 0,
            }
        )

    return render(
        request,
        "planner.html",
        {
            "recipes": session.execute(select(Recipe).order_by(Recipe.name)).scalars().all(),
            "results": results,
            "recipe": recipe,
            "batches": batches,
            "total_shortage_gs": int(total_shortage_gs),
        },
    )


# ──────────────────────────────────────────────────────────────────
# Delivery Zones
# ──────────────────────────────────────────────────────────────────


@delivery_router.get("", response_class=HTMLResponse)
def delivery_zones_list(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    zones = session.execute(
        select(DeliveryZone).order_by(DeliveryZone.position)
    ).scalars().all()
    return render(
        request,
        "delivery_zones.html",
        {"zones": zones},
    )


__all__ = [
    "wishlist_router",
    "risks_router",
    "pricing_router",
    "bank_router",
    "benchmarks_router",
    "dashboard_router",
    "planner_router",
    "delivery_router",
]
