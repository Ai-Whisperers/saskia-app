"""app/routers/dev.py — Dev-only routes for smoke testing new UI components.

These are wired only when DEV_COMBO_SMOKE=1 in the environment so they
can't leak to production. Gates the smoke test page + a /api/lookup/*
mock JSON endpoint the saskia-combo can hit.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.services.template_render import render

router = APIRouter(prefix="/dev", tags=["dev"])


@router.get("/combo-smoke", response_class=HTMLResponse)
def combo_smoke(request: Request):
    """Renders the saskia-combo smoke test page. Dev-only."""
    if not os.getenv("DEV_COMBO_SMOKE"):
        return HTMLResponse("<h1>404</h1>", status_code=404)

    qp = request.query_params
    submitted = None
    if qp.get("category") is not None or qp.get("product_id") is not None:
        submitted = {
            "category": qp.get("category"),
            "product_id": qp.get("product_id"),
        }

    # Mock client-side src — categories used in the demo bakery
    categories_src = [
        {"value": "reposteria", "label": "Repostería"},
        {"value": "panaderia", "label": "Panadería"},
        {"value": "bebidas", "label": "Bebidas"},
        {"value": "salados", "label": "Salados"},
        {"value": "tortas", "label": "Tortas"},
        {"value": "galletas", "label": "Galletas"},
        {"value": "facturas", "label": "Facturas"},
        {"value": "desayunos", "label": "Desayunos"},
        {"value": "meriendas", "label": "Meriendas"},
        {"value": "especiales", "label": "Especiales"},
    ]

    return render(
        request,
        "dev_combo_smoke.html",
        {
            "categories_src": categories_src,
            "selected_category": qp.get("category"),
            "selected_category_display": _find_label(categories_src, qp.get("category")),
            "selected_product": qp.get("product_id"),
            "selected_product_display": qp.get("product_id_display"),
            "submitted": submitted,
        },
    )


def _find_label(items, value):
    if not value:
        return None
    for item in items or []:
        if str(item.get("value")) == str(value):
            return item.get("label")
    return None


# Separate router for /api/lookup/* so it doesn't collide with /dev prefix
api_router = APIRouter(prefix="/api/lookup", tags=["dev-api"])


@api_router.get("/products")
def lookup_products(q: str = Query(default=""), limit: int = 25):
    """Mock server-side lookup endpoint for saskia-combo.

    Real implementation tomorrow: query the products table by name/CRE.
    For now, return a small mock dataset so the smoke page works.
    """
    if not os.getenv("DEV_COMBO_SMOKE"):
        return JSONResponse({"results": []}, status_code=404)

    mock = [
        {"value": 1, "label": "Pan de campo (Unidad)"},
        {"value": 2, "label": "Croissant de manteca"},
        {"value": 3, "label": "Medialuna de grasa"},
        {"value": 4, "label": "Tarta de manzana"},
        {"value": 5, "label": "Brownie de chocolate"},
        {"value": 6, "label": "Empanada de carne"},
        {"value": 7, "label": "Sándwich de miga"},
        {"value": 8, "label": "Café con leche"},
        {"value": 9, "label": "Submarino"},
        {"value": 10, "label": "Tostado mixto"},
        {"value": 11, "label": "Chipá relleno"},
        {"value": 12, "label": "Facturas surtidas (docena)"},
    ]
    query = (q or "").lower().strip()
    if query:
        mock = [p for p in mock if query in p["label"].lower()]
    return JSONResponse({"results": mock[:limit]})
