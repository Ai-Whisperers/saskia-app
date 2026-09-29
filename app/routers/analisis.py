"""Análisis — the analytics destination extracted from Inicio (2026-09-25
mockup plan: home = estado + acciones; análisis = destino separado).

Everything that used to stack 8 viewports deep on / now lives here:
Inteligencia KPIs, stars/dogs, rising/churning, price fluctuation, erosion
alerts, top margin, concentration, dow averages, turnover, complexity.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.analytics import (
    batch_stock_turnover,
    day_of_week_heatmap,
    ingredient_concentration,
    margin_erosion_alerts,
    recipe_complexity,
    top_margin_products,
)
from app.rms.config import ASUNCION_TZ
from app.rms.dependencies import get_session
from app.rms.insights import build_insights
from app.rms.models import Ingredient
from app.services.template_render import render

router = APIRouter(dependencies=[Depends(require_login)])


@router.get("/analisis", response_class=HTMLResponse)
def analisis_view(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    insights = build_insights(session)
    return render(
        request,
        "analisis.html",
        {
            "insights": insights,
            "top_margin": top_margin_products(session, days=30, limit=10),
            "concentration": ingredient_concentration(session, days=90)[:5],
            "erosion_alerts": margin_erosion_alerts(session, threshold_pct=5.0),
            "dow_buckets": day_of_week_heatmap(session, days=90),
            "turnover": list(
                batch_stock_turnover(
                    session,
                    [
                        ing.id
                        for ing in session.scalars(
                            select(Ingredient).where(Ingredient.stock_qty > 0).limit(12)
                        ).all()
                    ],
                    days=30,
                ).values()
            ),
            "complexity": recipe_complexity(session),
            "data_freshness": datetime.now(ASUNCION_TZ).strftime("%H:%M:%S"),
        },
    )


__all__ = ["router"]
