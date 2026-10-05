"""app/routers/insights_stock.py — wiring the dark intel engines into UI.

Engines surfaced here (all previously 0-caller "dark code"):
  - analytics.all_stock_turnover → rotación table
  - inventory_intel.dead_stock  → stock muerto table
  - sales_intel.top_pairs       → afinidades (what sells together)
  - variants.current_variant_price → used by the margin view for ingredient cost

Routes (all login-required, read-only):
  /reportes/stock-intel   — rotación + stock muerto
  /reportes/afinidades    — pares de productos que se venden juntos
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.analytics import all_stock_turnover
from app.rms.analytics import dead_stock as dead_stock_rows
from app.rms.dependencies import get_session
from app.rms.product_price_history import margin_drift_all, product_price_history
from app.rms.sales_intel import top_pairs
from app.services.template_render import render

router = APIRouter(prefix="/reportes", dependencies=[Depends(require_login)])


@router.get("/stock-intel", response_class=HTMLResponse)
def stock_intel_view(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    dead_days: int = Query(30, ge=1, le=365),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    turnover = all_stock_turnover(session, days=days)
    dead = dead_stock_rows(session, threshold_days=dead_days)
    # sort: slowest movers first (highest days_of_stock), then by value idle
    turnover_sorted = sorted(turnover, key=lambda t: t.days_of_stock or 0, reverse=True)
    dead_sorted = sorted(dead, key=lambda d: d.stock_qty or 0, reverse=True)
    return render(
        request,
        "insight_stock.html",
        {
            "turnover": turnover_sorted,
            "dead": dead_sorted,
            "days": days,
            "dead_days": dead_days,
        },
    )


@router.get("/afinidades", response_class=HTMLResponse)
def afinidades_view(
    request: Request,
    n: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    pairs = top_pairs(session, n=n)
    return render(
        request,
        "insight_afinidades.html",
        {
            "pairs": pairs,
        },
    )


@router.get("/margenes", response_class=HTMLResponse)
def margenes_view(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    drift = margin_drift_all(session, days=days)
    return render(
        request,
        "insight_margenes.html",
        {
            "drift": drift,
            "days": days,
        },
    )


@router.get("/margenes/{product_id}", response_class=HTMLResponse)
def margenes_product_view(
    request: Request,
    product_id: int,
    days: int = Query(90, ge=1, le=365),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    from fastapi import HTTPException

    from app.rms.models import Product

    prod = session.get(Product, product_id)
    if prod is None:
        raise HTTPException(404, "Producto no encontrado")
    hist = product_price_history(session, product_id, days=days)
    return render(
        request,
        "insight_margenes_detalle.html",
        {
            "product": prod,
            "history": hist,
            "days": days,
        },
    )
